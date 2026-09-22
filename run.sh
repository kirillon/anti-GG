#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -x "$project_dir/.venv/bin/python" ]; then
    printf '%s\n' 'Не найдено окружение .venv. Установите зависимости по инструкции в README.md.' >&2
    exit 1
fi
exec "$project_dir/.venv/bin/python" "$project_dir/app.py" "$@"
