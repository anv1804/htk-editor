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
import numpy as np

from repair_outfit_sprite import repair_sheet, build_base_profile, base_profile_identity, foreground_mask
from ui_forge import generate as generate_ui, export_zip as export_ui_zip


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
UI_PATH = ROOT / "repair_outfit_ui.html"
DIST_DIR = ROOT / "dist"
DEFAULT_BASE_PATH = PROJECT_ROOT / "assets" / "default-base.png"
DEFAULT_GREEN_BASE_PATH = PROJECT_ROOT / "assets" / "default-green-base.png"
DEFAULT_HEAD_BASE_PATH = PROJECT_ROOT / "assets" / "default-head-base.png"
DEFAULT_BODY_BASE_PATH = PROJECT_ROOT / "assets" / "default-body-base.png"
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
        if image.width * image.height > 4_194_304:
            raise ValueError('Sheet must contain at most 4 million pixels')
        image.load()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Cannot read the uploaded image") from exc
    return image.convert("RGBA")


def encode_png(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def analyze_base(payload):
    if not isinstance(payload, dict):
        raise ValueError('Request must be a JSON object')
    rows, cols = int(payload.get('rows',7)), int(payload.get('cols',4))
    if not 1 <= rows <= 64 or not 1 <= cols <= 64:
        raise ValueError('Rows and columns must be between 1 and 64')
    base = decode_image(str(payload.get('base','')))
    threshold = float(payload.get('backgroundThreshold',36))
    profile = build_base_profile(base,rows=rows,cols=cols,threshold=threshold)
    identity = base_profile_identity(base,rows,cols)
    return dict(profile=encode_png(profile),baseId=identity,width=base.width,height=base.height,
                rows=rows,cols=cols)


def process_request(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError('Request must be a JSON object')
    rows = int(payload.get("rows", 7))
    cols = int(payload.get("cols", 4))
    colors = int(payload.get("colors", 32))
    skin_expand = int(payload.get("skinExpand", 0))
    threshold = float(payload.get("backgroundThreshold", 36))
    cleanup = int(payload.get('cleanup', 3))
    paint = int(payload.get('paint', 4))
    outline = payload.get('outline', True)
    composition = payload.get('composition','layers')
    logo_cleanup = payload.get('logoCleanup', 'auto')
    if not isinstance(outline, bool):
        raise ValueError('Outline must be true or false')

    if not 1 <= rows <= 64 or not 1 <= cols <= 64:
        raise ValueError("Rows and columns must be between 1 and 64")
    if not -1 <= colors <= 256:
        raise ValueError("Palette colors must be -1 (automatic) or between 0 and 256")
    if not 0 <= skin_expand <= 4:
        raise ValueError("Skin expansion must be between 0 and 4")

    base = decode_image(str(payload.get("base", "")))
    outfit = decode_image(str(payload.get("outfit", "")))
    green_base = decode_image(payload['greenBase']) if payload.get('greenBase') else None
    head_base = decode_image(payload['headBase']) if payload.get('headBase') else None
    body_base = decode_image(payload['bodyBase']) if payload.get('bodyBase') else None
    green_source = 'uploaded' if green_base is not None else 'none'
    head_source = 'uploaded' if head_base is not None else 'none'
    body_source = 'uploaded' if body_base is not None else 'none'
    if green_base is None and (rows, cols) == (7, 4) and DEFAULT_BASE_PATH.is_file() and DEFAULT_GREEN_BASE_PATH.is_file():
        with Image.open(DEFAULT_BASE_PATH) as bundled_base:
            if base.size == bundled_base.size and np.array_equal(
                    np.asarray(base), np.asarray(bundled_base.convert('RGBA'))):
                with Image.open(DEFAULT_GREEN_BASE_PATH) as bundled_green:
                    green_base = bundled_green.convert('RGBA')
                green_source = 'bundled'
    if head_base is None and (rows, cols) == (7, 4) and DEFAULT_BASE_PATH.is_file() and DEFAULT_HEAD_BASE_PATH.is_file():
        with Image.open(DEFAULT_BASE_PATH) as bundled_base:
            if base.size == bundled_base.size and np.array_equal(
                    np.asarray(base), np.asarray(bundled_base.convert('RGBA'))):
                with Image.open(DEFAULT_HEAD_BASE_PATH) as bundled_head:
                    head_base = bundled_head.convert('RGBA')
                head_source = 'bundled'
    if body_base is None and (rows, cols) == (7, 4) and DEFAULT_BASE_PATH.is_file() and DEFAULT_BODY_BASE_PATH.is_file():
        with Image.open(DEFAULT_BASE_PATH) as bundled_base:
            if base.size == bundled_base.size and np.array_equal(
                    np.asarray(base), np.asarray(bundled_base.convert('RGBA'))):
                with Image.open(DEFAULT_BODY_BASE_PATH) as bundled_body:
                    body_base = bundled_body.convert('RGBA')
                body_source = 'bundled'
    if max(base.width*base.height, outfit.width*outfit.height,
           green_base.width*green_base.height if green_base else 0,
           head_base.width*head_base.height if head_base else 0,
           body_base.width*body_base.height if body_base else 0) > 4_194_304:
        raise ValueError('Sheet must contain at most 4 million pixels')
    def merge_memory(current, saved):
        active=decode_image(payload[current]) if payload.get(current) else None
        memory=decode_image(payload[saved]) if payload.get(saved) else None
        for image in (active,memory):
            if image is not None and image.size != base.size:
                raise ValueError('Saved corrections must match the sheet dimensions')
        if memory is None:
            return active,0
        merged=np.array(memory)
        if current == 'retouch' and payload.get('overrides'):
            corrections=decode_image(payload['overrides'])
            if corrections.size != base.size:
                raise ValueError('Saved corrections must match the sheet dimensions')
            merged[np.asarray(corrections)[:,:,3]>=128]=0
        if active is not None:
            pixels=np.asarray(active); marked=pixels[:,:,3]>=128
            merged[marked]=pixels[marked]
        return Image.fromarray(merged),int((np.asarray(memory)[:,:,3]>=128).sum())
    overrides,remembered_mask=merge_memory('overrides','learnedOverrides')
    retouch,remembered_paint=merge_memory('retouch','learnedRetouch')
    logo_report = {}
    learning_report = {}
    repaired, frames, mask = repair_sheet(
        base,
        outfit,
        rows=rows,
        cols=cols,
        colors=colors,
        background_threshold=threshold,
        skin_expand=skin_expand,
        cleanup=cleanup,
        paint=paint,
        outline=outline,
        overrides=overrides,
        return_masks=True,
        accessories=True,
        composition=composition,
        logo_cleanup=logo_cleanup,
        logo_report=logo_report,
        learning_report=learning_report,
        lock_base=bool(payload.get('lockBase',True)),
        base_profile=decode_image(payload['baseProfile']) if payload.get('baseProfile') else None,
        retouch=retouch,
        green_base=green_base,
        head_base=head_base,
        body_base=body_base,
    )
    opaque_colors = len({p[:3] for p in repaired.get_flattened_data() if p[3]}) if hasattr(repaired, 'get_flattened_data') else len({p[:3] for p in repaired.getdata() if p[3]})
    outfit_layer = np.array(repaired)
    garment = np.all(np.asarray(mask)[:,:,:3] == [70,155,255],axis=2)
    garment |= np.all(np.asarray(mask)[:,:,:3] == [180,80,230],axis=2)
    headwear = np.all(np.asarray(mask)[:,:,:3] == [255,200,0],axis=2)
    head_layer = np.array(repaired)
    head_layer[~headwear] = 0
    outfit_layer[~garment] = 0
    # Export an actual bottom layer, including the body hidden under clothes.
    # The original source remains untouched. Explicit full-pixel erasures and
    # legacy reconstructed anatomy must also survive three-layer reassembly.
    base_layer = np.array(base.convert('RGBA'))
    cw, ch = base.width//cols, base.height//rows
    for y in range(0,base.height,ch):
        for x in range(0,base.width,cw):
            tile = base_layer[y:y+ch,x:x+cw]
            fg = foreground_mask(tile,threshold)
            tile[~fg] = 0
            tile[fg,3] = 255
    anatomy = np.all(np.asarray(mask)[:,:,:3] == [255,80,80],axis=2)
    anatomy |= np.all(np.asarray(mask)[:,:,:3] == [240,190,60],axis=2)
    base_layer[anatomy] = np.asarray(repaired)[anatomy]
    base_layer[np.asarray(repaired)[:,:,3] == 0] = 0
    return {
        'baseLayer': encode_png(Image.fromarray(base_layer)),
        'outfitLayer': encode_png(Image.fromarray(outfit_layer)),
        'headwearLayer': encode_png(Image.fromarray(head_layer)),
        "image": encode_png(repaired),
        "width": repaired.width,
        "height": repaired.height,
        "frameCount": len(frames),
        "restoredPixels": sum(frame["restored_anatomy_pixels"] for frame in frames),
        "outlinedPixels": sum(frame["outlined_outfit_pixels"] for frame in frames),
        'reconstructedPixels': sum(frame['reconstructed_skin_pixels'] for frame in frames),
        'removedPixels': sum(frame['removed_noise_pixels'] for frame in frames),
        'paletteColors': opaque_colors,
        'mask': encode_png(mask),
        'report': {'version': 6, 'assetVersion': 3, 'paletteColors': opaque_colors, 'baseColorsLocked': True,
                   'greenBaseSource': green_source,
                   'headBaseSource': head_source,
                   'bodyBaseSource': body_source,
                   'greenMarkerPixels': sum(frame['green_marker_pixels'] for frame in frames),
                   'processingRevision': 'separate-head-overlay-29',
                   'learning': {**learning_report,'rememberedMaskPixels':remembered_mask,
                                'rememberedPaintPixels':remembered_paint},
                   'logoCleanup': logo_report,
                   'layers': [
                       {'id':'base','name':'Base','order':0},
                       {'id':'outfit','name':'Outfit','order':1},
                       {'id':'headwear','name':'Tóc / băng cài / mũ','order':2}],
                   'skinRemoval': 'source-marker-aperture; diffuse-flesh-fallback; covered-equipment-veto',
                   'necklineProtection': 'marker-connected-shadows; enclosed-face-details; source-fabric-boundary',
                   'layerLayout': {'rows':rows,'cols':cols,'frameWidth':cw,'frameHeight':ch,
                                   'trimmed':False,'samePoseLayoutRequired':True,
                                   'hiddenRegionsReconstructed':False},
                   'composition': composition,
                   'layerPriority': 'headwear-over-outfit-over-base' if composition != 'pinned' else 'headwear-over-outfit; pinned-base-palms',
                   'settings': {'rows': rows, 'cols': cols, 'colors': colors, 'outline': outline,
                                'paint': paint, 'cleanup': cleanup, 'backgroundThreshold': threshold,
                                'logoCleanup': logo_cleanup},
                   'frames': frames},
    }


class RepairHandler(BaseHTTPRequestHandler):
    def send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        # Serve compiled Vite/TS app if present
        dist_index = DIST_DIR / "index.html"
        if self.path in ("/", "/index.html"):
            if dist_index.is_file():
                self.send_bytes(200, "text/html; charset=utf-8", dist_index.read_bytes())
                return
            self.send_bytes(200, "text/html; charset=utf-8", UI_PATH.read_bytes())
            return
        if self.path.startswith("/assets/"):
            dist_file = DIST_DIR / self.path.lstrip("/")
            if dist_file.is_file():
                mime = "text/javascript" if dist_file.suffix == ".js" else "text/css" if dist_file.suffix == ".css" else "image/svg+xml" if dist_file.suffix == ".svg" else "application/octet-stream"
                self.send_bytes(200, f"{mime}; charset=utf-8", dist_file.read_bytes())
                return
        if self.path == "/api/health":
            self.send_bytes(200, "application/json", b'{"ok":true,"version":6}')
            return
        if self.path == '/repair_outfit_ui.js':
            self.send_bytes(200, 'text/javascript; charset=utf-8', (ROOT / 'repair_outfit_ui.js').read_bytes())
            return
        if self.path == '/repair_outfit_editor.js':
            self.send_bytes(200, 'text/javascript; charset=utf-8', (ROOT / 'repair_outfit_editor.js').read_bytes())
            return
        if self.path == '/repair_outfit_ui.css':
            self.send_bytes(200, 'text/css; charset=utf-8', (ROOT / 'repair_outfit_ui.css').read_bytes())
            return
        if self.path == '/assets/default-base.png' and DEFAULT_BASE_PATH.is_file():
            self.send_bytes(200, 'image/png', DEFAULT_BASE_PATH.read_bytes())
            return
        if self.path == '/assets/default-green-base.png' and DEFAULT_GREEN_BASE_PATH.is_file():
            self.send_bytes(200, 'image/png', DEFAULT_GREEN_BASE_PATH.read_bytes())
            return
        if self.path == '/assets/default-head-base.png' and DEFAULT_HEAD_BASE_PATH.is_file():
            self.send_bytes(200, 'image/png', DEFAULT_HEAD_BASE_PATH.read_bytes())
            return
        if self.path == '/assets/default-body-base.png' and DEFAULT_BODY_BASE_PATH.is_file():
            self.send_bytes(200, 'image/png', DEFAULT_BODY_BASE_PATH.read_bytes())
            return
        self.send_bytes(404, "text/plain; charset=utf-8", b"Not found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/api/repair", "/api/base-profile", "/api/ui-forge/generate", "/api/ui-forge/export"):
            self.send_bytes(404, "application/json", b'{"error":"Not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("Upload is empty or larger than 32 MB")
            payload = json.loads(self.rfile.read(length))
            if self.path in ('/api/ui-forge/export', '/api/ui-forge/generate'):
                import importlib, sys
                if 'ui_segments' in sys.modules:
                    importlib.reload(sys.modules['ui_segments'])
                if 'ui_motifs' in sys.modules:
                    importlib.reload(sys.modules['ui_motifs'])
                if 'ui_forge' in sys.modules:
                    importlib.reload(sys.modules['ui_forge'])
                from ui_forge import generate as generate_ui, export_zip as export_ui_zip
            if self.path == '/api/ui-forge/export':
                self.send_bytes(200, 'application/zip', export_ui_zip(payload))
                return
            if self.path == '/api/ui-forge/generate':
                self.send_bytes(200, 'application/json', json.dumps(generate_ui(payload)).encode('utf-8'))
                return
            result = analyze_base(payload) if self.path == '/api/base-profile' else process_request(payload)
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
