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


def _overlay_frame_layers(base, outfit, *, background_threshold, skin_expand=0,
                          cleanup=3, overrides=None, profile=None):
    """Base underneath a cut-out outfit. Fabric always occludes the base."""
    b,o = np.asarray(base.convert('RGBA')),np.asarray(outfit.convert('RGBA'))
    base_fg = foreground_mask(b,background_threshold)
    rgb,fg,debris = clean_outfit(o,background_threshold,cleanup)
    cleaned = np.dstack((rgb,fg.astype(np.uint8)*255))
    regions = occlusion_regions(b,base_fg,cleaned,fg)
    base_skin = skin_mask(b,base_fg)
    candidate = skin_mask(cleaned,fg)
    palette = np.unique(b[:,:,:3][base_skin],axis=0)
    skin = np.zeros(fg.shape,bool)
    if len(palette) and np.any(candidate):
        pixels = rgb[candidate]
        nearest = nearest_colors(pixels,palette)
        distance = np.linalg.norm(pixels.astype(np.float32)-palette[nearest].astype(np.float32),axis=1)
        skin[candidate] = distance <= 65
    # Look for skin openings anywhere, including bare feet. Match to base
    # flesh spatially, so a warm ornament away from the body stays clothing.
    removable = np.zeros(fg.shape,bool)
    for points in components(skin):
        area = group_mask(fg.shape,points)
        if np.any(area & dilate(base_skin,5)):
            removable |= fill_holes(area) & fg
    # Replace warm generated face pixels against the base head footprint. The
    # loose color test handles one-pixel head shifts and shaded skin while
    # confident cloth colors remain on top.
    base_head = base_head_mask(b,base_fg)
    head_zone = dilate(base_head,2) & fg
    head_area = head_zone & ~regions['cloth']
    r,g,blue = (rgb[:,:,i].astype(np.int32) for i in range(3))
    face_tone = head_area & (r >= 105) & (r > g+12) & (g > blue+3)
    neutral_fringe = head_area & (np.max(rgb,axis=2).astype(np.int16)-np.min(rgb,axis=2).astype(np.int16) <= 42)
    neutral_fringe &= (luminance(rgb) >= 55) & (luminance(rgb) <= 245)
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
    dark = luminance(rgb) < 110
    # Remove old skin outlines only next to the detected aperture, keeping
    # dark seams attached to the surrounding garment.
    rim = dilate(removable,1) & dark & fg & ~regions['cloth']
    removed = removable | rim | (regions['removed'] & dilate(regions['head'],2))
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
    material = regions['cloth'] & ~removed
    chromatic = ((g > r+8) & (g > blue+8)) | ((blue > r+8) & (blue > g+4))
    material &= (luminance(rgb) >= 110) | (chromatic & (luminance(rgb) > 45))
    offsets = [(dy,dx) for dy in (-1,0,1) for dx in (-1,0,1) if dy or dx]
    skin_support = sum(shift(removed,dy,dx).astype(np.uint8) for dy,dx in offsets)
    cloth_support = sum(shift(material,dy,dx).astype(np.uint8) for dy,dx in offsets)
    # Snap ambiguous dark fringes to the base only where skin surrounds them.
    # Colored sleeves and cuffs provide material support and remain in place.
    fringe = fg & dark & ~material & (skin_support >= 3) & (cloth_support <= 1)
    removed |= fringe & (~base_fg | boundary(base_fg))
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
                removed |= group_mask(fg.shape,points) & fg
    garment = fg & ~removed
    erase = np.zeros(fg.shape,bool)
    if overrides is not None:
        labels = np.asarray(overrides.convert('RGBA'))
        marked = labels[:,:,3] >= 128
        reveal = marked & (labels[:,:,0] > 200) & (labels[:,:,1] < 100)
        keep = marked & (labels[:,:,2] > 200) & (labels[:,:,0] < 100)
        erase = marked & (labels[:,:,1] > 200) & (labels[:,:,0] < 100)
        # Revealing outside the base means transparency, never invented skin.
        garment = (garment & ~reveal & ~erase) | (keep & foreground_mask(o,background_threshold))
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
                    # Ink follows narrow ridges; broad shadows stay in the
                    # material ramp instead of becoming solid black patches.
                    ridge = np.zeros(fabric.shape,bool)
                    for dy,dx in ((0,1),(1,0),(1,1),(1,-1)):
                        a = shift(light,dy,dx)
                        b = shift(light,-dy,-dx)
                        paired = shift(fabric,dy,dx) & shift(fabric,-dy,-dx)
                        ridge |= paired & (a > light+12) & (b > light+12)
                    block = dark & shift(dark,0,1) & shift(dark,1,0) & shift(dark,1,1)
                    thick = block | shift(block,-1,0) | shift(block,0,-1) | shift(block,-1,-1)
                    contours[y:y+ch,x:x+cw] |= dark & ridge & ~thick & (adjacent >= 1) & (bright-light > 55)
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
                 base_profile=None, lock_base=False, retouch=None, composition='pinned'):
    if composition not in ('layers','pinned'):
        raise ValueError('Unknown composition mode')
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
    if composition == 'pinned' and lock_base and base_profile is None:
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
            compose = _overlay_frame_layers if composition == 'layers' else _frame_layers
            out,a,g,s,stats = compose(base.crop(box),outfit.crop(box),background_threshold=background_threshold,
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
    parser.add_argument('--composition',choices=('layers','pinned'),default='layers')
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
