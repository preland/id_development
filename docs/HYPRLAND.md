# Running the graphics demos without losing your place

A windowed `id` program is an ordinary X11 client, so a tiling compositor does
what it does for any application: focuses the new window, warps the pointer to
it, and drops whatever was fullscreen. That is right for an application and
wrong for a test.

There are two situations and they want different answers.

## Running them as tests: no window at all

`tools/headless.sh` starts a private Xvfb on a free display, runs the command
against it, and tears it down:

```sh
tools/headless.sh ./gl3d
GFX_MAX_FRAMES=3 tools/headless.sh /tmp/gl3d
```

The window is real, the GLX context is real, the frames are real — the
compositor never learns it exists. `tests/backends.sh` uses this for its two
windowed checks, so the suite no longer touches your session, and the graphics
tests now run on a machine with no session at all.

Xvfb comes from the dev shell (`flake.nix`), so this works under
`nix develop` or `tools/devshell.sh` and says so clearly when it doesn't.

**Caveat:** Xvfb has no GPU, so GL runs on llvmpipe (software Mesa). That is
correct for behaviour — `tests/backends.sh` reads pixels back and checks
them — but it is not a GPU test. Use the rules below when you need real
hardware.

## Watching one run: a workspace it does not follow you to

Both backends now set `WM_CLASS`, which they did not before — a rule had
nothing to match on except the window title, which is whatever string the
program passed to `gfx_open`. The classes are:

| backend | `WM_CLASS` |
| --- | --- |
| `backends/gfx` (software framebuffer) | `id-gfx` |
| `backends/gl` (OpenGL) | `id-gl` |

On this machine Hyprland's user rules live in
`~/.config/hypr-user/rules.lua`, which is loaded *after* ML4W's own rules and
so overrides them. Add:

```lua
-- id graphics demos: open on workspace 10 without going there, and never
-- take focus. `silent` is the part that stops the workspace switch.
hl.window_rule({
    name  = "id-gfx-demos",
    match = { class = "^(id-gfx|id-gl)$" },
    workspace = "10 silent",
    no_initial_focus = true,
})
```

The equivalent in raw hyprlang, if you would rather put it in
`~/.config/hypr/conf/custom.conf`:

```
windowrulev2 = workspace 10 silent, class:^(id-gfx|id-gl)$
windowrulev2 = noinitialfocus,      class:^(id-gfx|id-gl)$
```

**Check which one this build actually honours.** `custom.conf`'s own notes
record that on this ML4W-Lua build the Lua layer is authoritative for keybinds
and `exec-once`, and that hyprlang lines for those "silently never run". Window
rules come from both layers here (`conf/windowrule.conf` sources
`windowrules/default.conf`, and `conf/windowrule.lua` loads a Lua variant), so
which wins is worth confirming with `hyprctl clients` on a live window rather
than assuming. The Lua form is the safer bet, because `rules.lua` is documented
as loading last.

Neither form is applied by this repository — it is your configuration, and a
rule that silently does not fire is worse than no rule, so it is written down
here to be applied deliberately.
