#!/usr/bin/env bash
# Run a command inside the `id` development toolchain.
#
# This repo is developed on NixOS, where dev headers/libraries are NOT on the
# default compiler search path -- they are provided by nix-shell, which sets
# NIX_CFLAGS_COMPILE / NIX_LDFLAGS so the wrapped `cc`/`clang` find them without
# any pkg-config plumbing. Every build that links a graphics backend or targets
# LLVM/WASM must run inside this shell.
#
#   tools/devshell.sh ./idc.py demos/gfxdemo --backend backends/gfx -o /tmp/gfxdemo
#   tools/devshell.sh bash tests/run.sh
#   tools/devshell.sh clang --target=wasm32 ...
#
# Provides: C toolchain, X11 + OpenGL/GLX (graphics), LLVM/clang/lld (llvm
# target), wabt + wasmtime (wasm target).
exec nix-shell -p \
  libx11 libGL libglvnd mesa pkg-config \
  llvm clang lld wabt wasmtime \
  --run "$*"
