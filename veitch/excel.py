"""Isolated formula workbook export with bounded subprocess execution."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def export_timing(data):
    with tempfile.TemporaryDirectory(prefix='veitch-excel-') as directory:
        source, output = Path(directory)/'timing.json', Path(directory)/'timing.xlsx'
        source.write_text(json.dumps(data), encoding='utf-8')
        try:
            subprocess.run(['node', str(ROOT/'export_timing.mjs'), str(source), str(output)],
                           check=True, capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError('Не удалось создать Excel. Проверьте Node.js и @oai/artifact-tool (VEITCH_NODE_MODULES).') from exc
        return output.read_bytes()
