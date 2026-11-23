#!/bin/sh
# Does an image note survive in the PDF that Skim writes? Compiles
# tools/imagenotecheck.m against the SkimNotes headers of the build in
# src/build/Release and runs it — against that build, or against the framework
# binary in the folder given (an installed app ships it without headers):
#
#   tools/imagenotecheck.sh                                               # the fresh build
#   tools/imagenotecheck.sh /Applications/Skim.app/Contents/Frameworks   # the installed app
#
# Exit 0 = PASS. With poppler installed it also renders the written page, the
# check that a reader other than PDFKit draws the image.
set -e
here=$(cd "$(dirname "$0")" && pwd)
build=$here/../src/build/Release
work=$(mktemp -d -t imagenotecheck)
trap 'rm -rf "$work"' EXIT

clang -fobjc-arc -F "$build" -framework SkimNotes -framework Quartz -framework Cocoa \
    -Wl,-rpath,"$build" "$here/imagenotecheck.m" -o "$work/check"
status=0
if [ -n "$1" ]; then
    DYLD_FRAMEWORK_PATH="$1" "$work/check" "$work/note.pdf" || status=$?
else
    "$work/check" "$work/note.pdf" || status=$?
fi

if command -v pdftoppm >/dev/null 2>&1 && [ -f "$work/note.pdf" ]; then
    pdftoppm -r 72 -png -singlefile "$work/note.pdf" "$work/page" 2>"$work/poppler.err" || true
    if grep -q . "$work/poppler.err"; then
        echo "poppler: $(head -1 "$work/poppler.err")"
    else
        echo "poppler: renders without complaint"
    fi
fi
exit $status