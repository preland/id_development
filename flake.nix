{
  description = "id language: self-hosted compiler, LLVM/WASM targets, and hardware-accelerated graphics/3D backends";

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
      #   - C toolchain
      #   - python3                  (only the oracle suites: editor_*.sh and
      #                              the pack round trip's checksum)
      #   - X11 + OpenGL/GLX + mesa  (the gfx/gl backends; Linux)
      #   - llvm/clang/lld           (`idc/bin/idc --target llvm`)
      #   - wabt + wasmtime          (inspecting and running `--target wasm`)
      #   - xdotool                  (driving windowed demos in tests)
      #   - clang-unwrapped + wasilibc + wasm32 compiler-rt
      #                              (`idc/bin/idc --target wasm`: the C target
      #                              recompiled for wasm32-wasi, docs/TODO.md 9b)
      #
      # `strict` is the same toolchain without python3, so work that must not
      # drift back into it cannot. Enter it with `nix develop -i .#strict`: plain
      # `nix develop` only prepends to PATH, so the system profile's python3
      # stays reachable unless the environment is ignored.
      devShells = forAll (pkgs:
        let
          # Native graphics dev libs, in buildInputs so the cc wrapper injects
          # their -I/-L automatically (this is what fixes "GL/gl.h: not found"
          # on NixOS). macOS uses system frameworks, so nothing is needed there.
          gfxLibs = with pkgs;
            if stdenv.isDarwin then [ ]
            else [ libx11 libGL libglvnd mesa libxkbcommon pipewire zlib sqlite ];
          # `idc/bin/idc --target wasm` drives clang itself rather than through
          # the wrapper (the wrapper mis-handles `--target=wasm32-*`), so it
          # needs the unwrapped binary plus a wasm32-wasi sysroot and
          # compiler-rt by path -- none of which the wrapped `clang` on PATH
          # exposes. IDC_WASI_* are read by idc/bin/idc's --target wasm.
          wasiLibc = pkgs.pkgsCross.wasi32.wasilibc;
          wasiCompilerRt = pkgs.pkgsCross.wasi32.llvmPackages.compiler-rt;
          toolchain = with pkgs; [
            gcc pkg-config
            llvm clang lld wabt wasmtime
            llvmPackages.clang-unwrapped
            # qemu, for booting the kernel (docs/KERNEL.md). tests/kernel.sh
            # skips itself when it is absent, so a checkout without it still
            # runs the rest of the suite.
            qemu
            # Stand-in QMP and serial peers for idc/tools/qmon's cases:
            # idstd's sockets are client-only, so a case cannot listen itself.
            socat netcat
            xdotool
            # A virtual X server, so a windowed demo can be built and run
            # without a window ever reaching the real compositor -- see
            # tools/headless.sh. Both graphics backends are X11, so one
            # Xvfb covers gfx and gl alike.
            xorg.xvfb
          ];
          wasiEnv = ''
            export IDC_WASI_CLANG="${pkgs.llvmPackages.clang-unwrapped}/bin/clang-${pkgs.lib.versions.major pkgs.llvmPackages.clang-unwrapped.version}"
            export IDC_WASI_SYSROOT_INCLUDE="${wasiLibc.dev}/include"
            export IDC_WASI_LIBDIR="${wasiLibc}/lib"
            export IDC_WASI_COMPILER_RT="${wasiCompilerRt}/lib/wasi/libclang_rt.builtins-wasm32.a"
          '' + pkgs.lib.optionalString (!pkgs.stdenv.isDarwin) ''
            export ID_PIPEWIRE_LIB="${pkgs.pipewire}/lib/libpipewire-0.3.so.0"
            export ID_XKBCOMMON_LIB="${pkgs.libxkbcommon}/lib/libxkbcommon.so.0"
          '';
        in {
          default = pkgs.mkShell {
            nativeBuildInputs = toolchain ++ [ pkgs.python3 ];
            buildInputs = gfxLibs;
            shellHook = ''
              echo "id dev shell: cc=$(command -v cc)  python3=$(python3 --version 2>&1)" >&2
            '' + wasiEnv;
          };
          strict = pkgs.mkShell {
            nativeBuildInputs = toolchain;
            buildInputs = gfxLibs;
            shellHook = ''
              if command -v python3 >/dev/null 2>&1; then
                echo "id strict shell: python3 is reachable at $(command -v python3) -- enter with 'nix develop -i .#strict' so only the declared toolchain is on PATH" >&2
              else
                echo "id strict shell: cc=$(command -v cc), no python3" >&2
              fi
            '' + wasiEnv;
          };
        });
    };
}
