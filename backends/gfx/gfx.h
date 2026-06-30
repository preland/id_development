/* gfx.h -- the `id` graphics backend ABI (the platform-agnostic seam).
 *
 * This header defines the *entire* contract between `id` programs and the
 * native window/present code. An `id` program never names a platform API; it
 * only calls these five functions, which `idc` resolves at link time against
 * one platform backend object (gfx_macos.m, gfx_linux.c, ...). Swapping the OS
 * swaps the object behind this header and nothing else -- the same way the
 * terminal engine abstracts over termios/ANSI behind put/getkey/flush.
 *
 * Design: a *software framebuffer*. The `id` side owns an `int[]` of w*h pixels
 * (one 0xRRGGBB value per pixel, row-major, top row first) and draws into it in
 * pure, portable `id`. Once per frame it hands the whole buffer to gfx_present,
 * which blits it to the window. All drawing logic stays in `id`; the backend
 * only opens a window, copies pixels, and reports input. This keeps the
 * per-platform code tiny and is the most portable possible seam.
 *
 * Path to true-native rendering: this same header is the place to grow a
 * second tier of entry points (gfx_rect, gfx_blit, a GPU pipeline, ...) backed
 * per-OS by Metal/Vulkan, while gfx_present stays as the always-available
 * software path. The framebuffer is the floor, not the ceiling.
 *
 * ABI notes (dictated by how `idc` links unknown functions):
 *   - Every entry point is declared `extern int id_<name>()` by idc and is
 *     called as `id_<name>(args)`. So each function here is named with the
 *     `id_` prefix and returns `int`.
 *   - Argument lowering mirrors idc's: `id` int -> C int, `id` string -> char*,
 *     `id` int[] -> IdList* (below). These match what idc emits at the call.
 */
#ifndef ID_GFX_H
#define ID_GFX_H

/* Growable list, byte-for-byte identical to the IdList in idc.py's RUNTIME.
 * An `id` `int[]` lowers to `IdList*`; each element is one cell. For an int
 * list the cell holds the int directly (only floats are bit-boxed), so a pixel
 * value is simply `(int)data[i]`. If idc's runtime layout ever changes, this
 * struct must change with it. */
typedef struct { int len, cap; long long* data; } IdList;

/* Open a window with a w*h pixel surface and the given UTF-8 title.
 * Returns 1 on success, 0 on failure. Call once before presenting. */
extern int id_gfx_open(int w, int h, const char* title);

/* Present one frame: copy w*h pixels from `fb` (0xRRGGBB each, row-major, top
 * row first) to the window and pump the platform's pending events. `fb` must
 * hold at least w*h elements; extra elements are ignored, missing ones read as
 * black. Returns 0. Call once per frame. */
extern int id_gfx_present(IdList* fb);

/* Poll one input event without blocking. Drains/advances the platform event
 * queue and returns:
 *     -2  the window wants to close (close button / quit) -- stop the loop
 *     -1  no event this poll
 *    >=0  a key was pressed; the value is its character/byte code
 * Mirrors getkey()'s -1 convention, with -2 added for "quit". Poll in a loop
 * each frame to drain everything buffered since the last frame. */
extern int id_gfx_poll(void);

/* Close the window and release backend resources. Safe to call once at exit;
 * a no-op if no window is open. Returns 0. */
extern int id_gfx_close(void);

#endif /* ID_GFX_H */
