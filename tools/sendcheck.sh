#!/bin/bash
# Sign and send, on the installed Skim and through its window, with two test PDFs
# of its own in a scratch folder (nothing else that is open is touched):
#   A. Signature button, then File > Save  ->  "<name>-signed.pdf" beside the file,
#      the signature in it as a Stamp, the original as it was, the window on the new file
#   B. Signature button, then a real mouse drag (CGEvent) of the File button, with
#      Skim in the back, into a window of tools/dragtest.swift  ->  saved to -signed
#      first and that file dropped, offered as a copy, and Skim still in the back
#
#   tools/sendcheck.sh           # now, if nobody touched the Mac for 30 s
#   tools/sendcheck.sh --wait    # waits up to 30 min for that first
#
# It takes the screen for ~15 s: Skim comes forward with the test PDFs, the mouse
# moves, and the app that was in front gets the focus back. Each step that touches
# the screen checks first that nobody touched the Mac for 30 s and that the window
# is the test document's; anything else aborts. Needs Accessibility for the
# terminal. Exit 0 = PASS.
set -u
here=$(cd "$(dirname "$0")" && pwd)
work=$(cd "$(mktemp -d -t sendcheck)" && pwd -P)   # the /private path Skim reports
A="sendcheck A.pdf"; B="sendcheck B.pdf"
failures=0

idle() { ioreg -c IOHIDSystem | awk '/HIDIdleTime/ {print int($NF/1000000000); exit}'; }
front() { osascript -e 'tell application "System Events" to get name of first application process whose frontmost is true'; }
frontwin() { osascript -e 'tell application "System Events" to tell process "Skim" to get name of window 1' 2>/dev/null; }
sheets() { osascript -e 'tell application "System Events" to tell process "Skim"
  set n to 0
  repeat with w in windows
    set n to n + (count of sheets of w)
  end repeat
  return n
end tell' 2>/dev/null; }
docstate() { osascript -e "tell application \"Skim\" to get {modified, count of notes} of document \"$1\"" 2>/dev/null | tr -d ' '; }
sha() { shasum -a 256 "$1" | cut -c1-16; }
check() { if eval "$2"; then echo "ok    $1"; else echo "FAIL  $1"; failures=$((failures + 1)); fi; }
prev=""
cleanup() {
  osascript -e 'tell application "Skim" to close (every document whose name begins with "sendcheck ") saving no' >/dev/null 2>&1
  [ -n "$prev" ] && open -b "$prev"
  rm -rf "$work"
}
abort() { echo "ABORT: $1"; cleanup; exit 3; }
need_idle() { local i; i=$(idle); [ "$i" -ge 30 ] || abort "o Mac foi usado há ${i}s ($1)"; }
wait_front_doc() {
  for _ in $(seq 20); do [[ "$(front)" == "Skim" && "$(frontwin)" == "$1"* ]] && return 0; sleep 0.25; done
  abort "a janela de $1 não veio para a frente"
}
press_signature() {
  osascript -e "tell application \"System Events\" to tell process \"Skim\" to click (first button of toolbar 1 of (first window whose name begins with \"$1\") whose description is \"Signature\")" >/dev/null
}

if [[ "${1:-}" == "--wait" ]]; then
  for _ in $(seq 900); do [ "$(idle)" -ge 32 ] && break; sleep 2; done
fi
need_idle start
[ "$(sheets)" = "0" ] || abort "há uma folha aberta no Skim"
prev=$(osascript -e 'tell application "System Events" to get bundle identifier of first application process whose frontmost is true')
for f in "$A" "$B"; do
  printf 'Signing test\n\nA document to sign and send.\n' | cupsfilter -i text/plain -m application/pdf - > "$work/$f" 2>/dev/null
done
swiftc -O "$here/dragtest.swift" -o "$work/dragtest" || abort "dragtest não compilou"
shaA=$(sha "$work/$A"); shaB=$(sha "$work/$B")

echo "A. Signature, then File > Save"
need_idle A1
open -a /Applications/Skim.app "$work/$A"; wait_front_doc "$A"
need_idle A2
press_signature "$A"; sleep 0.5
check "the Signature button adds one unsaved note" '[ "$(docstate "$A")" = "true,1" ]'
need_idle A3
[[ "$(front)" == "Skim" && "$(frontwin)" == "$A"* ]] || abort "a frente mudou antes do Save"
osascript -e 'tell application "System Events" to tell process "Skim" to click menu item "Save" of menu "File" of menu bar item "File" of menu bar 1' >/dev/null
sleep 1.5
check "Save writes \"sendcheck A-signed.pdf\" beside it" '[ -f "$work/sendcheck A-signed.pdf" ]'
check "with the signature as a Stamp" 'LC_ALL=C grep -q -a "/Subtype */Stamp" "$work/sendcheck A-signed.pdf"'
check "and leaves the original as it was" '[ "$(sha "$work/$A")" = "$shaA" ]'
check "the window is on the signed file, saved" '[[ "$(docstate "sendcheck A-signed.pdf")" == false,* ]]'

echo "B. Signature, then a drag of the File button, Skim in the back"
need_idle B1
open -a /Applications/Skim.app "$work/$B"; wait_front_doc "$B"
need_idle B2
press_signature "$B"; sleep 0.5
check "the Signature button adds one unsaved note" '[ "$(docstate "$B")" = "true,1" ]'
xy=$(osascript <<EOF
tell application "System Events" to tell process "Skim"
	set w to first window whose name begins with "$B"
	set b to first button of toolbar 1 of w whose description is "File"
	set p to position of b
	set s to size of b
	return (((item 1 of p) + (item 1 of s) div 2) as text) & "," & (((item 2 of p) + (item 2 of s) div 2) as text)
end tell
EOF
)
[[ "$xy" =~ ^[0-9]+,[0-9]+$ ]] || abort "o botão File não foi achado na janela"
need_idle B3
"$work/dragtest" "${xy%,*}" "${xy#*,}" "$B" "$work/drag.log" >/dev/null
sleep 1
check "the drag drops \"sendcheck B-signed.pdf\", saved first" 'grep -q "^dropped: $work/sendcheck B-signed.pdf size=[1-9]" "$work/drag.log"'
check "offered as a copy, never a move" 'grep -q "^entered: source mask=5$" "$work/drag.log"'
check "Skim stays in the back" 'grep "^front at drop: " "$work/drag.log" | grep -qv "Skim$"'
check "with the signature as a Stamp" 'LC_ALL=C grep -q -a "/Subtype */Stamp" "$work/sendcheck B-signed.pdf"'
check "and the original as it was" '[ "$(sha "$work/$B")" = "$shaB" ]'

cleanup
[ $failures -eq 0 ] && echo PASS || echo "FAIL ($failures)"
exit $((failures > 0))