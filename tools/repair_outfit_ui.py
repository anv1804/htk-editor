#!/usr/bin/env python3
"""Local browser UI for the outfit sprite repair tool."""

from __future__ import annotations

import argparse
import base64
import io
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PIL import Image

from repair_outfit_sprite import repair_sheet


ROOT = Path(__file__).resolve().parent
UI_PATH = ROOT / "repair_outfit_ui.html"
MAX_REQUEST_BYTES = 32 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local outfit sprite repair UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def decode_image(data_url: str) -> Image.Image:
    if "," not in data_url:
        raise ValueError("Invalid image data")
    encoded = data_url.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise ValueError("Cannot read the uploaded image") from exc
    return image.convert("RGBA")


def encode_png(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def process_request(payload: dict[str, Any]) -> dict[str, Any]:
    rows = int(payload.get("rows", 7))
    cols = int(payload.get("cols", 4))
    colors = int(payload.get("colors", 32))
    skin_expand = int(payload.get("skinExpand", 1))
    threshold = float(payload.get("backgroundThreshold", 36))

    if not 1 <= rows <= 64 or not 1 <= cols <= 64:
        raise ValueError("Rows and columns must be between 1 and 64")
    if not 0 <= colors <= 256:
        raise ValueError("Palette colors must be between 0 and 256")
    if not 0 <= skin_expand <= 4:
        raise ValueError("Skin expansion must be between 0 and 4")

    base = decode_image(str(payload.get("base", "")))
    outfit = decode_image(str(payload.get("outfit", "")))
    repaired, frames = repair_sheet(
        base,
        outfit,
        rows=rows,
        cols=cols,
        colors=colors,
        background_threshold=threshold,
        skin_expand=skin_expand,
    )
    return {
        "image": encode_png(repaired),
        "width": repaired.width,
        "height": repaired.height,
        "frameCount": len(frames),
        "restoredPixels": sum(frame["restored_anatomy_pixels"] for frame in frames),
        "outlinedPixels": sum(frame["outlined_outfit_pixels"] for frame in frames),
    }


class RepairHandler(BaseHTTPRequestHandler):
    def send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            self.send_bytes(200, "text/html; charset=utf-8", UI_PATH.read_bytes())
            return
        if self.path == "/api/health":
            self.send_bytes(200, "application/json", b'{"ok":true}')
            return
        self.send_bytes(404, "text/plain; charset=utf-8", b"Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/repair":
            self.send_bytes(404, "application/json", b'{"error":"Not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("Upload is empty or larger than 32 MB")
            payload = json.loads(self.rfile.read(length))
            result = process_request(payload)
            body = json.dumps(result, separators=(",", ":")).encode("utf-8")
            self.send_bytes(200, "application/json", body)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            body = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_bytes(400, "application/json", body)
        except Exception as exc:
            body = json.dumps({"error": f"Processing failed: {exc}"}).encode("utf-8")
            self.send_bytes(500, "application/json", body)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[UI] {format % args}")


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), RepairHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Outfit Sprite Repair UI: {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
