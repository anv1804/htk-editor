"""Deterministic map-wide palette/cluster processing. Not semantic reconstruction.

Keeps source dimensions and alpha (unless the user selects hard alpha), learns a
shared source palette, protects strong details and refines weak color islands.
OpenCV accelerates local statistics; no model downloads or network calls.
"""
from __future__ import annotations

import base64
import io
import math
import time

import numpy as np
from PIL import Image

from map_asset_pipeline import to_oklab, from_oklab, encode

MAX_PIXELS = 16_777_216
MAX_SIDE = 8192


class Cancelled(Exception):
    pass


def options(raw):
    if not isinstance(raw, dict):
        raise ValueError('Thông số pixel không hợp lệ.')
    def integer(key, default, low, high):
        v = raw.get(key, default)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or int(v) != v or not low <= v <= high:
            raise ValueError(f'{key} phải là số nguyên từ {low} đến {high}.')
        return int(v)
    result = dict(colors=integer('colors', 128, 16, 256), grid=integer('grid', 1, 1, 4),
                  strength=integer('strength', 2, 1, 3), passes=integer('passes', 3, 1, 5))
    result['alpha'] = raw.get('alpha', 'preserve')
    if result['alpha'] not in ('preserve', 'hard'):
        raise ValueError('Alpha phải là preserve hoặc hard.')
    return result


def decode_source(src):
    if not isinstance(src, str) or not src.startswith('data:image/') or len(src) > 32 * 1024 * 1024:
        raise ValueError('Cần ảnh tải lên, tối đa 32 MB dữ liệu.')
    try:
        im = Image.open(io.BytesIO(base64.b64decode(src.split(',', 1)[1], validate=True)))
        if max(im.size) > MAX_SIDE or im.width * im.height > MAX_PIXELS:
            raise ValueError('Ảnh tối đa 16 triệu pixel, mỗi chiều tối đa 8192.')
        im.load()
        return np.array(im.convert('RGBA'))
    except (OSError, IndexError, Image.DecompressionBombError) as exc:
        raise ValueError('Không đọc được ảnh nguồn.') from exc


def reference_profile(rgba, cv):
    rgb = rgba[..., :3].astype(np.float32)
    mask = (rgba[..., 3] >= 200).astype(np.float32)
    luma = rgb @ np.array([.2126, .7152, .0722], np.float32)
    weight = cv.boxFilter(mask, -1, (3, 3), normalize=True)
    local = cv.boxFilter(luma * mask, -1, (3, 3), normalize=True) / np.maximum(weight, 1e-5)
    sample = np.abs(luma - local)[(mask > 0) & (weight > .9)]
    # A modest bounded signal, not a quality score or exact style transfer.
    contrast = float(np.percentile(sample, 70)) if len(sample) else 8.0
    return {'localContrast': round(contrast, 3), 'detailBias': float(np.clip(contrast / 12, .7, 1.3))}


def grid_source(src, grid):
    if grid == 1:
        return src.copy()
    # Pick a real source pixel per cell; no interpolation-generated shades.
    h, w = src.shape[:2]
    ys = np.minimum(np.arange(0, h, grid) + grid // 2, h - 1)
    xs = np.minimum(np.arange(0, w, grid) + grid // 2, w - 1)
    return src[np.ix_(ys, xs)].copy()


def local_prepare(src, opt, bias, cv, check):
    rgb = src[..., :3].copy(); alpha = src[..., 3]
    mask = alpha > 0
    # Work inside opaque regions only: no background-color bleeding at cutouts.
    opaque = (alpha >= 200).astype(np.uint8)
    interior = cv.erode(opaque, np.ones((3, 3), np.uint8), borderType=cv.BORDER_CONSTANT, borderValue=0).astype(bool)
    filtered = rgb.copy()
    for _ in range(opt['strength']):
        check()
        smooth = cv.bilateralFilter(filtered, 5, 14 + 5 * opt['strength'], 2)
        filtered[interior] = smooth[interior]
    luma = rgb.astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    mean = cv.boxFilter(luma, -1, (3, 3), normalize=True)
    contrast = np.abs(luma - mean)
    # Protect tiny highlights, ink strokes and branches from majority filtering.
    protected = (contrast > max(12, 22 - 5 * bias)) & mask
    filtered[protected] = rgb[protected]
    # Strengthen only an already-dark side of a local edge, not every color border.
    shadow = np.clip((mean - luma - 9) / 24, 0, 1) * interior
    factor = (1 - shadow * (.025 + .015 * opt['strength']))[..., None]
    filtered = np.clip(np.rint(filtered.astype(np.float32) * factor), 0, 255).astype(np.uint8)
    filtered[~mask] = 0
    return filtered, protected


def palette_from(samples, count, check):
    nonempty = [s for s in samples if len(s)]
    if not nonempty:
        return np.array([[0, 0, 0]], np.uint8)
    pixels = np.concatenate(nonempty)
    pixels = pixels[::max(1, math.ceil(len(pixels) / 65536))]
    check()
    p = Image.fromarray(pixels.reshape((-1, 1, 3))).quantize(colors=count, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    initial = np.array(p.getpalette(), np.uint8).reshape((-1, 3))[np.unique(np.asarray(p))]
    # Refine centers in perceptual space, using bounded memory and deterministic seeds.
    lab = to_oklab(pixels); centers = to_oklab(initial)
    for _ in range(3):
        sums = np.zeros_like(centers); counts = np.zeros(len(centers), np.int64)
        for start in range(0, len(lab), 2048):
            check(); block = lab[start:start + 2048]
            delta = block[:, None] - centers[None]; delta[..., 0] *= 1.15
            labels = np.argmin(np.sum(delta * delta, axis=2), axis=1)
            np.add.at(sums, labels, block); counts += np.bincount(labels, minlength=len(centers))
        valid = counts > 0; centers[valid] = sums[valid] / counts[valid, None]
    return np.unique(from_oklab(centers), axis=0)


def palette_samples(visible, cv):
    if not len(visible):
        return visible
    uniform = visible[::max(1, math.ceil(len(visible) / 16384))]
    # Small red lanterns and pink lotus flowers must survive a blue/green map.
    # Oversample existing rare hue families, never import unrelated reference hues.
    hsv = cv.cvtColor(visible.reshape((-1, 1, 3)), cv.COLOR_RGB2HSV).reshape((-1, 3))
    vivid = (hsv[:, 1] >= 96) & (hsv[:, 2] >= 80)
    samples = [uniform]
    for hue in range(15):
        group = visible[vivid & (hsv[:, 0] // 12 == hue)]
        if len(group):
            group = group[::max(1, math.ceil(len(group) / 192))]
            samples.append(np.tile(group, (3, 1)))
    return np.concatenate(samples)


def assign(rgb, mask, palette, check):
    labels = np.zeros(mask.shape, np.uint16)
    pixels = to_oklab(rgb[mask]); colors = to_oklab(palette)
    mapped = np.zeros(len(pixels), np.uint16)
    for start in range(0, len(pixels), 2048):
        check(); delta = pixels[start:start + 2048, None] - colors[None]
        delta[..., 0] *= 1.15
        mapped[start:start + 2048] = np.argmin(np.sum(delta * delta, axis=2), axis=1)
    labels[mask] = mapped
    return labels


def refine_clusters(labels, rgb, mask, protected, palette, rounds, strength, cv, check, progress):
    lab = to_oklab(rgb); plab = to_oklab(palette)
    h, w = mask.shape
    # Synchronous, color-aware voting: only merge small, low-contrast components.
    for iteration in range(rounds):
        check(); small = np.zeros((h, w), bool)
        for color in np.unique(labels[mask]):
            check(); binary = ((labels == color) & mask).astype(np.uint8)
            _, components, stats, _ = cv.connectedComponentsWithStats(binary, connectivity=4)
            sizes = stats[:, cv.CC_STAT_AREA]
            flags = sizes <= (1 + strength * 2); flags[0] = False
            small |= flags[components]
        candidates = small & ~protected & mask
        if not candidates.any():
            break
        padded = np.pad(labels, 1, mode='edge'); mp = np.pad(mask, 1)
        best = labels.copy(); best_cost = np.sum((plab[labels] - lab) ** 2, axis=2)
        # Reward same-color neighbors while retaining the original material color.
        best_cost -= .0007 * strength * sum((padded[dy:dy+h, dx:dx+w] == labels) & mp[dy:dy+h, dx:dx+w] for dy, dx in ((0,1),(2,1),(1,0),(1,2)))
        for dy, dx in ((0,1),(2,1),(1,0),(1,2)):
            check(); neighbor = padded[dy:dy+h, dx:dx+w]
            color_delta = np.sum((plab[neighbor] - plab[labels]) ** 2, axis=2)
            votes = sum((padded[yy:yy+h, xx:xx+w] == neighbor) & mp[yy:yy+h, xx:xx+w] for yy, xx in ((0,1),(2,1),(1,0),(1,2)))
            cost = np.sum((plab[neighbor] - lab) ** 2, axis=2) - .0007 * strength * votes
            choose = candidates & mp[dy:dy+h, dx:dx+w] & (votes >= 2) & (color_delta < .008) & (cost < best_cost)
            best[choose] = neighbor[choose]; best_cost[choose] = cost[choose]
        if np.array_equal(best, labels):
            break
        labels = best
        progress(iteration + 1, rounds)
    return labels


def process(payload, progress=None, cancelled=None, deadline_seconds=300):
    try:
        import cv2 as cv
    except ImportError as exc:
        raise ValueError('Cần OpenCV: cài dependencies trong tools/requirements-map.txt rồi khởi động lại server.') from exc
    if not isinstance(payload, dict):
        raise ValueError('Yêu cầu không hợp lệ.')
    opt = options(payload.get('settings', {})); items = payload.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 128:
        raise ValueError('Chọn từ 1 đến 128 ảnh hoặc layer.')
    ids = set(); total = 0; start_time = time.monotonic()
    def check():
        if cancelled and cancelled():
            raise Cancelled('Đã hủy; ảnh nguồn không thay đổi.')
        if time.monotonic() - start_time > deadline_seconds:
            raise TimeoutError('Đã chạm giới hạn 5 phút. Chia nhỏ bộ ảnh hoặc giảm số lượt tinh chỉnh.')
    def report(p, message):
        check()
        if progress:
            progress(int(p), message)
    profile = {'detailBias': 1.0}
    if payload.get('reference'):
        report(1, 'Đọc mẫu nét vẽ…'); ref = decode_source(payload['reference']); profile = reference_profile(ref, cv); del ref
    prepared = []; samples = []
    for index, item in enumerate(items):
        check()
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not 1 <= len(item['id']) <= 200 or item['id'] in ids:
            raise ValueError('Mỗi ảnh cần ID riêng, tối đa 200 ký tự.')
        ids.add(item['id']); src = decode_source(item.get('image')); h, w = src.shape[:2]; total += w * h
        if total > MAX_PIXELS:
            raise ValueError('Mỗi lượt xử lý tối đa 16 triệu pixel; hãy chia nhỏ bộ layer.')
        report(3 + 22 * index / len(items), f'Phân tích ảnh {index+1}/{len(items)}: {item.get("name", "map")}')
        reduced = grid_source(src, opt['grid']); rgb, protected = local_prepare(reduced, opt, profile['detailBias'], cv, check)
        visible = rgb[reduced[..., 3] > 0]
        samples.append(palette_samples(visible, cv))
        prepared.append((item, (w, h), reduced[..., 3], rgb, protected))
    report(26, 'Học bảng màu chung, cân bằng màu của các vật liệu…')
    palette = palette_from(samples, opt['colors'], check)
    results = []
    for index, (item, size, alpha, rgb, protected) in enumerate(prepared):
        base = 32 + 62 * index / len(items); span = 62 / len(items)
        report(base, f'Gom mảng màu {index+1}/{len(items)}…')
        mask = alpha > 0; labels = assign(rgb, mask, palette, check)
        labels = refine_clusters(labels, rgb, mask, protected, palette, opt['passes'], opt['strength'], cv, check,
            lambda done, rounds: report(base + span * (.4 + .5 * done / rounds), f'Tinh chỉnh cụm ảnh {index+1}/{len(items)} · lượt {done}/{rounds}'))
        color = palette[labels].copy(); color[~mask] = 0
        out_alpha = np.where(alpha >= 110, 255, 0).astype(np.uint8) if opt['alpha'] == 'hard' else alpha.copy()
        output = np.dstack([color, out_alpha]); grid = opt['grid']
        if grid > 1:
            output = np.repeat(np.repeat(output, grid, axis=0), grid, axis=1)[:size[1], :size[0]]
        output[output[..., 3] == 0, :3] = 0
        check(); result_image = Image.fromarray(output)
        report(base + span * .98, f'Đóng gói ảnh {index+1}/{len(items)}…')
        results.append({'id': item['id'], 'name': str(item.get('name', 'map'))[:200], 'width': size[0], 'height': size[1],
                        'image': encode(result_image), 'colors': int(len(np.unique(labels[mask]))),
                        'partialAlphaPixels': int(((output[..., 3] > 0) & (output[..., 3] < 255)).sum())})
    report(100, 'Hoàn tất. So sánh với ảnh gốc trước khi áp dụng.')
    return {'items': results, 'settings': opt, 'palette': palette.tolist(), 'referenceProfile': profile,
            'elapsedSeconds': round(time.monotonic() - start_time, 2), 'semanticLayersCreated': False,
            'method': 'perceptual-palette-cluster-refinement',
            'note': 'Gom cụm màu theo ảnh nguồn; không vẽ bù phần bị che và không tự chứng nhận chất lượng pixel art.'}
