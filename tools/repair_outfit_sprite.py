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


def remove_color_spurs(rgb, garment, protected=None):
    """Remove isolated, off-palette garment pixels without eroding contours."""
    rgb = rgb.astype(np.int16)
    neighbors = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                 if dy or dx]
    cardinal = sum(shift(garment, dy, dx).astype(np.uint8)
                   for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)))
    diagonal = sum(shift(garment, dy, dx).astype(np.uint8)
                   for dy, dx in ((1, 1), (1, -1), (-1, 1), (-1, -1)))
    support = np.zeros(garment.shape + (3,), np.int16)
    samples = np.zeros(garment.shape, np.uint8)
    for dy, dx in neighbors:
        adjacent = shift(garment, dy, dx)
        support += shift(rgb, dy, dx) * adjacent[..., None]
        samples += adjacent
    mean = support / np.maximum(samples[..., None], 1)
    deviation = np.sqrt(np.mean((rgb - mean) ** 2, axis=2))
    anchors = sum(shift(samples, dy, dx) * shift(garment, dy, dx)
                  for dy, dx in neighbors)
    luminance_value = luminance(rgb.astype(np.uint8))
    spurs = garment & (cardinal == 0) & (diagonal == 1) & (samples == 1)
    spurs &= (anchors >= 3) & (deviation >= 30)
    spurs &= (luminance_value >= 95) & (luminance_value <= 220)
    if protected is not None:
        spurs &= ~protected
    cleaned = garment & ~spurs
    return cleaned, int(spurs.sum())


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

    Strategy: "quét lấy outfit truoc" - base skin is the ground truth.
    Anywhere the BASE has skin AND the outfit covers it => erase outfit, reveal base.
    Cloth pixels (by hue/color) are protected even if base has skin underneath.
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

    # Step 1: Identify confident cloth pixels by hue (non-skin warm colors = not cloth)
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

    # Step 2: Neck zone (below chin)
    neck = generated_skin & (yy > bottom) & (yy <= bottom+max(3, round(width*.25)))
    neck &= abs(xx-center) <= width*.38

    # Step 3: "Quét lấy outfit truoc" - erase outfit where BASE has skin AND outfit also has skin
    # Key insight: if base has skin at a pixel BUT outfit has a cloth-colored pixel there,
    # that means CLOTH is correctly covering the base limb -> keep cloth, do NOT erase.
    # Only erase when BOTH base has skin AND outfit has a skin-colored pixel (bare AI limb).
    base_skin_exposed = base_skin & generated_skin & outfit_fg & ~head & ~cloth
    # Also erase outfit skin detected via chroma matching (shaded/dark AI skin same hue as face)
    if np.any(source_face):
        face_rgb = outfit[source_face][:, :3].astype(np.float32)
        face_mean = face_rgb.mean(axis=0)
        face_norm = face_mean / (np.linalg.norm(face_mean) + 1e-5)
        all_rgb = outfit[:, :, :3].astype(np.float32)
        all_norms = np.linalg.norm(all_rgb, axis=2, keepdims=True) + 1e-5
        chroma_dist = np.linalg.norm(all_rgb / all_norms - face_norm, axis=2)
        outfit_skin_by_chroma = outfit_fg & (chroma_dist <= 0.15) & (all_rgb[:,:,0] >= 35)
        base_skin_exposed |= base_skin & outfit_skin_by_chroma & ~head & ~cloth
    # Expand to adjacent dark outline pixels (outlines are part of the anatomy boundary)
    base_skin_exposed |= dilate(base_skin_exposed, 1) & outfit_fg & dark & ~cloth & ~head

    # Step 4: Legacy small-blob hand detection (for cuff gap reconstruction)
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
            discarded |= region
            continue
        aperture = fill_holes(region)
        aperture |= dilate(region,1) & dark & outfit_fg & ~cloth & ~source_face
        hands |= aperture

    # Step 5: Merge all exposed zones
    exposed = (hands | neck | base_skin_exposed) & ~cloth & ~visible_head
    anatomy = visible_head | (exposed & base_skin) | (exposed & dark & base_fg)
    removed = generated_head | exposed | discarded

    if fixed_hands is not None:
        visible_hands = fixed_hands & dilate(outfit_fg,2)
        cloth &= ~visible_hands
        # Profile mode: erase outfit pixels at base skin locations ONLY if the outfit
        # pixel itself is skin-colored. If outfit has cloth color there, keep it.
        # Use cloth_seeds (includes isolated cloth pixels) not just cloth (min size 3).
        r_o, g_o, b_o = (outfit[:,:,i].astype(np.int32) for i in range(3))
        outfit_is_cloth_color = (g_o >= r_o-10) | (b_o >= r_o)  # non-warm = cloth
        outfit_is_skin = generated_skin | ~outfit_is_cloth_color
        base_skin_full = base_skin & outfit_fg & outfit_is_skin & ~head & ~cloth
        # Chroma-based skin: same hue as face, even if shaded
        if np.any(source_face):
            face_rgb_fp = outfit[source_face][:, :3].astype(np.float32)
            face_mn = face_rgb_fp.mean(axis=0)
            face_nrm = face_mn / (np.linalg.norm(face_mn) + 1e-5)
            all_rgb_fp = outfit[:, :, :3].astype(np.float32)
            all_nrm = np.linalg.norm(all_rgb_fp, axis=2, keepdims=True) + 1e-5
            cdist = np.linalg.norm(all_rgb_fp / all_nrm - face_nrm, axis=2)
            outfit_chroma_skin = outfit_fg & (cdist <= 0.15) & (all_rgb_fp[:,:,0] >= 35) & ~cloth
            base_skin_full |= base_skin & outfit_chroma_skin & ~head
        base_skin_full |= dilate(base_skin_full, 1) & outfit_fg & dark & ~cloth
        exposed_all = (base_skin_full | neck) & ~cloth & ~visible_head
        anatomy = visible_head | visible_hands | (exposed_all & base_skin)
        removed |= hands | base_skin_full
        exposed = exposed_all

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
    garment, removed_spurs = remove_color_spurs(rgb, garment, force_outfit)
    debris += removed_spurs
    for points in components(garment):
        attached = dilate(anatomy | reconstructed,1)[points[:,0],points[:,1]]
        if len(points) < cleanup and not np.any(attached) and not np.any(force_outfit[points[:,0],points[:,1]]):
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


def warm_material_mask(base, base_fg, rgb, fg):
    """Separate yellow/tan material from the base's redder flesh chroma."""
    flesh = skin_mask(base, base_fg) & (luminance(base[:,:,:3]) > 150)
    if not flesh.any():
        return np.zeros_like(fg)
    samples = base[:,:,:3][flesh].astype(float)
    flesh_ratio = np.median((samples[:,0]-samples[:,1]) / np.maximum(samples[:,0]-samples[:,2], 1))
    r, g, b = rgb.astype(float).transpose(2,0,1)
    ratio = (r-g) / np.maximum(r-b, 1)
    seeds = fg & (r > g) & (g-b > 15) & (ratio < flesh_ratio-.1)
    material = np.zeros_like(fg)
    for points in components(seeds):
        if len(points) >= 3:
            material |= fill_holes(group_mask(fg.shape, points)) & fg
    # Keep the material's own dark stitching, not nearby bright flesh.
    material |= dilate(material, 1) & fg & (luminance(rgb) < 115)
    head = base_head_mask(base, base_fg)
    hy = np.nonzero(head)[0]
    if len(hy):
        yy = np.indices(fg.shape)[0]
        body = fg & (yy > hy.max())
        # Cream trim plus blue sleeves is not a uniformly tan suit. Expanding
        # protection across that whole body also protects its skin-colored
        # fists, leaving them to be recolored as beige cloth.
        cool = (g > r+8) | (b > r+8)
        mostly_warm = np.count_nonzero(cool & body) < body.sum()*.12
        if mostly_warm and np.count_nonzero(material & body) > max(12, body.sum()*.25):
            # A predominantly tan suit is ambiguous, not bare anatomy. Keep
            # it unless a bright flesh pixel also agrees with the base.
            distance = np.linalg.norm(rgb.astype(float)-base[:,:,:3], axis=2)
            # The base has several skin shades. Requiring a very close color
            # match avoids treating the yellow/tan suit's palette as flesh.
            confident_skin = (fg & base_fg & (luminance(rgb) > 165)
                              & (abs(ratio-flesh_ratio) < .09) & (distance < 30))
            material |= body & ~confident_skin
            material &= (yy > hy.max()) | ~dilate(head, 1)
        elif np.count_nonzero(material & (yy < hy.min())) < 6:
            return np.zeros_like(fg)
    return material


def headwear_mask(base, outfit, threshold=36, cleanup=3):
    """Grow crown-anchored material, not a rectangular crop of the head."""
    b = np.asarray(base.convert('RGBA'))
    rgb, fg, _ = clean_outfit(np.asarray(outfit.convert('RGBA')), threshold, cleanup)
    head = base_head_mask(b, foreground_mask(b, threshold))
    result = np.zeros(fg.shape, bool)
    hy, hx = np.nonzero(head)
    if not len(hy):
        return result
    yy, xx = np.indices(fg.shape)
    top, bottom = hy.min(), hy.max()
    left, right = hx.min(), hx.max()
    width = right-left+1
    row_widths = np.zeros(fg.shape[0], int)
    for y in range(max(0, top-width), min(fg.shape[0], top+max(3, round((bottom-top)*.5)))):
        xs = np.flatnonzero(fg[y] & (xx[y] >= left-width) & (xx[y] <= right+width))
        if len(xs):
            row_widths[y] = xs[-1]-xs[0]+1
    brim = int(row_widths.argmax())
    if row_widths[brim] >= width*1.3 and fg[:max(0,top-1)].any():
        # Wide hats have a geometric brim; its warm fill is not skin.
        return fg & (yy <= brim+1) & (xx >= left-width) & (xx <= right+width)
    skin = skin_mask(np.dstack((rgb, fg.astype(np.uint8)*255)), fg)
    light = luminance(rgb)
    warm = warm_material_mask(b, foreground_mask(b, threshold), rgb, fg)
    # Require material above the scalp, avoiding the bald head's own outline.
    crown = fg & (~skin | warm) & (yy < top-1) & (xx >= left-4) & (xx <= right+4)
    seeds = np.zeros_like(fg)
    for points in components(crown):
        if len(points) >= 3:
            seeds |= group_mask(fg.shape, points)
    if seeds.any():
        zone = (xx >= left-width//2) & (xx <= right+width//2)
        zone &= yy <= bottom+round(width*.65)
        upper = yy <= top+max(3, round((bottom-top)*.48))
        sides = (xx <= left+2) | (xx >= right-2)
        allowed = fg & (~skin | warm | (yy < top)) & zone & (upper | sides)
        # Crown colors allow long hair to continue below the face, but not into
        # differently colored shoulder fabric merely touching the hair.
        palette = np.unique(rgb[seeds], axis=0)
        distance = np.full(fg.shape, 255., dtype=np.float32)
        nearest = nearest_colors(rgb[fg], palette)
        distance[fg] = np.linalg.norm(rgb[fg].astype(float)-palette[nearest], axis=1)
        allowed &= upper | ((distance < 40) & (light < 125))
        exposed_limb = skin_mask(b, foreground_mask(b, threshold)) & ~dilate(head, 1)
        allowed &= ~(dilate(exposed_limb, 1) & ~upper)
        result = seeds.copy()
        for _ in range(fg.shape[0]+fg.shape[1]):
            grown = result | (dilate(result, 1) & allowed)
            if np.array_equal(grown, result):
                break
            result = grown

    # Profile sprites can have a scarf/tie trailing behind the skull rather
    # than above the crown. Use the base eye to identify the rear side, then
    # collect only cool-colored, skull-adjacent pixels in that narrow band.
    interior_dark = (luminance(b[:,:,:3]) < 80) & head & ~boundary(head)
    eye_parts = [group for group in components(interior_dark) if len(group) >= 2]
    if eye_parts:
        eye = max(eye_parts, key=len)
        eye_x = float(eye[:,1].mean())
        center = (left+right)/2
        facing = np.sign(eye_x-center)
        if abs(eye_x-center) >= width*.12:
            rear_left = facing > 0
            band_top = top+max(2, round((bottom-top)*.28))
            band_bottom = bottom
            side = (xx < left+1) & (xx >= left-round(width*.85)) if rear_left else (
                (xx > right-1) & (xx <= right+round(width*.85)))
            band = fg & side & (yy >= band_top) & (yy <= band_bottom)
            cool = (rgb[:,:,2].astype(int) > rgb[:,:,0].astype(int)+8) & (
                rgb[:,:,2].astype(int) > rgb[:,:,1].astype(int)+2)
            cool_seeds = band & cool & (light > 45)
            skull_neighborhood = dilate(head, 2)
            for group in components(band):
                region = group_mask(fg.shape, group)
                if np.count_nonzero(region & cool_seeds) >= 2 and np.any(region & skull_neighborhood):
                    result |= region
    return fill_holes(result) & fg


def outfit_skin_openings(rgb, fg, base, base_fg, protected):
    """Learn flesh colors from the outfit face before cutting its hands/feet.

    The base supplies pose proximity only; its palette must not decide whether
    a differently shaded source hand survives as a piece of clothing.
    """
    head = base_head_mask(base, base_fg)
    rgba = np.dstack((rgb, fg.astype(np.uint8)*255))
    flesh = skin_mask(rgba, fg) & ~protected
    samples = flesh & head & ~boundary(head)
    if np.count_nonzero(samples) < 4:
        return np.zeros_like(fg)
    palette = np.unique(rgb[samples], axis=0)
    candidates = flesh & dilate(base_fg, 5)
    matched = np.zeros_like(fg)
    colors = rgb[candidates].astype(np.float32)
    nearest = nearest_colors(colors, palette)
    matched[candidates] = np.linalg.norm(colors-palette[nearest],axis=1) < 38
    result = np.zeros_like(fg)
    for points in components(matched):
        region = group_mask(fg.shape, points)
        if len(points) >= 2 and np.any(region & dilate(skin_mask(base,base_fg),3)):
            result |= region
    # Follow warm shadow pixels only one step from confirmed flesh. Never
    # flood a brown belt or widen the cut through a colored cuff.
    r,g,b = rgb.astype(np.int32).transpose(2,0,1)
    shadow = fg & ~protected & (r > g+12) & (g > b+3) & (luminance(rgb) > 45)
    neighbor_count = sum(shift(result,dy,dx).astype(np.uint8)
                         for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)))
    result |= shadow & (neighbor_count >= 3)
    return result


def mask_distance(seeds, allowed, limit=4):
    """Short geodesic distance inside the source silhouette, within one frame."""
    distance=np.full(allowed.shape,limit+1,np.int16)
    frontier=seeds & allowed
    distance[frontier]=0
    for step in range(1,limit+1):
        frontier=dilate(frontier,1) & allowed & (distance > step)
        distance[frontier]=step
    return distance


def collar_material_mask(rgb, fg, head, cloth):
    """Protect cream collar continuations before applying skin cutouts.

    Warm highlights are ambiguous by color alone. Require connection to the
    source cloth and a position beside/below the chin, never the central face.
    """
    result = np.zeros_like(fg)
    hy, hx = np.nonzero(head)
    if not len(hy):
        return result
    yy, xx = np.indices(fg.shape)
    width = int(np.ptp(hx))+1
    bottom, center = int(hy.max()), (hx.min()+hx.max())/2
    band = (yy >= bottom-2) & (yy <= bottom+max(4, round(width*.35)))
    band &= (abs(xx-center) <= width*.7)
    band &= (abs(xx-center) > width*.18) | (yy > bottom+1)
    r,g,b = rgb.astype(np.int32).transpose(2,0,1)
    cream = (r-g <= 30) & (g-b >= 10) & (r-b <= 85) & (luminance(rgb) > 130)
    cream &= (r-g) <= (g-b)*1.1
    eligible = fg & band & cream
    result = eligible & cloth
    for _ in range(3):
        result |= eligible & dilate(result,1)
    return result


def source_material_evidence(rgb, fg, head, cloth):
    """Compare source flesh AND source fabric before allowing a body cut.

    The base determines pose, not the color of clothing. Relative evidence
    prevents cream cloth shadows near base skin colors being punched out.
    Ambiguous pixels attached to source fabric stay fabric for manual review.
    """
    result = np.zeros_like(fg)
    hy = np.nonzero(head)[0]
    if not len(hy):
        return result
    yy = np.indices(fg.shape)[0]
    rgba = np.dstack((rgb, fg.astype(np.uint8)*255))
    flesh = skin_mask(rgba, fg)
    r,g,b = rgb.astype(np.int32).transpose(2,0,1)
    # Include the source jaw's brown shadow, not only bright cheek colors.
    # Otherwise that shadow is closer to fabric and survives as a neck stripe.
    face_samples = fg & head & ~boundary(head) & (r > g+12) & (g > b+4)
    face_samples &= luminance(rgb) > 45
    cloth_samples = cloth & ~flesh & (yy >= hy.max()-1) & (luminance(rgb) > 90)
    if face_samples.sum() < 4 or cloth_samples.sum() < 4:
        return result
    face_palette = np.unique(rgb[face_samples], axis=0)
    cloth_palette = np.unique(rgb[cloth_samples], axis=0)
    # Restrict comparison to the chin/body. Source eyes and scalp fringes
    # must never be retained merely because they share a fabric color.
    candidates = fg & (yy >= hy.max()-1)
    values = rgb[candidates].astype(np.float32)
    ds = np.linalg.norm(values-face_palette[nearest_colors(values,face_palette)],axis=1)
    dc = np.linalg.norm(values-cloth_palette[nearest_colors(values,cloth_palette)],axis=1)
    plausible = np.zeros_like(fg)
    plausible[candidates] = (dc <= ds+6) & (dc < 65)
    result = cloth_samples.copy()
    for _ in range(5):
        result |= plausible & dilate(result,1)
    # Existing cool cloth already has its own protection. This classifier is
    # only a veto for warm pixels otherwise mistaken for skin; do not grow new
    # protection across neutral outlines of bare feet or hands.
    return result & fg & flesh


def source_palm_apertures(rgb, fg, base, base_fg):
    """Recover flesh and red/brown hand rims without exposing the forearm."""
    head, palms = base_landmarks(base, base_fg)
    r,g,b = rgb.astype(np.int32).transpose(2,0,1)
    ratio = (r-g)/np.maximum(g-b,1)
    flesh = skin_mask(np.dstack((rgb,fg.astype(np.uint8)*255)),fg)
    face = flesh & head & ~boundary(head)
    if face.sum() < 4:
        return np.zeros_like(fg)
    cutoff = max(1.15,float(np.percentile(ratio[face],25)))
    # Do not grow a palm through its cuff. The ordinary source-skin pass
    # handles skin outside base; this recovery step is restricted to the palm.
    zone = palms & ~head
    seeds = flesh & zone & (ratio >= cutoff)
    palette = np.unique(rgb[face],axis=0)
    values = rgb[seeds].astype(np.float32)
    if len(values):
        matched = np.linalg.norm(values-palette[nearest_colors(values,palette)],axis=1) <= 30
        seeds[seeds] = matched
    result = np.zeros_like(fg)
    for points in components(seeds):
        area = group_mask(fg.shape,points)
        if len(points) >= 2 and np.any(area & palms):
            result |= area
    red_rim = fg & zone & (luminance(rgb) < 115) & (r > g+5)
    red_rim &= ratio >= cutoff
    return result | (dilate(result,1) & red_rim)


def refine_bare_foot_edges(rgb, fg, base_fg, base_skin, removed, material, protected, head):
    """Assign neutral toe/heel fringes to nearby exposed skin or fabric.

    Only a narrow exterior band of an already exposed foot is eligible. Boots
    and hems have material anchors; a covered foot has no skin seed at all.
    """
    hy=np.nonzero(head)[0]; by=np.nonzero(base_fg)[0]
    if not len(hy) or not len(by):
        return removed
    yy=np.indices(fg.shape)[0]
    lower=yy > hy.max()+(by.max()-hy.max())*.55
    exposed=removed & base_skin & lower
    if not exposed.any():
        return removed
    light=luminance(rgb)
    saturation=np.ptp(rgb.astype(np.int16),axis=2)
    anchors=material & ~removed & (saturation > 28)
    # A few bright matte pixels around an old foot are not a white garment.
    # Require a connected neutral panel before using it as a fabric anchor.
    for points in components(material & ~removed & (saturation <= 28) & (light > 155)):
        if len(points) >= 9:
            anchors |= group_mask(fg.shape,points)
    allowed=fg & ~protected
    skin_distance=mask_distance(exposed,allowed,4)
    cloth_distance=mask_distance(anchors,allowed,4)
    neutral=saturation <= 45
    band=lower & ~base_fg & dilate(base_fg,2)
    discard=band & allowed & neutral & (skin_distance <= 3) & (skin_distance < cloth_distance)
    return removed | discard


def iterative_skin_residue(rgb, fg, base_skin, seed, removed, protected,
                           skin_palette, cloth_palette, *, max_passes=8):
    """Peel only connected, skin-like residue from a cutout, to a fixed point.

    Each pass adds at most one pixel of geodesic reach. A pixel must be near
    base skin, match the outfit sheet's learned face chroma better than its
    learned cloth chroma, and remain unprotected by collar/cuff evidence.
    The pass limit is deliberately small; empty frontiers stop immediately.
    """
    if skin_palette is None or cloth_palette is None or len(skin_palette) < 4 or len(cloth_palette) < 4:
        return np.zeros_like(fg)
    allowed = fg & dilate(base_skin, 3) & ~removed & ~protected
    if not np.any(allowed) or not np.any(seed):
        return np.zeros_like(fg)

    values = rgb[allowed].astype(np.float32)
    colors = values.astype(np.int32)
    r, g, b = colors.T
    ratios = (r-g) / np.maximum(g-b, 1)
    source_skin = np.asarray(skin_palette, dtype=np.float32)
    face_ratio = (source_skin[:, 0]-source_skin[:, 1]) / np.maximum(source_skin[:, 1]-source_skin[:, 2], 1)
    ratio_floor = max(.95, float(np.percentile(face_ratio, 15))*.68)
    warm = (r > g+5) & (g > b+1) & (r >= 38) & (ratios >= ratio_floor)

    def normalized_palette_distance(colors, palette):
        reference = palette / np.maximum(palette.sum(axis=1, keepdims=True), 1)
        distances = np.empty(len(colors), dtype=np.float32)
        # Process large frames in bounded chunks so memory use stays predictable.
        for start in range(0, len(colors), 4096):
            stop = min(len(colors), start+4096)
            chunk = colors[start:stop]
            normalized = chunk / np.maximum(chunk.sum(axis=1, keepdims=True), 1)
            distances[start:stop] = np.sqrt(
                ((normalized[:, None, :] - reference[None, :, :]) ** 2).sum(axis=2)
            ).min(axis=1)
        return distances

    face_distance = normalized_palette_distance(values, source_skin)
    cloth_distance = normalized_palette_distance(values, np.asarray(cloth_palette, dtype=np.float32))
    # Ambiguous cream highlights and warm embroidery have no clear skin-over-
    # cloth margin, so they stay in the garment for manual review.
    classified = warm & (face_distance <= .105) & ((cloth_distance-face_distance) >= .018)
    candidate = np.zeros_like(fg)
    candidate[allowed] = classified

    reached = seed.copy()
    result = np.zeros_like(fg)
    for _ in range(max_passes):
        frontier = candidate & dilate(reached, 1) & ~reached
        if not np.any(frontier):
            break
        result |= frontier
        reached |= frontier
    return result


def learn_sheet_material_palettes(base, outfit, *, rows, cols, threshold, cleanup):
    """Learn shared face and fabric colors from every aligned sheet frame."""
    cw, ch = base.width//cols, base.height//rows
    skin_samples, cloth_samples = [], []
    for row in range(rows):
        for col in range(cols):
            box = (col*cw, row*ch, (col+1)*cw, (row+1)*ch)
            b = np.asarray(base.crop(box).convert('RGBA'))
            o = np.asarray(outfit.crop(box).convert('RGBA'))
            base_fg = foreground_mask(b, threshold)
            rgb, fg, _ = clean_outfit(o, threshold, cleanup)
            head = base_head_mask(b, base_fg)
            rgba = np.dstack((rgb, fg.astype(np.uint8)*255))
            flesh = skin_mask(rgba, fg)
            face = flesh & head & ~boundary(head)
            if np.count_nonzero(face) >= 4:
                skin_samples.append(rgb[face])
            regions = occlusion_regions(b, base_fg, rgba, fg)
            cloth = regions['cloth'] & ~flesh & (luminance(rgb) > 35)
            if np.count_nonzero(cloth) >= 4:
                cloth_samples.append(rgb[cloth])
    skin = np.unique(np.concatenate(skin_samples, axis=0), axis=0) if skin_samples else None
    cloth = np.unique(np.concatenate(cloth_samples, axis=0), axis=0) if cloth_samples else None
    # Keep per-frame comparisons bounded even for large, unusually varied sheets.
    if skin is not None and len(skin) > 256:
        skin = skin[np.linspace(0, len(skin)-1, 256, dtype=np.int32)]
    if cloth is not None and len(cloth) > 256:
        cloth = cloth[np.linspace(0, len(cloth)-1, 256, dtype=np.int32)]
    return skin, cloth


def _overlay_frame_layers(base, outfit, *, background_threshold, skin_expand=0,
                          cleanup=3, overrides=None, profile=None, headwear=None, conservative=False,
                          sheet_skin_palette=None, sheet_cloth_palette=None):
    """Base underneath a cut-out outfit. Fabric always occludes the base."""
    b,o = np.asarray(base.convert('RGBA')),np.asarray(outfit.convert('RGBA'))
    base_fg = foreground_mask(b,background_threshold)
    rgb,fg,debris = clean_outfit(o,background_threshold,cleanup)
    cleaned = np.dstack((rgb,fg.astype(np.uint8)*255))
    regions = occlusion_regions(b,base_fg,cleaned,fg)
    base_skin = skin_mask(b,base_fg)
    candidate = skin_mask(cleaned,fg)
    protected_material = (warm_material_mask(b, base_fg, rgb, fg)
                          if headwear is not None else np.zeros_like(fg))
    collar = collar_material_mask(rgb,fg,regions['head'],regions['cloth'])
    tan_material = bool(protected_material.sum() >= max(24, int(fg.sum()*.2)))
    if tan_material:
        # On warm/tan outfits the torso and trouser panels can match the base
        # skin palette. Preserve source pixels over the central body panel;
        # exposed hands/arms remain governed by the base-pose skin test.
        body_y, body_x = np.indices(fg.shape)
        core_head = base_head_mask(b, base_fg)
        core_y, core_x = np.nonzero(core_head)
        if len(core_y):
            core_width = int(np.ptp(core_x))+1
            center = (core_x.min()+core_x.max())/2
            # Clothing protection begins below the chin, never inside the
            # source face. A height estimated from head width retained jaws.
            torso_start = int(core_y.max())+1
            core = (body_y >= torso_start) & (abs(body_x-center) <= core_width*.62)
            protected_material |= fg & base_fg & core
    structural_protection = protected_material.copy()
    candidate &= ~protected_material
    protected_material |= collar
    cuff_material = np.zeros_like(fg)
    if conservative:
        # A cuff's shaded green/blue material can be almost black. The later
        # rim cleanup must not treat these low-luminance cloth pixels as skin
        # outline merely because they border an exposed hand.
        head, palms = base_landmarks(b,base_fg)
        cr,cg,cb = rgb.astype(np.int32).transpose(2,0,1)
        olive = (cg-cb >= 8) & (cr-cg <= (cg-cb)*.95)
        cool = (cb >= cr+6) | ((cg >= cr+6) & (cg >= cb))
        cuff_material = fg & dilate(palms,5) & ~head & (olive | cool)
        protected_material |= cuff_material
        material_evidence = source_material_evidence(rgb,fg,regions['head'],regions['cloth'])
        # Base skin describes the body UNDER the outfit, not exposed skin in
        # the source. It must never override source fabric evidence. Rebuild
        # the apertures after the veto so false cloth seeds cannot drive the
        # later shadow/rim expansion into adjacent folds. The separate palm
        # pass recovers actual hands using source face chroma and palm geometry.
        protected_material |= material_evidence
        source_skin = outfit_skin_openings(
            rgb,fg,b,base_fg,
            protected_material | (headwear if headwear is not None else False))
    else:
        source_skin = outfit_skin_openings(
            rgb,fg,b,base_fg,protected_material | (headwear if headwear is not None else False))
    candidate &= ~collar
    candidate &= ~protected_material
    palette = np.unique(b[:,:,:3][base_skin],axis=0)
    flesh_samples = b[:,:,:3][base_skin & (luminance(b[:,:,:3]) > 150)].astype(np.float32)
    if len(flesh_samples):
        flesh_ratio = float(np.median((flesh_samples[:,0]-flesh_samples[:,1]) /
                                      np.maximum(flesh_samples[:,1]-flesh_samples[:,2],1)))
    else:
        flesh_ratio = 1.0
    source_ratio = (rgb[:,:,0].astype(np.float32)-rgb[:,:,1]) / np.maximum(rgb[:,:,1].astype(np.float32)-rgb[:,:,2],1)
    if tan_material:
        candidate &= source_ratio >= max(1.1, flesh_ratio*.92)
    skin = np.zeros(fg.shape,bool)
    if len(palette) and np.any(candidate):
        pixels = rgb[candidate]
        nearest = nearest_colors(pixels,palette)
        distance = np.linalg.norm(pixels.astype(np.float32)-palette[nearest].astype(np.float32),axis=1)
        yy = np.indices(fg.shape)[0]
        head_y = np.nonzero(base_head_mask(b, base_fg))[0]
        body = yy > (head_y.max()+1 if len(head_y) else -1)
        tolerance = np.where(body, 32, 65)
        if not tan_material:
            tolerance[:] = 65
        skin[candidate] = distance <= tolerance[candidate]
    if conservative:
        # Base palette similarity alone is not evidence that outfit is skin.
        # Only extend an aperture confirmed from the source face palette.
        skin &= dilate(source_skin,1)
    # Look for skin openings anywhere, including bare feet. Match to base
    # flesh spatially, so a warm ornament away from the body stays clothing.
    removable = source_skin.copy()
    for points in components(skin):
        area = group_mask(fg.shape,points)
        if np.any(area & dilate(base_skin,5)):
            # An enclosed colored pixel may be a cuff, collar or embroidery,
            # not skin. Hole filling here punched holes through real fabric.
            # Face interiors are handled separately by the head-specific mask.
            removable |= area
    # Replace warm generated face pixels against the base head footprint. The
    # loose color test handles one-pixel head shifts and shaded skin while
    # confident cloth colors remain on top.
    base_head = base_head_mask(b,base_fg)
    head_zone = dilate(base_head,2) & fg
    head_area = head_zone & ~regions['cloth'] & ~protected_material
    r,g,blue = (rgb[:,:,i].astype(np.int32) for i in range(3))
    face_tone = head_area & (r >= 105) & (r > g+12) & (g > blue+3)
    if tan_material:
        face_tone &= source_ratio >= max(1.1, flesh_ratio*.92)
    neutral_fringe = head_area & (np.max(rgb,axis=2).astype(np.int16)-np.min(rgb,axis=2).astype(np.int16) <= 42)
    neutral_fringe &= (luminance(rgb) >= 55) & (luminance(rgb) <= 245)
    if conservative and np.any(base_head):
        # A neutral pixel below the chin may be ivory collar fabric. Do not
        # let the broad face-fringe rule cut it merely for lacking saturation.
        neutral_fringe &= np.indices(fg.shape)[0] < np.nonzero(base_head)[0].max()-1
    base_ink = (luminance(b[:,:,:3]) < 100) & (np.linalg.norm(rgb.astype(np.float32)-b[:,:,:3],axis=2) < 65)
    removable |= face_tone | neutral_fringe | (head_zone & base_ink)
    # Skin shadows can be darker than skin_mask's brightness cutoff. Do not
    # let the cloth dilation claim these red/brown pixels and repaint them.
    # Require both attachment to an aperture and nearby base flesh geometry.
    warm_shadow = fg & (r > g+8) & (r > blue+12) & (g >= blue-8)
    warm_shadow &= luminance(rgb) > 35
    skin_distance = np.linalg.norm(rgb.astype(np.float32)-b[:,:,:3],axis=2)
    warm_shadow &= base_fg & (luminance(b[:,:,:3]) < 155) & (skin_distance < 50)
    for _ in range(2):
        removable |= dilate(removable,1) & warm_shadow
    # Dark green/blue embroidery is still material, not the rim of a fist.
    colored_material = ((g > r+8) & (g > blue+8)) | ((blue > r+8) & (blue > g+4))
    dark = (luminance(rgb) < 110) & ~colored_material
    # Remove old skin outlines only next to the detected aperture, keeping
    # dark seams attached to the surrounding garment.
    rim = dilate(removable,1) & dark & fg & ~regions['cloth']
    legacy_face_cut = regions['removed'] & dilate(regions['head'],2)
    if conservative:
        # Neck/hand openings already have source-color evidence above. The
        # legacy chroma rule is too broad for warm white collar highlights.
        legacy_face_cut &= base_head
    removed = removable | rim | legacy_face_cut
    # Keep the original anatomy's dark edge where both layers agree on its
    # color. This restores complete skin contours without cutting green/blue
    # sleeves or inventing a limb outside the base.
    same_edge = np.linalg.norm(rgb.astype(np.float32)-b[:,:,:3],axis=2) < 40
    removed |= dilate(removable,1) & base_fg & fg & dark & same_edge
    # Red skin shadows may sit over a bright base pixel. Brightness matching
    # alone misses them; require skin chroma and attachment to an aperture.
    red_shadow = fg & (r > g+14) & (r > blue+18) & (blue >= g*.66)
    red_shadow &= (r >= 40) & dilate(removed,1)
    removed |= red_shadow & (base_head | dilate(base_skin,1))
    removed &= ~protected_material
    material = (regions['cloth'] | protected_material) & ~removed
    chromatic = ((g > r+8) & (g > blue+8)) | ((blue > r+8) & (blue > g+4))
    material &= (luminance(rgb) >= 110) | (chromatic & (luminance(rgb) > 45))
    offsets = [(dy,dx) for dy in (-1,0,1) for dx in (-1,0,1) if dy or dx]
    skin_support = sum(shift(removed,dy,dx).astype(np.uint8) for dy,dx in offsets)
    cloth_support = sum(shift(material,dy,dx).astype(np.uint8) for dy,dx in offsets)
    # The old fist's dark rim belongs to its cutout unless it also borders
    # cloth. Preserve that shared cuff seam; discard free-standing skin rims.
    removed |= fg & dark & dilate(source_skin,1) & ~material & (cloth_support == 0)
    # Snap ambiguous dark fringes to the base only where skin surrounds them.
    # Colored sleeves and cuffs provide material support and remain in place.
    fringe = fg & dark & ~material & (skin_support >= 3) & (cloth_support <= 1)
    removed |= fringe & (~base_fg | boundary(base_fg))
    aperture_removed = removed.copy()
    # Read every gap in the lower silhouette, including off-center running
    # poses. Confirm bare openings on both sides so long robes remain intact.
    hy,hx = np.nonzero(base_head)
    by = np.nonzero(base_fg)[0]
    if len(hy) and len(by):
        start = int(hy.max()+max(8,round((by.max()-hy.max())*.48)))
        gap = np.zeros(fg.shape,bool)
        near = dilate(removed & base_skin,2)
        for y in range(start,min(base_fg.shape[0],int(by.max())+1)):
            occupied = np.flatnonzero(base_fg[y])
            for lo,hi in zip(occupied[:-1],occupied[1:]):
                if hi-lo <= 1:
                    continue
                gap[y,lo+1:hi] = True
        for points in components(gap):
            left_open = right_open = False
            for y in np.unique(points[:,0]):
                xs = points[points[:,0] == y,1]
                left_open |= bool(near[y,xs.min()-1])
                right_open |= bool(near[y,xs.max()+1])
            if left_open and right_open:
                # Bare feet on both sides do not prove that the entire middle
                # is empty: a long robe/ribbon may extend to the foot line.
                # A short bridge near the crotch is a different shape.
                region=group_mask(fg.shape,points)
                keep=np.zeros_like(fg)
                for cloth_points in components(region & material):
                    if cloth_points[:,0].max() >= int(by.max())-2:
                        keep |= group_mask(fg.shape,cloth_points)
                removed |= region & fg & ~dilate(keep,1)
    if headwear is not None:
        # Snap only ambiguous edge pixels near an already exposed foot.
        # A material neighborhood veto protects boots, hems and trouser legs.
        if len(hy) and len(by):
            yy = np.indices(fg.shape)[0]
            lower = yy > hy.max()+(by.max()-hy.max())*.55
            aperture = removed & base_skin & lower
            fringe = dilate(aperture, 2) & fg & lower & ~material & (cloth_support <= 2)
            removed |= fringe & (dark | red_shadow) & (boundary(base_fg) | ~base_fg)
        removed &= ~(headwear | protected_material)
    if conservative:
        # A base pose cannot tell us whether the source wears a skirt, ribbon
        # or trousers. Only the detected skin aperture may cut source material.
        removed = aperture_removed
    protected=protected_material | (headwear if headwear is not None else False)
    removed &= ~protected
    if conservative:
        palm_aperture = source_palm_apertures(rgb,fg,b,base_fg)
        palm_aperture &= ~structural_protection
        if headwear is not None:
            palm_aperture &= ~headwear
        removed |= palm_aperture
        if sheet_skin_palette is not None and sheet_cloth_palette is not None:
            skin_residue = iterative_skin_residue(
                rgb, fg, base_skin, source_skin | palm_aperture, removed,
                protected_material | collar | structural_protection |
                (headwear if headwear is not None else False),
                sheet_skin_palette, sheet_cloth_palette)
            removed |= skin_residue
    removed=refine_bare_foot_edges(rgb,fg,base_fg,base_skin,removed,material,protected,base_head)
    garment = fg & ~removed
    erase = np.zeros(fg.shape,bool)
    force_outfit = np.zeros(fg.shape,bool)
    if overrides is not None:
        labels = np.asarray(overrides.convert('RGBA'))
        marked = labels[:,:,3] >= 128
        reveal = marked & (labels[:,:,0] > 200) & (labels[:,:,1] < 100)
        keep = marked & (labels[:,:,2] > 200) & (labels[:,:,0] < 100)
        if headwear is not None:
            keep |= marked & (labels[:,:,0] > 200) & (labels[:,:,1] > 100) & (labels[:,:,2] < 100)
        force_outfit = keep
        erase = marked & (labels[:,:,1] > 200) & (labels[:,:,0] < 100)
        # Revealing outside the base means transparency, never invented skin.
        garment = (garment & ~reveal & ~erase) | (keep & foreground_mask(o,background_threshold))
    protected_spurs = force_outfit | (headwear if headwear is not None else False)
    if conservative:
        removed_spurs = 0
        # Cutting a source face/fist can strand tiny old rim fragments. Only
        # discard detached fragments touching that cut, not attached embroidery
        # or deliberately retained source/accessory pixels.
        for points in components(garment):
            if len(points) <= 2:
                fragment = group_mask(fg.shape, points)
                if np.any(fragment & dilate(removed, 1)) and not np.any(fragment & protected_spurs):
                    garment[fragment] = False
                    removed_spurs += len(points)
    else:
        garment, removed_spurs = remove_color_spurs(rgb, garment, protected_spurs)
    debris += removed_spurs
    anatomy = base_fg & ~garment & ~erase
    output = np.zeros_like(b)
    output[anatomy] = b[anatomy]
    output[garment,:3] = rgb[garment]
    output[anatomy | garment,3] = 255
    output[erase] = 0
    empty = np.zeros(fg.shape,bool)
    stats = dict(outfit_pixels=int(garment.sum()),restored_anatomy_pixels=int(anatomy.sum()),
        removed_outfit_anatomy_pixels=int((removed & fg).sum()),removed_noise_pixels=debris,
        head_pixels=int((anatomy & regions['head']).sum()),outlined_outfit_pixels=0,
        reconstructed_skin_pixels=0,protected_cloth_pixels=int(garment.sum()),
        restored_hand_pixels=int((anatomy & regions['hands']).sum()))
    return output,anatomy,garment,empty,stats


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


def coherent_fabric(rgb, fill, cell_size):
    """Remove weak isolated pigment noise without touching connected strokes."""
    cw,ch = cell_size
    yy,xx = np.indices(fill.shape)
    source = rgb.astype(np.float32)
    samples, validity = [], []
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            if not (dy or dx):
                continue
            valid = fill & shift(fill,dy,dx)
            valid &= (yy//ch == (yy-dy)//ch) & (xx//cw == (xx-dx)//cw)
            samples.append(shift(source,dy,dx))
            validity.append(valid)
    neighbors, valid = np.stack(samples), np.stack(validity)
    # Include self so empty neighborhoods have a finite median.
    stack = np.concatenate([np.where(valid[...,None],neighbors,np.nan),source[None]])
    median = np.nanmedian(stack,axis=0)
    distance = lambda a,b: np.sqrt(np.mean((a-b)**2,axis=-1))
    own = np.sum(valid & (distance(neighbors,source) < 12),axis=0)
    agreement = np.sum(valid & (distance(neighbors,median) < 12),axis=0)
    replace = fill & (valid.sum(axis=0) >= 5) & (own <= 1) & (agreement >= 4)
    replace &= distance(source,median) < 45
    # Select an existing neighbor color, not a blended new palette entry.
    nearest = np.where(valid,distance(neighbors,median),np.inf).argmin(axis=0)
    chosen = np.take_along_axis(neighbors,nearest[None,...,None],axis=0)[0]
    result = rgb.copy()
    result[replace] = chosen[replace].astype(np.uint8)
    return result


def shade_materials(rgb, fill, budget, cell_size):
    """Build shared material ramps, then redraw coherent shadow/mid/highlight areas."""
    rgb = coherent_fabric(rgb,fill,cell_size)
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
    # Smooth only small tonal fluctuations; strong folds remain at source value.
    weak = fill & (abs(levels-median) < 16)
    filtered[weak] = .5*levels[weak]+.5*median[weak]
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
        # Nearly identical tones should not become separate salt-and-pepper
        # patches. Preserve the palette budget as a ceiling, not a quota.
        merged = []
        for center in sorted(tone_centers):
            if not merged or center-merged[-1] >= 18:
                merged.append(center)
            else:
                merged[-1] = (merged[-1]+center)/2
        tone_centers = np.asarray(merged)
        shades = len(tone_centers)
        tone = abs(values[:,None]-tone_centers[None]).argmin(1)
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
    return coherent_fabric(result,fill,cell_size)


def clean_parallel_outline(rgb, fabric, contour, distances=(1,2)):
    """Recolor a redundant inner stroke alongside a continuous outer edge.

    Require three parallel pixels and a brighter inward fabric donor. This
    leaves crossing folds, narrow ribbons, dark panels and silhouettes intact.
    Run on one frame at a time, before palette fitting or seam normalization.
    """
    result = rgb.copy()
    light = luminance(rgb)
    dark = fabric & (light < 105) & ~contour
    repaired = np.zeros(fabric.shape,bool)
    for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
        ty,tx = -dx,dy
        run = dark & shift(dark,ty,tx) & shift(dark,-ty,-tx)
        run = dark & (run | shift(run,ty,tx) | shift(run,-ty,-tx))
        donor = shift(rgb,-dy,-dx)
        donor_light = shift(light,-dy,-dx)
        supported = shift(fabric,-dy,-dx) & (donor_light > 115) & (donor_light > light+55)
        for distance in distances:
            outer = shift(contour,dy*distance,dx*distance)
            parallel = outer & shift(outer,ty,tx) & shift(outer,-ty,-tx)
            gap = np.ones_like(fabric) if distance == 1 else (
                shift(fabric,dy,dx) & (shift(light,dy,dx) > light+35))
            take = run & supported & parallel & gap & ~repaired
            result[take] = donor[take]
            repaired |= take
    return result


def thin_contour(mask):
    """Thin ink, not alpha, while retaining endpoints and connected loops."""
    result = mask.copy()
    for _ in range(max(mask.shape)):
        changed = False
        for step in (0,1):
            n = [shift(result,dy,dx) for dy,dx in
                 ((1,0),(1,-1),(0,-1),(-1,-1),(-1,0),(-1,1),(0,1),(1,1))]
            degree = sum(p.astype(np.uint8) for p in n)
            transitions = sum((~n[i] & n[(i+1)%8]).astype(np.uint8) for i in range(8))
            allowed = (~(n[0]&n[2]&n[4]) & ~(n[2]&n[4]&n[6])) if step == 0 else (
                ~(n[0]&n[2]&n[6]) & ~(n[0]&n[4]&n[6]))
            remove = result & (degree >= 2) & (degree <= 6) & (transitions == 1) & allowed
            changed |= bool(remove.any())
            result[remove] = False
        if not changed:
            break
    # Tiny isolated ink marks can otherwise vanish in a parallel thinning
    # iteration. Retain one original pixel for each such component.
    for points in components(mask):
        if not np.any(result[points[:,0],points[:,1]]):
            p=points[np.argmin(((points-points.mean(axis=0))**2).sum(1))]
            result[p[0],p[1]]=True
    return result


def repaint_redundant_ink(rgb, fabric, redundant, retained):
    """Fill discarded ink from local cloth, never skin or another frame."""
    result = rgb.copy()
    donors = fabric & ~redundant & ~retained & (luminance(rgb) > 110)
    targets = np.argwhere(redundant)
    for y,x in targets:
        y0,y1=max(0,y-2),min(fabric.shape[0],y+3)
        x0,x1=max(0,x-2),min(fabric.shape[1],x+3)
        points = np.argwhere(donors[y0:y1,x0:x1])+[y0,x0]
        if len(points):
            p=points[np.argmin(((points-[y,x])**2).sum(1))]
            result[y,x]=rgb[p[0],p[1]]
    return result


def consolidate_palette_islands(rgb, fill, cell_size):
    """Merge isolated near-color dots after quantization, within a frame.

    Connected folds, high-contrast embroidery and anatomy are excluded. Votes
    use exact palette entries, so this cannot add colors or blur an edge.
    """
    result = rgb.copy()
    cw,ch = cell_size
    yy,xx = np.indices(fill.shape)
    offsets = [(dy,dx) for dy in (-1,0,1) for dx in (-1,0,1) if dy or dx]
    for _ in range(2):
        source = result.copy()
        neighbors = [shift(source,dy,dx) for dy,dx in offsets]
        valid = [fill & shift(fill,dy,dx) & (yy//ch == (yy-dy)//ch)
                 & (xx//cw == (xx-dx)//cw) for dy,dx in offsets]
        own = sum((v & np.all(n == source,axis=2)).astype(np.uint8)
                  for n,v in zip(neighbors,valid))
        best = np.zeros_like(own)
        for n,v in zip(neighbors,valid):
            votes = sum((nv & np.all(other == n,axis=2)).astype(np.uint8)
                        for other,nv in zip(neighbors,valid))
            distance = np.linalg.norm(source.astype(float)-n.astype(float),axis=2)
            # Only collapse a low-contrast singleton with a decisive local
            # majority. Thin highlights, stitches and line endpoints survive.
            take = v & (own <= 1) & (votes >= 6) & (votes > best) & (distance < 32)
            take &= (luminance(source) > 100) & (luminance(n) > 100)
            result[take] = n[take]
            best[take] = votes[take]
    return result


def clarify_fabric_tones(rgb, fill, cell_size, strength=.16, saturation=.04):
    """Gently separate source tones without turning shading into new ink.

    Pixels do not move, alpha is untouched, and flat cloth is left alone. The
    caller fits the adjusted pixels to the requested palette budget.
    """
    result = rgb.copy()
    levels = luminance(rgb).astype(np.float32)
    cw, ch = cell_size
    for y in range(0, fill.shape[0], ch):
        for x in range(0, fill.shape[1], cw):
            region = fill[y:y+ch, x:x+cw]
            tone = levels[y:y+ch, x:x+cw]
            if np.count_nonzero(region) < 8:
                continue
            values = tone[region]
            low, high = np.percentile(values, (10, 90))
            if high-low < 28:
                continue
            center = float(np.median(values))
            delta = tone-center
            eligible = region & (np.abs(delta) >= 6)
            if not np.any(eligible):
                continue
            # Large contrast changes turn antialiased folds into dark flecks
            # and flatten ivory highlights. Bound the tonal change regardless
            # of how bright the other materials in this frame happen to be.
            shift = np.clip(delta[eligible]*strength, -8, 8)
            source = rgb[y:y+ch, x:x+cw].astype(np.float32)
            chroma = source[eligible] - tone[eligible, None]
            source[eligible] = tone[eligible, None] + shift[:, None] + chroma*(1+saturation)
            result[y:y+ch, x:x+cw][eligible] = np.clip(np.rint(source[eligible]),0,255).astype(np.uint8)
    return result


def fit_source_palette(rgb, fill, budget, cell_size, *, redraw=False):
    """Fit a crisp, source-only palette without smoothing pixel structure.

    A single shared palette retains hues and shading across frames. No color
    dithering or interpolated colors; these create speckles or muddy ramps at
    sprite scale. Optional tone separation is bounded, and palette centers
    snap to real source pixels.
    """
    source = coherent_fabric(rgb,fill,cell_size)
    working = clarify_fabric_tones(source,fill,cell_size) if redraw else source
    pixels = source[fill]
    targets = working[fill]
    if not len(pixels):
        return source
    source_palette = np.unique(pixels,axis=0)
    if len(source_palette) <= budget:
        result = source.copy()
        result[fill] = source_palette[nearest_colors(targets,source_palette)]
        return consolidate_palette_islands(result,fill,cell_size)
    sample = Image.fromarray(pixels.reshape(1,-1,3))
    quantized = sample.quantize(colors=budget,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    raw = np.asarray(quantized.getpalette(),np.uint8).reshape(-1,3)
    palette = raw[np.unique(np.asarray(quantized))].astype(np.float32)
    weights = np.array([.299,.587,.114],np.float32)
    # Refine with all source pixels, then snap each center to its nearest real
    # source color. This prevents muddy averaged shades and invented pixels.
    for _ in range(6):
        labels = nearest_colors(pixels,palette)
        for i in range(len(palette)):
            selected = pixels[labels == i]
            if len(selected):
                center = selected.mean(axis=0)
                distance = ((selected.astype(np.float32)-center)**2*weights).sum(axis=1)
                palette[i] = selected[np.argmin(distance)]
    palette = np.rint(palette).astype(np.uint8)
    result = source.copy()
    result[fill] = palette[nearest_colors(targets,palette)]
    return consolidate_palette_islands(result,fill,cell_size)


def garment_edge_mask(rgb, foreground, fabric, anatomy):
    """Repair supported silhouette strokes and existing seams, never skin joins.

    Internal strokes require a source luminance valley and a connected run;
    this prevents a bright collar or an isolated shading dot becoming ink.
    """
    light = luminance(rgb)
    neighbors = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
    support = sum(shift(foreground, dy, dx).astype(np.uint8) for dy, dx in neighbors)
    outside = boundary(foreground) & fabric
    # The silhouette is geometry, not a luminance threshold. Bright hems and
    # soles need a border too. Thin ribbon tips retain their source color.
    contour = outside & ((light < 110) | (support >= 4))
    valleys = np.zeros_like(fabric)
    for dy, dx in ((0, 1), (1, 0)):
        a, b = shift(light, dy, dx), shift(light, -dy, -dx)
        backed = shift(fabric, dy, dx) & shift(fabric, -dy, -dx)
        valleys |= backed & (a > light+25) & (b > light+25)
    valleys &= fabric & (light < 105) & ~dilate(anatomy, 1) & ~dilate(outside, 1)
    for points in components(valleys):
        if len(points) >= 3:
            contour |= group_mask(fabric.shape, points)
    return contour


def repaint(rgba, anatomy, garment, *, colors, paint, outline, cell_size, headwear=None, conservative=False):
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
                # The composite silhouette hides internal cuff/collar edges.
                # Normalize existing dark cloth-side pixels at those joins,
                # without adding ink over the original base hand or face.
                skin = anatomy[y:y+ch,x:x+cw]
                joint = np.logical_or.reduce([shift(skin,dy,dx)
                                             for dy,dx in ((0,1),(0,-1),(1,0),(-1,0))])
                base_ink = skin & (light < 105)
                beside_base_ink = np.logical_or.reduce([shift(base_ink,dy,dx)
                                                       for dy,dx in ((0,1),(0,-1),(1,0),(-1,0))])
                cloth_support = sum(shift(fabric,dy,dx).astype(np.uint8)
                                    for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)))
                # Reconstruct missing cuff boundaries, but use the base's
                # existing ink as the shared edge when it already has one.
                if not conservative:
                    contours[y:y+ch,x:x+cw] |= joint & fabric & ~beside_base_ink & (cloth_support >= 2)
                duplicate = fabric & beside_base_ink & (light < 105) & ~boundary(fg)
                contours[y:y+ch,x:x+cw] &= ~duplicate
                tile = out[y:y+ch,x:x+cw,:3]
                if conservative:
                    contours[y:y+ch,x:x+cw] = garment_edge_mask(tile,fg,fabric,skin)
                    # Remove the cloth-side duplicate directly under an
                    # already restored palm outline, but leave neck joins alone.
                    head_y = np.nonzero(base_head_mask(out[y:y+ch,x:x+cw],skin))[0]
                    if len(head_y):
                        yy = np.indices(skin.shape)[0]
                        cuff_duplicate = duplicate & (yy > head_y.max()+2)
                        tile[:] = repaint_redundant_ink(tile,fabric,cuff_duplicate,
                            contours[y:y+ch,x:x+cw])
                    tile[:] = clean_parallel_outline(tile, fabric,
                        contours[y:y+ch,x:x+cw], distances=(1,))
                else:
                    tile[:] = repaint_redundant_ink(tile,fabric,duplicate,contours[y:y+ch,x:x+cw])
                    tile[:] = clean_parallel_outline(tile,fabric,contours[y:y+ch,x:x+cw])
                light = luminance(tile)
                # Internal folds keep their source tones. Turning local dark
                # ridges into uniform ink produced false stitches and speckles.
        out[contours,:3] = ink
    locked = np.unique(out[:,:,:3][anatomy | contours],axis=0)
    fill = garment & ~contours
    if colors and len(locked) > colors:
        raise ValueError(f'Palette needs at least {len(locked)} colors to preserve base anatomy; choose a larger limit')
    if colors and np.any(fill):
        remaining = colors-len(locked)
        if remaining < 1:
            raise ValueError(f'Palette needs at least {len(locked)+1} colors to preserve base anatomy; choose a larger limit')
        if paint in (3,4):
            out[:,:,:3] = fit_source_palette(out[:,:,:3],fill,remaining,cell_size,redraw=paint == 4)
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
                 base_profile=None, lock_base=False, retouch=None, composition='pinned', accessories=False):
    if composition not in ('layers','pinned','cutout'):
        raise ValueError('Unknown composition mode')
    if not isinstance(rows,int) or not isinstance(cols,int) or not 1 <= rows <= 64 or not 1 <= cols <= 64:
        raise ValueError('Rows and columns must be between 1 and 64')
    if base.size != outfit.size:
        raise ValueError(f'Base and outfit sizes differ: {base.size} vs {outfit.size}')
    if base.width % cols or base.height % rows:
        raise ValueError('Sheet size is not divisible by the requested grid')
    if not 0 <= colors <= 256 or not np.isfinite(background_threshold) or not 0 <= background_threshold <= 255:
        raise ValueError('Invalid palette limit or background threshold')
    if not 0 <= skin_expand <= 4 or not 0 <= cleanup <= 16 or paint not in (0,1,2,3,4):
        raise ValueError('Invalid cleanup, paint or skin expansion setting')
    if overrides is not None and overrides.size != base.size:
        raise ValueError('Correction mask must match the sheet dimensions')
    if base_profile is not None and base_profile.size != base.size:
        raise ValueError('Base profile must match the sheet dimensions')
    if retouch is not None and retouch.size != base.size:
        raise ValueError('Retouch layer must match the sheet dimensions')
    if composition == 'pinned' and lock_base and base_profile is None:
        base_profile = build_base_profile(base,rows=rows,cols=cols,threshold=background_threshold)
    cw, ch = base.width//cols, base.height//rows
    sheet_skin_palette, sheet_cloth_palette = (None, None)
    if composition == 'cutout':
        sheet_skin_palette, sheet_cloth_palette = learn_sheet_material_palettes(
            base, outfit, rows=rows, cols=cols, threshold=background_threshold, cleanup=cleanup)
    output = np.zeros((base.height,base.width,4),np.uint8)
    anatomy = np.zeros(output.shape[:2],bool)
    garment = np.zeros(output.shape[:2],bool)
    reconstructed = np.zeros(output.shape[:2],bool)
    headwear = np.zeros(output.shape[:2],bool)
    reports = []
    for row in range(rows):
        for col in range(cols):
            x,y = col*cw,row*ch
            box = (x,y,x+cw,y+ch)
            compose = _overlay_frame_layers if composition != 'pinned' else _frame_layers
            extra = {}
            if composition == 'cutout':
                extra['conservative'] = True
                extra['sheet_skin_palette'] = sheet_skin_palette
                extra['sheet_cloth_palette'] = sheet_cloth_palette
            if accessories and composition != 'pinned':
                h = headwear_mask(base.crop(box), outfit.crop(box), background_threshold, cleanup)
                if overrides is not None:
                    labels = np.asarray(overrides.crop(box).convert('RGBA'))
                    marked = labels[:,:,3] >= 128
                    force_head = marked & (labels[:,:,0] > 200) & (labels[:,:,1] > 100) & (labels[:,:,2] < 100)
                    h = (h & ~marked) | force_head
                headwear[y:y+ch,x:x+cw] = h
                extra['headwear'] = h
            out,a,g,s,stats = compose(base.crop(box),outfit.crop(box),background_threshold=background_threshold,
                                         skin_expand=skin_expand,cleanup=cleanup,
                                         overrides=overrides.crop(box) if overrides is not None else None,
                                         profile=base_profile.crop(box) if base_profile is not None else None, **extra)
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
    output,contours = repaint(output,anatomy | reconstructed | painted,garment,colors=colors,paint=paint,outline=outline,cell_size=(cw,ch),headwear=headwear if accessories else None,conservative=composition == 'cutout')
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
        if accessories:
            mask[headwear & (garment | painted)] = [255,200,0,255]
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
    parser.add_argument('--paint',type=int,choices=(0,1,2,3,4),default=4)
    parser.add_argument('--base-profile',type=Path)
    parser.add_argument('--retouch',type=Path)
    parser.add_argument('--composition',choices=('cutout','layers','pinned'),default='cutout')
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
                                 composition=getattr(args,'composition','pinned'),
                                 retouch=load_rgba(args.retouch) if getattr(args,'retouch',None) else None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    result.save(args.output)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({'frames':report},indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
