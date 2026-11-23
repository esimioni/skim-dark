// imagenotecheck — does an image note survive in the PDF that PDFKit writes?
//
// Builds a one-page PDF, adds a SkimNotes image note (an anchored note that draws
// its image) and writes the document the way "PDF With Embedded Notes" and the
// fork's Save do. Then it opens the written file with CGPDF and looks at the
// note's normal appearance: it passes when that appearance draws an image
// XObject that is really there. Before the fix PDFKit wrote `/Fm1 Do` with empty
// resources, so other readers drew nothing (poppler: "XObject 'Fm1' is unknown").
//
// Run through tools/imagenotecheck.sh, which compiles it against a SkimNotes
// framework. Exit 0 = the image is in the file.
#import <Cocoa/Cocoa.h>
#import <Quartz/Quartz.h>
#import <SkimNotes/SkimNotes.h>

static NSImage *testImage(void) {
    // a blue stroke on a transparent background, like a signature
    NSBitmapImageRep *rep = [[NSBitmapImageRep alloc] initWithBitmapDataPlanes:NULL pixelsWide:300 pixelsHigh:140 bitsPerSample:8 samplesPerPixel:4 hasAlpha:YES isPlanar:NO colorSpaceName:NSCalibratedRGBColorSpace bytesPerRow:0 bitsPerPixel:0];
    [NSGraphicsContext saveGraphicsState];
    [NSGraphicsContext setCurrentContext:[NSGraphicsContext graphicsContextWithBitmapImageRep:rep]];
    [[NSColor colorWithCalibratedRed:0.1 green:0.15 blue:0.8 alpha:1.0] setFill];
    NSRectFill(NSMakeRect(20, 60, 260, 20));
    [NSGraphicsContext restoreGraphicsState];
    NSImage *image = [[NSImage alloc] initWithSize:NSMakeSize(150, 70)];
    [image addRepresentation:rep];
    return image;
}

static NSData *basePDF(void) {
    NSMutableData *data = [NSMutableData data];
    CGRect box = CGRectMake(0, 0, 595, 842);
    CGDataConsumerRef consumer = CGDataConsumerCreateWithCFData((__bridge CFMutableDataRef)data);
    CGContextRef ctx = CGPDFContextCreate(consumer, &box, NULL);
    CGPDFContextBeginPage(ctx, NULL);
    CGContextMoveToPoint(ctx, 150, 195);
    CGContextAddLineToPoint(ctx, 400, 195);
    CGContextStrokePath(ctx);
    CGPDFContextEndPage(ctx);
    CGPDFContextClose(ctx);
    CGContextRelease(ctx);
    CGDataConsumerRelease(consumer);
    return data;
}

// the image XObjects the normal appearance of the page's first annotation can draw
static NSUInteger imagesInAppearance(CGPDFDocumentRef doc) {
    CGPDFDictionaryRef page = CGPDFPageGetDictionary(CGPDFDocumentGetPage(doc, 1));
    CGPDFArrayRef annots = NULL;
    CGPDFDictionaryRef annot = NULL, ap = NULL, resources = NULL, xobjects = NULL;
    CGPDFStreamRef normal = NULL;
    if (CGPDFDictionaryGetArray(page, "Annots", &annots) == false || CGPDFArrayGetCount(annots) == 0 ||
        CGPDFArrayGetDictionary(annots, 0, &annot) == false) {
        printf("no annotation on the page\n");
        return 0;
    }
    const char *subtype = NULL;
    CGPDFDictionaryGetName(annot, "Subtype", &subtype);
    printf("annotation /%s\n", subtype ?: "?");
    if (CGPDFDictionaryGetDictionary(annot, "AP", &ap) == false || CGPDFDictionaryGetStream(ap, "N", &normal) == false) {
        printf("no normal appearance\n");
        return 0;
    }
    CGPDFDictionaryRef normalDict = CGPDFStreamGetDictionary(normal);
    if (CGPDFDictionaryGetDictionary(normalDict, "Resources", &resources) == false ||
        CGPDFDictionaryGetDictionary(resources, "XObject", &xobjects) == false) {
        printf("appearance has no XObject resources\n");
        return 0;
    }
    __block NSUInteger images = 0;
    CGPDFDictionaryApplyBlock(xobjects, ^bool(const char *key, CGPDFObjectRef value, void *info) {
        CGPDFStreamRef stream = NULL;
        const char *kind = NULL;
        if (CGPDFObjectGetValue(value, kCGPDFObjectTypeStream, &stream) &&
            CGPDFDictionaryGetName(CGPDFStreamGetDictionary(stream), "Subtype", &kind)) {
            printf("appearance XObject /%s: /%s\n", key, kind);
            if (strcmp(kind, "Image") == 0)
                images++;
        }
        return true;
    }, NULL);
    return images;
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc < 2) {
            fprintf(stderr, "usage: imagenotecheck <output.pdf>\n");
            return 2;
        }
        NSURL *outURL = [NSURL fileURLWithPath:@(argv[1])];
        PDFDocument *document = [[PDFDocument alloc] initWithData:basePDF()];
        SKNPDFAnnotationNote *note = [[SKNPDFAnnotationNote alloc] initSkimNoteWithBounds:NSMakeRect(150, 190, 150, 70)];
        [note setImage:testImage()];
        [note setDrawsImage:YES];
        [[document pageAtIndex:0] addAnnotation:note];
        if ([document writeToURL:outURL] == NO) {
            printf("FAIL: PDFKit did not write %s\n", argv[1]);
            return 1;
        }
        CGPDFDocumentRef written = CGPDFDocumentCreateWithURL((__bridge CFURLRef)outURL);
        NSUInteger images = imagesInAppearance(written);
        CGPDFDocumentRelease(written);
        if (images == 0) {
            printf("FAIL: the image note was written without its image\n");
            return 1;
        }
        printf("PASS: the image note's appearance draws %lu image(s)\n", (unsigned long)images);
        return 0;
    }
}