/* gfx_linux.c -- Linux/X11 backend for the `id` graphics ABI (see gfx.h).
 *
 * The Linux counterpart to gfx_macos.m, behind the identical header: an Xlib
 * window with a software framebuffer blitted by XPutImage. Zero third-party
 * dependencies -- only libX11, which ships with every X server. Like the macOS
 * backend it never blocks: id_gfx_poll drains the X event queue with XPending,
 * so `id` keeps driving its own frame loop.
 *
 * Status: validated on Linux (X11/XWayland) -- builds and runs demos/gfxdemo
 * headlessly via the GFX_MAX_FRAMES self-terminate hook (see below). It is the
 * concrete proof that the seam is platform-agnostic. A Wayland backend would
 * slot in the same way -- another object behind the same gfx.h.
 *
 * Headless/CI testing: if the environment variable GFX_MAX_FRAMES is set to a
 * positive integer N, id_gfx_present counts calls and, once N presents have
 * happened, makes the *next* id_gfx_poll() report quit (-2). This lets a build
 * run a bounded number of frames and exit 0 with no human closing the window.
 */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "gfx.h"

static Display* g_dpy = NULL;
static Window   g_win = 0;
static GC       g_gc  = 0;
static XImage*  g_img = NULL;
static uint32_t* g_px = NULL;          /* 0x00RRGGBB words, 32bpp            */
static Atom     g_wm_delete = 0;
static int      g_w = 0, g_h = 0;
static int      g_quit = 0;

/* GFX_MAX_FRAMES headless self-terminate hook (see file header). -1 = unset
 * (never auto-quit), otherwise the number of id_gfx_present calls to allow
 * before synthesizing a quit signal on the next id_gfx_poll. */
static int g_max_frames = -1;
static int g_max_frames_read = 0;
static int g_frame_count = 0;

static int max_frames(void) {
    if (!g_max_frames_read) {
        g_max_frames_read = 1;
        const char* s = getenv("GFX_MAX_FRAMES");
        if (s && *s) g_max_frames = atoi(s);
    }
    return g_max_frames;
}

/* tiny key ring, same contract as the macOS backend */
#define GFX_KEYQ 256
static int g_keyq[GFX_KEYQ];
static int g_keyhead = 0, g_keytail = 0;
static void key_push(int code) {
    int n = (g_keytail + 1) % GFX_KEYQ;
    if (n == g_keyhead) return;
    g_keyq[g_keytail] = code; g_keytail = n;
}
static int key_pop(void) {
    if (g_keyhead == g_keytail) return -1;
    int code = g_keyq[g_keyhead];
    g_keyhead = (g_keyhead + 1) % GFX_KEYQ;
    return code;
}

/* drain everything X has queued without blocking */
static void pump(void) {
    if (!g_dpy) return;
    while (XPending(g_dpy)) {
        XEvent ev;
        XNextEvent(g_dpy, &ev);
        if (ev.type == ClientMessage) {
            if ((Atom)ev.xclient.data.l[0] == g_wm_delete) g_quit = 1;
        } else if (ev.type == KeyPress) {
            char buf[8];
            KeySym ks;
            int n = XLookupString(&ev.xkey, buf, sizeof(buf), &ks, NULL);
            if (n > 0) key_push((unsigned char)buf[0]);
        }
    }
}

int id_gfx_open(int w, int h, const char* title) {
    if (g_dpy) return 1;
    if (w <= 0 || h <= 0) return 0;
    g_dpy = XOpenDisplay(NULL);
    if (!g_dpy) return 0;

    int screen = DefaultScreen(g_dpy);
    g_win = XCreateSimpleWindow(g_dpy, RootWindow(g_dpy, screen), 0, 0, w, h, 0,
                                BlackPixel(g_dpy, screen),
                                BlackPixel(g_dpy, screen));
    XStoreName(g_dpy, g_win, title ? title : "id");
    XSelectInput(g_dpy, g_win, ExposureMask | KeyPressMask);
    g_wm_delete = XInternAtom(g_dpy, "WM_DELETE_WINDOW", False);
    XSetWMProtocols(g_dpy, g_win, &g_wm_delete, 1);

    g_gc = XCreateGC(g_dpy, g_win, 0, NULL);
    g_px = (uint32_t*)calloc((size_t)w * h, sizeof(uint32_t));
    if (!g_px) return 0;
    /* 32bpp TrueColor image over our buffer; on the common little-endian
     * 24/32-bit visual a 0x00RRGGBB word renders as that color directly. */
    g_img = XCreateImage(g_dpy, DefaultVisual(g_dpy, screen),
                         DefaultDepth(g_dpy, screen), ZPixmap, 0,
                         (char*)g_px, w, h, 32, 0);
    if (!g_img) return 0;

    XMapWindow(g_dpy, g_win);
    XFlush(g_dpy);
    g_w = w; g_h = h; g_quit = 0;
    g_keyhead = g_keytail = 0;
    g_frame_count = 0;
    return 1;
}

int id_gfx_present(IdList* fb) {
    if (!g_dpy || !g_px) return 0;
    int n = g_w * g_h;
    int have = (fb ? fb->len : 0);
    for (int i = 0; i < n; i++)
        g_px[i] = (i < have) ? (uint32_t)(fb->data[i] & 0xFFFFFF) : 0u;
    XPutImage(g_dpy, g_win, g_gc, g_img, 0, 0, 0, 0, g_w, g_h);
    XFlush(g_dpy);
    pump();
    g_frame_count++;
    int max = max_frames();
    if (max >= 0 && g_frame_count >= max) {
        fprintf(stderr, "gfx_linux: GFX_MAX_FRAMES=%d reached, presented %d frame(s), "
                        "synthesizing quit\n", max, g_frame_count);
        g_quit = 1;
    }
    return 0;
}

int id_gfx_poll(void) {
    if (!g_dpy) return -1;
    pump();
    if (g_quit) return -2;
    return key_pop();
}

int id_gfx_close(void) {
    if (!g_dpy) return 0;
    if (g_img) { XDestroyImage(g_img); g_img = NULL; g_px = NULL; } /* frees g_px */
    if (g_gc)  { XFreeGC(g_dpy, g_gc); g_gc = 0; }
    if (g_win) { XDestroyWindow(g_dpy, g_win); g_win = 0; }
    XCloseDisplay(g_dpy);
    g_dpy = NULL; g_w = g_h = 0;
    return 0;
}
