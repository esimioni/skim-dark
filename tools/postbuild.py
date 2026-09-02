#!/usr/bin/env python3
"""Neutralises Sparkle in a built Skim.app, then re-signs it ad hoc.

Without this the fork is self-destructing: Sparkle points at upstream's appcast
(SUFeedURL, checked every SUScheduledCheckInterval = 86400s), so the first
update replaces the patched binary with a stock Skim and the configured colors
silently stop working. Turning off SUEnableAutomaticChecks in user defaults is
not enough — "Check for Updates..." in the menu still does it on demand.

Removing the feed key makes both paths fail loudly instead. Updating is manual:
svn up, tools/apply-patch.py, rebuild, run this again.

    python3 tools/postbuild.py [/path/to/Skim.app]     (default: /Applications/Skim.app)
"""
import plistlib, pathlib, subprocess, sys

app = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/Applications/Skim.app")
info = app / "Contents" / "Info.plist"
if not info.is_file():
    sys.exit(f"ABORT: {info} nao existe")

data = plistlib.loads(info.read_bytes())
removed = [k for k in ("SUFeedURL", "SUScheduledCheckInterval") if data.pop(k, None) is not None]
if removed:
    info.write_bytes(plistlib.dumps(data))
    # Editing Info.plist invalidates the bundle seal, so re-sign. --deep is needed,
    # not optional: Xcode strips Headers/ when it copies Sparkle.framework into the
    # bundle, but the framework's own seal still lists them, so a top-level-only
    # signature leaves "a sealed resource is missing or invalid" behind (19/08/2026).
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)],
                   check=True, capture_output=True)
print(f"sparkle neutralizado: removida(s) {removed or 'nenhuma (ja estava)'}")

check = subprocess.run(["codesign", "--verify", "--deep", "--strict", "--verbose=1", str(app)],
                       capture_output=True, text=True)
print("assinatura:", "ok" if check.returncode == 0 else check.stderr.strip())
