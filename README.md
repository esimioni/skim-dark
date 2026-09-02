# skim-dark — the missing end of Skim's dark-mode inversion

A fork of [Skim](https://skim-app.sourceforge.io/) (BSD 3-clause) that makes
the *text* end of the dark-mode inversion configurable, and puts both ends in
the preferences window. Proposed upstream and declined, so it is maintained
here: [github.com/esimioni/skim-dark](https://github.com/esimioni/skim-dark).

## The problem

Skim's "Invert colors in Dark Mode" runs the page through
`CIGammaAdjust(0.625) -> CIColorMatrix -> CIGammaAdjust(1.6)`. For a gray input
`g` the matrix gives `out = g(1 - f) + bias`, so the two ends are:

| input | lands on |
|---|---|
| white page | `bias + 1 - f` |
| black text | `bias` |

Since **r16405** (2026-08-30) upstream can move the first one:
`SKInvertedColorsBackgroundWhite` sets `f = 2 - gamma16(white)`. The second one
is still hardcoded — `inputBiasVector` is `(1,1,1)` — so originally black
content is pinned to pure white, whatever the background is set to. On a warm
gray page that is the one thing that still glares.

## The patch

`bias` is exactly the level black content lands on, so exposing it is the same
move upstream already made for the other end:

    bias_c = text_c                    (level originally-black content lands on)
    f_c    = 1 + text_c - back_c       (per-channel luminance factor)

`SKInvertedColorsTextBlack` is added for `text_c`, in the style of the existing
key. Three things follow from it:

- **Both preferences accept a color**, not only a white value, because a text
  tone worth choosing is rarely neutral gray. The plain number the background
  key already took still works — `invertedColorsLevels()` reads either.
- **`f` becomes per channel.** With a tinted end the three channels no longer
  share one factor. `invertedColorsFilterFactor()` becomes
  `invertedColorsMatrix()`, returning both vectors, and `SKPreInvertedColor()`
  solves the same equation against them; for a scalar factor and a bias of 1 it
  reduces to the expression it had.
- **The factor is no longer cached in a static**, so a color well can move it
  while a document is open.

With both preferences unset this is upstream, exactly: `text_c = 1`,
`back_c = 2 - f`, giving back a bias of `(1,1,1)` and the original `f`.
`tools/filtercheck.swift` renders white and black through the real filter chain
and confirms the baseline — white -> `#2D2D2D` (the 45/255 the code comments
promise), black -> `#FFFFFF`.

## Preferences UI

Both ends are editable in **Preferences > Display**, on a `Page:` / `Text:` row
under the "Invert colors in Dark Mode" checkbox, disabled while that checkbox is
off. Where a preference is unset, its well shows the color the built-in default
produces — `#2D2D2D` for the page, white for the text, `#1E1E1E` for the page
with Increase Contrast — so the starting point is the real one, not an empty
swatch. `SKInvertedColorsBackgroundColor()` / `SKInvertedColorsTextColor()` own
that mapping; the pane observes both keys and the Increase Contrast
notification.

The open document follows the wells while a color is dragged: both keys were
added to `defaultKeysToObserve()` in `SKBasePDFView`, and to the observers in
`SKMainWindowController` that recompute the window background, which is
pre-inverted from the same math.

## Layout

- `src/` — Skim trunk at the revision of the last `upstream:` commit, with the
  patch applied; locally also an svn working copy (`.svn/` is not committed)
- `tools/apply-patch.py` — applies the change to `src/`; idempotent, re-run after `svn up`
- `tools/sync-upstream.sh` — follows trunk: two commits (upstream snapshot, then
  the fork re-applied), then build by hand
- `tools/filtercheck.swift` — renders white and black through the real filter
  chain and prints the resulting sRGB values, so the color math is verified
  numerically rather than by eye
- `tools/postbuild.py` — strips Sparkle's `SUFeedURL` from the built bundle and
  re-signs it; run after every build (see below)
- `tools/install.sh` — quits Skim, swaps `/Applications/Skim.app`, reopens
- `patches/` — `svn diff` output, which is what upstream would receive
- `LICENSE` — BSD 3-clause: upstream's, and the same terms for the fork

Seven files: the color math (`NSGraphics_SKExtensions.h/.m`), the live update
(`SKBasePDFView.m`, `SKMainWindowController.m`), and the preference pane
(`SKDisplayPreferences.h/.m` plus `Base.lproj/DisplayPreferences.xib`). Only the
Base localization gains the two new labels; the other
`*.lproj/DisplayPreferences.strings` are untouched and fall back to English.

⚠️ A build rewrites `en.lproj/DisplayPreferences.strings` in the source tree.
It is a build artifact, not part of the patch — `svn revert` it before
regenerating the diff.

## Build

Skim's trunk does not build straight out of the box on Xcode 26. Three
workarounds, none of which touch the patch itself:

1. Build `SkimNotesBase` and `SkimNotes` first — the Skim target expects both
   frameworks in the build products directory.
2. Point `FRAMEWORK_SEARCH_PATHS` at that directory; the importer target ships a
   stale hardcoded path.
3. Build `arm64` only. The universal build pulls in an x86_64 slice of the
   frameworks that is not produced here.

```sh
cd src
for t in SkimNotesBase SkimNotes; do
  xcodebuild -project SkimNotes/SkimNotes.xcodeproj -target "$t" -configuration Release \
    SYMROOT="$PWD/build" ARCHS=arm64 ONLY_ACTIVE_ARCH=YES \
    CODE_SIGN_IDENTITY="-" CODE_SIGNING_REQUIRED=NO
done
xcodebuild -project Skim.xcodeproj -target Skim -configuration Release \
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES CODE_SIGN_IDENTITY="-" CODE_SIGNING_REQUIRED=NO \
  FRAMEWORK_SEARCH_PATHS="$PWD/build/Release \$(inherited)"
cd .. && python3 tools/postbuild.py src/build/Release/Skim.app && tools/install.sh
```

`tools/unblock-build.py` drops the Skim -> Sparkle target dependency, which Xcode
26 rejects as a cycle between `Autoupdate` and `Sparkle`. It edits
`project.pbxproj` and must stay out of `patches/`.

The `postbuild.py` step is not optional: the app still embeds Sparkle, pointed at
upstream's appcast. Left alone, the first update replaces the patched binary with
a stock Skim and the colors quietly stop working. Turning off automatic checks in
user defaults does not cover the menu's "Check for Updates...", so the feed URL is
removed from the bundle instead and both paths fail loudly. Updates are therefore
manual: `svn up`, re-apply the patch, rebuild.

A xib edit is worth a syntax check before a full build, since `xcodebuild` reports
it late:

```sh
cd src && ibtool --errors --warnings --output-format human-readable-text \
  --compile /tmp/x.nib Base.lproj/DisplayPreferences.xib
```

⚠️ **Preference keys changed on 2026-09-01.** The first version of this patch used
`SKDarkModeBackgroundColor` / `SKDarkModeTextColor`; it now uses upstream's
`SKInvertedColorsBackgroundWhite` and the new `SKInvertedColorsTextBlack`. A
build from before that date reads the old names, so the colors have to be written
under the new ones once:

```sh
defaults write -app Skim SKInvertedColorsBackgroundWhite -array -float 0.1725 -float 0.1725 -float 0.1725
defaults write -app Skim SKInvertedColorsTextBlack -array -float 0.7216 -float 0.702 -float 0.6824
```

## Tahoe: the toolbar and tab bar turn light

Not part of the patch, and not a Skim bug — a macOS 26 interaction worth
recording, since it looks like one.

On Tahoe the toolbar is Liquid Glass, and per [WWDC25 session 310](https://developer.apple.com/videos/play/wwdc2025/310/):
*"The toolbar glass will even switch between a light and dark appearance if the
scrolled content is especially bright or dark. This appearance change is
communicated to the toolbar's content using the NSAppearance system."*

Skim's main window uses `fullSizeContentView`, so the PDF scroll view runs under
the toolbar and the tab bar. With inversion on, that scroll view is drawn in
**Aqua** with a white page on a light gray background and only inverted
afterwards, by `contentFilters` on the layer. AppKit reads the bright,
pre-filter content and flips the chrome to its light variant: white toolbar
capsules with dark glyphs, and a light tab bar, over a dark `#2C2C2C` titlebar.

There is no documented opt-out. What removes the trigger is Skim's own hidden
preference, which sets `mwcFlags.fullSizeContent = NO` and stops the content
from extending under the title bar:

```sh
defaults write -app Skim SKDisableSearchBarBlurring -bool YES   # undo: defaults delete
```

Measured on a screenshot before and after: the item capsules go from `#F2F2F2`
to `#141414`, the glyphs invert with them, and the selected item keeps a
`#494949` highlight — so the grouping survives, only its polarity changes. The
tab bar follows: `#828282` with a near-white `#E8E8E8` active tab and dark
labels becomes `#515151` with a `#575757` active tab and light labels.

The cost is the blur behind the find bar. `NSToolbarItem.bordered = NO` would
drop the glass capsule from each item instead, but it would also drop the
grouping, and it does nothing for the tab bar.

## Fork on GitHub

The whole tree is at [github.com/esimioni/skim-dark](https://github.com/esimioni/skim-dark),
`src/` included. The history keeps upstream and the fork apart: the first commit
is Skim trunk r16409 untouched (tag `upstream-r16409`), every `upstream:` commit
after it is a plain snapshot of a newer trunk, and the fork is everything else —
so `git diff upstream-r16409 -- src` is the fork, and nothing but the fork.

Following upstream is `tools/sync-upstream.sh`: revert `src/` to pristine,
`svn up`, commit the new trunk as `upstream: Skim trunk rNNNNN` with the svn log
in the body, re-apply the patch and the build workaround, commit again. It stops
before the build; the Build section comes next. If `apply-patch.py` aborts, an
anchor moved upstream — fix the tool, re-run.

`src/` is an svn working copy here, but `.svn/` is not committed. A fresh clone
that wants to follow upstream gets one with
`svn checkout --force svn://svn.code.sf.net/p/skim-app/code/trunk@16409 src`,
at the revision of the last `upstream` commit: `--force` is documented to leave
the existing files in place and mark the ones that differ as modified, which is
exactly the patched set. Not exercised here — this working copy predates the repo.

## Upstream

Skim lives on SourceForge under SVN, not GitHub, so a contribution is a ticket or
a mail, never a pull request. **There is no Patches tracker** — `/p/skim-app/patches/`
redirects to the download page. The two that exist are
[Feature Requests](https://sourceforge.net/p/skim-app/feature-requests/) and
[Bugs](https://sourceforge.net/p/skim-app/bugs/), and SourceForge tickets take
file attachments. The lists are `skim-app-develop` and `skim-app-users`
([overview](https://sourceforge.net/p/skim-app/mailman/)).

**Outcome (2026-09-02):** [Feature Request #1777](https://sourceforge.net/p/skim-app/feature-requests/1777/)
— the text-end preference plus the Preferences UI — was rejected and closed by the
maintainer the same night (*"goes much too far"*; the UI: *"I rejected that already"*).
Nothing in this fork is heading upstream: every `svn up` re-applies the patch and
rebuilds, for good. If a ticket is ever filed again: the one that got rejected was 491
words of math and function names with no screenshot, and the reply engaged with none
of it — put the ask in one sentence, the result in one image, the details in the attachment.

`patches/` holds the `svn diff` in the form they would expect. Regenerate it
against the seven patched files only — never the whole tree, which would drag in
the build workaround and the strings artifact — and force real unified diff,
since svn's built-in one ignores `-U`:

```sh
cd src && svn revert en.lproj/DisplayPreferences.strings && svn diff --diff-cmd diff -x -U3 \
  Base.lproj/DisplayPreferences.xib \
  NSGraphics_SKExtensions.h NSGraphics_SKExtensions.m \
  SKBasePDFView.m SKMainWindowController.m \
  SKDisplayPreferences.h SKDisplayPreferences.m \
  > ../patches/configurable-dark-mode-colors.diff
```
