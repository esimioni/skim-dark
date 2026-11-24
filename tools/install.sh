#!/bin/bash
# Installs the built fork over /Applications/Skim.app.
#
#   tools/install.sh              install only
#   tools/install.sh --dark-chrome    also set SKDisableSearchBarBlurring, which
#                                     keeps Tahoe from flipping the toolbar and
#                                     tab bar to their light variant (README)
#   tools/install.sh --background     reopen Skim behind the app in front, so an
#                                     install while someone types in another app
#                                     does not take the keystrokes (both flags combine)
#
# Skim must be quit for both steps: a running app keeps the old binary mapped,
# and it rewrites its user defaults on quit, discarding anything written while
# it was up.
#
# The documents that were open come back through SKIsRelaunch, the flag Skim's
# own updater sets before a relaunch: the next launch reopens SKLastOpenFileNames
# (written on quit, with each window's setup) and clears the flag. Nothing else
# brings them back — macOS does not restore Skim's windows, and Skim's own
# "reopen last files" preference defaults to never (measured 2026-09-28: without
# the flag both documents stayed closed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILT="$ROOT/src/build/Release/Skim.app"
DEST="/Applications/Skim.app"
DARK_CHROME=0
OPEN_FLAGS=()
for arg in "$@"; do
  case "$arg" in
    --dark-chrome) DARK_CHROME=1 ;;
    --background)  OPEN_FLAGS=(-g) ;;
    *) echo "opção desconhecida: $arg"; exit 1 ;;
  esac
done

[[ -d "$BUILT" ]] || { echo "sem build em $BUILT — rode o xcodebuild do README"; exit 1; }
codesign --verify --deep "$BUILT" 2>/dev/null || { echo "build sem assinatura válida — rode tools/postbuild.py"; exit 1; }
/usr/libexec/PlistBuddy -c 'Print :SUFeedURL' "$BUILT/Contents/Info.plist" >/dev/null 2>&1 \
  && { echo "SUFeedURL ainda no bundle — rode tools/postbuild.py"; exit 1; }

WAS_RUNNING=0
if pgrep -xq Skim; then
  WAS_RUNNING=1
  echo "fechando o Skim..."
  osascript -e 'tell application "Skim" to quit' || true
  for _ in $(seq 30); do pgrep -xq Skim || break; sleep 1; done
  pgrep -xq Skim && { echo "Skim não fechou (documento não salvo?) — feche na mão e rode de novo"; exit 1; }
fi

echo "instalando em $DEST"
rm -rf "$DEST"
ditto "$BUILT" "$DEST"

# The patch was rebased onto upstream's own keys on 2026-09-01; a build from
# before that read SKDarkMode*. Carry the colors over once, or the first launch
# of a new build silently falls back to white text.
migrate_key() {
  local old=$1 new=$2 value
  defaults read -app Skim "$new" >/dev/null 2>&1 && return 0
  value=$(defaults read -app Skim "$old" 2>/dev/null) || return 0
  defaults write -app Skim "$new" "$value" && echo "migrado: $old -> $new"
}
migrate_key SKDarkModeBackgroundColor SKInvertedColorsBackgroundWhite
migrate_key SKDarkModeTextColor SKInvertedColorsTextBlack

if [[ $DARK_CHROME -eq 1 ]]; then
  defaults write -app Skim SKDisableSearchBarBlurring -bool YES
  echo "SKDisableSearchBarBlurring=YES  (desfazer: defaults delete -app Skim SKDisableSearchBarBlurring)"
fi

if [[ $WAS_RUNNING -eq 1 ]]; then
  defaults write -app Skim SKIsRelaunch -bool YES
fi

open ${OPEN_FLAGS[@]+"${OPEN_FLAGS[@]}"} -a "$DEST"
echo "ok — Skim $(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$DEST/Contents/Info.plist") reaberto"
