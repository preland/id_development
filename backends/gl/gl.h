/* gl.h -- the `id` hardware-accelerated graphics backend ABI.
 *
 * This is the second tier promised by backends/gfx/README.md's "path to
 * true-native rendering": where `gfx` presents a software framebuffer that
 * `id` paints one pixel at a time, `gl` hands the pixels to a real GPU. The
 * window/input primitives (gfx_open, gfx_poll, gfx_close) are the SAME names
 * and the SAME contract as backends/gfx/gfx.h on purpose -- an `id` program's
 * frame-loop shape doesn't change when it switches from the software floor to
 * the hardware path, only what it calls each frame to draw.
 *
 * ABI notes (same rules as gfx.h, dictated by how `idc` links unknown
 * functions): every entry point is declared by idc as `extern int
 * id_<name>()` (no prototype) and called as `id_<name>(args)`, so every
 * function here returns `int`, is named with the `id_` prefix, and takes only
 * argument types idc knows how to lower: `id` int -> C int, `id` int[] ->
 * IdList* (below). There is no `id` string arg on this second tier except the
 * window title, matching gfx.h.
 *
 * -----------------------------------------------------------------------
 * The float problem, and how this backend solves it
 * -----------------------------------------------------------------------
 * `id` cannot conveniently build the float matrices a GPU pipeline needs
 * (see demos/gl3d/README.md for the full rationale), so this backend follows
 * the division of labor the task calls "legitimate and clean": ALL matrix
 * math lives here, in C, using real `double`/`float` arithmetic. `id` only
 * ever passes and receives *integers*:
 *
 *   - angles and translations cross the seam as integers scaled by 1000
 *     ("milli-units"): an id int `y` meaning translate-by-y/1000.0 units, or
 *     `deg` meaning deg/1000.0 degrees. This mirrors demos/gfxdemo's own
 *     `rgb(r,g,b)` packing trick -- plain integer arithmetic standing in for
 *     something the language can't spell directly.
 *   - a built matrix is never marshalled back into `id` at all. Instead each
 *     gl_mat_* builder returns an opaque *handle*: a small int index into a
 *     fixed pool of 4x4 matrices kept entirely on the native side. `id` just
 *     threads handles between calls (gl_mat_mul(a, b) -> new handle, then
 *     gl_set_modelview(handle)). This is simpler than round-tripping 16
 *     bit-cast floats through an IdList* and just as legitimate a lowering.
 *   - vertex data (positions, colors) DOES cross as IdList* of int, but every
 *     element is either a milli-unit coordinate (divide by 1000.0 on this
 *     side to get the float) or a packed 0xRRGGBB color (same convention
 *     gfx.h's framebuffer already uses).
 *
 * -----------------------------------------------------------------------
 * The seam, function by function
 * -----------------------------------------------------------------------
 */
#ifndef ID_GL_H
#define ID_GL_H

/* Growable list, byte-for-byte identical to the IdList in idc.py's RUNTIME
 * (and to backends/gfx/gfx.h's copy). An `id` `int[]` lowers to `IdList*`. */
typedef struct { int len, cap; long long* data; } IdList;

/* ---- window / input (identical contract to backends/gfx/gfx.h) ---------- */

/* Open a w x h GPU-backed window with the given UTF-8 title. 1 on success, 0
 * on failure (e.g. no GLX-capable visual). Call once before any gl_* call. */
extern int id_gfx_open(int w, int h, const char* title);

/* Poll one input event, non-blocking: -2 quit (close button, or the
 * GFX_MAX_FRAMES headless self-terminate hook firing), -1 no event this poll,
 * >=0 a key code. Same convention as gfx.h's id_gfx_poll. */
extern int id_gfx_poll(void);

/* Tear down the GL context and window. Safe to call once at exit. Returns 0. */
extern int id_gfx_close(void);

/* ---- per-frame primitives ------------------------------------------------ */

/* Begin a frame: clear the color buffer to (r, g, b) (each 0..255) and clear
 * the depth buffer. Call once at the start of every frame. Returns 0. */
extern int id_gl_begin_frame(int r, int g, int b);

/* End a frame: swap the front/back buffers (presenting what was drawn) and
 * pump the platform event queue. Also advances the GFX_MAX_FRAMES counter
 * (see backends/gfx for the identical hook) and logs a
 * "rendered N frame(s)" line to stderr so headless runs have visible proof
 * real draw calls happened. Call once at the end of every frame. Returns the
 * number of frames rendered so far (>=1). */
extern int id_gl_end_frame(void);

/* ---- matrix builders: each returns an opaque handle (>=0) into a native
 * pool of 4x4 matrices. `id` never sees the floats, only the handle. -------- */

/* The 4x4 identity matrix. */
extern int id_gl_mat_identity(void);

/* A perspective projection matrix (like gluPerspective): vertical field of
 * view in thousandths of a degree, aspect ratio (width/height) in
 * thousandths, near and far clip planes in thousandths of a unit. */
extern int id_gl_mat_perspective(int fov_deg_x1000, int aspect_x1000,
                                  int near_x1000, int far_x1000);

/* Rotation about the X/Y/Z axis, by an angle in thousandths of a degree. */
extern int id_gl_mat_rotate_x(int deg_x1000);
extern int id_gl_mat_rotate_y(int deg_x1000);
extern int id_gl_mat_rotate_z(int deg_x1000);

/* A translation matrix, each axis in thousandths of a unit. */
extern int id_gl_mat_translate(int x_x1000, int y_x1000, int z_x1000);

/* Matrix product a*b (a and b are handles from any gl_mat_* builder above),
 * returned as a new handle. Order matches OpenGL's column-vector convention:
 * applying the result to a vector v computes a*(b*v), i.e. b is applied
 * first. */
extern int id_gl_mat_mul(int a, int b);

/* ---- pipeline state ------------------------------------------------------ */

/* Load `handle`'s matrix onto the GL_PROJECTION stack. */
extern int id_gl_set_projection(int handle);

/* Load `handle`'s matrix onto the GL_MODELVIEW stack. */
extern int id_gl_set_modelview(int handle);

/* ---- geometry -------------------------------------------------------------
 * Draw `count` triangles (so 3*count vertices). `verts` holds 9 ints per
 * triangle (x,y,z, x,y,z, x,y,z), each a milli-unit coordinate (divide by
 * 1000.0 for the float). `colors` holds 3 ints per triangle, one packed
 * 0xRRGGBB per vertex, in the same order as `verts` -- GL interpolates them
 * across the triangle (Gouraud shading) via the fixed-function pipeline.
 * Uses whatever matrices are currently loaded via gl_set_projection /
 * gl_set_modelview. Returns 0. */
extern int id_gl_draw_tris(IdList* verts, IdList* colors, int count);

#endif /* ID_GL_H */
