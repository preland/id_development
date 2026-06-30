/* gfx_macos.m -- macOS backend for the `id` graphics ABI (see gfx.h).
 *
 * Zero third-party dependencies: just Cocoa + QuartzCore from the system SDK,
 * compiled by the same clang that builds the rest of `id`. A software
 * framebuffer is presented through a layer-backed NSView as a CGImage.
 *
 * The hard part on macOS is that `id` drives its own frame loop (draw ->
 * present -> poll -> sleep) and must NOT hand control to [NSApp run]. So we
 * finishLaunching the app once, then on every present/poll we *pump* the event
 * queue non-blockingly with nextEventMatchingMask:untilDate:distantPast. This
 * is the standard "embed Cocoa in a custom loop" pattern.
 *
 * Built with -fobjc-arc, so no manual retain/release.
 */
#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>
#include <string.h>
#include "gfx.h"

/* ---- pixel surface --------------------------------------------------------
 * We keep one uint32 buffer in 0xAARRGGBB layout. Paired with
 * (kCGImageAlphaNoneSkipFirst | kCGBitmapByteOrder32Little) this is the
 * canonical "ARGB word" software-framebuffer format on little-endian macOS:
 * each 32-bit word displays as the color you wrote, no byte juggling. */

/* The view that owns the pixels and draws them. Flipped so row 0 is the top. */
@interface GfxView : NSView {
@public
    uint32_t* pixels;
    int pxw, pxh;
}
@end

@implementation GfxView
- (BOOL)isFlipped { return YES; }      /* top-left origin: matches our buffer */
- (BOOL)acceptsFirstResponder { return YES; }  /* so keyDown reaches us       */
- (void)drawRect:(NSRect)dirty {
    (void)dirty;
    if (!pixels || pxw <= 0 || pxh <= 0) return;
    CGContextRef ctx = [[NSGraphicsContext currentContext] CGContext];
    CGColorSpaceRef cs = CGColorSpaceCreateDeviceRGB();
    CGContextRef bmp = CGBitmapContextCreate(
        pixels, pxw, pxh, 8, (size_t)pxw * 4, cs,
        kCGImageAlphaNoneSkipFirst | kCGBitmapByteOrder32Little);
    CGImageRef img = bmp ? CGBitmapContextCreateImage(bmp) : NULL;
    if (img) {
        /* nearest-neighbour scale to the view (crisp pixels if resized) */
        CGContextSetInterpolationQuality(ctx, kCGInterpolationNone);
        CGContextDrawImage(ctx, self.bounds, img);
        CGImageRelease(img);
    }
    if (bmp) CGContextRelease(bmp);
    CGColorSpaceRelease(cs);
}
@end

/* The window's delegate: turns a close request into the -2 quit signal. */
@interface GfxDelegate : NSObject <NSWindowDelegate>
@end
static int g_quit = 0;
@implementation GfxDelegate
- (BOOL)windowShouldClose:(NSWindow*)sender { (void)sender; g_quit = 1; return NO; }
@end

/* ---- backend state -------------------------------------------------------- */
static NSWindow*   g_window = nil;
static GfxView*    g_view   = nil;
static GfxDelegate* g_delegate = nil;
static int g_w = 0, g_h = 0;

/* tiny key ring drained by id_gfx_poll */
#define GFX_KEYQ 256
static int g_keyq[GFX_KEYQ];
static int g_keyhead = 0, g_keytail = 0;
static void key_push(int code) {
    int n = (g_keytail + 1) % GFX_KEYQ;
    if (n == g_keyhead) return;          /* full: drop oldest-safe (skip)   */
    g_keyq[g_keytail] = code;
    g_keytail = n;
}
static int key_pop(void) {
    if (g_keyhead == g_keytail) return -1;
    int code = g_keyq[g_keyhead];
    g_keyhead = (g_keyhead + 1) % GFX_KEYQ;
    return code;
}

/* Non-blocking event pump. Capture key codes; let everything else flow to the
 * app so the window stays live. keyDown is consumed here (not forwarded) to
 * avoid the system beep on keys no responder handles. */
static void pump(void) {
    NSApplication* app = [NSApplication sharedApplication];
    for (;;) {
        NSEvent* ev = [app nextEventMatchingMask:NSEventMaskAny
                                       untilDate:[NSDate distantPast]
                                          inMode:NSDefaultRunLoopMode
                                         dequeue:YES];
        if (!ev) break;
        if (ev.type == NSEventTypeKeyDown) {
            NSString* s = ev.charactersIgnoringModifiers;
            if (s.length > 0) key_push((int)[s characterAtIndex:0]);
            continue;
        }
        [app sendEvent:ev];
    }
}

int id_gfx_open(int w, int h, const char* title) {
    if (g_window) return 1;              /* already open                     */
    if (w <= 0 || h <= 0) return 0;
    @autoreleasepool {
        NSApplication* app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];

        NSRect frame = NSMakeRect(0, 0, w, h);
        NSUInteger style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable |
                           NSWindowStyleMaskMiniaturizable;
        g_window = [[NSWindow alloc] initWithContentRect:frame
                                               styleMask:style
                                                 backing:NSBackingStoreBuffered
                                                   defer:NO];
        g_delegate = [GfxDelegate new];
        g_window.delegate = g_delegate;
        g_window.releasedWhenClosed = NO;
        [g_window setTitle:[NSString stringWithUTF8String:(title ? title : "id")]];

        g_view = [[GfxView alloc] initWithFrame:frame];
        g_view->pxw = w; g_view->pxh = h;
        g_view->pixels = (uint32_t*)calloc((size_t)w * h, sizeof(uint32_t));
        g_window.contentView = g_view;

        [g_window center];
        [g_window makeKeyAndOrderFront:nil];
        [g_window makeFirstResponder:g_view];
        [app activateIgnoringOtherApps:YES];
        [app finishLaunching];           /* ready to pump, without -run      */

        g_w = w; g_h = h; g_quit = 0;
        g_keyhead = g_keytail = 0;
    }
    return g_view->pixels ? 1 : 0;
}

int id_gfx_present(IdList* fb) {
    if (!g_window || !g_view || !g_view->pixels) return 0;
    @autoreleasepool {
        int n = g_w * g_h;
        int have = (fb ? fb->len : 0);
        uint32_t* dst = g_view->pixels;
        for (int i = 0; i < n; i++) {
            uint32_t rgb = (i < have) ? (uint32_t)(fb->data[i] & 0xFFFFFF) : 0u;
            dst[i] = 0xFF000000u | rgb;   /* opaque ARGB word                 */
        }
        [g_view setNeedsDisplay:YES];
        [g_view displayIfNeeded];         /* draw now, inside our loop        */
        pump();
    }
    return 0;
}

int id_gfx_poll(void) {
    if (!g_window) return -1;
    pump();
    if (g_quit) return -2;
    return key_pop();
}

int id_gfx_close(void) {
    if (!g_window) return 0;
    @autoreleasepool {
        if (g_view && g_view->pixels) { free(g_view->pixels); g_view->pixels = NULL; }
        [g_window close];
        g_window = nil; g_view = nil; g_delegate = nil;
        g_w = g_h = 0;
    }
    return 0;
}
