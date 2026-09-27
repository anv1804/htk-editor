"""Conservative, local restoration of Gemini's visible corner overlay.

Only RGB is unblended: no erasing, inpainting, or silhouette changes. Assets and
their licenses are in assets/gemini. A match must improve the measured edge
signal; a corner position alone is never evidence of a watermark.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image


ASSETS = Path(__file__).resolve().parent / 'assets' / 'gemini'


@lru_cache(maxsize=96)
def alpha_template(name, size):
    if name == 'bg_36_v2.bin':
        alpha = np.fromfile(ASSETS / name, dtype='<f4').reshape(36, 36)
    else:
        with Image.open(ASSETS / name) as image:
            alpha = np.asarray(image.convert('RGB'), dtype=np.float32).max(axis=2) / 255
    # The calibration captures contain a small background noise floor.
    alpha[alpha <= 3 / 255] = 0
    if alpha.shape != (size, size):
        alpha = np.asarray(Image.fromarray(alpha).resize((size, size), Image.Resampling.LANCZOS))
    alpha = np.clip(alpha, 0, .8)
    alpha[alpha <= 3 / 255] = 0
    return alpha


def candidates(width, height):
    """Known margins, plus uniformly reduced exports. Never scan every sprite."""
    profiles = [('bg_48.png', 48, 32), ('bg_48.png', 48, 96),
                ('bg_96.png', 96, 64), ('bg_96_20260520.png', 96, 192),
                ('bg_36_v2.bin', 36, 96)]
    long_side = max(width, height)
    if long_side <= 2048:
        short_side = min(width, height)
        reference = 2752 if short_side >= 566 else (2816 if short_side >= 550 else 2848)
        profiles.append(('bg_36_v2.bin', 36, round(192 * long_side / reference)))
    scales = {1.0}
    if long_side < 1536:
        scales.update(long_side / n for n in (768, 1024, 1344, 1536, 1792, 2048, 2304, 2816, 3072))
    seen = set()
    for name, native, margin in profiles:
        for scale in sorted(scales):
            size, gap = round(native * scale), round(margin * scale)
            if size < 7 or size > min(width, height) * .22:
                continue
            x, y = width - gap - size, height - gap - size
            if x < width * .65 or y < height * .65:
                continue
            key = (name, size, x, y)
            if key not in seen:
                seen.add(key)
                yield key


def match_score(patch, alpha):
    """Test the overlay's gradient in log-distance from white.

    log(255-observed) = log(255-original) + log(1-alpha). Texture edges
    are robustly capped so they cannot provide evidence just by being bright.
    Multiple edges and both axes must agree; clipping is a rejection.
    """
    rgb = patch[:, :, :3].astype(np.float32)
    distance = 255 - rgb
    log_rgb = np.log(np.maximum(distance, 1))
    log_alpha = np.log1p(-alpha)
    errors, original_errors, slopes = [], [], []
    axis_counts = []
    for axis in (0, 1):
        observed = np.diff(log_rgb, axis=axis)
        expected = np.diff(log_alpha, axis=axis)
        if axis == 0:
            valid = (distance[:-1] > 30) & (distance[1:] > 30)
            opaque = (patch[:-1, :, 3] == 255) & (patch[1:, :, 3] == 255)
        else:
            valid = (distance[:, :-1] > 30) & (distance[:, 1:] > 30)
            opaque = (patch[:, :-1, 3] == 255) & (patch[:, 1:, 3] == 255)
        valid &= opaque[:, :, None] & (np.abs(expected[:, :, None]) > .035)
        # RGB channels of a white logo must move together.
        count = int(np.count_nonzero(valid.any(axis=2)))
        axis_counts.append(count)
        e = np.broadcast_to(expected[:, :, None], observed.shape)[valid]
        o = observed[valid]
        original_errors.extend(np.minimum(np.abs(o), .3))
        errors.extend(np.minimum(np.abs(o - e), .3))
        slopes.extend(o / e)
    if min(axis_counts) < 4 or sum(axis_counts) < max(14, alpha.shape[0] // 2):
        return 0.0
    before, after = float(np.mean(original_errors)), float(np.mean(errors))
    slope = float(np.median(slopes))
    if before < .02 or not .55 < slope < 1.45:
        return 0.0
    active = (alpha > .03) & (patch[:, :, 3] == 255)
    restored = (rgb - alpha[:, :, None] * 255) / (1 - alpha[:, :, None])
    if not active.any() or np.mean((restored[active] < -5).any(axis=1)) > .03:
        return 0.0
    return max(0.0, 1 - after / before)


def restore_corner_logo(image, *, mode='auto', protected=None):
    if mode not in ('auto', 'off'):
        raise ValueError('Gemini logo mode must be auto or off')
    report = {'mode': mode, 'status': 'disabled' if mode == 'off' else 'not_detected',
              'correctedPixels': 0, 'regions': []}
    if mode == 'off':
        return image, report
    rgba = np.asarray(image.convert('RGBA'))
    h, w = rgba.shape[:2]
    best = None
    for name, size, x, y in candidates(w, h):
        alpha = alpha_template(name, size)
        # Exported sheets may have been resized and rounded at a different
        # stage from the logo. A 4px anchor discrepancy is large at sprite
        # resolution; test a bounded coarse neighborhood before rejecting it.
        shifts = (-4,-2,0,2,4) if size <= 24 else (0,)
        for dy in shifts:
            for dx in shifts:
                cx,cy=x+dx,y+dy
                if cx < 0 or cy < 0 or cx+size > w or cy+size > h:
                    continue
                score = match_score(rgba[cy:cy+size, cx:cx+size], alpha)
                if best is None or score > best[0]:
                    best = (score, name, size, cx, cy)
    # Refine only a plausible anchor. Bounded search avoids matching arbitrary
    # bright clothing details elsewhere in the sheet.
    if best is None or best[0] < .12:
        return image, report
    _, name, size, bx, by = best
    alpha = alpha_template(name, size)
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            x, y = bx + dx, by + dy
            if x < 0 or y < 0 or x + size > w or y + size > h:
                continue
            score = match_score(rgba[y:y+size, x:x+size], alpha)
            if score > best[0]:
                best = (score, name, size, x, y)
    score, name, size, x, y = best
    report['score'] = round(score, 4)
    # Small exports mix logo and source edge pixels during resampling. Their
    # gradient improvement is weaker even for the correct shape. Keep all
    # chroma/clipping/axis-support gates in match_score; only this scale-aware
    # acceptance threshold differs from the native-resolution detector.
    if score < (.25 if size <= 24 else .32):
        report['status'] = 'uncertain'
        return image, report
    output = rgba.copy()
    patch = output[y:y+size, x:x+size]
    rgb = patch[:, :, :3].astype(np.float32)
    fixed = np.rint(np.clip((rgb - alpha[:, :, None] * 255) / (1 - alpha[:, :, None]), 0, 255)).astype(np.uint8)
    affected = (alpha > 0) & (patch[:, :, 3] == 255) & np.any(fixed != patch[:, :, :3], axis=2)
    if protected is not None:
        affected &= ~protected[y:y+size, x:x+size]
    patch[affected, :3] = fixed[affected]
    count = int(affected.sum())
    report.update(status='restored' if count else 'protected', correctedPixels=count,
                  regions=[{'x': x, 'y': y, 'width': size, 'height': size,
                            'template': name, 'score': round(score, 4)}])
    return Image.fromarray(output), report
