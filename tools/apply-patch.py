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
