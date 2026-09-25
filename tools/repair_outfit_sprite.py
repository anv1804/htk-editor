#!/usr/bin/env python3
"""Aligned sprite compositing with locked base colors, matte cleanup and garment repaint.
Painted overrides: red=base, blue=outfit, green=erase, transparent=automatic.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import base64
import io
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def load_rgba(path):
    with Image.open(path) as image:
        return image.convert("RGBA")


def components(mask, diagonal=True):
    seen = np.zeros(mask.shape, bool)
    height, width = mask.shape
    groups = []
    offsets = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
               if (dy or dx) and (diagonal or not (dy and dx))]
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        queue = deque([(int(y), int(x))])
        seen[y, x] = True
        group = []
        while queue:
            cy, cx = queue.popleft()
            group.append((cy, cx))
            for dy, dx in offsets:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        groups.append(np.asarray(group, dtype=np.int32))
    return sorted(groups, key=len, reverse=True)


def group_mask(shape, points):
    mask = np.zeros(shape, bool)
    if len(points):
        mask[points[:, 0], points[:, 1]] = True
    return mask


def shift(mask, dy, dx, fill=0):
    out = np.full_like(mask, fill)
    h, w = mask.shape[:2]
    if abs(dy) < h and abs(dx) < w:
        out[max(0, dy):min(h, h+dy), max(0, dx):min(w, w+dx)] = mask[
            max(0, -dy):min(h, h-dy), max(0, -dx):min(w, w-dx)]
    return out


def dilate(mask, radius):
    out = mask.copy()
    for _ in range(radius):
        out = np.logical_or.reduce([shift(out, dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    return out


def boundary(mask):
    interior = np.logical_and.reduce([shift(mask, dy, dx) for dy, dx in ((0,1),(0,-1),(1,0),(-1,0))])
    return mask & ~interior


def fill_holes(mask):
    out = mask.copy()
    h, w = mask.shape
    for points in components(~mask, diagonal=False):
        ys, xs = points.T
        if not np.any((ys == 0) | (ys == h-1) | (xs == 0) | (xs == w-1)):
            out[ys, xs] = True
    return out


def luminance(rgb):
    # int16 overflows when multiplied by 587. Accumulate in float32.
    return rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)


def background_color(rgba):
    edge = np.concatenate([rgba[0,:,:3], rgba[-1,:,:3], rgba[:,0,:3], rgba[:,-1,:3]])
    return np.median(edge, axis=0).astype(np.float32)


def foreground_mask(rgba, threshold):
    if np.any(rgba[:,:,3] < 128):
        return rgba[:,:,3] >= 128
    distance = np.linalg.norm(rgba[:,:,:3].astype(np.float32) - background_color(rgba), axis=2)
    candidates = distance <= threshold
    fg = np.ones(candidates.shape, bool)
    h, w = fg.shape
    for points in components(candidates):
        ys, xs = points.T
        touches_edge = np.any((ys == 0) | (xs == 0) | (ys == h-1) | (xs == w-1))
        # Preserve tiny enclosed eye/highlight clusters.
        hole = len(points) >= 8 and np.mean(distance[ys, xs] <= min(6, threshold)) >= .25
        if touches_edge or hole:
            fg[ys, xs] = False
    return fg


def clean_outfit(rgba, threshold, min_component):
    fg = foreground_mask(rgba, threshold)
    original = int(fg.sum())
    rgb = rgba[:,:,:3].astype(np.float32).copy()
    if not np.any(rgba[:,:,3] < 128):
        bg = background_color(rgba)
        edge = boundary(fg)
        reference = rgb.copy()
        best = np.linalg.norm(rgb-bg, axis=2)
        for dy, dx in ((0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)):
            neighbor = shift(rgb, dy, dx)
            score = np.linalg.norm(neighbor-bg, axis=2)
            take = shift(fg, dy, dx) & (score > best)
            reference[take] = neighbor[take]
            best[take] = score[take]
        # Remove the white matte from boundary pixels using a neighboring solid
        # edge color. This does not erode every contour or blur native pixels.
        direction, delta = reference-bg, rgb-bg
        coverage = np.clip(np.sum(delta*direction,axis=2) / np.maximum(np.sum(direction**2,axis=2),1),0,1)
        residual = np.linalg.norm(delta-coverage[:,:,None]*direction, axis=2)
        mixed = edge & (residual < 24) & (best > 80)
        # Neutral matte haze may be removed; colored fringe can be the only
        # pixel of a narrow sleeve tip or ribbon and must keep its silhouette.
        neutral_fringe = np.ptp(rgb, axis=2) < 18
        fg[mixed & (coverage < .48) & (neutral_fringe | (coverage < .22))] = False
        keep = mixed & fg & (coverage < .95)
        rgb[keep] = np.clip(bg + delta[keep] / np.maximum(coverage[keep,None],.48),0,255)
    for points in components(fg):
        if len(points) < min_component:
            fg[points[:,0],points[:,1]] = False
    return np.rint(rgb).astype(np.uint8), fg, original-int(fg.sum())


def skin_mask(rgba, fg):
    r, g, b = (rgba[:,:,i].astype(np.int32) for i in range(3))
    return fg & (r >= 115) & (r > g+16) & (g > b+7)


def base_head_mask(base, fg):
    """Find the bright face component instead of using a body-height ratio."""
    skin = skin_mask(base, fg)
    if not np.any(skin):
        return np.zeros(fg.shape, bool)
    light = luminance(base[:,:,:3])
    cutoff = float(np.percentile(light[skin], 70)) - 1
    candidates = components(skin & (light >= cutoff))
    if not candidates:
        return np.zeros(fg.shape, bool)
    face = max(candidates, key=lambda c: len(c)/(1+c[:,0].mean()/fg.shape[0]))
    # Some bases use one flat skin color all the way down the torso. Such a
    # component is not a face: cap its height by its width, never body height.
    face_width = int(np.ptp(face[:,1])) + 1
    if int(np.ptp(face[:,0])) + 1 > face_width * 1.6:
        face = face[face[:,0] < face[:,0].min() + max(1, int(face_width * 1.5))]
    core = group_mask(fg.shape, face)
    ys, xs = face.T
    yy, xx = np.indices(fg.shape)
    limit = (yy <= ys.max()+1) & (yy >= ys.min()-2) & (xx >= xs.min()-3) & (xx <= xs.max()+3)
    flesh = core.copy()
    for _ in range(2):
        flesh |= dilate(flesh,1) & skin & limit
    return fill_holes(dilate(flesh,1)) & fg & limit


def base_landmarks(base, fg):
    """Infer a reusable anatomy map from the base alone, before seeing clothing."""
    head = base_head_mask(base, fg)
    hands = np.zeros(fg.shape, bool)
    hy, hx = np.nonzero(head)
    if not len(hy):
        return head, hands
    body = fg & ~head
    skeleton = body.copy()
    # Zhang-Suen thinning retains the limb centerlines without an extra runtime.
    for _ in range(max(fg.shape)):
        changed = False
        for step in (0, 1):
            n = [shift(skeleton,dy,dx) for dy,dx in
                 ((1,0),(1,-1),(0,-1),(-1,-1),(-1,0),(-1,1),(0,1),(1,1))]
            degree = sum(p.astype(np.uint8) for p in n)
            transitions = sum((~n[i] & n[(i+1)%8]).astype(np.uint8) for i in range(8))
            if step == 0:
                removable = ~(n[0]&n[2]&n[4]) & ~(n[2]&n[4]&n[6])
            else:
                removable = ~(n[0]&n[2]&n[6]) & ~(n[0]&n[4]&n[6])
            remove = skeleton & (degree >= 2) & (degree <= 6) & (transitions == 1) & removable
            changed |= bool(np.any(remove))
            skeleton[remove] = False
        if not changed:
            break
    degree = sum(shift(skeleton,dy,dx).astype(np.uint8)
                 for dy in (-1,0,1) for dx in (-1,0,1) if dy or dx)
    yy, xx = np.indices(fg.shape)
    width = int(np.ptp(hx))+1
    center = (hx.min()+hx.max())/2
    bottom = int(hy.max())
    body_bottom = int(np.nonzero(fg)[0].max())
    limb_height = (yy >= bottom-2) | (abs(xx-center) > width*.6)
    candidates = np.argwhere(skeleton & (degree <= 1) & limb_height & (yy >= hy.min()+width*.45)
                             & (yy <= bottom+(body_bottom-bottom)*.72)
                             & (abs(xx-center) >= width*.3))
    # One palm per side. Keep only a small distal patch, never the entire arm.
    radius = max(1, round(width*.12))
    flesh = skin_mask(base,fg) & body & limb_height & (yy <= bottom+(body_bottom-bottom)*.72)
    for side in (-1, 1):
        points = [p for p in candidates if (p[1]-center)*side > 0]
        extremities = np.argwhere(flesh & ((xx-center)*side > width*.4))
        if len(extremities):
            outer = np.max((extremities[:,1]-center)*side)
            tip = extremities[(extremities[:,1]-center)*side >= outer-2]
            y,x = np.rint(np.mean(tip,axis=0)).astype(int)
        elif points:
            y,x = max(points, key=lambda p: abs(p[1]-center)+.15*(p[0]-bottom))
        else:
            continue
        hands |= ((yy-y)**2+(xx-x)**2 <= (radius+.5)**2) & body
    return head, hands


def build_base_profile(base, *, rows, cols, threshold=36):
    if rows < 1 or cols < 1 or base.width % cols or base.height % rows:
        raise ValueError('Invalid base profile grid')
    cw, ch = base.width//cols, base.height//rows
    labels = np.zeros((base.height,base.width,4),np.uint8)
    for y in range(0,base.height,ch):
        for x in range(0,base.width,cw):
            pixels = np.asarray(base.crop((x,y,x+cw,y+ch)).convert('RGBA'))
            head,hands = base_landmarks(pixels,foreground_mask(pixels,threshold))
            tile = labels[y:y+ch,x:x+cw]
            tile[head] = [255,0,0,255]
            tile[hands] = [255,128,0,255]
    return Image.fromarray(labels)


def base_profile_identity(base, rows, cols):
    return hashlib.sha256(base.convert('RGBA').tobytes()+f'{base.size}:{rows}:{cols}'.encode()).hexdigest()


def load_base_profile(path, base, rows, cols):
    if path.suffix.lower() != '.json':
        return load_rgba(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') != 1 or data.get('baseId') != base_profile_identity(base,rows,cols):
        raise ValueError('Saved profile belongs to a different base or grid')
    raw = base64.b64decode(data['mask'].split(',',1)[1],validate=True)
    with Image.open(io.BytesIO(raw)) as image:
        if image.size != base.size:
            raise ValueError('Base profile must match the sheet dimensions')
        return image.convert('RGBA')


def occlusion_regions(base, base_fg, outfit, outfit_fg, profile=None):
    """Separate the exposed skin apertures from the clothing that covers them.

    In particular, a hand location is NOT a license to dilate through a sleeve.
    The input garment silhouette is authoritative at every covered body pixel.
    """
    head = base_head_mask(base, base_fg)
    fixed_hands = None
    if profile is not None:
        labels = np.asarray(profile.convert('RGBA'))
        marked = (labels[:,:,3] >= 128) & (labels[:,:,0] > 200)
        head = marked & (labels[:,:,1] < 64) & base_fg
        fixed_hands = marked & (labels[:,:,1] >= 64) & base_fg
    generated_skin = skin_mask(outfit, outfit_fg)
    base_skin = skin_mask(base, base_fg)
    yy, xx = np.indices(head.shape)
    hy, hx = np.nonzero(head)
    empty = np.zeros(head.shape, bool)
    if not len(hy):
        return dict(head=head, anatomy=empty.copy(), removed=empty.copy(), exposed=empty.copy(),
                    cloth=outfit_fg.copy(), hands=empty.copy())
    bottom, width = int(hy.max()), int(np.ptp(hx))+1
    center = (hx.min()+hx.max())/2
    source_face = fill_holes(generated_skin & dilate(head,3) & (yy <= bottom))
    dark = luminance(outfit[:,:,:3]) < 110

    # Fabric must be connected to clothing outside the face. This excludes
    # isolated eye whites/highlights from the occluder, but protects sleeves
    # passing in front of the face and the collar directly under the chin.
    r, g, b = (outfit[:,:,i].astype(np.int32) for i in range(3))
    cloth_seeds = outfit_fg & ~generated_skin & ((g >= r-10) | (b >= r))
    cloth_seeds &= (luminance(outfit[:,:,:3]) > 110) | (g > r+4) | (b > r+4)
    cloth = empty.copy()
    for group in components(cloth_seeds):
        ys, xs = group.T
        if len(group) >= 3 and np.any((ys > bottom+1) | (~dilate(head,2)[ys,xs])):
            cloth[ys,xs] = True
    cloth |= dilate(cloth,1) & outfit_fg & dark & ~source_face
    generated_head = (source_face | (dilate(source_face,1) & dark & outfit_fg)) & (yy <= bottom)
    generated_head &= ~cloth
    visible_head = head & ~cloth

    # Keep the exposed neck as an aperture instead of deleting a strip below
    # the chin. It will be replaced with base skin, behind the collar.
    neck = generated_skin & (yy > bottom) & (yy <= bottom+max(3, round(width*.25)))
    neck &= abs(xx-center) <= width*.38
    hands = empty.copy()
    discarded = empty.copy()
    body_y = np.nonzero(base_fg)[0]
    hand_bottom = bottom + max(4, (int(body_y.max())-bottom)*.72)
    for points in components(generated_skin & ~source_face & ~neck):
        ys, xs = points.T
        if len(points) < 3 or len(points) > max(12, head.sum()*.35) or ys.mean() > hand_bottom:
            continue
        region = group_mask(head.shape, points)
        if not np.any(dilate(region,2) & base_skin & ~head):
            continue
        if not np.any(dilate(region,2) & cloth):
            discarded |= region  # detached skin fleck, not an opening in a sleeve
            continue
        aperture = fill_holes(region)
        # Dark rim pixels belong to the hand only if they are not part of the
        # sleeve. No expansion of base skin or flood into the forearm follows.
        aperture |= dilate(region,1) & dark & outfit_fg & ~cloth & ~source_face
        hands |= aperture
    exposed = (hands | neck) & ~cloth & ~visible_head
    # A dark base forearm contour can land in the middle of an outfit fist.
    # Do not copy that line into skin: reconstruct the uncovered aperture from
    # nearby base flesh instead. Dark pixels are copied only onto source rims.
    anatomy = visible_head | (exposed & base_skin) | (exposed & dark & base_fg)
    removed = generated_head | exposed | discarded
    if fixed_hands is not None:
        # Keep coordinates and all colors of the base palm, including its
        # outline. The sleeve still occludes it. Never synthesize a new fist
        # using the generated hand's silhouette at a different position.
        # The pinned palm defines the cuff opening. Only this small distal
        # region may replace fabric; the forearm remains covered by the sleeve.
        visible_hands = fixed_hands & dilate(outfit_fg,2)
        cloth &= ~visible_hands
        anatomy = visible_head | visible_hands | (neck & base_skin & ~cloth)
        removed |= hands
        exposed = neck & ~cloth & ~visible_head
    return dict(head=visible_head, anatomy=anatomy, removed=removed, exposed=exposed,
                cloth=cloth, hands=hands, fixed_hands=fixed_hands)


def anatomy_masks(base, base_fg, outfit, outfit_fg, expand=0):
    regions = occlusion_regions(base, base_fg, outfit, outfit_fg)
    return regions['anatomy'], regions['removed'], regions['head']


def rebuild_exposed_skin(base, outfit, exposed, missing, base_fg):
    """Complete a small wrist/neck gap from nearby base pixels, inside its aperture."""
    repaired = np.zeros_like(base)
    skin = skin_mask(base, base_fg)
    for group in components(exposed):
        region = group_mask(exposed.shape, group)
        holes = region & missing
        if not np.any(holes):
            continue
        samples = dilate(region,2) & skin
        if not np.any(samples):
            samples = skin
        if not np.any(samples):
            continue
        targets, donors = np.argwhere(holes), np.argwhere(samples)
        # Prefer spatially close base colors. Source shading only breaks ties;
        # no generated skin color survives in these reconstructed pixels.
        spatial = ((targets[:,None]-donors[None])**2).sum(2).astype(np.float32)
        donor_rgb = base[donors[:,0],donors[:,1],:3].astype(np.float32)
        target_rgb = outfit[targets[:,0],targets[:,1],:3].astype(np.float32)
        color = ((target_rgb[:,None]-donor_rgb[None])**2).sum(2)/2500
        nearest = (spatial+color).argmin(1)
        repaired[targets[:,0],targets[:,1]] = base[donors[nearest,0],donors[nearest,1]]
        repaired[targets[:,0],targets[:,1],3] = 255
    return repaired


def anatomy_restore_mask(base_rgba, base_fg, outfit_rgba, outfit_fg, expand):
    return anatomy_masks(base_rgba, base_fg, outfit_rgba, outfit_fg, expand)[0]


def _frame_layers(base, outfit, *, background_threshold, skin_expand, cleanup=3, overrides=None, profile=None):
    b, o = np.asarray(base.convert('RGBA')), np.asarray(outfit.convert('RGBA'))
    base_fg = foreground_mask(b, background_threshold)
    rgb, fg, debris = clean_outfit(o, background_threshold, cleanup)
    cleaned = np.dstack([rgb, fg.astype(np.uint8)*255])
    regions = occlusion_regions(b, base_fg, cleaned, fg, profile)
    anatomy, removed, head = regions['anatomy'], regions['removed'], regions['head']
    rebuilt = rebuild_exposed_skin(b, cleaned, regions['exposed'], regions['exposed'] & ~anatomy, base_fg)
    reconstructed = rebuilt[:,:,3] > 0
    garment = fg & ~removed & ~anatomy
    if profile is not None:
        # Fill the obsolete generated hand opening with neighboring sleeve
        # material. Limit donors to this cuff; do not sample another frame.
        holes = regions['hands'] & ~anatomy & ~reconstructed
        for group in components(holes):
            region = group_mask(fg.shape, group)
            donors = np.argwhere(dilate(region,3) & garment & regions['cloth'])
            if not len(donors):
                continue
            targets = np.argwhere(region)
            nearest = ((targets[:,None]-donors[None])**2).sum(2).argmin(1)
            rgb[targets[:,0],targets[:,1]] = rgb[donors[nearest,0],donors[nearest,1]]
            garment |= region
    erase = np.zeros(fg.shape, bool)
    force_base = np.zeros(fg.shape, bool)
    force_outfit = np.zeros(fg.shape, bool)
    if overrides is not None:
        labels = np.asarray(overrides.convert('RGBA'))
        marked = labels[:,:,3] >= 128
        force_base = marked & (labels[:,:,0] > 200) & (labels[:,:,1] < 100)
        force_outfit = marked & (labels[:,:,2] > 200) & (labels[:,:,0] < 100)
        erase = marked & (labels[:,:,1] > 200) & (labels[:,:,0] < 100)
        anatomy = (anatomy & ~force_outfit & ~erase) | (force_base & base_fg)
        reconstructed &= ~marked
        # A manual mark can recover a small detail that automatic cleanup
        # rejected. Background pixels still remain transparent.
        garment = (garment & ~force_base & ~erase) | (force_outfit & foreground_mask(o, background_threshold))
    for points in components(garment):
        if len(points) < cleanup and not np.any(force_outfit[points[:,0],points[:,1]]):
            garment[points[:,0],points[:,1]] = False
            debris += len(points)
    # Replacing source hands can leave a disconnected base finger fragment.
    # Clean the composite too, while respecting explicitly painted pixels.
    for points in components(anatomy | garment | reconstructed):
        ys, xs = points.T
        if len(points) < cleanup and not np.any((force_base | force_outfit)[ys,xs]):
            anatomy[ys,xs] = False
            garment[ys,xs] = False
            reconstructed[ys,xs] = False
            debris += len(points)
    output = np.zeros_like(b)
    output[garment,:3] = rgb[garment]
    output[garment,3] = 255
    output[anatomy] = b[anatomy]
    output[anatomy,3] = 255
    output[reconstructed] = rebuilt[reconstructed]
    output[erase] = 0
    stats = {'outfit_pixels': int(garment.sum()), 'restored_anatomy_pixels': int(anatomy.sum()),
             'removed_outfit_anatomy_pixels': int((removed & fg).sum()),
             'removed_noise_pixels': debris, 'head_pixels': int(head.sum()), 'outlined_outfit_pixels': 0,
             'reconstructed_skin_pixels': int(reconstructed.sum()),
             'protected_cloth_pixels': int(regions['cloth'].sum()),
             'restored_hand_pixels': int((anatomy & regions['hands']).sum())}
    return output, anatomy, garment, reconstructed, stats


def nearest_colors(points, palette):
    result = np.empty(len(points), np.int32)
    weights = np.array([.299,.587,.114], np.float32)
    for start in range(0,len(points),4096):
        distance = ((points[start:start+4096,None].astype(np.float32)-palette[None])**2*weights).sum(2)
        result[start:start+4096] = distance.argmin(1)
    return result


def outline_color(base, mask):
    pixels = base[:,:,:3][mask]
    if not len(pixels):
        return np.array([39,25,32], np.uint8)
    colors, counts = np.unique(pixels,axis=0,return_counts=True)
    dark = luminance(colors) < 80
    return colors[dark][counts[dark].argmax()] if np.any(dark) else np.array([39,25,32],np.uint8)


def shade_materials(rgb, fill, budget, cell_size):
    """Build shared material ramps, then redraw coherent shadow/mid/highlight areas."""
    pixels = rgb[fill].astype(np.float32)
    if not len(pixels):
        return rgb
    light = luminance(pixels)
    chroma = pixels-light[:,None]
    families = min(2, max(1,budget//3))
    # Chroma clustering distinguishes fabric colors independently of shadows.
    centers = [np.median(chroma,axis=0)]
    for _ in range(1,families):
        distance = ((chroma[:,None]-np.asarray(centers)[None])**2).sum(2).min(1)
        centers.append(chroma[np.argmax(distance)])
    centers = np.asarray(centers)
    for _ in range(12):
        family = ((chroma[:,None]-centers[None])**2).sum(2).argmin(1)
        for i in range(families):
            if np.any(family == i):
                centers[i] = np.mean(chroma[family == i],axis=0)
    labels = np.full(fill.shape,-1,np.int32)
    labels[fill] = family
    levels = luminance(rgb)
    filtered = levels.copy()
    cw,ch = cell_size
    # Median only within the same material and cell. It removes mottled
    # anti-alias shades without blurring a seam or changing a silhouette.
    yy,xx = np.indices(fill.shape)
    neighbors = []
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            valid = (shift(labels,dy,dx,fill=-2) == labels) & fill
            valid &= (yy//ch == (yy-dy)//ch) & (xx//cw == (xx-dx)//cw)
            neighbors.append(np.where(valid,shift(levels,dy,dx),np.nan))
    stack = np.stack(neighbors)
    # Non-fill locations get a finite placeholder to avoid all-NaN warnings.
    stack[:,~fill] = 0
    median = np.nanmedian(stack,axis=0)
    # Keep folds and one-pixel highlights; only suppress isolated shade noise.
    filtered[fill] = .8*levels[fill]+.2*median[fill]
    result = rgb.copy()
    used = 0
    for i in range(families):
        area = labels == i
        if not np.any(area):
            continue
        shades = min(3,budget-used-(families-i-1))
        values = filtered[area]
        # Fit tones to the source's light distribution. Quantile thresholds
        # force equal-sized dark/light patches even on almost flat fabric.
        tone_centers = np.linspace(*np.percentile(values,[5,95]),shades)
        for _ in range(12):
            tone = abs(values[:,None]-tone_centers[None]).argmin(1)
            for j in range(shades):
                if np.any(tone == j):
                    tone_centers[j] = np.mean(values[tone == j])
        source = rgb[area].astype(np.float32)
        ramp = []
        for j in range(shades):
            samples = source[tone == j]
            color = np.median(samples,axis=0) if len(samples) else centers[i]+tone_centers[j]
            # A small contrast increase sharpens existing shadows without
            # inventing new ones or averaging blue shadows into cream cloth.
            level = float(luminance(color))
            color += (level-float(np.median(values)))*.12
            ramp.append(np.clip(np.rint(color),0,255).astype(np.uint8))
        ramp = np.asarray(ramp)
        result[area] = ramp[tone]
        used += shades
    return result


def repaint(rgba, anatomy, garment, *, colors, paint, outline, cell_size):
    out = rgba.copy()
    ink = outline_color(out, anatomy)
    contours = np.zeros(garment.shape,bool)
    cw, ch = cell_size
    if outline:
        for y in range(0,out.shape[0],ch):
            for x in range(0,out.shape[1],cw):
                fg = out[y:y+ch,x:x+cw,3] > 0
                # One-pixel, four-neighbor inward border. Anatomy is untouched.
                fabric = garment[y:y+ch,x:x+cw]
                light = luminance(out[y:y+ch,x:x+cw,:3])
                support = sum(shift(fg,dy,dx).astype(np.uint8)
                              for dy in (-1,0,1) for dx in (-1,0,1) if dy or dx)
                # Preserve the colored center of a one-pixel ribbon/tip.
                # Existing dark outlines can still be normalized there.
                contours[y:y+ch,x:x+cw] = boundary(fg) & fabric & ((light < 135) | (support >= 4))
                if paint == 3:
                    # Keep connected dark seams inside the silhouette (belt,
                    # cuff and folds). Otherwise the material ramps wash them
                    # into broad shadow patches. Restrict to high contrast
                    # edges so a dark fabric panel is not filled with ink.
                    dark = fabric & (light < 92)
                    adjacent = sum(shift(dark,dy,dx).astype(np.uint8)
                                   for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)))
                    bright = np.maximum.reduce([np.where(shift(fabric,dy,dx),shift(light,dy,dx),0)
                                                for dy in (-1,0,1) for dx in (-1,0,1)])
                    contours[y:y+ch,x:x+cw] |= dark & (adjacent >= 1) & (bright-light > 55)
        out[contours,:3] = ink
    locked = np.unique(out[:,:,:3][anatomy | contours],axis=0)
    fill = garment & ~contours
    if colors and len(locked) > colors:
        raise ValueError(f'Palette needs at least {len(locked)} colors to preserve base anatomy; choose a larger limit')
    if colors and np.any(fill):
        remaining = colors-len(locked)
        if remaining < 1:
            raise ValueError(f'Palette needs at least {len(locked)+1} colors to preserve base anatomy; choose a larger limit')
        if paint == 3:
            out[:,:,:3] = shade_materials(out[:,:,:3],fill,min(remaining,9),cell_size)
            out[out[:,:,3] == 0] = 0
            return out, contours
        count = min(remaining, {0:256,1:12,2:6}[paint])
        pixels = out[:,:,:3][fill]
        sample = Image.fromarray(pixels.reshape(1,-1,3))
        quantized = sample.quantize(colors=count,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
        raw = np.asarray(quantized.getpalette(),np.uint8).reshape(-1,3)
        palette = raw[np.unique(np.asarray(quantized))]
        palette = np.unique(np.vstack([palette,ink]) if outline else palette,axis=0)
        labels = np.full(fill.shape,-1,np.int32)
        labels[fill] = nearest_colors(pixels,palette)
        if paint:
            for _ in range(paint):
                updated = labels.copy()
                neighbors = []
                yy, xx = np.indices(labels.shape)
                for dy in (-1,0,1):
                    for dx in (-1,0,1):
                        if not (dy or dx):
                            continue
                        neighbor = shift(labels,dy,dx,fill=-1)
                        same_frame = (yy//ch == (yy-dy)//ch) & (xx//cw == (xx-dx)//cw)
                        neighbor[~same_frame] = -1
                        neighbors.append(neighbor)
                own = sum((n == labels).astype(np.uint8) for n in neighbors)
                for label in range(len(palette)):
                    votes = sum((n == label).astype(np.uint8) for n in neighbors)
                    current = palette[np.maximum(labels,0)].astype(np.int32)
                    close = np.linalg.norm(current-palette[label],axis=2) < 65
                    updated[fill & (votes >= 5) & (own <= 1) & close] = label
                labels = updated
        out[fill,:3] = palette[labels[fill]]
    out[out[:,:,3] == 0] = 0
    return out, contours


def repair_frame(base, outfit, *, background_threshold, skin_expand, outline=True, cleanup=3):
    if base.size != outfit.size:
        raise ValueError('Base and outfit sizes differ')
    out, anatomy, garment, reconstructed, stats = _frame_layers(base,outfit,background_threshold=background_threshold,
                                               skin_expand=skin_expand,cleanup=cleanup)
    out, contours = repaint(out,anatomy | reconstructed,garment,colors=0,paint=0,outline=outline,cell_size=base.size)
    stats['outlined_outfit_pixels'] = int(contours.sum())
    return Image.fromarray(out), stats


def repair_sheet(base, outfit, *, rows, cols, colors, background_threshold, skin_expand,
                 outline=True, cleanup=3, paint=1, overrides=None, return_masks=False,
                 base_profile=None, lock_base=False, retouch=None):
    if not isinstance(rows,int) or not isinstance(cols,int) or not 1 <= rows <= 64 or not 1 <= cols <= 64:
        raise ValueError('Rows and columns must be between 1 and 64')
    if base.size != outfit.size:
        raise ValueError(f'Base and outfit sizes differ: {base.size} vs {outfit.size}')
    if base.width % cols or base.height % rows:
        raise ValueError('Sheet size is not divisible by the requested grid')
    if not 0 <= colors <= 256 or not np.isfinite(background_threshold) or not 0 <= background_threshold <= 255:
        raise ValueError('Invalid palette limit or background threshold')
    if not 0 <= skin_expand <= 4 or not 0 <= cleanup <= 16 or paint not in (0,1,2,3):
        raise ValueError('Invalid cleanup, paint or skin expansion setting')
    if overrides is not None and overrides.size != base.size:
        raise ValueError('Correction mask must match the sheet dimensions')
    if base_profile is not None and base_profile.size != base.size:
        raise ValueError('Base profile must match the sheet dimensions')
    if retouch is not None and retouch.size != base.size:
        raise ValueError('Retouch layer must match the sheet dimensions')
    if lock_base and base_profile is None:
        base_profile = build_base_profile(base,rows=rows,cols=cols,threshold=background_threshold)
    cw, ch = base.width//cols, base.height//rows
    output = np.zeros((base.height,base.width,4),np.uint8)
    anatomy = np.zeros(output.shape[:2],bool)
    garment = np.zeros(output.shape[:2],bool)
    reconstructed = np.zeros(output.shape[:2],bool)
    reports = []
    for row in range(rows):
        for col in range(cols):
            x,y = col*cw,row*ch
            box = (x,y,x+cw,y+ch)
            out,a,g,s,stats = _frame_layers(base.crop(box),outfit.crop(box),background_threshold=background_threshold,
                                         skin_expand=skin_expand,cleanup=cleanup,
                                         overrides=overrides.crop(box) if overrides is not None else None,
                                         profile=base_profile.crop(box) if base_profile is not None else None)
            output[y:y+ch,x:x+cw], anatomy[y:y+ch,x:x+cw], garment[y:y+ch,x:x+cw] = out,a,g
            reconstructed[y:y+ch,x:x+cw] = s
            stats.update(row=row,col=col)
            reports.append(stats)
    painted = np.zeros(anatomy.shape,bool)
    if retouch is not None:
        manual = np.asarray(retouch.convert('RGBA'))
        painted = manual[:,:,3] >= 128
        output[painted] = manual[painted]
        output[painted,3] = 255
        anatomy[painted] = reconstructed[painted] = garment[painted] = False
    output,contours = repaint(output,anatomy | reconstructed | painted,garment,colors=colors,paint=paint,outline=outline,cell_size=(cw,ch))
    for stats in reports:
        x,y = stats['col']*cw,stats['row']*ch
        stats['outlined_outfit_pixels'] = int(contours[y:y+ch,x:x+cw].sum())
    result = Image.fromarray(output)
    if return_masks:
        mask = np.zeros_like(output)
        mask[anatomy] = [255,80,80,255]
        mask[garment] = [70,155,255,255]
        mask[reconstructed] = [240,190,60,255]
        mask[painted] = [180,80,230,255]
        return result, reports, Image.fromarray(mask)
    return result, reports


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base','outfit','output'):
        parser.add_argument('--'+name, required=True,type=Path)
    parser.add_argument('--rows',type=int,default=7)
    parser.add_argument('--cols',type=int,default=4)
    parser.add_argument('--colors',type=int,default=32,help='Maximum opaque colors; 0 disables recoloring')
    parser.add_argument('--background-threshold',type=float,default=36)
    parser.add_argument('--skin-expand',type=int,default=0)
    parser.add_argument('--cleanup',type=int,default=3)
    parser.add_argument('--paint',type=int,choices=(0,1,2,3),default=3)
    parser.add_argument('--base-profile',type=Path)
    parser.add_argument('--retouch',type=Path)
    parser.add_argument('--free-skin',action='store_true',help='Use legacy outfit-guided hand locations')
    parser.add_argument('--no-outline',action='store_true')
    parser.add_argument('--overrides',type=Path)
    parser.add_argument('--report',type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    base = load_rgba(args.base)
    result,report = repair_sheet(base,load_rgba(args.outfit),rows=args.rows,cols=args.cols,
                                 colors=args.colors,background_threshold=args.background_threshold,
                                 skin_expand=args.skin_expand,outline=not getattr(args,'no_outline',False),
                                 cleanup=getattr(args,'cleanup',3),paint=getattr(args,'paint',1),
                                 overrides=load_rgba(args.overrides) if getattr(args,'overrides',None) else None,
                                 base_profile=load_base_profile(args.base_profile,base,args.rows,args.cols) if getattr(args,'base_profile',None) else None,
                                 lock_base=not getattr(args,'free_skin',False),
                                 retouch=load_rgba(args.retouch) if getattr(args,'retouch',None) else None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    result.save(args.output)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({'frames':report},indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
