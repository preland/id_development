{
  description = "id language: compiler (idc.py + self-hosted), LLVM/WASM targets, and hardware-accelerated graphics/3D backends";

  # Follows the system registry's `nixpkgs` (a local, already-realised store
  # path on this machine), so `nix develop` resolves offline with no fetch.
  inputs.nixpkgs.url = "flake:nixpkgs";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    in {
      # `nix develop` / `direnv` / `tools/devshell.sh` all land here. It provides
      # exactly the toolchain the repo needs so that graphics (`--backend`) and
      # the LLVM/WASM targets build without any manual header/lib plumbing:
      #   - C toolchain + python3 (the reference compiler idc.py)
      #   - X11 + OpenGL/GLX + mesa  (the gfx/gl backends; Linux)
      #   - llvm/clang/lld           (`idc.py --target llvm`)
      #   - wabt + wasmtime          (`idc.py --target wasm`, and running it)
      #   - xdotool                  (driving windowed demos in tests)
      #   - clang-unwrapped + wasilibc + wasm32 compiler-rt
      #                              (`idc/bin/idc --target wasm`: the C target
      #                              recompiled for wasm32-wasi, docs/TODO.md 9b)
      devShells = forAll (pkgs:
        let
          # Native graphics dev libs, in buildInputs so the cc wrapper injects
          # their -I/-L automatically (this is what fixes "GL/gl.h: not found"
          # on NixOS). macOS uses system frameworks, so nothing is needed there.
          gfxLibs = with pkgs;
            if stdenv.isDarwin then [ ]
            else [ libx11 libGL libglvnd mesa ];
          # `idc/bin/idc --target wasm` drives clang itself rather than through
          # the wrapper (the wrapper mis-handles `--target=wasm32-*`), so it
          # needs the unwrapped binary plus a wasm32-wasi sysroot and
          # compiler-rt by path -- none of which the wrapped `clang` on PATH
          # exposes. IDC_WASI_* are read by idc/bin/idc's --target wasm.
          wasiLibc = pkgs.pkgsCross.wasi32.wasilibc;
          wasiCompilerRt = pkgs.pkgsCross.wasi32.llvmPackages.compiler-rt;
        in {
          default = pkgs.mkShell {
            nativeBuildInputs = with pkgs; [
              gcc python3 pkg-config
              llvm clang lld wabt wasmtime
              llvmPackages.clang-unwrapped
              # qemu, for booting the kernel (docs/KERNEL.md). tests/kernel.sh
              # skips itself when it is absent, so a checkout without it still
              # runs the rest of the suite.
              qemu
              xdotool
              # A virtual X server, so a windowed demo can be built and run
              # without a window ever reaching the real compositor -- see
              # tools/headless.sh. Both graphics backends are X11, so one
              # Xvfb covers gfx and gl alike.
              xorg.xvfb
            ];
            buildInputs = gfxLibs;
            shellHook = ''
              echo "id dev shell: cc=$(command -v cc)  python3=$(python3 --version 2>&1)" >&2
              export IDC_WASI_CLANG="${pkgs.llvmPackages.clang-unwrapped}/bin/clang-${pkgs.lib.versions.major pkgs.llvmPackages.clang-unwrapped.version}"
              export IDC_WASI_SYSROOT_INCLUDE="${wasiLibc.dev}/include"
              export IDC_WASI_LIBDIR="${wasiLibc}/lib"
              export IDC_WASI_COMPILER_RT="${wasiCompilerRt}/lib/wasi/libclang_rt.builtins-wasm32.a"
            '';
          };
        });
    };
}
