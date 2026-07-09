from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .desktop_app import render_answer, render_entry, render_exact, render_hybrid, render_sloka


STATIC_DIR = Path(__file__).with_name("web_static")


def render_search(mode: str, query: str) -> dict[str, str]:
    mode = mode.strip().casefold()
    if mode == "entry":
        result = render_entry(query)
    elif mode == "exact":
        result = render_exact(query)
    elif mode == "sloka":
        result = render_sloka(query)
    elif mode == "hybrid":
        result = render_hybrid(query)
    elif mode == "answer":
        result = render_answer(query)
    else:
        raise ValueError("Unknown search mode.")
    return {
        "display_text": result.display_text,
        "copy_text": result.copy_text,
        "meta_text": "",
    }


def local_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return None


class VishnuWebHandler(BaseHTTPRequestHandler):
    server_version = "VishnusahasranamamWeb/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.write_json({"ok": True})
            return
        path = "index.html" if parsed.path in ("", "/") else unquote(parsed.path).lstrip("/")
        self.serve_static(path)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        path = "index.html" if parsed.path in ("", "/") else unquote(parsed.path).lstrip("/")
        self.serve_static(path, include_body=False)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/search":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            query = str(payload.get("query", "")).strip()
            mode = str(payload.get("mode", "entry"))
            if not query:
                self.write_json({"error": "Please type a nāma or phrase first."}, HTTPStatus.BAD_REQUEST)
                return
            self.write_json(render_search(mode, query))
        except ValueError as exc:
            self.write_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - server safety net
            self.write_json({"error": f"Search failed: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, relative_path: str, include_body: bool = True) -> None:
        if "/" in relative_path:
            parts = relative_path.split("/")
            if any(part in ("", ".", "..") for part in parts):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        target = (STATIC_DIR / relative_path).resolve()
        if not target.is_file() or STATIC_DIR.resolve() not in target.parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache" if target.name == "index.html" else "public, max-age=3600")
        self.end_headers()
        if include_body:
            self.wfile.write(data)

    def write_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> int:
    server = ThreadingHTTPServer((host, port), VishnuWebHandler)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Vishnusahasranamam web app: {url}", flush=True)
    lan_ip = local_ip()
    if host in ("0.0.0.0", "") and lan_ip:
        print(f"Same Wi-Fi device URL: http://{lan_ip}:{server.server_port}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Vishnusahasranamam PWA.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the app in the default browser.")
    args = parser.parse_args()
    return serve(args.host, args.port, args.open)


if __name__ == "__main__":
    raise SystemExit(main())
