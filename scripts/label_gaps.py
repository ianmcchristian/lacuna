"""Mark the real gaps in your own shelf photos, for scripts/evaluate_real.py.

Usage: uv run python scripts/label_gaps.py samples/real

Opens a local page. Drag a box over each hole, then mark the photo done.
Labels save as you go to <folder>/gaps.json, as fractions of the upright photo,
so they don't depend on the resolution the photo is scored at.
"""

import argparse
import contextlib
import json
import webbrowser
from functools import cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from lacuna.imaging import encode_jpeg, fit_within, read_image

PAGE = Path(__file__).with_suffix(".html")
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp"}
DISPLAY_SIDE = 1600


def labels_path(folder: Path) -> Path:
    return folder / "gaps.json"


def load_labels(folder: Path) -> dict[str, dict[str, object]]:
    path = labels_path(folder)
    return json.loads(path.read_text()) if path.exists() else {}


def make_handler(folder: Path) -> type[BaseHTTPRequestHandler]:
    photos = sorted(p.name for p in folder.iterdir() if p.suffix.lower() in PHOTO_TYPES)

    @cache
    def display_jpeg(name: str) -> bytes:
        image = read_image(folder / name)
        if image is None:
            raise ValueError(f"can't read {name}")
        return encode_jpeg(fit_within(image, DISPLAY_SIDE))

    class Handler(BaseHTTPRequestHandler):
        def send(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def photo_name(self, prefix: str) -> str | None:
            name = unquote(self.path.removeprefix(prefix))
            return name if name in photos else None

        def do_GET(self) -> None:
            if self.path == "/":
                self.send(PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/photos":
                body = {"photos": photos, "labels": load_labels(folder)}
                self.send(json.dumps(body).encode(), "application/json")
            elif name := self.photo_name("/photo/"):
                self.send(display_jpeg(name), "image/jpeg")
            else:
                self.send(b"not found", "text/plain", HTTPStatus.NOT_FOUND)

        def do_PUT(self) -> None:
            name = self.photo_name("/api/labels/")
            if name is None:
                self.send(b"not found", "text/plain", HTTPStatus.NOT_FOUND)
                return
            entry = json.loads(self.rfile.read(int(self.headers["content-length"])))
            labels = load_labels(folder)
            labels[name] = {"done": bool(entry["done"]), "gaps": entry["gaps"]}
            tmp = labels_path(folder).with_suffix(".tmp")
            tmp.write_text(json.dumps(labels, indent=1, sort_keys=True) + "\n")
            tmp.replace(labels_path(folder))  # never leave a half-written file
            self.send(b"{}", "application/json")

        def log_message(self, format: str, *args: object) -> None:
            pass  # quiet

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.folder))
    url = f"http://127.0.0.1:{args.port}/"
    print(f"labeling {args.folder} at {url} (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()


if __name__ == "__main__":
    main()
