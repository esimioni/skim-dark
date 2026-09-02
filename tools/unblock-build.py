#!/usr/bin/env python3
"""Build-environment workaround, NOT part of the upstream patch.

Xcode 26 refuses Skim's graph with "Cycle in dependencies between targets
'Autoupdate' and 'Sparkle'". Sparkle builds fine on its own, so we drop the
Skim -> Sparkle target dependency and let Skim link and embed the framework
that was already built into the shared products directory.

Keep this out of patches/ — it touches project.pbxproj only.
"""
import pathlib, sys

SPARKLE_DEP = "CE2BD8610BD4144000A5F4DB /* PBXTargetDependency */,"
p = pathlib.Path(__file__).resolve().parent.parent / "src" / "Skim.xcodeproj" / "project.pbxproj"
t = p.read_text()

if SPARKLE_DEP not in t:
    print("dependencia do Sparkle ja removida")
    sys.exit(0)
if t.count(SPARKLE_DEP) != 1:
    sys.exit(f"ABORT: esperava 1 ocorrencia, achei {t.count(SPARKLE_DEP)}")

lines = [l for l in t.splitlines(keepends=True) if l.strip() != SPARKLE_DEP]
p.write_text("".join(lines))
print("dependencia Skim -> Sparkle removida")
