{ pkgs ? import <nixpkgs> { config = { cudaSupport = false; rocmSupport = false; }; } }:

let
  pythonEnv = pkgs.python3.withPackages (ps: [ ps.torch ps.numpy ]);
in
pkgs.mkShell {
  packages = [ pythonEnv ];

  # Prefer Nix's interpreter even when an old pip-based .venv exists.
  VEITCH_PYTHON = "${pythonEnv}/bin/python";
  PYTHON = "${pythonEnv}/bin/python";
  PYTHONNOUSERSITE = "1";

  shellHook = ''
    echo "Вейч: ./run.sh — запуск на http://127.0.0.1:8000"
  '';
}
