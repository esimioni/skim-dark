#!/bin/sh
# Follow Skim's trunk: revert src/ to pristine, svn up, commit the new trunk as
# an `upstream:` snapshot, re-apply the fork, commit that too. Two commits, so
# `git log` keeps upstream and the fork apart. Stops before the build — run the
# Build section of README.md next.
set -eu
cd "$(dirname "$0")/.."
[ -d src/.svn ] || { echo "src/ is not an svn working copy — see README.md, Fork on GitHub"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "git tree not clean — commit or stash first"; exit 1; }
before=$(svn info --show-item revision src)
(cd src && svn revert -R -q . && svn up -q)
after=$(svn info --show-item revision src)
[ "$after" != "$before" ] || { echo "already at r$before"; exit 0; }
if (cd src && svn status | grep -qv '^?'); then echo "svn tree not clean after revert + up"; exit 1; fi
git add -A src
git commit -q -m "upstream: Skim trunk r$after" -m "$(cd src && svn log -r "$((before + 1)):$after" | head -300)"
python3 tools/apply-patch.py
python3 tools/unblock-build.py
git add -A src
git commit -q -m "Re-apply the fork on r$after"
echo "r$before -> r$after, two commits. Now build: README.md > Build."
