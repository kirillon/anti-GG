#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_python=${VEITCH_PYTHON:-"$project_dir/.venv/bin/python"}
if [ ! -x "$project_python" ]; then
    printf '%s\n' 'Не найден Python проекта. На NixOS выполните nix-shell, иначе установите .venv по инструкции в README.md.' >&2
    exit 1
fi
exec "$project_python" "$project_dir/app.py" "$@"
