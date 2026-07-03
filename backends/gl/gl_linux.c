/* gl_linux.c -- Linux/GLX backend for the `id` hardware-accelerated graphics
 * ABI (see gl.h).
 *
 * Opens an X11 window with a GLX-capable visual, creates a legacy
 * (fixed-function) OpenGL context with glXCreateContext, and drives it with
 * immediate-mode glBegin/glEnd -- the simplest thing that reliably works
 * against mesa's software/hardware GLX implementation, per the task's
 * guidance to prefer "actually renders via GPU" over modern-GL purity.
 *
 * Like backends/gfx/gfx_linux.c, `id` drives its own frame loop, so events
 * are drained non-blockingly with XPending/XNextEvent each poll/end_frame --
 * never XNextEvent in a blocking loop.
 *
 * Headless/CI testing: GFX_MAX_FRAMES works exactly like the gfx backend
 * (see gfx_linux.c's header comment): after N calls to id_gl_end_frame, the
 * next id_gfx_poll() reports quit (-2).
 */
#include <GL/gl.h>
#include <GL/glx.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "gl.h"

/* M_PI is a glibc/POSIX extension, not ISO C -- <math.h> only defines it when
 * a feature-test macro (_DEFAULT_SOURCE etc.) is active, which isn't
 * guaranteed under every -std= a caller might build this with. Define our own
 * so this file doesn't depend on the compiler's default feature-test mode. */
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ---- window / GLX state --------------------------------------------------- */
static Display*     g_dpy = NULL;
static Window       g_win = 0;
static GLXContext   g_ctx = NULL;
static XVisualInfo* g_vi = NULL;
static Colormap     g_cmap = 0;
static Atom         g_wm_delete = 0;
static int          g_w = 0, g_h = 0;
static int          g_quit = 0;

/* tiny key ring, same contract as backends/gfx */
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

/* GFX_MAX_FRAMES headless self-terminate hook -- identical convention to
 * backends/gfx/gfx_linux.c. */
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

int id_gfx_open(int w, int h, const char* title) {
    if (g_dpy) return 1;
    if (w <= 0 || h <= 0) return 0;
    g_dpy = XOpenDisplay(NULL);
    if (!g_dpy) return 0;

    int screen = DefaultScreen(g_dpy);
    /* Ask for a double-buffered RGBA visual with a depth buffer -- the
     * minimum a 3D scene needs. */
    int attrs[] = { GLX_RGBA, GLX_DEPTH_SIZE, 16, GLX_DOUBLEBUFFER, None };
    g_vi = glXChooseVisual(g_dpy, screen, attrs);
    if (!g_vi) {
        /* fall back to single-buffered in case the display can't double-buffer */
        int attrs_sb[] = { GLX_RGBA, GLX_DEPTH_SIZE, 16, None };
        g_vi = glXChooseVisual(g_dpy, screen, attrs_sb);
    }
    if (!g_vi) { XCloseDisplay(g_dpy); g_dpy = NULL; return 0; }

    g_cmap = XCreateColormap(g_dpy, RootWindow(g_dpy, screen), g_vi->visual, AllocNone);
    XSetWindowAttributes swa;
    memset(&swa, 0, sizeof(swa));
    swa.colormap = g_cmap;
    swa.event_mask = ExposureMask | KeyPressMask | StructureNotifyMask;

    g_win = XCreateWindow(g_dpy, RootWindow(g_dpy, screen), 0, 0, w, h, 0,
                          g_vi->depth, InputOutput, g_vi->visual,
                          CWColormap | CWEventMask, &swa);
    XStoreName(g_dpy, g_win, title ? title : "id");
    g_wm_delete = XInternAtom(g_dpy, "WM_DELETE_WINDOW", False);
    XSetWMProtocols(g_dpy, g_win, &g_wm_delete, 1);

    g_ctx = glXCreateContext(g_dpy, g_vi, NULL, GL_TRUE);
    if (!g_ctx) {
        /* no direct rendering available (common headlessly) -- retry indirect */
        g_ctx = glXCreateContext(g_dpy, g_vi, NULL, GL_FALSE);
    }
    if (!g_ctx) {
        XDestroyWindow(g_dpy, g_win); g_win = 0;
        XCloseDisplay(g_dpy); g_dpy = NULL;
        return 0;
    }

    XMapWindow(g_dpy, g_win);
    XFlush(g_dpy);

    if (!glXMakeCurrent(g_dpy, g_win, g_ctx)) {
        glXDestroyContext(g_dpy, g_ctx); g_ctx = NULL;
        XDestroyWindow(g_dpy, g_win); g_win = 0;
        XCloseDisplay(g_dpy); g_dpy = NULL;
        return 0;
    }

    glViewport(0, 0, w, h);
    glEnable(GL_DEPTH_TEST);
    glDisable(GL_CULL_FACE);   /* correctness over perf for a small demo mesh */

    g_w = w; g_h = h; g_quit = 0;
    g_keyhead = g_keytail = 0;
    g_frame_count = 0;
    fprintf(stderr, "gl_linux: opened %dx%d window, GL_RENDERER=%s GL_VERSION=%s\n",
            w, h, (const char*)glGetString(GL_RENDERER),
            (const char*)glGetString(GL_VERSION));
    return 1;
}

int id_gfx_poll(void) {
    if (!g_dpy) return -1;
    pump();
    if (g_quit) return -2;
    return key_pop();
}

int id_gfx_close(void) {
    if (!g_dpy) return 0;
    fprintf(stderr, "gl_linux: closing after %d frame(s) rendered\n", g_frame_count);
    if (g_ctx) { glXMakeCurrent(g_dpy, None, NULL); glXDestroyContext(g_dpy, g_ctx); g_ctx = NULL; }
    if (g_win) { XDestroyWindow(g_dpy, g_win); g_win = 0; }
    if (g_cmap) { XFreeColormap(g_dpy, g_cmap); g_cmap = 0; }
    if (g_vi) { XFree(g_vi); g_vi = NULL; }
    XCloseDisplay(g_dpy);
    g_dpy = NULL; g_w = g_h = 0;
    return 0;
}

/* ---- per-frame ------------------------------------------------------------ */

int id_gl_begin_frame(int r, int g, int b) {
    glClearColor((float)r / 255.0f, (float)g / 255.0f, (float)b / 255.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);
    return 0;
}

int id_gl_end_frame(void) {
    if (g_dpy) glXSwapBuffers(g_dpy, g_win);
    pump();
    g_frame_count++;
    /* Throttle to ~1/sec (assuming a ~60fps caller) so a long-running windowed
     * session doesn't spam stderr, while still proving draw calls are
     * happening; headless GFX_MAX_FRAMES runs are short enough that the
     * final "reached" line below is the important signal anyway. */
    if (g_frame_count == 1 || g_frame_count % 60 == 0)
        fprintf(stderr, "gl_linux: rendered %d frame(s)\n", g_frame_count);
    int max = max_frames();
    if (max >= 0 && g_frame_count >= max) {
        fprintf(stderr, "gl_linux: GFX_MAX_FRAMES=%d reached, synthesizing quit\n", max);
        g_quit = 1;
    }
    return g_frame_count;
}

/* ---- matrix pool ----------------------------------------------------------
 * A fixed ring of 4x4 column-major float matrices (OpenGL's own layout, so
 * glLoadMatrixf can consume one directly). Handles are just pool indices;
 * nothing is ever freed explicitly -- a demo rebuilds a handful of matrices
 * every frame, so the ring simply wraps and overwrites the oldest slot. */
#define MAT_POOL 1024
static float g_mat[MAT_POOL][16];
static int g_mat_next = 0;

static int mat_alloc(void) {
    int h = g_mat_next;
    g_mat_next = (g_mat_next + 1) % MAT_POOL;
    return h;
}

static void mat_set_identity(float* m) {
    memset(m, 0, sizeof(float) * 16);
    m[0] = m[5] = m[10] = m[15] = 1.0f;
}

int id_gl_mat_identity(void) {
    int h = mat_alloc();
    mat_set_identity(g_mat[h]);
    return h;
}

int id_gl_mat_perspective(int fov_deg_x1000, int aspect_x1000, int near_x1000, int far_x1000) {
    double fov = (double)fov_deg_x1000 / 1000.0 * (M_PI / 180.0);
    double aspect = (double)aspect_x1000 / 1000.0;
    double zn = (double)near_x1000 / 1000.0;
    double zf = (double)far_x1000 / 1000.0;
    double f = 1.0 / tan(fov / 2.0);
    int h = mat_alloc();
    float* m = g_mat[h];
    memset(m, 0, sizeof(float) * 16);
    m[0] = (float)(f / aspect);
    m[5] = (float)f;
    m[10] = (float)((zf + zn) / (zn - zf));
    m[11] = -1.0f;
    m[14] = (float)((2.0 * zf * zn) / (zn - zf));
    return h;
}

int id_gl_mat_rotate_x(int deg_x1000) {
    double a = (double)deg_x1000 / 1000.0 * (M_PI / 180.0);
    float c = (float)cos(a), s = (float)sin(a);
    int h = mat_alloc();
    float* m = g_mat[h];
    mat_set_identity(m);
    m[5] = c;  m[6] = s;
    m[9] = -s; m[10] = c;
    return h;
}

int id_gl_mat_rotate_y(int deg_x1000) {
    double a = (double)deg_x1000 / 1000.0 * (M_PI / 180.0);
    float c = (float)cos(a), s = (float)sin(a);
    int h = mat_alloc();
    float* m = g_mat[h];
    mat_set_identity(m);
    m[0] = c;  m[2] = -s;
    m[8] = s;  m[10] = c;
    return h;
}

int id_gl_mat_rotate_z(int deg_x1000) {
    double a = (double)deg_x1000 / 1000.0 * (M_PI / 180.0);
    float c = (float)cos(a), s = (float)sin(a);
    int h = mat_alloc();
    float* m = g_mat[h];
    mat_set_identity(m);
    m[0] = c; m[1] = s;
    m[4] = -s; m[5] = c;
    return h;
}

int id_gl_mat_translate(int x_x1000, int y_x1000, int z_x1000) {
    int h = mat_alloc();
    float* m = g_mat[h];
    mat_set_identity(m);
    m[12] = (float)x_x1000 / 1000.0f;
    m[13] = (float)y_x1000 / 1000.0f;
    m[14] = (float)z_x1000 / 1000.0f;
    return h;
}

int id_gl_mat_mul(int a, int b) {
    int h = mat_alloc();
    /* Guard bad handles from `id` (shouldn't happen, but link-time externs
     * have no type checking) by clamping into the pool. */
    a = ((a % MAT_POOL) + MAT_POOL) % MAT_POOL;
    b = ((b % MAT_POOL) + MAT_POOL) % MAT_POOL;
    const float* A = g_mat[a];
    const float* B = g_mat[b];
    float* R = g_mat[h];
    /* Both operands are column-major OpenGL matrices; column-major product
     * R = A*B: R[col*4+row] = sum_k A[k*4+row] * B[col*4+k]. */
    for (int col = 0; col < 4; col++) {
        for (int row = 0; row < 4; row++) {
            float sum = 0.0f;
            for (int k = 0; k < 4; k++) sum += A[k * 4 + row] * B[col * 4 + k];
            R[col * 4 + row] = sum;
        }
    }
    return h;
}

int id_gl_set_projection(int handle) {
    handle = ((handle % MAT_POOL) + MAT_POOL) % MAT_POOL;
    glMatrixMode(GL_PROJECTION);
    glLoadMatrixf(g_mat[handle]);
    glMatrixMode(GL_MODELVIEW);
    return 0;
}

int id_gl_set_modelview(int handle) {
    handle = ((handle % MAT_POOL) + MAT_POOL) % MAT_POOL;
    glMatrixMode(GL_MODELVIEW);
    glLoadMatrixf(g_mat[handle]);
    return 0;
}

/* ---- geometry -------------------------------------------------------------- */

int id_gl_draw_tris(IdList* verts, IdList* colors, int count) {
    if (!verts || !colors || count <= 0) return 0;
    int nv = count * 3;
    int have_v = verts->len / 3;      /* vertices actually available */
    int have_c = colors->len;         /* one packed color per vertex */
    if (nv > have_v) nv = have_v;
    if (nv > have_c) nv = have_c;

    glBegin(GL_TRIANGLES);
    for (int i = 0; i < nv; i++) {
        long long c = colors->data[i];
        float r = (float)((c / 65536) % 256) / 255.0f;
        float g = (float)((c / 256) % 256) / 255.0f;
        float b = (float)(c % 256) / 255.0f;
        glColor3f(r, g, b);
        float x = (float)verts->data[i * 3 + 0] / 1000.0f;
        float y = (float)verts->data[i * 3 + 1] / 1000.0f;
        float z = (float)verts->data[i * 3 + 2] / 1000.0f;
        glVertex3f(x, y, z);
    }
    glEnd();
    return 0;
}
