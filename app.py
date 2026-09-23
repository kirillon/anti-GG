"""Local web server, Python standard library. Run: python app.py."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit
import torch
from veitch.model import GroupModel, MODEL_PATH
from veitch.service import solve
from veitch.system import solve_system
from veitch.timing import netlist, simulate
from veitch.excel import export_timing

ROOT = Path(__file__).resolve().parent


def handler_for(model):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status, value):
            self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/api/status":
                self.send_json(200, {"model_ready": model is not None})
                return
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/theme.js": ("theme.js", "text/javascript; charset=utf-8"),
                      "/system.js": ("system.js", "text/javascript; charset=utf-8"),
                      "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in assets:
                self.send_json(404, {"error": "Страница не найдена."})
                return
            filename, mime = assets[path]
            self.send_bytes(200, (ROOT / "static" / filename).read_bytes(), mime)

        def do_POST(self):
            if self.path not in ("/api/minimize", "/api/system", "/api/timing", "/api/timing.xlsx"):
                self.send_json(404, {"error": "Метод не найден."})
                return
            if self.headers.get_content_type() != "application/json":
                self.send_json(415, {"error": "Ожидается application/json."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    self.send_json(413, {"error": "Недопустимый размер запроса."})
                    return
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Ожидается объект с полем function.")
                if self.path == '/api/minimize':
                    result = solve(body.get('function'), model)
                else:
                    result = solve_system(body.get('variables'), body.get('functions'))
                    circuit = netlist(result['sheffer'], result['variables'])
                    timing = simulate(circuit, body.get('period', 12), body.get('t01', 2), body.get('t10', 3))
                    if self.path == '/api/timing.xlsx':
                        self.send_bytes(200, export_timing(timing), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                        return
                    if self.path == '/api/timing':
                        result = timing
                    else:
                        result.update(circuit=circuit, timing=timing)
            except (ValueError, UnicodeError) as error:
                self.send_json(400, {"error": str(error)})
                return
            except RuntimeError as error:
                self.send_json(503, {'error': str(error)})
                return
            self.send_json(200, result)
    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    torch.set_num_threads(1)
    model = GroupModel.load() if MODEL_PATH.exists() else None
    if model is None:
        print("Модель отсутствует: доступен точный алгоритм. Для обучения: python train.py", flush=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(model))
    print(f"Откройте http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
