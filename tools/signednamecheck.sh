#!/bin/sh
# Where does a signed document go? Compiles tools/signednamecheck.m with the real
# NSURL_SKExtensions.m of src/ (it needs nothing else of Skim) and runs it in an
# empty scratch folder:
#
#   tools/signednamecheck.sh
#
# Exit 0 = PASS.
set -e
here=$(cd "$(dirname "$0")" && pwd)
src=$here/../src
work=$(mktemp -d -t signednamecheck)
trap 'rm -rf "$work"' EXIT

clang -fobjc-arc -mmacosx-version-min=12.0 -Wno-deprecated-declarations -I "$src" -include "$src/Skim_Prefix.pch" \
    "$here/signednamecheck.m" "$src/NSURL_SKExtensions.m" -framework Cocoa -framework Quartz -o "$work/check"
mkdir "$work/folder"
"$work/check" "$work/folder"