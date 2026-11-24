// signednamecheck — where does a signed document go?
//
// Checks NSURL's signedFileURL (src/NSURL_SKExtensions.m, compiled in by
// tools/signednamecheck.sh): the first Save after the Signature button writes the
// document beside its file as "<name>-signed.<extension>", made unique with -1,
// -2 when that name is taken, and saves in place (nil) when the name already
// says it is signed. Run in an empty scratch folder. Exit 0 = PASS.
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

// the signed name of a file in the folder, or a marker when it lands in another folder
static NSString *signedName(NSString *folder, NSString *name) {
    NSURL *url = [NSURL fileURLWithPath:[folder stringByAppendingPathComponent:name] isDirectory:NO];
    NSURL *signedURL = [url signedFileURL];
    if (signedURL && [[[signedURL URLByDeletingLastPathComponent] path] isEqualToString:folder] == NO)
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
        NSString *folder = [[[NSURL fileURLWithPath:[NSString stringWithUTF8String:argv[1]] isDirectory:YES] URLByStandardizingPath] path];
        void (^touch)(NSString *) = ^(NSString *name){
            [[NSFileManager defaultManager] createFileAtPath:[folder stringByAppendingPathComponent:name] contents:[NSData data] attributes:nil];
        };
        NSString *received = @"Minute declaring dividend1.pdf";
        touch(received);

        expect(@"beside the file", signedName(folder, received), @"Minute declaring dividend1-signed.pdf");
        touch(@"Minute declaring dividend1-signed.pdf");
        expect(@"name taken", signedName(folder, received), @"Minute declaring dividend1-signed-1.pdf");
        touch(@"Minute declaring dividend1-signed-1.pdf");
        expect(@"two names taken", signedName(folder, received), @"Minute declaring dividend1-signed-2.pdf");

        expect(@"already signed", signedName(folder, @"Minute declaring dividend1-signed.pdf"), nil);
        expect(@"already signed, numbered", signedName(folder, @"Minute declaring dividend1-signed-1.pdf"), nil);
        expect(@"already signed, upper case", signedName(folder, @"Contract-SIGNED.pdf"), nil);
        expect(@"a name that only contains -signed", signedName(folder, @"Form-signedness.pdf"), @"Form-signedness-signed.pdf");
        expect(@"no extension", signedName(folder, @"contract"), @"contract-signed");
        expect(@"dots in the name", signedName(folder, @"v1.2 terms.pdf"), @"v1.2 terms-signed.pdf");
    }
    printf("%s\n", failures ? "FAIL" : "PASS");
    return failures ? 1 : 0;
}