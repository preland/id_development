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
      devShells = forAll (pkgs:
        let
          # Native graphics dev libs, in buildInputs so the cc wrapper injects
          # their -I/-L automatically (this is what fixes "GL/gl.h: not found"
          # on NixOS). macOS uses system frameworks, so nothing is needed there.
          gfxLibs = with pkgs;
            if stdenv.isDarwin then [ ]
            else [ libx11 libGL libglvnd mesa ];
        in {
          default = pkgs.mkShell {
            nativeBuildInputs = with pkgs; [
              gcc python3 pkg-config
              llvm clang lld wabt wasmtime
              xdotool
            ];
            buildInputs = gfxLibs;
            shellHook = ''
              echo "id dev shell: cc=$(command -v cc)  python3=$(python3 --version 2>&1)" >&2
            '';
          };
        });
    };
}
