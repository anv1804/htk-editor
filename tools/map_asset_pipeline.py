"""Native-size map asset cleanup, ZIP import/export. Pillow + NumPy only.

No generated outlines, resampling, global dark-color key, or inferred geometry.
All operations run in memory; uploaded archive paths are never extracted.
"""
from __future__ import annotations

import base64
from collections import deque
import io
import json
import math
from pathlib import PurePosixPath
import re
import zipfile

import numpy as np
from PIL import Image

MAX_PIXELS = 4_194_304
MAX_ITEM_PIXELS = 1_048_576
MAX_ITEMS = 512


def decode(data):
    try:
        if not isinstance(data, str) or not data.startswith('data:'):
            raise ValueError('Ảnh phải là dữ liệu PNG tải lên.')
        raw = base64.b64decode(data.split(',', 1)[1], validate=True)
        im = Image.open(io.BytesIO(raw))
        if im.width * im.height > MAX_PIXELS:
            raise ValueError('Ảnh vượt quá 4 triệu pixel.')
        im.load()
        return im.convert('RGBA')
    except (IndexError, OSError, TypeError) as exc:
        raise ValueError('Không đọc được ảnh tải lên.') from exc


def encode(im):
    out = io.BytesIO()
    im.save(out, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(out.getvalue()).decode('ascii')


def number(settings, key, default, lo, hi):
    value = float(settings.get(key, default))
    if not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'Thông số {key} phải từ {lo} đến {hi}.')
    return value


def options(raw):
    if not isinstance(raw, dict):
        raise ValueError('Thông số xử lý không hợp lệ.')
    low = int(number(raw, 'alphaLow', 110, 1, 255))
    high = int(number(raw, 'alphaHigh', 200, low, 255))
    mode = raw.get('alphaMode', 'hard')
    if mode not in ('hard', 'preserve'):
        raise ValueError('Chế độ alpha không hợp lệ.')
    colors = int(number(raw, 'colors', 0, 0, 256))
    if colors == 1:
        raise ValueError('Chọn giữ màu hoặc ít nhất 2 màu.')
    return dict(alphaLow=low, alphaHigh=high, alphaMode=mode, colors=colors,
                smooth=number(raw, 'smooth', 16, 0, 32),
                chroma=number(raw, 'chroma', 1.08, .5, 1.5),
                contrast=number(raw, 'contrast', 1.04, .5, 1.5))


def alpha_mask(alpha, low, high):
    keep = alpha >= high
    weak = (alpha >= low) & ~keep
    padded = np.pad(keep, 1)
    h, w = keep.shape
    adjacent = np.zeros_like(keep)
    for dy in range(3):
        for dx in range(3):
            adjacent |= padded[dy:dy+h, dx:dx+w]
    frontier = weak & adjacent
    keep |= frontier
    q = deque(zip(*np.nonzero(frontier)))
    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            yy, xx = y+dy, x+dx
            if 0 <= yy < h and 0 <= xx < w and weak[yy, xx] and not keep[yy, xx]:
                keep[yy, xx] = True
                q.append((yy, xx))
    return keep


def bilateral(rgb, mask, sigma):
    if sigma == 0:
        return rgb.astype(np.float32)
    center = rgb.astype(np.float32)
    p = np.pad(center, ((1, 1), (1, 1), (0, 0)), mode='edge')
    m = np.pad(mask, 1)
    h, w = mask.shape
    total = np.zeros_like(center)
    weights = np.zeros((h, w), np.float32)
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            n = p[1+dy:1+dy+h, 1+dx:1+dx+w]
            weight = np.exp(-((center-n)**2).sum(axis=2)/(2*sigma*sigma)-(dx*dx+dy*dy)/2)
            weight *= m[1+dy:1+dy+h, 1+dx:1+dx+w]
            total += n*weight[..., None]
            weights += weight
    return np.where(mask[..., None], total/np.maximum(weights[..., None], 1e-9), center)


def to_oklab(rgb):
    s = np.asarray(rgb, np.float32)/255
    linear = np.where(s <= .04045, s/12.92, ((s+.055)/1.055)**2.4)
    lms = linear @ np.array([[.4122214708, .5363325363, .0514459929],
                            [.2119034982, .6806995451, .1073969566],
                            [.0883024619, .2817188376, .6299787005]], np.float32).T
    return np.cbrt(lms) @ np.array([[.2104542553, .7936177850, -.0040720468],
                                  [1.9779984951, -2.4285922050, .4505937099],
                                  [.0259040371, .7827717662, -.8086757660]], np.float32).T


def from_oklab(lab):
    l, a, b = np.moveaxis(lab, -1, 0)
    lms = np.stack([l+.3963377774*a+.2158037573*b, l-.1055613458*a-.0638541728*b,
                    l-.0894841775*a-1.2914855480*b], axis=-1)**3
    linear = lms @ np.array([[4.0767416621, -3.3077115913, .2309699292],
                            [-1.2684380046, 2.6097574011, -.3413193965],
                            [-.0041960863, -.7034186147, 1.7076147010]], np.float32).T
    linear = np.clip(linear, 0, 1)
    s = np.where(linear <= .0031308, 12.92*linear, 1.055*linear**(1/2.4)-.055)
    return np.clip(np.rint(s*255), 0, 255).astype(np.uint8)


def learn_palette(samples, count):
    pixels = np.concatenate([rgb[alpha > 0] for rgb, alpha in samples])
    if not len(pixels):
        return np.array([[0, 0, 0]], dtype=np.uint8)
    pixels = pixels[::max(1, math.ceil(len(pixels)/262144))]
    p = Image.fromarray(pixels.reshape((-1, 1, 3))).quantize(
        colors=count, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    return np.array(p.getpalette(), np.uint8).reshape((-1, 3))[np.unique(np.asarray(p))]


def remap(rgb, mask, palette):
    result = rgb.copy()
    plab = to_oklab(palette)
    pixels = to_oklab(rgb[mask])
    out = np.empty((len(pixels), 3), np.uint8)
    for start in range(0, len(pixels), 2048):
        delta = pixels[start:start+2048, None, :]-plab[None, :, :]
        delta[..., 0] *= 1.2
        out[start:start+2048] = palette[np.argmin((delta*delta).sum(axis=2), axis=1)]
    result[mask] = out
    return result


def crop_image(im, crop):
    if crop is None:
        return im
    if not isinstance(crop, dict):
        raise ValueError('Khung cắt không hợp lệ.')
    x, y, w, h = [int(number(crop, k, -1, 0 if k in ('x', 'y') else 1, MAX_PIXELS)) for k in ('x', 'y', 'w', 'h')]
    if x+w > im.width or y+h > im.height:
        raise ValueError('Khung cắt nằm ngoài ảnh.')
    return im.crop((x, y, x+w, y+h))


def process(payload):
    if not isinstance(payload, dict):
        raise ValueError('Yêu cầu không hợp lệ.')
    items = payload.get('items', [])
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise ValueError('Chọn từ 1 đến 512 item.')
    opt = options(payload.get('settings', {}))
    prepared, total = [], 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Item không hợp lệ.')
        im = crop_image(decode(item.get('image')), item.get('crop'))
        total += im.width*im.height
        if im.width*im.height > MAX_ITEM_PIXELS or total > MAX_PIXELS:
            raise ValueError('Mỗi item tối đa 1 triệu pixel; mỗi lượt tối đa 4 triệu pixel.')
        src = np.array(im)
        alpha = src[..., 3].copy() if opt['alphaMode'] == 'preserve' else alpha_mask(
            src[..., 3], opt['alphaLow'], opt['alphaHigh']).astype(np.uint8)*255
        if item.get('overrides'):
            edits = np.array(decode(item['overrides']))
            if edits.shape != src.shape:
                raise ValueError('Lớp sửa khuôn phải cùng kích thước item.')
            touched = edits[..., 3] > 0
            alpha[touched & (edits[..., 0] > edits[..., 1])] = 0
            alpha[touched & (edits[..., 1] > edits[..., 0])] = 255
        mask = alpha > 0
        rgb = bilateral(src[..., :3], mask, opt['smooth'])
        if opt['chroma'] != 1 or opt['contrast'] != 1:
            lab = to_oklab(rgb)
            lab[..., 0] = np.clip((lab[..., 0]-.5)*opt['contrast']+.5, 0, 1)
            lab[..., 1:] *= opt['chroma']
            rgb = from_oklab(lab)
        else:
            rgb = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
        prepared.append((item, src, rgb, alpha))
    palette = learn_palette([(rgb, alpha) for _, _, rgb, alpha in prepared], opt['colors']) if opt['colors'] else None
    results = []
    for item, src, rgb, alpha in prepared:
        mask = alpha > 0
        if palette is not None:
            rgb = remap(rgb, mask, palette)
        rgb[~mask] = 0
        out = np.dstack([rgb, alpha])
        results.append(dict(id=str(item.get('id', '')), name=str(item.get('name', 'item'))[:160],
            image=encode(Image.fromarray(out)), original=encode(Image.fromarray(src)),
            mask=encode(Image.fromarray(alpha)), width=out.shape[1], height=out.shape[0],
            report=dict(colors=int(len(np.unique(rgb[mask], axis=0))), visiblePixels=int(mask.sum()),
                        partialAlphaPixels=int(((alpha > 0) & (alpha < 255)).sum()),
                        addedPixels=int((mask & (src[..., 3] == 0)).sum()),
                        removedPixels=int((~mask & (src[..., 3] > 0)).sum()))))
    return dict(items=results, settings=opt, palette=palette.tolist() if palette is not None else None)


def extract_crop(payload):
    if not isinstance(payload, dict):
        raise ValueError('Yêu cầu không hợp lệ.')
    im = crop_image(decode(payload.get('image')), payload.get('crop'))
    if im.width*im.height > MAX_ITEM_PIXELS:
        raise ValueError('Chọn một item nhỏ hơn 1 triệu pixel.')
    return dict(image=encode(im), width=im.width, height=im.height)


def import_zip(payload):
    if not isinstance(payload, dict):
        raise ValueError('Yêu cầu không hợp lệ.')
    try:
        raw = base64.b64decode(payload.get('archive', '').split(',', 1)[1], validate=True)
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except (ValueError, IndexError, zipfile.BadZipFile) as exc:
        raise ValueError('Không đọc được ZIP.') from exc
    with archive as z:
        files = z.infolist()
        if len(files) > 2048 or sum(f.file_size for f in files) > 128*1024*1024:
            raise ValueError('ZIP quá lớn: tối đa 128 MB sau giải nén.')
        pngs = [f for f in files if f.filename.lower().endswith('.png') and not f.is_dir()]
        item_files = [f for f in pngs if '/items/' in '/'+f.filename or '/output/' in '/'+f.filename]
        pngs = item_files or [f for f in pngs if PurePosixPath(f.filename).name not in ('preview_sheet.png', 'palette.png')]
        if not 1 <= len(pngs) <= MAX_ITEMS:
            raise ValueError('ZIP phải chứa từ 1 đến 512 PNG item.')
        manifest = {}
        mf = next((f for f in files if PurePosixPath(f.filename).name == 'manifest.json'), None)
        if mf:
            try:
                manifest = json.loads(z.read(mf))
                if not isinstance(manifest, dict):
                    manifest = {}
            except (ValueError, UnicodeDecodeError):
                manifest = {}
        sheet = decode(payload['sheet']) if payload.get('sheet') else None
        if sheet and manifest.get('source_size') != list(sheet.size):
            raise ValueError('Sheet phải đúng source_size trong manifest của ZIP. Bỏ chọn dùng sheet để nhập PNG có sẵn.')
        records = {r.get('file'): r for r in manifest.get('assets', []) if isinstance(r, dict)}
        results, total = [], 0
        for i, entry in enumerate(sorted(pngs, key=lambda f: f.filename)):
            try:
                im = Image.open(io.BytesIO(z.read(entry)))
                if im.width*im.height > MAX_ITEM_PIXELS:
                    raise ValueError('Item trong ZIP vượt quá 1 triệu pixel.')
                im = im.convert('RGBA')
            except OSError as exc:
                raise ValueError(f'PNG không hợp lệ: {entry.filename}') from exc
            name = PurePosixPath(entry.filename).name
            record = records.get(name, records.get(entry.filename, {}))
            source_box, from_sheet = None, False
            if sheet is not None:
                box = record.get('source_box')
                if not isinstance(box, list) or len(box) != 4:
                    raise ValueError(f'Thiếu source_box cho {name}.')
                x0, y0, x1, y1 = [int(v) for v in box]
                # Known source manifest stores a one-pixel outer margin.
                def inset(lo, hi, size, extent):
                    delta = hi-lo-size
                    if delta == 0:
                        return lo, hi
                    if delta == 2:
                        return lo+1, hi-1
                    if delta == 1 and lo == 0:
                        return lo, hi-1
                    if delta == 1 and hi == extent:
                        return lo+1, hi
                    raise ValueError(f'Khung nguồn và PNG không cùng kích thước: {name}.')
                ax, bx = inset(x0, x1, im.width, sheet.width)
                ay, by = inset(y0, y1, im.height, sheet.height)
                source_box = [ax, ay, bx, by]
                a, b, c, d = source_box
                im = crop_image(sheet, dict(x=a, y=b, w=c-a, h=d-b))
                from_sheet = True
            total += im.width*im.height
            if total > MAX_PIXELS:
                raise ValueError('Tổng item trong ZIP vượt quá 4 triệu pixel.')
            pivot = record.get('pivot', [im.width//2, im.height])
            if not isinstance(pivot, list) or len(pivot) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in pivot):
                pivot = [im.width//2, im.height]
            results.append(dict(id=f'import-{i}', name=name, image=encode(im), width=im.width,
                                height=im.height, sourceBox=source_box, fromSheet=from_sheet, pivot=pivot))
        return dict(items=results)


def export_zip(payload):
    if not isinstance(payload, dict):
        raise ValueError('Yêu cầu không hợp lệ.')
    items = payload.get('items', [])
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise ValueError('Chọn từ 1 đến 512 item để xuất.')
    out, records, total = io.BytesIO(), [], 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for i, item in enumerate(items):
            im = decode(item.get('image'))
            total += im.width*im.height
            if total > MAX_PIXELS:
                raise ValueError('Tổng ảnh xuất vượt quá 4 triệu pixel.')
            slug = re.sub(r'[^a-zA-Z0-9_-]+', '-', str(item.get('name', 'item'))).strip('-')[:80] or 'item'
            name = f'items/{i+1:03d}-{slug}.png'
            pivot = item.get('pivot', [im.width//2, im.height])
            if not isinstance(pivot, list) or len(pivot) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in pivot):
                raise ValueError('Điểm đặt chân không hợp lệ.')
            if not (0 <= pivot[0] <= im.width and 0 <= pivot[1] <= im.height):
                raise ValueError('Điểm đặt chân nằm ngoài item.')
            png = io.BytesIO()
            im.save(png, 'PNG')
            z.writestr(name, png.getvalue())
            records.append(dict(file=name, name=str(item.get('name', 'item'))[:160],
                                width=im.width, height=im.height, pivot=pivot))
        z.writestr('manifest.json', json.dumps(dict(version=1, nativeSize=True, resampled=False,
                    terrainConnectionsAuthored=False, assets=records), ensure_ascii=False, indent=2))
    return out.getvalue()
