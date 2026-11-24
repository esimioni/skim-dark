// signednamecheck — where does a signed document go?
//
// Checks NSURL's signedFileURLInFolder: (src/NSURL_SKExtensions.m, compiled in by
// tools/signednamecheck.sh). The first Save after the Signature button writes the
// document to Downloads as "<name>-signed.<extension>" (the name as it is when it
// already says signed), made unique with -1, -2 when taken; nil, a save in place,
// when that is the file itself. Here a scratch folder stands in for Downloads and
// another for the folder a PDF was opened from (WhatsApp's container). Exit 0 = PASS.
#import <Cocoa/Cocoa.h>
#import "NSURL_SKExtensions.h"

static int failures = 0;

static void expect(NSString *what, NSString *got, NSString *want) {
    BOOL ok = got == want || [got isEqualToString:want];
    printf("%s  %s: %s", ok ? "ok  " : "FAIL", [what UTF8String], got ? [got UTF8String] : "nil");
    if (ok == NO)
        printf("  (want %s)", want ? [want UTF8String] : "nil");
    printf("\n");
    failures += ok ? 0 : 1;
}

static NSString *resolved(NSString *path) {
    return [[[NSURL fileURLWithPath:path] URLByResolvingSymlinksInPath] path];
}

// the signed name of a file of the folder `from`, or a marker when it does not land in `downloads`
static NSString *signedName(NSString *from, NSString *name, NSString *downloads) {
    NSURL *url = [NSURL fileURLWithPath:[from stringByAppendingPathComponent:name] isDirectory:NO];
    NSURL *signedURL = [url signedFileURLInFolder:[NSURL fileURLWithPath:downloads isDirectory:YES]];
    if (signedURL && [resolved([[signedURL URLByDeletingLastPathComponent] path]) isEqualToString:resolved(downloads)] == NO)
        return [@"another folder: " stringByAppendingString:[signedURL path]];
    return [signedURL lastPathComponent];
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc < 2) {
            fprintf(stderr, "usage: signednamecheck <empty folder>\n");
            return 2;
        }
        // absolute, or every answer would look like it landed in another folder
        NSString *root = [[[NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]] isDirectory:YES] URLByStandardizingPath] path];
        NSString *whatsapp = [root stringByAppendingPathComponent:@"whatsapp"];
        NSString *downloads = [root stringByAppendingPathComponent:@"Downloads"];
        NSFileManager *fm = [NSFileManager defaultManager];
        [fm createDirectoryAtPath:whatsapp withIntermediateDirectories:YES attributes:nil error:NULL];
        [fm createDirectoryAtPath:downloads withIntermediateDirectories:YES attributes:nil error:NULL];
        void (^touch)(NSString *, NSString *) = ^(NSString *folder, NSString *name){
            [fm createFileAtPath:[folder stringByAppendingPathComponent:name] contents:[NSData data] attributes:nil];
        };
        NSString *received = @"Minute declaring dividend1.pdf";
        touch(whatsapp, received);

        expect(@"to Downloads, -signed", signedName(whatsapp, received, downloads), @"Minute declaring dividend1-signed.pdf");
        touch(downloads, @"Minute declaring dividend1-signed.pdf");
        expect(@"name taken in Downloads", signedName(whatsapp, received, downloads), @"Minute declaring dividend1-signed-1.pdf");
        touch(downloads, @"Minute declaring dividend1-signed-1.pdf");
        expect(@"two names taken", signedName(whatsapp, received, downloads), @"Minute declaring dividend1-signed-2.pdf");

        expect(@"signed, already in Downloads: in place", signedName(downloads, @"Minute declaring dividend1-signed.pdf", downloads), nil);
        expect(@"signed and numbered, in Downloads: in place", signedName(downloads, @"Minute declaring dividend1-signed-1.pdf", downloads), nil);
        expect(@"signed elsewhere: to Downloads, name kept", signedName(whatsapp, @"Contract-SIGNED.pdf", downloads), @"Contract-SIGNED.pdf");
        expect(@"in Downloads, not signed yet", signedName(downloads, @"Report.pdf", downloads), @"Report-signed.pdf");
        expect(@"a name that only contains -signed", signedName(whatsapp, @"Form-signedness.pdf", downloads), @"Form-signedness-signed.pdf");
        expect(@"no extension", signedName(whatsapp, @"contract", downloads), @"contract-signed");
        expect(@"dots in the name", signedName(whatsapp, @"v1.2 terms.pdf", downloads), @"v1.2 terms-signed.pdf");
    }
    printf("%s\n", failures ? "FAIL" : "PASS");
    return failures ? 1 : 0;
}