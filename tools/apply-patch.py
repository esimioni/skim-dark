#!/usr/bin/env python3
"""Adds the missing end of Skim's dark-mode inversion, plus its preference UI.

Since r16405 upstream can configure the level a white page background lands on
(SKInvertedColorsBackgroundWhite). The other end is still fixed: the color matrix
biases by (1,1,1), so originally black content is pinned to pure white. This adds
SKInvertedColorsTextBlack for that end, generalises the two functions that read
the first one from a scalar to a per channel vector, and puts both ends in
Preferences > Display as color wells.

Both preferences accept a color, so a tone that is not neutral gray is possible;
the plain white number the background one already used still works. With both
unset the math reduces exactly to upstream, verified by tools/filtercheck.swift
(white -> #2D2D2D, black -> #FFFFFF).

Also adds View > Invert Colors in Dark Mode (ctrl-cmd-I), which flips the same
preference as the Display checkbox: upstream exposes it only there and to
AppleScript, so there was no way to toggle it from the keyboard. And it lets an
App Shortcut on Option without Command (Option-Shift-A) reach the menus: such a
key is also a typed letter (Å), the focused view got it first, and it never fired.

And a Signature toolbar button (2026-11-23): it puts the signature image the
preferences keep on the page as an image note, and Save writes image notes into
the PDF — which needed SkimNotes to draw the note's image as a CGImage, or PDFKit
saves it without the image (README, "Signature button"). And notes drawn at the
screen's resolution: PDFKit draws each annotation layer at one pixel per point.

And to send it on (2026-11-24): the first Save after the Signature button keeps
the file as it came and writes "<name>-signed" to Downloads; and a File toolbar
button, the document's file to drag into another app (README, "File button").

Idempotent: running it twice is a no-op. Run after `svn up`.
"""
import sys, pathlib

SRC = pathlib.Path(__file__).resolve().parent.parent / "src"

# ---------------------------------------------------------------- color math

OLD_MATH = '''#define SKInvertedColorsBackgroundWhiteKey @"SKInvertedColorsBackgroundWhite"

static inline CGFloat sRGBToGamma16(CGFloat c) { return c <= 0.04045 ? pow(c / 12.92, 0.625) : pow((c + 0.055) / 1.055, 1.5); }

static inline CGFloat sRGBFromGamma16(CGFloat c) { return c <= 0.0031308 ? 12.92 * pow(c, 1.6) : 1.055 * pow(c, 2.0/3.0) - 0.055; }

static CGFloat invertedColorsFilterFactor() {
    static CGFloat customFactor = -1.0;
    if (customFactor < 0.0) {
        NSNumber *bgw = [[NSUserDefaults standardUserDefaults] objectForKey:SKInvertedColorsBackgroundWhiteKey];
        customFactor = bgw ? 2.0 - sRGBToGamma16(fmax(0.0, fmin(1.0, [bgw  doubleValue]))) : 0.0;
    }
    return customFactor ?: [[NSWorkspace sharedWorkspace] accessibilityDisplayShouldIncreaseContrast] ? 1.9338 : 1.8972;
}
'''

NEW_MATH = '''NSString * const SKInvertedColorsBackgroundWhiteKey = @"SKInvertedColorsBackgroundWhite";
NSString * const SKInvertedColorsTextBlackKey = @"SKInvertedColorsTextBlack";

static inline CGFloat sRGBToGamma16(CGFloat c) { return c <= 0.04045 ? pow(c / 12.92, 0.625) : pow((c + 0.055) / 1.055, 1.5); }

static inline CGFloat sRGBFromGamma16(CGFloat c) { return c <= 0.0031308 ? 12.92 * pow(c, 1.6) : 1.055 * pow(c, 2.0/3.0) - 0.055; }

// maps a white page background to 45/255, or 30/255 with high contrast
static CGFloat invertedColorsDefaultFactor(void) {
    return [[NSWorkspace sharedWorkspace] accessibilityDisplayShouldIncreaseContrast] ? 1.9338 : 1.8972;
}

// The levels a preference maps to in the color matrix. A color allows a tone that
// is not neutral gray, and the plain white value still works. Returns NO and
// leaves the levels untouched when the preference is unset.
static BOOL invertedColorsLevels(NSString *key, CGFloat levels[3]) {
    NSUserDefaults *sud = [NSUserDefaults standardUserDefaults];
    NSColor *color = [[sud colorForKey:key] colorUsingColorSpace:[NSColorSpace sRGBColorSpace]];
    NSUInteger i;
    if (color) {
        CGFloat c[4] = {0.0, 0.0, 0.0, 1.0};
        [color getComponents:c];
        for (i = 0; i < 3; i++)
            levels[i] = sRGBToGamma16(fmax(0.0, fmin(1.0, c[i])));
        return YES;
    }
    id value = [sud objectForKey:key];
    if ([value isKindOfClass:[NSNumber class]] == NO)
        return NO;
    levels[0] = levels[1] = levels[2] = sRGBToGamma16(fmax(0.0, fmin(1.0, [value doubleValue])));
    return YES;
}

// The bias and the luminance factor of the inversion, per channel. Originally
// black content lands on the bias, originally white content on bias + 1 - factor,
// so each end follows from its own preference. With both unset this is the
// inversion as it was: a bias of 1, and the default factor.
static void invertedColorsMatrix(CGFloat bias[3], CGFloat factor[3]) {
    CGFloat f = invertedColorsDefaultFactor();
    CGFloat back[3] = {2.0 - f, 2.0 - f, 2.0 - f};
    CGFloat text[3] = {1.0, 1.0, 1.0};
    NSUInteger i;
    invertedColorsLevels(SKInvertedColorsBackgroundWhiteKey, back);
    invertedColorsLevels(SKInvertedColorsTextBlackKey, text);
    for (i = 0; i < 3; i++) {
        bias[i] = text[i];
        factor[i] = 1.0 + text[i] - back[i];
    }
}

// What an end resolves to as a color, so the preference pane can show the value
// in force rather than an empty well when the preference is unset.
static NSColor *invertedColorsColor(NSString *key, CGFloat defaultLevel) {
    CGFloat levels[3] = {defaultLevel, defaultLevel, defaultLevel};
    NSUInteger i;
    invertedColorsLevels(key, levels);
    for (i = 0; i < 3; i++)
        levels[i] = sRGBFromGamma16(fmax(0.0, fmin(1.0, levels[i])));
    return [NSColor colorWithSRGBRed:levels[0] green:levels[1] blue:levels[2] alpha:1.0];
}

NSColor *SKInvertedColorsBackgroundColor(void) {
    return invertedColorsColor(SKInvertedColorsBackgroundWhiteKey, 2.0 - invertedColorsDefaultFactor());
}

NSColor *SKInvertedColorsTextColor(void) {
    return invertedColorsColor(SKInvertedColorsTextBlackKey, 1.0);
}
'''

OLD_BODY = '''        // map the white page background to 45/255, or 30/255 with high contrast
        CGFloat f = invertedColorsFilterFactor();
        CGFloat lrf = LR * f, lgf = LG * f, lbf = LB * f;
        // This is like CIColorInvert + CIHueAdjust, modified to map white to dark gray rather than black'''

NEW_BODY = '''        CGFloat bias[3], f[3];
        invertedColorsMatrix(bias, f);
        // This is like CIColorInvert + CIHueAdjust, modified to map white and black
        // to the configured background and text colors rather than to black and white'''

OLD_MATRIX = '''@"inputRVector", [CIVector vectorWithX:1.0-lrf Y:-lgf Z:-lbf W:0.0], @"inputGVector", [CIVector vectorWithX:-lrf Y:1.0-lgf Z:-lbf W:0.0], @"inputBVector", [CIVector vectorWithX:-lrf Y:-lgf Z:1.0-lbf W:0.0], @"inputAVector", [CIVector vectorWithX:0.0 Y:0.0 Z:0.0 W:1.0], @"inputBiasVector", [CIVector vectorWithX:1.0 Y:1.0 Z:1.0 W:0.0], nil]'''

NEW_MATRIX = '''@"inputRVector", [CIVector vectorWithX:1.0-LR*f[0] Y:-LG*f[0] Z:-LB*f[0] W:0.0], @"inputGVector", [CIVector vectorWithX:-LR*f[1] Y:1.0-LG*f[1] Z:-LB*f[1] W:0.0], @"inputBVector", [CIVector vectorWithX:-LR*f[2] Y:-LG*f[2] Z:1.0-LB*f[2] W:0.0], @"inputAVector", [CIVector vectorWithX:0.0 Y:0.0 Z:0.0 W:1.0], @"inputBiasVector", [CIVector vectorWithX:bias[0] Y:bias[1] Z:bias[2] W:0.0], nil]'''

OLD_PREINVERT = '''NSColor *SKPreInvertedColor(NSColor *color) {
    CGFloat f = invertedColorsFilterFactor();
    if (f <= 1.0001)
        return color;
    CGFloat c[4] = {0.0, 0.0, 0.0, 1.0};
    NSUInteger i;
    [[color colorUsingColorSpace:[NSColorSpace sRGBColorSpace]] getComponents:c];
    for (i = 0; i < 3; i++)
        c[i] = sRGBToGamma16(c[i]);
    CGFloat offset = (1.0 - f * (LR * c[0] + LG * c[1] + LB * c[2])) / (f - 1.0);
    for (i = 0; i < 3; i++)
        c[i] = sRGBFromGamma16(fmin(1.0, fmax(0.0, c[i] + offset)));
    return [NSColor colorWithSRGBRed:c[0] green:c[1] blue:c[2] alpha:c[3]];
}'''

NEW_PREINVERT = '''NSColor *SKPreInvertedColor(NSColor *color) {
    CGFloat bias[3], f[3];
    NSUInteger i;
    invertedColorsMatrix(bias, f);
    // the luminance of the factor, which is what the inversion of a luminance sees
    CGFloat lf = LR * f[0] + LG * f[1] + LB * f[2];
    if (lf <= 1.0001)
        return color;
    CGFloat c[4] = {0.0, 0.0, 0.0, 1.0};
    [[color colorUsingColorSpace:[NSColorSpace sRGBColorSpace]] getComponents:c];
    for (i = 0; i < 3; i++)
        c[i] = sRGBToGamma16(c[i]);
    // out_i = c_i - f_i * luminance(c) + bias_i, solved for the c that inverts to the wanted out
    CGFloat luminance = (LR * bias[0] + LG * bias[1] + LB * bias[2] - (LR * c[0] + LG * c[1] + LB * c[2])) / (lf - 1.0);
    for (i = 0; i < 3; i++)
        c[i] = sRGBFromGamma16(fmin(1.0, fmax(0.0, c[i] + f[i] * luminance - bias[i])));
    return [NSColor colorWithSRGBRed:c[0] green:c[1] blue:c[2] alpha:c[3]];
}'''

# ------------------------------------------------------------------- the xib

XIB_VIEWS = '''                        <binding destination="61" name="value" keyPath="values.SKInvertColorsInDarkMode" id="XrJ-7e-odj"/>
                    </connections>
                </button>
                <textField horizontalHuggingPriority="253" verticalHuggingPriority="750" translatesAutoresizingMaskIntoConstraints="NO" id="Dbg-La-bl1" userLabel="Page:">
                    <rect key="frame" x="63" y="208" width="39" height="16"/>
                    <textFieldCell key="cell" scrollable="YES" lineBreakMode="clipping" sendsActionOnEndEditing="YES" alignment="right" title="Page:" id="Dbg-Ce-ll1">
                        <font key="font" metaFont="system"/>
                        <color key="textColor" name="labelColor" catalog="System" colorSpace="catalog"/>
                        <color key="backgroundColor" name="textBackgroundColor" catalog="System" colorSpace="catalog"/>
                    </textFieldCell>
                    <connections>
                        <binding destination="-2" name="hidden" keyPath="allowsDarkMode" id="Dbg-Bi-hd1">
                            <dictionary key="options">
                                <string key="NSValueTransformerName">NSNegateBoolean</string>
                            </dictionary>
                        </binding>
                        <binding destination="61" name="enabled" keyPath="values.SKInvertColorsInDarkMode" id="Dbg-Bi-en1"/>
                    </connections>
                </textField>
                <colorWell toolTip="Color that an originally white page background becomes in Dark Mode" translatesAutoresizingMaskIntoConstraints="NO" id="Dbg-Cw-el1" customClass="SKColorWell">
                    <rect key="frame" x="108" y="204" width="52" height="24"/>
                    <constraints>
                        <constraint firstAttribute="height" constant="24" id="Dbg-Cn-hg1"/>
                        <constraint firstAttribute="width" constant="52" id="Dbg-Cn-wd1"/>
                    </constraints>
                    <color key="color" red="0.17647058799999999" green="0.17647058799999999" blue="0.17647058799999999" alpha="1" colorSpace="calibratedRGB"/>
                    <connections>
                        <accessibilityConnection property="link" destination="Dtx-Cw-el2" id="Dbg-Ax-lk1"/>
                        <accessibilityConnection property="title" destination="Dbg-La-bl1" id="Dbg-Ax-ti1"/>
                        <binding destination="-2" name="hidden" keyPath="allowsDarkMode" id="Dbg-Bi-hd2">
                            <dictionary key="options">
                                <string key="NSValueTransformerName">NSNegateBoolean</string>
                            </dictionary>
                        </binding>
                        <binding destination="61" name="enabled" keyPath="values.SKInvertColorsInDarkMode" id="Dbg-Bi-en2"/>
                        <outlet property="nextKeyView" destination="Dtx-Cw-el2" id="Dbg-Nk-vw1"/>
                    </connections>
                </colorWell>
                <textField horizontalHuggingPriority="253" verticalHuggingPriority="750" translatesAutoresizingMaskIntoConstraints="NO" id="Dtx-La-bl2" userLabel="Text:">
                    <rect key="frame" x="180" y="208" width="34" height="16"/>
                    <textFieldCell key="cell" scrollable="YES" lineBreakMode="clipping" sendsActionOnEndEditing="YES" alignment="right" title="Text:" id="Dtx-Ce-ll2">
                        <font key="font" metaFont="system"/>
                        <color key="textColor" name="labelColor" catalog="System" colorSpace="catalog"/>
                        <color key="backgroundColor" name="textBackgroundColor" catalog="System" colorSpace="catalog"/>
                    </textFieldCell>
                    <connections>
                        <binding destination="-2" name="hidden" keyPath="allowsDarkMode" id="Dtx-Bi-hd1">
                            <dictionary key="options">
                                <string key="NSValueTransformerName">NSNegateBoolean</string>
                            </dictionary>
                        </binding>
                        <binding destination="61" name="enabled" keyPath="values.SKInvertColorsInDarkMode" id="Dtx-Bi-en1"/>
                    </connections>
                </textField>
                <colorWell toolTip="Color that originally black text becomes in Dark Mode" translatesAutoresizingMaskIntoConstraints="NO" id="Dtx-Cw-el2" customClass="SKColorWell">
                    <rect key="frame" x="221" y="204" width="52" height="24"/>
                    <color key="color" red="1" green="1" blue="1" alpha="1" colorSpace="calibratedRGB"/>
                    <connections>
                        <accessibilityConnection property="title" destination="Dtx-La-bl2" id="Dtx-Ax-ti1"/>
                        <binding destination="-2" name="hidden" keyPath="allowsDarkMode" id="Dtx-Bi-hd2">
                            <dictionary key="options">
                                <string key="NSValueTransformerName">NSNegateBoolean</string>
                            </dictionary>
                        </binding>
                        <binding destination="61" name="enabled" keyPath="values.SKInvertColorsInDarkMode" id="Dtx-Bi-en2"/>
                    </connections>
                </colorWell>'''

XIB_CONSTRAINTS = '''                <constraint firstItem="26" firstAttribute="top" secondItem="Dbg-Cw-el1" secondAttribute="bottom" constant="12" id="6I5-BJ-rIA"/>
                <constraint firstItem="Dbg-La-bl1" firstAttribute="leading" relation="greaterThanOrEqual" secondItem="1" secondAttribute="leading" constant="48" id="Dbg-Cn-ld1"/>
                <constraint firstItem="Dbg-La-bl1" firstAttribute="leading" secondItem="1" secondAttribute="leading" priority="252" constant="48" id="Dbg-Cn-ld2"/>
                <constraint firstItem="Dbg-La-bl1" firstAttribute="top" secondItem="I3F-RC-rb4" secondAttribute="bottom" constant="10" id="Dbg-Cn-tp1"/>
                <constraint firstItem="Dbg-Cw-el1" firstAttribute="leading" secondItem="Dbg-La-bl1" secondAttribute="trailing" constant="8" symbolic="YES" id="Dbg-Cn-lw1"/>
                <constraint firstItem="Dbg-Cw-el1" firstAttribute="centerY" secondItem="Dbg-La-bl1" secondAttribute="centerY" id="Dbg-Cn-cy1"/>
                <constraint firstItem="Dtx-La-bl2" firstAttribute="leading" secondItem="Dbg-Cw-el1" secondAttribute="trailing" constant="20" id="Dtx-Cn-ld1"/>
                <constraint firstItem="Dtx-La-bl2" firstAttribute="centerY" secondItem="Dbg-La-bl1" secondAttribute="centerY" id="Dtx-Cn-cy1"/>
                <constraint firstItem="Dtx-Cw-el2" firstAttribute="leading" secondItem="Dtx-La-bl2" secondAttribute="trailing" constant="7" id="Dtx-Cn-lw1"/>
                <constraint firstItem="Dtx-Cw-el2" firstAttribute="top" secondItem="Dbg-Cw-el1" secondAttribute="top" id="Dtx-Cn-tp1"/>
                <constraint firstItem="Dtx-Cw-el2" firstAttribute="bottom" secondItem="Dbg-Cw-el1" secondAttribute="bottom" id="Dtx-Cn-bt1"/>
                <constraint firstItem="Dtx-Cw-el2" firstAttribute="width" secondItem="Dbg-Cw-el1" secondAttribute="width" id="Dtx-Cn-wd1"/>
                <constraint firstAttribute="trailing" relation="greaterThanOrEqual" secondItem="Dtx-Cw-el2" secondAttribute="trailing" constant="20" symbolic="YES" id="Dtx-Cn-tr1"/>'''

# --------------------------------------------------- signed copy, File button

FILE_DRAG_BUTTON = '''
// skim-dark: the File toolbar button. It is the document's file, to drag into
// another app (a chat, a mail, a folder), like the proxy icon of a window title,
// which Skim does not show: it hides the title under the toolbar. What is dropped
// is the file on disk, so unsaved changes are saved first, as Save does (a
// signature goes to Downloads, as "<name>-signed"); a save that does not finish at once (a
// panel, an error) leaves no drag. A copy, never a move: the file stays put. It
// drags from a window in the back too, the way Finder does, and Skim stays behind
// the app it is dragged into.
@interface SKFileDragButton : NSSegmentedControl <NSDraggingSource>
@property (nonatomic, nullable, weak) SKMainWindowController *mainController;
@end

@implementation SKFileDragButton

@synthesize mainController;

- (BOOL)acceptsFirstMouse:(NSEvent *)theEvent { return YES; }

- (BOOL)shouldDelayWindowOrderingForEvent:(NSEvent *)theEvent { return YES; }

- (void)mouseDown:(NSEvent *)theEvent {
    NSDocument *document = [mainController document];
    if ([self isEnabled] == NO || [document fileURL] == nil)
        return;
    NSPoint start = [theEvent locationInWindow];
    NSEvent *event = nil;
    do {
        event = [[self window] nextEventMatchingMask:NSEventMaskLeftMouseUp | NSEventMaskLeftMouseDragged];
        if ([event type] == NSEventTypeLeftMouseUp)
            return;
    } while (fabs([event locationInWindow].x - start.x) < 3.0 && fabs([event locationInWindow].y - start.y) < 3.0);
    if ([document isDocumentEdited]) {
        [document saveDocument:self];
        if ([document isDocumentEdited])
            return;
    }
    NSURL *fileURL = [document fileURL];
    NSPoint point = [self convertPoint:[event locationInWindow] fromView:nil];
    NSDraggingItem *item = [[NSDraggingItem alloc] initWithPasteboardWriter:fileURL];
    [item setDraggingFrame:NSMakeRect(point.x - 24.0, point.y - 24.0, 48.0, 48.0) contents:[[NSWorkspace sharedWorkspace] iconForFile:[fileURL path]]];
    [NSApp preventWindowOrdering];
    [self beginDraggingSessionWithItems:@[item] event:event source:self];
}

- (NSDragOperation)draggingSession:(NSDraggingSession *)session sourceOperationMaskForDraggingContext:(NSDraggingContext)context {
    return context == NSDraggingContextOutsideApplication ? (NSDragOperationCopy | NSDragOperationGeneric) : NSDragOperationNone;
}

@end

#pragma mark -

@interface SKMainToolbarController ()
'''

SIGNED_SAVE = '''- (void)didAddSignature {
    mdFlags.savesSignedCopy = 1;
}

// skim-dark: the first Save after the Signature button leaves the file as it came
// and writes the signed document to the Downloads folder, as "<name>-signed": a
// Save As, so the window moves to the new file and later saves replace that one.
// Downloads, not beside the file: a PDF opened from WhatsApp lives in WhatsApp's
// container, where macOS lets Skim save over the file it was handed but not make
// one next to it ("You don't have permission", kTCCServiceSystemPolicyAppDataDetailed
// in the log, 2026-11-24), and a copy there would stay lost; Downloads gets sorted.
// Only while an image note is there to write into the PDF; with the signature
// undone, or for a signed file already in Downloads, it is the plain Save. Save
// and the "save changes?" alert of a close both come here; a Save or Save As that
// goes through ends it.
- (void)saveDocumentWithDelegate:(id)delegate didSaveSelector:(SEL)didSaveSelector contextInfo:(void *)contextInfo {
    NSURL *signedURL = nil;
    if (mdFlags.savesSignedCopy && [self fileURL] && [[self imageNoteProperties] count] > 0) {
        NSURL *downloadsURL = [[NSFileManager defaultManager] URLForDirectory:NSDownloadsDirectory inDomain:NSUserDomainMask appropriateForURL:nil create:YES error:NULL];
        if (downloadsURL)
            signedURL = [[self fileURL] signedFileURLInFolder:downloadsURL];
    }
    if (signedURL)
        [self saveToURL:signedURL ofType:[self fileType] forSaveOperation:NSSaveAsOperation delegate:delegate didSaveSelector:didSaveSelector contextInfo:contextInfo];
    else
        [super saveDocumentWithDelegate:delegate didSaveSelector:didSaveSelector contextInfo:contextInfo];
}

// Prepare for saving and use callback to save notes and cleanup
'''

SIGNED_FILE_URL = '''- (NSURL *)signedFileURLInFolder:(NSURL *)folderURL {
    NSString *baseName = [[self lastPathComponent] stringByDeletingPathExtension];
    if ([baseName length] == 0)
        return nil;
    if ([baseName rangeOfString:@"-signed(-[0-9]+)?$" options:NSRegularExpressionSearch | NSCaseInsensitiveSearch].location == NSNotFound)
        baseName = [baseName stringByAppendingString:@"-signed"];
    NSString *fileName = [[self pathExtension] length] > 0 ? [baseName stringByAppendingPathExtension:[self pathExtension]] : baseName;
    NSURL *signedURL = [folderURL URLByAppendingPathComponent:fileName isDirectory:NO];
    if ([[[signedURL URLByResolvingSymlinksInPath] path] isEqualToString:[[self URLByResolvingSymlinksInPath] path]])
        return nil;
    return [signedURL uniqueFileURL];
}

- (BOOL)isTrashedFileURL {
'''

# -------------------------------------------------------------------- edits

EDITS = [
    # color math
    ("NSGraphics_SKExtensions.m", OLD_MATH, NEW_MATH),
    ("NSGraphics_SKExtensions.m", OLD_BODY, NEW_BODY),
    ("NSGraphics_SKExtensions.m", OLD_MATRIX, NEW_MATRIX),
    ("NSGraphics_SKExtensions.m", OLD_PREINVERT, NEW_PREINVERT),
    ("NSGraphics_SKExtensions.h",
     'extern NSColor *SKPreInvertedColor(NSColor *color);',
     'extern NSColor *SKPreInvertedColor(NSColor *color);\n\n'
     'extern NSString * const SKInvertedColorsBackgroundWhiteKey;\n'
     'extern NSString * const SKInvertedColorsTextBlackKey;\n\n'
     '// The colors an originally white page background and originally black content\n'
     '// are mapped to, from the preferences or the built in defaults.\n'
     'extern NSColor *SKInvertedColorsBackgroundColor(void);\n'
     'extern NSColor *SKInvertedColorsTextColor(void);'),

    # live update of the open document while the color wells change
    ("SKBasePDFView.m",
     'return @[SKInvertColorsInDarkModeKey, SKSepiaToneKey, SKWhitePointKey];',
     'return @[SKInvertColorsInDarkModeKey, SKSepiaToneKey, SKWhitePointKey, SKInvertedColorsBackgroundWhiteKey, SKInvertedColorsTextBlackKey];'),

    # ... and of the window background, which is pre-inverted from the same math
    # SKMainWindowController does not import the header the keys now live in
    ("SKMainWindowController.m",
     '#import "SKStringConstants.h"\n',
     '#import "SKStringConstants.h"\n#import "NSGraphics_SKExtensions.h"\n'),
    ("SKMainWindowController.m",
     '                            SKInvertColorsInDarkModeKey,\n'
     '                            SKThumbnailSizeKey, SKSnapshotThumbnailSizeKey,\n'
     '                            SKInterpolationQualityKey,\n'
     '                            SKTableFontSizeKey])\n'
     '        [sud addObserver:',
     '                            SKInvertColorsInDarkModeKey,\n'
     '                            SKInvertedColorsBackgroundWhiteKey, SKInvertedColorsTextBlackKey,\n'
     '                            SKThumbnailSizeKey, SKSnapshotThumbnailSizeKey,\n'
     '                            SKInterpolationQualityKey,\n'
     '                            SKTableFontSizeKey])\n'
     '        [sud addObserver:'),
    ("SKMainWindowController.m",
     '                            SKInvertColorsInDarkModeKey,\n'
     '                            SKThumbnailSizeKey, SKSnapshotThumbnailSizeKey,\n'
     '                            SKInterpolationQualityKey,\n'
     '                            SKTableFontSizeKey]) {\n'
     '        @try { [sud removeObserver:',
     '                            SKInvertColorsInDarkModeKey,\n'
     '                            SKInvertedColorsBackgroundWhiteKey, SKInvertedColorsTextBlackKey,\n'
     '                            SKThumbnailSizeKey, SKSnapshotThumbnailSizeKey,\n'
     '                            SKInterpolationQualityKey,\n'
     '                            SKTableFontSizeKey]) {\n'
     '        @try { [sud removeObserver:'),
    ("SKMainWindowController.m",
     '        if ([keyPath isEqualToString:SKBackgroundColorKey] || [keyPath isEqualToString:SKDarkBackgroundColorKey] || [keyPath isEqualToString:SKInvertColorsInDarkModeKey]) {',
     '        if ([keyPath isEqualToString:SKBackgroundColorKey] || [keyPath isEqualToString:SKDarkBackgroundColorKey] || [keyPath isEqualToString:SKInvertColorsInDarkModeKey] ||\n'
     '            [keyPath isEqualToString:SKInvertedColorsBackgroundWhiteKey] || [keyPath isEqualToString:SKInvertedColorsTextBlackKey]) {'),

    # preference pane outlets and actions
    ("SKDisplayPreferences.h",
     '    NSColorWell *fullScreenColorWell;\n',
     '    NSColorWell *fullScreenColorWell;\n'
     '    NSColorWell *invertedBackgroundColorWell;\n'
     '    NSColorWell *invertedTextColorWell;\n'),
    ("SKDisplayPreferences.h",
     '@property (nonatomic, nullable, strong) IBOutlet NSColorWell *fullScreenColorWell;\n',
     '@property (nonatomic, nullable, strong) IBOutlet NSColorWell *fullScreenColorWell;\n'
     '@property (nonatomic, nullable, strong) IBOutlet NSColorWell *invertedBackgroundColorWell;\n'
     '@property (nonatomic, nullable, strong) IBOutlet NSColorWell *invertedTextColorWell;\n'),
    ("SKDisplayPreferences.h",
     '- (IBAction)changeFullScreenBackgroundColor:(nullable id)sender;\n',
     '- (IBAction)changeFullScreenBackgroundColor:(nullable id)sender;\n'
     '- (IBAction)changeInvertedBackgroundColor:(nullable id)sender;\n'
     '- (IBAction)changeInvertedTextColor:(nullable id)sender;\n'),

    # preference pane wiring
    ("SKDisplayPreferences.m",
     '@interface SKDisplayPreferences ()\n- (void)updateBackgroundColors;\n@end',
     '@interface SKDisplayPreferences ()\n- (void)updateBackgroundColors;\n- (void)updateInvertedColors;\n@end'),
    ("SKDisplayPreferences.m",
     '@synthesize normalColorWell, fullScreenColorWell, colorSwatch, addRemoveColorButton;',
     '@synthesize normalColorWell, fullScreenColorWell, invertedBackgroundColorWell, invertedTextColorWell, colorSwatch, addRemoveColorButton;'),
    ("SKDisplayPreferences.m",
     '        for (NSString *key in @[SKBackgroundColorKey, SKFullScreenBackgroundColorKey, SKDarkBackgroundColorKey, SKDarkFullScreenBackgroundColorKey]) {\n'
     '            @try { [sud removeObserver:self forKeyPath:key context:&SKDisplayPreferencesDefaultsObservationContext]; }\n'
     '            @catch(id e) {}\n'
     '        }\n',
     '        for (NSString *key in @[SKBackgroundColorKey, SKFullScreenBackgroundColorKey, SKDarkBackgroundColorKey, SKDarkFullScreenBackgroundColorKey, SKInvertedColorsBackgroundWhiteKey, SKInvertedColorsTextBlackKey]) {\n'
     '            @try { [sud removeObserver:self forKeyPath:key context:&SKDisplayPreferencesDefaultsObservationContext]; }\n'
     '            @catch(id e) {}\n'
     '        }\n'
     '        [[[NSWorkspace sharedWorkspace] notificationCenter] removeObserver:self name:NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification object:nil];\n'),
    ("SKDisplayPreferences.m",
     '        [fullScreenColorWell setTarget:self];\n        \n        [self updateBackgroundColors];\n',
     '        [fullScreenColorWell setTarget:self];\n'
     '        [invertedBackgroundColorWell setAction:@selector(changeInvertedBackgroundColor:)];\n'
     '        [invertedBackgroundColorWell setTarget:self];\n'
     '        [invertedTextColorWell setAction:@selector(changeInvertedTextColor:)];\n'
     '        [invertedTextColorWell setTarget:self];\n'
     '        \n'
     '        [self updateBackgroundColors];\n'
     '        [self updateInvertedColors];\n'),
    ("SKDisplayPreferences.m",
     '        for (NSString *key in @[SKBackgroundColorKey, SKFullScreenBackgroundColorKey, SKDarkBackgroundColorKey, SKDarkFullScreenBackgroundColorKey])\n'
     '            [sud addObserver:self forKeyPath:key options:0 context:&SKDisplayPreferencesDefaultsObservationContext];\n'
     '        [NSApp addObserver:self forKeyPath:@"effectiveAppearance" options:0 context:&SKDisplayPreferencesDefaultsObservationContext];\n',
     '        for (NSString *key in @[SKBackgroundColorKey, SKFullScreenBackgroundColorKey, SKDarkBackgroundColorKey, SKDarkFullScreenBackgroundColorKey, SKInvertedColorsBackgroundWhiteKey, SKInvertedColorsTextBlackKey])\n'
     '            [sud addObserver:self forKeyPath:key options:0 context:&SKDisplayPreferencesDefaultsObservationContext];\n'
     '        [NSApp addObserver:self forKeyPath:@"effectiveAppearance" options:0 context:&SKDisplayPreferencesDefaultsObservationContext];\n'
     '        // the default the color wells fall back to depends on the high contrast setting\n'
     '        [[[NSWorkspace sharedWorkspace] notificationCenter] addObserver:self selector:@selector(handleAccessibilityDisplayOptionsDidChange:) name:NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification object:nil];\n'),
    ("SKDisplayPreferences.m",
     '- (IBAction)addRemoveColor:(id)sender {',
     '- (IBAction)changeInvertedBackgroundColor:(id)sender {\n'
     '    [[NSUserDefaults standardUserDefaults] setColor:[sender color] forKey:SKInvertedColorsBackgroundWhiteKey];\n'
     '}\n\n'
     '- (IBAction)changeInvertedTextColor:(id)sender {\n'
     '    [[NSUserDefaults standardUserDefaults] setColor:[sender color] forKey:SKInvertedColorsTextBlackKey];\n'
     '}\n\n'
     '- (IBAction)addRemoveColor:(id)sender {'),
    ("SKDisplayPreferences.m",
     '#pragma mark KVO\n',
     '#pragma mark Notifications\n\n'
     '- (void)handleAccessibilityDisplayOptionsDidChange:(NSNotification *)notification {\n'
     '    [self updateInvertedColors];\n'
     '}\n\n'
     '#pragma mark KVO\n'),
    ("SKDisplayPreferences.m",
     '    if (context == &SKDisplayPreferencesDefaultsObservationContext) {\n        [self updateBackgroundColors];\n    }',
     '    if (context == &SKDisplayPreferencesDefaultsObservationContext) {\n        [self updateBackgroundColors];\n        [self updateInvertedColors];\n    }'),
    ("SKDisplayPreferences.m",
     '    [normalColorWell setColor:color];\n    [fullScreenColorWell setColor:fsColor];\n}\n',
     '    [normalColorWell setColor:color];\n    [fullScreenColorWell setColor:fsColor];\n}\n\n'
     '- (void)updateInvertedColors {\n'
     '    [invertedBackgroundColorWell setColor:SKInvertedColorsBackgroundColor()];\n'
     '    [invertedTextColorWell setColor:SKInvertedColorsTextColor()];\n'
     '}\n'),

    # the preference pane nib
    ("Base.lproj/DisplayPreferences.xib",
     '                <outlet property="colorSwatch" destination="0cC-e4-fiv" id="trB-5r-ovc"/>',
     '                <outlet property="colorSwatch" destination="0cC-e4-fiv" id="trB-5r-ovc"/>\n'
     '                <outlet property="invertedBackgroundColorWell" destination="Dbg-Cw-el1" id="Dbg-Ou-tl1"/>\n'
     '                <outlet property="invertedTextColorWell" destination="Dtx-Cw-el2" id="Dtx-Ou-tl2"/>'),
    ("Base.lproj/DisplayPreferences.xib",
     '                        <binding destination="61" name="value" keyPath="values.SKInvertColorsInDarkMode" id="XrJ-7e-odj"/>\n'
     '                    </connections>\n'
     '                </button>',
     XIB_VIEWS),
    ("Base.lproj/DisplayPreferences.xib",
     '                <constraint firstItem="26" firstAttribute="top" secondItem="I3F-RC-rb4" secondAttribute="bottom" constant="12" id="6I5-BJ-rIA"/>',
     XIB_CONSTRAINTS),

    # View > Invert Colors in Dark Mode, ctrl-cmd-I (the one I combination Skim
    # leaves free). It sets the same default as the checkbox, so the open
    # documents follow it through the observers that already watch that key.
    ("Base.lproj/MainMenu.xib",
     '                                    <action selector="toggleReadingBar:" target="-1" id="718"/>\n'
     '                                </connections>\n'
     '                            </menuItem>\n',
     '                                    <action selector="toggleReadingBar:" target="-1" id="718"/>\n'
     '                                </connections>\n'
     '                            </menuItem>\n'
     '                            <menuItem title="Invert Colors in Dark Mode" keyEquivalent="i" id="Inv-Dk-mnu">\n'
     '                                <modifierMask key="keyEquivalentModifierMask" control="YES" command="YES"/>\n'
     '                                <connections>\n'
     '                                    <action selector="toggleInvertColorsInDarkMode:" target="-1" id="Inv-Dk-act"/>\n'
     '                                </connections>\n'
     '                            </menuItem>\n'),
    ("SKApplicationController.h",
     '- (IBAction)showDownloads:(nullable id)sender;\n',
     '- (IBAction)showDownloads:(nullable id)sender;\n'
     '- (IBAction)toggleInvertColorsInDarkMode:(nullable id)sender;\n'),
    ("SKApplicationController.m",
     '- (IBAction)changeFindPaneState:(id)sender {}\n',
     '- (IBAction)changeFindPaneState:(id)sender {}\n\n'
     '- (IBAction)toggleInvertColorsInDarkMode:(id)sender {\n'
     '    NSUserDefaults *sud = [NSUserDefaults standardUserDefaults];\n'
     '    [sud setBool:[sud boolForKey:SKInvertColorsInDarkModeKey] == NO forKey:SKInvertColorsInDarkModeKey];\n'
     '}\n'),
    ("SKApplicationController.m",
     '    } else if (action == @selector(changeFindPaneState:)) {\n'
     '        [menuItem setHidden:YES];\n'
     '        return NO;\n'
     '    }\n',
     '    } else if (action == @selector(changeFindPaneState:)) {\n'
     '        [menuItem setHidden:YES];\n'
     '        return NO;\n'
     '    } else if (action == @selector(toggleInvertColorsInDarkMode:)) {\n'
     '        [menuItem setState:[[NSUserDefaults standardUserDefaults] boolForKey:SKInvertColorsInDarkModeKey] ? NSControlStateValueOn : NSControlStateValueOff];\n'
     '        return YES;\n'
     '    }\n'),

    # An App Shortcut on Option without Command, like Option-Shift-A, is also a
    # typed letter (Å on the US layouts). It went to the focused view, where the
    # PDF view's type select takes letters, and never fired (2026-09-28). Outside
    # text editing the menus now get such a key first. Arrow keys are left out:
    # they are function keys, and upstream's Option-Up/Down keep their own path.
    ("SKApplication.m",
     '#import "SKPreferenceController.h"\n\n\n@implementation SKApplication\n',
     '#import "SKPreferenceController.h"\n\n'
     '// Option or Option-Shift on a key that types a character, not on a function key\n'
     'static inline BOOL SKIsOptionCharacterEvent(NSEvent *anEvent) {\n'
     '    if (([anEvent deviceIndependentModifierFlags] & (NSEventModifierFlagCommand | NSEventModifierFlagControl | NSEventModifierFlagOption | NSEventModifierFlagFunction)) != NSEventModifierFlagOption)\n'
     '        return NO;\n'
     '    NSString *characters = [anEvent charactersIgnoringModifiers];\n'
     '    return [characters length] > 0 && ([characters characterAtIndex:0] < 0xF700 || [characters characterAtIndex:0] > 0xF8FF);\n'
     '}\n\n'
     '@implementation SKApplication\n'),
    ("SKApplication.m",
     '        [NSEvent setCurrentPointingDeviceType:[anEvent isEnteringProximity] ? [anEvent pointingDeviceType] : NSPointingDeviceTypeUnknown];\n'
     '    }\n'
     '    [super sendEvent:anEvent];\n',
     '        [NSEvent setCurrentPointingDeviceType:[anEvent isEnteringProximity] ? [anEvent pointingDeviceType] : NSPointingDeviceTypeUnknown];\n'
     '    } else if ([anEvent type] == NSEventTypeKeyDown && SKIsOptionCharacterEvent(anEvent) &&\n'
     '               [[[self keyWindow] firstResponder] isKindOfClass:[NSText class]] == NO &&\n'
     '               [[self mainMenu] performKeyEquivalent:anEvent]) {\n'
     '        // an Option shortcut without Command is also a typed letter, which the\n'
     '        // first responder would get before the menus; in a text field it still types\n'
     '        return;\n'
     '    }\n'
     '    [super sendEvent:anEvent];\n'),

    # ------------------------------------------------------------ signature
    # The Signature toolbar button: one click puts the signature image the
    # preferences keep (SKSignatureImage, the image data) on the visible page as an image
    # note, selected, for the mouse to size and move; Save writes the image notes
    # into the PDF itself. Asked for on 2026-11-23, to sign PDFs in Skim instead
    # of PDFgear. Three parts, so each can be checked on its own.

    # 1. SkimNotes draws the image of an image note as a CGImage. PDFKit builds the
    # appearance stream it saves from this drawing, and an NSImage drawn here lands
    # there as a form XObject (/Fm1) without its resources: the image vanished from
    # every PDF Skim wrote, in any other reader — "PDF With Embedded Notes" gave a
    # stamp that poppler draws as nothing (macOS 27). tools/imagenotecheck.sh.
    ("SkimNotes/SKNPDFAnnotationNote.m",
     '- (void)drawWithBox:(PDFDisplayBox)box inContext:(CGContextRef)context {\n'
     '    if ([self drawsImage] && [self hasAppearanceStream] == NO && [self image] != nil) {\n'
     '        CGContextSaveGState(context);\n'
     '        [[self page] transformContext:context forBox:box];\n'
     '        [NSGraphicsContext saveGraphicsState];\n'
     '        [NSGraphicsContext setCurrentContext:[NSGraphicsContext graphicsContextWithCGContext:context flipped:NO]];\n'
     '        [[self image] drawInRect:[self bounds]];\n'
     '        [NSGraphicsContext restoreGraphicsState];\n'
     '        CGContextRestoreGState(context);\n',
     '// The largest bitmap of an image, or NULL when it has none (a PDF or EPS image).\n'
     '// PDFKit saves the appearance of a note from -drawWithBox:inContext:, and an\n'
     '// NSImage drawn there is saved as a form XObject without its resources, which\n'
     '// other readers draw as nothing; a CGImage is saved as an image XObject.\n'
     'static CGImageRef SKNBitmapImageForImage(NSImage *image) {\n'
     '    NSBitmapImageRep *best = nil;\n'
     '    for (NSImageRep *rep in [image representations]) {\n'
     '        if ([rep isKindOfClass:[NSBitmapImageRep class]] && [rep pixelsWide] * [rep pixelsHigh] > [best pixelsWide] * [best pixelsHigh])\n'
     '            best = (NSBitmapImageRep *)rep;\n'
     '    }\n'
     '    return [best CGImage];\n'
     '}\n'
     '\n'
     '- (void)drawWithBox:(PDFDisplayBox)box inContext:(CGContextRef)context {\n'
     '    if ([self drawsImage] && [self hasAppearanceStream] == NO && [self image] != nil) {\n'
     '        CGContextSaveGState(context);\n'
     '        [[self page] transformContext:context forBox:box];\n'
     '        CGImageRef bitmap = SKNBitmapImageForImage([self image]);\n'
     '        if (bitmap) {\n'
     '            CGContextDrawImage(context, NSRectToCGRect([self bounds]), bitmap);\n'
     '        } else {\n'
     '            [NSGraphicsContext saveGraphicsState];\n'
     '            [NSGraphicsContext setCurrentContext:[NSGraphicsContext graphicsContextWithCGContext:context flipped:NO]];\n'
     '            [[self image] drawInRect:[self bounds]];\n'
     '            [NSGraphicsContext restoreGraphicsState];\n'
     '        }\n'
     '        CGContextRestoreGState(context);\n'),

    # 2. The button, and the note it adds.
    ("SKPDFView.h",
     '- (void)addAnnotationWithType:(SKNoteType)annotationType;\n',
     '- (void)addAnnotationWithType:(SKNoteType)annotationType;\n'
     '- (BOOL)addSignatureNoteWithImage:(NSImage *)image;\n'),
    ("SKPDFView.m",
     '\n- (void)addAnnotationWithType:(SKNoteType)annotationType {\n',
     '\n'
     '// The note of the Signature toolbar button: the image note a pasted or dropped\n'
     '// image makes (built twice upstream, in -pasteNote:plainText: and\n'
     '// -performDragOperation:, which the fork leaves alone), in the middle of what is\n'
     '// visible, selected. A signature image rarely carries a useful resolution, so it\n'
     '// gets a fixed width rather than its natural size. NO when it beeped instead.\n'
     '#define SKSignatureNoteWidth 150.0\n'
     '\n'
     '- (BOOL)addSignatureNoteWithImage:(NSImage *)image {\n'
     '    NSSize size = [image size];\n'
     '    if ([self canAddNotes] == NO || size.width <= 0.0 || size.height <= 0.0) {\n'
     '        NSBeep();\n'
     '        return NO;\n'
     '    }\n'
     '    NSPoint center = SKCenterPoint([self unobscuredContentRect]);\n'
     '    PDFPage *page = [self pageForPoint:center nearest:YES];\n'
     '    center = [self convertPoint:center toPage:page];\n'
     '    NSRect bounds = SKRectFromCenterAndSize(center, NSMakeSize(SKSignatureNoteWidth, SKSignatureNoteWidth * size.height / size.width));\n'
     '    bounds.origin = SKIntegralPoint(bounds.origin);\n'
     '    bounds = SKConstrainRect(bounds, [page boundsForBox:[self displayBox]]);\n'
     '    PDFAnnotation *newAnnotation = [PDFAnnotation newSkimNoteWithBounds:bounds forType:SKNNoteString];\n'
     '    [(SKNPDFAnnotationNote *)newAnnotation setImage:image];\n'
     '    [(SKNPDFAnnotationNote *)newAnnotation setExtendedIconType:kSKNPDFTextAnnotationIconImage];\n'
     '    if (IS_TEXT_OR_NOTE_TOOL == NO)\n'
     '        [self setToolMode:SKToolModeText];\n'
     '    [self addAnnotation:newAnnotation toPage:page select:YES];\n'
     '    [[self window] makeFirstResponder:self];\n'
     '    return YES;\n'
     '}\n'
     '\n'
     '- (void)addAnnotationWithType:(SKNoteType)annotationType {\n'),
    ("SKMainToolbarController.m",
     '#define SKDocumentToolbarPrintItemIdentifier @"SKDocumentToolbarPrintItemIdentifier"\n',
     '#define SKDocumentToolbarPrintItemIdentifier @"SKDocumentToolbarPrintItemIdentifier"\n'
     '#define SKDocumentToolbarSignatureItemIdentifier @"SKDocumentToolbarSignatureItemIdentifier"\n'
     '#define SKDocumentToolbarFileItemIdentifier @"SKDocumentToolbarFileItemIdentifier"\n'
     '\n'
     '#define SKSignatureImageKey @"SKSignatureImage"\n'),
    ("SKMainToolbarController.m",
     '            [item setView:printButton];\n'
     '            [item setMenuFormRepresentation:menuItem];\n'
     '            \n'
     '        }\n',
     '            [item setView:printButton];\n'
     '            [item setMenuFormRepresentation:menuItem];\n'
     '            \n'
     '        } else if ([identifier isEqualToString:SKDocumentToolbarSignatureItemIdentifier]) {\n'
     '            \n'
     '            menuItem = [[NSMenuItem alloc] initWithTitle:NSLocalizedString(@"Signature", @"Menu item title") action:@selector(addSignature:) target:self];\n'
     '            \n'
     '            [item setLabels:NSLocalizedString(@"Signature", @"Toolbar item label")];\n'
     '            [item setToolTip:NSLocalizedString(@"Add Signature (Option-click to choose its image)", @"Tool tip message")];\n'
     '            [item setView:[self makeButtonOfClass:[NSSegmentedControl class] symbolName:@"signature" label:NSLocalizedString(@"Signature", @"Toolbar item label") action:@selector(addSignature:)]];\n'
     '            [item setMenuFormRepresentation:menuItem];\n'
     '            \n'
     '        } else if ([identifier isEqualToString:SKDocumentToolbarFileItemIdentifier]) {\n'
     '            \n'
     '            SKFileDragButton *button = (SKFileDragButton *)[self makeButtonOfClass:[SKFileDragButton class] symbolName:@"doc" label:NSLocalizedString(@"File", @"Toolbar item label") action:NULL];\n'
     '            [button setMainController:mainController];\n'
     '            \n'
     '            [item setLabels:NSLocalizedString(@"File", @"Toolbar item label")];\n'
     '            [item setToolTip:NSLocalizedString(@"Drag the file into another app (unsaved changes are saved first)", @"Tool tip message")];\n'
     '            [item setView:button];\n'
     '            \n'
     '        }\n'),
    ("SKMainToolbarController.m",
     '\n- (NSToolbarItem *)toolbar:(NSToolbar *)toolbar itemForItemIdentifier:(NSString *)itemIdent willBeInsertedIntoToolbar:(BOOL)willBeInserted {\n',
     '\n'
     '// Upstream\'s buttons come from MainToolbar.xib; the fork\'s are built here, in the\n'
     '// style of the Print button, so the fork leaves the nib alone.\n'
     '- (NSSegmentedControl *)makeButtonOfClass:(Class)buttonClass symbolName:(NSString *)symbolName label:(NSString *)label action:(SEL)action {\n'
     '    NSImage *image = nil;\n'
     '    if (@available(macOS 11.0, *))\n'
     '        image = [NSImage imageWithSystemSymbolName:symbolName accessibilityDescription:label];\n'
     '    NSSegmentedControl *button = image ? [buttonClass segmentedControlWithImages:@[image] trackingMode:NSSegmentSwitchTrackingMomentary target:self action:action] : [buttonClass segmentedControlWithLabels:@[label] trackingMode:NSSegmentSwitchTrackingMomentary target:self action:action];\n'
     '    [button setSegmentStyle:NSSegmentStyleTexturedSquare];\n'
     '    if (image)\n'
     '        [button setWidth:27.0 forSegment:0];\n'
     '    return button;\n'
     '}\n'
     '\n'
     '// the note, and the mark that sends the next Save to "<name>-signed"\n'
     '- (void)addSignatureImage:(NSImage *)image {\n'
     '    if ([mainController.pdfView addSignatureNoteWithImage:image])\n'
     '        [(SKMainDocument *)[mainController document] didAddSignature];\n'
     '}\n'
     '\n'
     '// Adds the signature image the preferences keep. It asks for one the first time,\n'
     '// and on Option-click. The preference holds the image itself, not a path: a\n'
     '// file read on every click of an image in ~/Documents made macOS stop the app\n'
     '// for a Documents-folder permission (2026-11-23); a file picked in the open\n'
     '// panel is readable without one.\n'
     '- (IBAction)addSignature:(id)sender {\n'
     '    NSData *data = [[NSUserDefaults standardUserDefaults] dataForKey:SKSignatureImageKey];\n'
     '    NSImage *image = nil;\n'
     '    if (data && ([NSEvent modifierFlags] & NSEventModifierFlagOption) == 0)\n'
     '        image = [[NSImage alloc] initWithData:data];\n'
     '    if (image) {\n'
     '        [self addSignatureImage:image];\n'
     '        return;\n'
     '    }\n'
     '    NSOpenPanel *openPanel = [NSOpenPanel openPanel];\n'
     '#pragma clang diagnostic push\n'
     '#pragma clang diagnostic ignored "-Wdeprecated-declarations"\n'
     '    [openPanel setAllowedFileTypes:[NSImage imageTypes]];\n'
     '#pragma clang diagnostic pop\n'
     '    [openPanel setMessage:NSLocalizedString(@"Choose the image of your signature. Skim remembers it; Option-click the Signature button to change it.", @"Open panel message")];\n'
     '    [openPanel beginSheetModalForWindow:[mainController window] completionHandler:^(NSModalResponse result){\n'
     '        if (result != NSModalResponseOK)\n'
     '            return;\n'
     '        NSData *chosenData = [NSData dataWithContentsOfURL:[openPanel URL]];\n'
     '        NSImage *chosen = chosenData ? [[NSImage alloc] initWithData:chosenData] : nil;\n'
     '        if (chosen == nil) {\n'
     '            NSBeep();\n'
     '            return;\n'
     '        }\n'
     '        [[NSUserDefaults standardUserDefaults] setObject:chosenData forKey:SKSignatureImageKey];\n'
     '        [self addSignatureImage:chosen];\n'
     '    }];\n'
     '}\n'
     '\n'
     '- (NSToolbarItem *)toolbar:(NSToolbar *)toolbar itemForItemIdentifier:(NSString *)itemIdent willBeInsertedIntoToolbar:(BOOL)willBeInserted {\n'),
    ("SKMainToolbarController.m",
     '        SKDocumentToolbarNewNoteItemIdentifier];\n}\n\n',
     '        SKDocumentToolbarNewNoteItemIdentifier,\n'
     '        SKDocumentToolbarSignatureItemIdentifier,\n'
     '        SKDocumentToolbarFileItemIdentifier];\n}\n\n'),
    ("SKMainToolbarController.m",
     '        SKDocumentToolbarPrintItemIdentifier,\n        NSToolbarFlexibleSpaceItemIdentifier,\n',
     '        SKDocumentToolbarPrintItemIdentifier,\n'
     '        SKDocumentToolbarSignatureItemIdentifier,\n'
     '        SKDocumentToolbarFileItemIdentifier,\n'
     '        NSToolbarFlexibleSpaceItemIdentifier,\n'),
    ("SKMainToolbarController.m",
     '    } else if ([identifier isEqualToString:NSToolbarPrintItemIdentifier]) {\n',
     '    } else if ([identifier isEqualToString:SKDocumentToolbarSignatureItemIdentifier]) {\n'
     '        return [mainController hasOverview] == NO && [mainController.pdfView canAddNotes];\n'
     '    } else if ([identifier isEqualToString:SKDocumentToolbarFileItemIdentifier]) {\n'
     '        return [[mainController document] fileURL] != nil;\n'
     '    } else if ([identifier isEqualToString:NSToolbarPrintItemIdentifier]) {\n'),

    # 5. The signed copy and the File button (2026-11-24): to send a signed document
    # on, its file had to be found on disk, in the folder of the app it came from
    # (WhatsApp keeps it in its container's tmp). The File button is the file, to
    # drag into the other app; the first Save after the Signature button writes it
    # to Downloads, as "<name>-signed" (NSURL's signedFileURLInFolder:,
    # tools/signednamecheck.sh), and leaves the original as it came.
    ("SKMainToolbarController.m",
     '#import "SKApplicationController.h"\n',
     '#import "SKApplicationController.h"\n'
     '#import "SKMainDocument.h"\n'),
    ("SKMainToolbarController.m", '\n@interface SKMainToolbarController ()\n', FILE_DRAG_BUTTON),
    ("SKMainDocument.h",
     '- (IBAction)convertNotes:(nullable id)sender;\n',
     '- (IBAction)convertNotes:(nullable id)sender;\n'
     '\n'
     '// skim-dark: the Signature button added a signature. The next Save, while an image\n'
     '// note is still there, keeps the file as it came and writes the signed document\n'
     '// to Downloads as "<name>-signed", where the document then lives.\n'
     '- (void)didAddSignature;\n'),
    ("SKMainDocument.m", '// Prepare for saving and use callback to save notes and cleanup\n', SIGNED_SAVE),
    ("NSURL_SKExtensions.h",
     '@property (nonatomic, readonly) NSURL *uniqueFileURL;\n',
     '@property (nonatomic, readonly) NSURL *uniqueFileURL;\n'
     '// skim-dark: where a document signed with the Signature button is saved, in the\n'
     '// folder given: "<name>-signed.<extension>", or the name as it is when it already\n'
     '// ends in -signed (or -signed-2), made unique like uniqueFileURL; nil when that is\n'
     '// this file itself, which then saves in place.\n'
     '- (nullable NSURL *)signedFileURLInFolder:(NSURL *)folderURL;\n'),
    ("NSURL_SKExtensions.m", '- (BOOL)isTrashedFileURL {\n', SIGNED_FILE_URL),

    # 3. Save writes the image notes into the PDF. A Skim note lives in the file's
    # extended attributes, which no other reader sees: a signature saved that way
    # looks signed in Skim and nowhere else. Only when the document itself is
    # saved (Save, Save As); exports keep their meaning. Afterwards the document
    # reloads, so the page shows them as part of the file and the notes list
    # drops them; File > Convert Notes turns them back into notes.
    ("SKMainDocument.h",
     '        unsigned int recentInfoNeedsUpdate:1;\n    } mdFlags;\n',
     '        unsigned int recentInfoNeedsUpdate:1;\n'
     '        unsigned int savingDocument:1;\n'
     '        unsigned int embeddedImageNotes:1;\n'
     '        unsigned int savesSignedCopy:1;\n'
     '    } mdFlags;\n'),
    ("SKMainDocument.m",
     '\n- (NSArray *)SkimNoteProperties {\n',
     '\n'
     '// a note that draws an image on the page (skim-dark: Save writes these into the PDF)\n'
     'static BOOL SKIsImageNoteProperties(NSDictionary *dict) {\n'
     '    return [[dict objectForKey:SKNPDFAnnotationTypeKey] isEqualToString:SKNNoteString] &&\n'
     '           [[dict objectForKey:SKNPDFAnnotationDrawsImageKey] boolValue] &&\n'
     '           [dict objectForKey:SKNPDFAnnotationImageKey] != nil;\n'
     '}\n'
     '\n'
     '- (NSArray *)SkimNoteProperties {\n'),
    ("SKMainDocument.m",
     '        array = mutableArray;\n    }\n    return  array;\n}\n',
     '        array = mutableArray;\n'
     '    }\n'
     '    // during a save that wrote them into the PDF, the image notes are not notes anymore\n'
     '    if (mdFlags.embeddedImageNotes)\n'
     '        array = [array filteredArrayUsingPredicate:[NSPredicate predicateWithBlock:^BOOL(id dict, NSDictionary *bindings){ return SKIsImageNoteProperties(dict) == NO; }]];\n'
     '    return  array;\n'
     '}\n'
     '\n'
     '// the image notes, the ones Save writes into the PDF\n'
     '- (NSArray *)imageNoteProperties {\n'
     '    return [[self SkimNoteProperties] filteredArrayUsingPredicate:[NSPredicate predicateWithBlock:^BOOL(id dict, NSDictionary *bindings){ return SKIsImageNoteProperties(dict); }]];\n'
     '}\n'
     '\n'
     '// The PDF data with the image notes written into it, as Stamp annotations that\n'
     '// carry their own appearance; nil when there is none, or when the PDF does not\n'
     '// allow notes. Added the way Skim adds notes when it opens a file.\n'
     '- (NSData *)PDFDataWithImageNotes {\n'
     '    NSArray *imageNotes = [self imageNoteProperties];\n'
     '    if ([imageNotes count] == 0)\n'
     '        return nil;\n'
     '    PDFDocument *pdfDoc = [[PDFDocument alloc] initWithData:pdfData];\n'
     '    if (pdfDoc == nil || [pdfDoc isLocked] || [pdfDoc allowsNotes] == NO)\n'
     '        return nil;\n'
     '    [pdfDoc addSkimNotesWithProperties:imageNotes];\n'
     '    return [pdfDoc dataRepresentation];\n'
     '}\n'),
    ("SKMainDocument.m",
     '    } else if ([ws type:SKDocumentTypePDF conformsToType:typeName]) {\n'
     '        if (mdFlags.exportOption == SKExportOptionWithEmbeddedNotes)\n'
     '            didWrite = [[self pdfDocument] writeToURL:absoluteURL];\n'
     '        else\n',
     '    } else if ([ws type:SKDocumentTypePDF conformsToType:typeName]) {\n'
     '        NSData *dataWithImageNotes = mdFlags.savingDocument ? [self PDFDataWithImageNotes] : nil;\n'
     '        if (mdFlags.exportOption == SKExportOptionWithEmbeddedNotes) {\n'
     '            didWrite = [[self pdfDocument] writeToURL:absoluteURL];\n'
     '        } else if (dataWithImageNotes) {\n'
     '            didWrite = [dataWithImageNotes writeToURL:absoluteURL options:0 error:&error];\n'
     '            mdFlags.embeddedImageNotes = didWrite;\n'
     '        } else\n'),
    ("SKMainDocument.m",
     '    \n    BOOL didSave = [super writeSafelyToURL:absoluteURL ofType:typeName forSaveOperation:saveOperation error:outError];\n',
     '    \n'
     '    // saving the document itself writes its image notes into the PDF\n'
     '    mdFlags.embeddedImageNotes = 0;\n'
     '    mdFlags.savingDocument = attachNotes && (saveOperation == NSSaveOperation || saveOperation == NSSaveAsOperation);\n'
     '    BOOL didSave = [super writeSafelyToURL:absoluteURL ofType:typeName forSaveOperation:saveOperation error:outError];\n'
     '    mdFlags.savingDocument = 0;\n'),
    ("SKMainDocument.m",
     '        // reset this for the next save, in case this was set in the save script command\n'
     '        mdFlags.exportOption = SKExportOptionDefault;\n'
     '        \n',
     '        // reset this for the next save, in case this was set in the save script command\n'
     '        mdFlags.exportOption = SKExportOptionDefault;\n'
     '        \n'
     '        // the image notes are in the PDF now: reload it, so the page shows them as\n'
     '        // part of the file and the notes list drops them\n'
     '        if (mdFlags.embeddedImageNotes) {\n'
     '            mdFlags.embeddedImageNotes = 0;\n'
     '            NSError *revertError = nil;\n'
     '            if (errorOrNil == nil && [self revertToContentsOfURL:[self fileURL] ofType:[self fileType] error:&revertError] == NO && revertError)\n'
     '                [self presentError:revertError];\n'
     '        }\n'
     '        \n'
     '        // a Save or Save As that went through ends the one to a signed copy\n'
     '        if (errorOrNil == nil && (saveOperation == NSSaveOperation || saveOperation == NSSaveAsOperation))\n'
     '            mdFlags.savesSignedCopy = 0;\n'
     '        \n'),

    # 4. Notes drawn at the screen's resolution. PDFKit (macOS 27) draws each
    # annotation in a layer of its own, a PDFPageLayerAnnotationEffect, at one pixel
    # per point, and magnifies that bitmap with the page: at 170% on a Retina screen
    # a note is 3.4 times too coarse, pixelated and washed out, while the page text,
    # in tiles at the screen's resolution (scale 3.4), stays sharp. Measured on a
    # plain PDFView, so not Skim's doing (2026-11-23). Before the layer draws it gets
    # the scale it is shown at; a zoom redraws the layers. Same pattern as Skim's
    # other PDFKit replacements, and a no-op when the private class is gone.
    ("PDFDocumentView_SKExtensions.h",
     'extern void SKSwizzlePDFAccessibilityNodeAnnotationMethods();\n',
     'extern void SKSwizzlePDFAccessibilityNodeAnnotationMethods();\n'
     'extern void SKSwizzlePDFPageLayerAnnotationEffectMethods(void);\n'
     'extern void SKRedisplayPDFPageLayerAnnotationEffects(CALayer * _Nullable layer);\n'),
    ("PDFDocumentView_SKExtensions.m",
     '    original_annotation_accessibilityPerformShowMenu = (BOOL (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFAccessibilityNodeAnnotationClass, @selector(accessibilityPerformShowMenu), (IMP)replacement_annotation_accessibilityPerformShowMenu);\n'
     '}\n',
     '    original_annotation_accessibilityPerformShowMenu = (BOOL (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFAccessibilityNodeAnnotationClass, @selector(accessibilityPerformShowMenu), (IMP)replacement_annotation_accessibilityPerformShowMenu);\n'
     '}\n'
     '\n'
     '#pragma mark SKSwizzlePDFPageLayerAnnotationEffectMethods\n'
     '\n'
     '// PDFKit (macOS 27) draws each annotation in a layer of its own, a\n'
     '// PDFPageLayerAnnotationEffect, at one pixel per point of the page, and magnifies\n'
     '// that bitmap with the page: at 170% on a Retina screen a note comes out 3.4 times\n'
     '// too coarse, while the page text, drawn in tiles at the screen\'s resolution, stays\n'
     '// sharp. Before such a layer draws, it gets the scale it is shown at, capped so a\n'
     '// page-sized note at a high zoom stays a sane bitmap.\n'
     '#define SKMaxAnnotationEffectPixels (8.0 * 1024.0 * 1024.0)\n'
     '\n'
     'static Class PDFPageLayerAnnotationEffectClass = Nil;\n'
     'static void (*original_annotationEffect_display)(id, SEL) = NULL;\n'
     '\n'
     'static void replacement_annotationEffect_display(id self, SEL _cmd) {\n'
     '    CALayer *layer = self, *root = self, *viewLayer = nil;\n'
     '    for (CALayer *ancestor = [layer superlayer]; ancestor; ancestor = [ancestor superlayer]) {\n'
     '        if (viewLayer == nil && [[ancestor delegate] isKindOfClass:[NSView class]])\n'
     '            viewLayer = ancestor;\n'
     '        root = ancestor;\n'
     '    }\n'
     '    CGSize size = [layer bounds].size;\n'
     '    if (viewLayer && size.width > 0.0 && size.height > 0.0) {\n'
     '        CGRect shown = [layer convertRect:[layer bounds] toLayer:root];\n'
     '        CGFloat scale = sqrt((CGRectGetWidth(shown) * CGRectGetHeight(shown)) / (size.width * size.height)) * [viewLayer contentsScale];\n'
     '        scale = fmax(1.0, fmin(scale, sqrt(SKMaxAnnotationEffectPixels / (size.width * size.height))));\n'
     '        if (fabs(scale - [layer contentsScale]) > 0.01)\n'
     '            [layer setContentsScale:scale];\n'
     '    }\n'
     '    original_annotationEffect_display(self, _cmd);\n'
     '}\n'
     '\n'
     'void SKSwizzlePDFPageLayerAnnotationEffectMethods(void) {\n'
     '    PDFPageLayerAnnotationEffectClass = NSClassFromString(@"PDFPageLayerAnnotationEffect");\n'
     '    if (PDFPageLayerAnnotationEffectClass && [PDFPageLayerAnnotationEffectClass isSubclassOfClass:[CALayer class]])\n'
     '        original_annotationEffect_display = (void (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFPageLayerAnnotationEffectClass, @selector(display), (IMP)replacement_annotationEffect_display);\n'
     '}\n'
     '\n'
     '// a zoom only transforms the layers, so they draw again to pick up the new scale\n'
     'void SKRedisplayPDFPageLayerAnnotationEffects(CALayer *layer) {\n'
     '    if (original_annotationEffect_display == NULL || layer == nil)\n'
     '        return;\n'
     '    if ([layer isKindOfClass:PDFPageLayerAnnotationEffectClass])\n'
     '        [layer setNeedsDisplay];\n'
     '    for (CALayer *sublayer in [[layer sublayers] copy])\n'
     '        SKRedisplayPDFPageLayerAnnotationEffects(sublayer);\n'
     '}\n'),
    ("SKPDFView.m",
     '    SKSwizzlePDFAccessibilityNodeAnnotationMethods();\n}\n',
     '    SKSwizzlePDFAccessibilityNodeAnnotationMethods();\n'
     '    SKSwizzlePDFPageLayerAnnotationEffectMethods();\n'
     '}\n'),
    ("SKPDFView.m",
     '- (void)handleScaleChangedNotification:(NSNotification *)notification {\n'
     '    [self resetPDFToolTipRects];\n'
     '    [self updatePacer];\n'
     '    if (editor)\n'
     '        [self textNoteEditorSetFrame:editor];\n'
     '}\n',
     '- (void)handleScaleChangedNotification:(NSNotification *)notification {\n'
     '    [self resetPDFToolTipRects];\n'
     '    [self updatePacer];\n'
     '    if (editor)\n'
     '        [self textNoteEditorSetFrame:editor];\n'
     '    SKRedisplayPDFPageLayerAnnotationEffects([self layer]);\n'
     '}\n'),
]

# Two phases on purpose. An anchor that upstream rewrote makes the whole run
# abort, and aborting mid-write would leave src/ half patched — which is exactly
# what happened on the 16409 rebase, where the trunk had moved under three of the
# anchors. Nothing reaches disk until every edit has resolved.
buffers = {}
changed = skipped = 0
for name, old, new in EDITS:
    body = buffers.get(name)
    if body is None:
        body = buffers[name] = (SRC / name).read_text()
    if new in body:
        skipped += 1
        continue
    if body.count(old) != 1:
        sys.exit(f"ABORT: {name}: expected exactly 1 match, found {body.count(old)} "
                 f"(nada foi escrito; `svn up` mexeu na ancora?)")
    buffers[name] = body.replace(old, new)
    changed += 1

for name, body in buffers.items():
    path = SRC / name
    if body != path.read_text():
        path.write_text(body)

print(f"patch aplicado: {changed} edicao(oes), {skipped} ja presente(s)")
