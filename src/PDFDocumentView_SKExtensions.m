//
//  PDFDocumentView_SKExtensions.m
//  Skim
//
//  Created by Christiaan Hofman on 4/22/08.
/*
 This software is Copyright (c) 2008
 Christiaan Hofman. All rights reserved.

 Redistribution and use in source and binary forms, with or without
 modification, are permitted provided that the following conditions
 are met:

 - Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

 - Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in
    the documentation and/or other materials provided with the
    distribution.

 - Neither the name of Christiaan Hofman nor the names of any
    contributors may be used to endorse or promote products derived
    from this software without specific prior written permission.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#import "PDFDocumentView_SKExtensions.h"
#import <Quartz/Quartz.h>
#import "SKRuntime.h"
#import <SkimNotes/SkimNotes.h>

@interface NSView (SKPDFDisplayViewPrivateDeclarations)
- (id)pdfView;
@end

@interface NSObject (SKPDFAccessibilityNodeAnnotationPrivateDeclarations)
- (PDFAnnotation *)annotation;
@end

#pragma mark -

static id enclosingPDFView(id self) {
    if (self == nil)
        return nil;
    else if ([self isKindOfClass:[PDFView class]])
        return self;
    else
        return enclosingPDFView([self superview]);
}

static id get_pdfView(id self) {
    if ([self respondsToSelector:@selector(pdfView)])
        return [self pdfView];
    else
        return enclosingPDFView(self);
}

static id (*original_menuForEvent)(id, SEL, id) = NULL;

static BOOL (*original_accessibilityPerformShowAlternateUI)(id, SEL) = NULL;
static BOOL (*original_accessibilityPerformShowDefaultUI)(id, SEL) = NULL;
static BOOL (*original_accessibilityPerformShowMenu)(id, SEL) = NULL;
static BOOL (*original_annotation_accessibilityPerformPress)(id, SEL) = NULL;
static BOOL (*original_annotation_accessibilityPerformPick)(id, SEL) = NULL;
static BOOL (*original_annotation_accessibilityPerformShowMenu)(id, SEL) = NULL;

#pragma mark PDFPageView fix

// On Sierra and later menuForEvent: is forwarded to the PDFView of the PDFPage rather than the actual PDFView,
static NSMenu *replacement_menuForEvent(id self, SEL _cmd, NSEvent *event) {
    id pdfView = enclosingPDFView(self);
    if (pdfView)
        return [pdfView menuForEvent:event];
    else
        return original_menuForEvent(self, _cmd, event);
}

#pragma mark Enhanced accessibility support

static BOOL replacement_accessibilityPerformShowAlternateUI(id self, SEL _cmd) {
    id pdfView = get_pdfView(self);
    if ([pdfView respondsToSelector:_cmd])
        return [pdfView accessibilityPerformShowAlternateUI];
    else
        return original_accessibilityPerformShowAlternateUI(self, _cmd);
}

static BOOL replacement_accessibilityPerformShowDefaultUI(id self, SEL _cmd) {
    id pdfView = get_pdfView(self);
    if ([pdfView respondsToSelector:_cmd])
        return [pdfView accessibilityPerformShowDefaultUI];
    else
        return original_accessibilityPerformShowDefaultUI(self, _cmd);
}

static BOOL replacement_accessibilityPerformShowMenu(id self, SEL _cmd) {
    id pdfView = get_pdfView(self);
    if ([pdfView respondsToSelector:_cmd])
        return [pdfView accessibilityPerformShowMenu];
    else
        return original_accessibilityPerformShowMenu(self, _cmd);
}

static BOOL replacement_annotation_accessibilityPerformPress(id self, SEL _cmd) {
    id annotation = [self annotation];
    if ([annotation respondsToSelector:@selector(isSkimNote)] && [annotation isSkimNote] && [annotation respondsToSelector:_cmd])
        return [annotation accessibilityPerformPress];
    return original_annotation_accessibilityPerformPress(self, _cmd);
}

static BOOL replacement_annotation_accessibilityPerformPick(id self, SEL _cmd) {
    id annotation = [self annotation];
    if ([annotation respondsToSelector:@selector(isSkimNote)] && [annotation isSkimNote] && [annotation respondsToSelector:_cmd])
        return [annotation accessibilityPerformPick];
    return original_annotation_accessibilityPerformPick(self, _cmd);
}

static BOOL replacement_annotation_accessibilityPerformShowMenu(id self, SEL _cmd) {
    id annotation = [self annotation];
    if ([annotation respondsToSelector:@selector(isSkimNote)] && [annotation isSkimNote] && [annotation respondsToSelector:_cmd])
        return [annotation accessibilityPerformShowMenu];
    return original_annotation_accessibilityPerformShowMenu(self, _cmd);
}

#pragma mark SKSwizzlePDFDocumentViewMethods

void SKSwizzlePDFDocumentViewMethods() {
    Class PDFDocumentViewClass = NSClassFromString(@"PDFDocumentView");
    if (PDFDocumentViewClass == Nil)
        return;

    original_accessibilityPerformShowAlternateUI = (BOOL (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFDocumentViewClass, @selector(accessibilityPerformShowAlternateUI), (IMP)replacement_accessibilityPerformShowAlternateUI);
    original_accessibilityPerformShowDefaultUI = (BOOL (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFDocumentViewClass, @selector(accessibilityPerformShowDefaultUI), (IMP)replacement_accessibilityPerformShowDefaultUI);
    original_accessibilityPerformShowMenu = (BOOL (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFDocumentViewClass, @selector(accessibilityPerformShowMenu), (IMP)replacement_accessibilityPerformShowMenu);
}

void SKSwizzlePDFPageViewMethods() {
    Class PDFPageViewClass = NSClassFromString(@"PDFPageView");
    if (PDFPageViewClass)
        original_menuForEvent = (id (*)(id, SEL, id))SKReplaceInstanceMethodImplementation(PDFPageViewClass, @selector(menuForEvent:), (IMP)replacement_menuForEvent);
    
}

void SKSwizzlePDFAccessibilityNodeAnnotationMethods() {
    Class PDFAccessibilityNodeAnnotationClass = NSClassFromString(@"PDFAccessibilityNodeAnnotation");
    
    if (PDFAccessibilityNodeAnnotationClass == Nil || [PDFAccessibilityNodeAnnotationClass instancesRespondToSelector:@selector(annotation)] == NO)
        return;
    
    original_annotation_accessibilityPerformPress = (BOOL (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFAccessibilityNodeAnnotationClass, @selector(accessibilityPerformPress), (IMP)replacement_annotation_accessibilityPerformPress);
    original_annotation_accessibilityPerformPick = (BOOL (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFAccessibilityNodeAnnotationClass, @selector(accessibilityPerformPick), (IMP)replacement_annotation_accessibilityPerformPick);
    original_annotation_accessibilityPerformShowMenu = (BOOL (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFAccessibilityNodeAnnotationClass, @selector(accessibilityPerformShowMenu), (IMP)replacement_annotation_accessibilityPerformShowMenu);
}

#pragma mark SKSwizzlePDFPageLayerAnnotationEffectMethods

// PDFKit (macOS 27) draws each annotation in a layer of its own, a
// PDFPageLayerAnnotationEffect, at one pixel per point of the page, and magnifies
// that bitmap with the page: at 170% on a Retina screen a note comes out 3.4 times
// too coarse, while the page text, drawn in tiles at the screen's resolution, stays
// sharp. Before such a layer draws, it gets the scale it is shown at, capped so a
// page-sized note at a high zoom stays a sane bitmap.
#define SKMaxAnnotationEffectPixels (8.0 * 1024.0 * 1024.0)

static Class PDFPageLayerAnnotationEffectClass = Nil;
static void (*original_annotationEffect_display)(id, SEL) = NULL;

static void replacement_annotationEffect_display(id self, SEL _cmd) {
    CALayer *layer = self, *root = self, *viewLayer = nil;
    for (CALayer *ancestor = [layer superlayer]; ancestor; ancestor = [ancestor superlayer]) {
        if (viewLayer == nil && [[ancestor delegate] isKindOfClass:[NSView class]])
            viewLayer = ancestor;
        root = ancestor;
    }
    CGSize size = [layer bounds].size;
    if (viewLayer && size.width > 0.0 && size.height > 0.0) {
        CGRect shown = [layer convertRect:[layer bounds] toLayer:root];
        CGFloat scale = sqrt((CGRectGetWidth(shown) * CGRectGetHeight(shown)) / (size.width * size.height)) * [viewLayer contentsScale];
        scale = fmax(1.0, fmin(scale, sqrt(SKMaxAnnotationEffectPixels / (size.width * size.height))));
        if (fabs(scale - [layer contentsScale]) > 0.01)
            [layer setContentsScale:scale];
    }
    original_annotationEffect_display(self, _cmd);
}

void SKSwizzlePDFPageLayerAnnotationEffectMethods(void) {
    PDFPageLayerAnnotationEffectClass = NSClassFromString(@"PDFPageLayerAnnotationEffect");
    if (PDFPageLayerAnnotationEffectClass && [PDFPageLayerAnnotationEffectClass isSubclassOfClass:[CALayer class]])
        original_annotationEffect_display = (void (*)(id, SEL))SKReplaceInstanceMethodImplementation(PDFPageLayerAnnotationEffectClass, @selector(display), (IMP)replacement_annotationEffect_display);
}

// a zoom only transforms the layers, so they draw again to pick up the new scale
void SKRedisplayPDFPageLayerAnnotationEffects(CALayer *layer) {
    if (original_annotationEffect_display == NULL || layer == nil)
        return;
    if ([layer isKindOfClass:PDFPageLayerAnnotationEffectClass])
        [layer setNeedsDisplay];
    for (CALayer *sublayer in [[layer sublayers] copy])
        SKRedisplayPDFPageLayerAnnotationEffects(sublayer);
}
