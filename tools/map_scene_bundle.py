"""Read a synchronized map package without resampling or extracting archive paths."""
import base64
import binascii
import io
import json
from pathlib import PurePosixPath
import zipfile

from PIL import Image


def safe_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError('Đường dẫn gói map không hợp lệ.')
    if value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Đường dẫn gói map không hợp lệ.')
    return value


def import_bundle(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('archive'), str):
        raise ValueError('Cần ZIP chứa layout.json.')
    try:
        raw = base64.b64decode(payload['archive'].split(',', 1)[1], validate=True)
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (ValueError, IndexError, binascii.Error, zipfile.BadZipFile) as exc:
        raise ValueError('Không đọc được ZIP map.') from exc
    with archive as z:
        files = z.infolist()
        if len(files) > 2048 or sum(f.file_size for f in files) > 256 * 1024 * 1024:
            raise ValueError('ZIP map vượt giới hạn giải nén.')
        manifests = [f for f in files if not f.is_dir() and PurePosixPath(f.filename).name == 'layout.json' and not f.filename.startswith('__MACOSX/')]
        if len(manifests) != 1 or manifests[0].file_size > 1048576:
            raise ValueError('ZIP cần một layout.json, tối đa 1 MB.')
        manifest = manifests[0]
        safe_path(manifest.filename)
        base = manifest.filename[:-len('layout.json')]
        try:
            layout = json.loads(z.read(manifest))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError('Layout map không hợp lệ.') from exc
        if not isinstance(layout, dict) or not isinstance(layout.get('layers'), list) or not isinstance(layout.get('objects', []), list):
            raise ValueError('Layout cần danh sách layers và objects.')
        entries = layout['layers'] + layout.get('objects', [])
        if not 1 <= len(entries) <= 512:
            raise ValueError('Gói map cần từ 1 đến 512 ảnh tham chiếu.')
        images, pixels = {}, 0
        names = [f.filename for f in files]
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('Mục trong layout không hợp lệ.')
            path = safe_path(entry.get('file'))
            if path in images:
                continue
            if names.count(base + path) != 1:
                raise ValueError(f'Thiếu hoặc trùng file: {path}')
            raw_image = z.read(base + path)
            try:
                with Image.open(io.BytesIO(raw_image)) as image:
                    if image.format != 'PNG' or max(image.size) > 8192 or image.width * image.height > 16777216:
                        raise ValueError('Mỗi PNG tối đa 16 triệu pixel, mỗi chiều tối đa 8192.')
                    pixels += image.width * image.height
                    if pixels > 67108864:
                        raise ValueError('Tổng ảnh vượt 64 triệu pixel.')
                    image.load()
            except (OSError, Image.DecompressionBombError) as exc:
                raise ValueError(f'Ảnh không hợp lệ: {path}') from exc
            # Keep the original PNG bytes, including palette and alpha.
            images[path] = 'data:image/png;base64,' + base64.b64encode(raw_image).decode('ascii')
        return {'layout': layout, 'images': images}
