"""Reproducible, non-generative asset cleanup experiment (Pillow + NumPy).

Reads the supplied sheet and ZIP; never overwrites either. The demo uses
reviewed item bounds, not a claim of automatic semantic item segmentation.
No resize is performed on exported items. Previews use integer nearest scale.
"""
from __future__ import annotations

import argparse
from collections import deque
import io
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont


SAMPLES = [(19, "platform", "Bục đá / cỏ"), (167, "gate", "Cổng / mái ngói"),
           (158, "bamboo", "Cụm tre / lá mảnh")]

# Visually reviewed exclusions in crop-local coordinates. The gate rectangle
# includes fragments of adjacent sheet items; these are NOT automatic repairs.
MANUAL_EXCLUSIONS = {"gate": [(0, 23, 9, 31), (160, 68, 163, 76),
                              (76, 151, 85, 154), (161, 148, 163, 153),
                              (162, 104, 163, 106)]}


def stats(a):
    alpha = a[..., 3]
    visible = alpha > 0
    return {"size": [a.shape[1], a.shape[0]],
            "visible_pixels": int(visible.sum()),
            "rgb_colors_visible": int(len(np.unique(a[..., :3][visible], axis=0))),
            "partial_alpha_pixels": int(((alpha > 0) & (alpha < 255)).sum())}


def mask_from_alpha(alpha, low=110, high=200):
    """Keep high-confidence seeds and connected edge pixels; no erosion.

    Isolated low-alpha specks are rejected. Disconnected leaves with strong
    seeds are retained. Thresholds are demo settings, not a universal key.
    """
    allowed = alpha >= low
    keep = alpha >= high
    q = deque(zip(*np.nonzero(keep)))
    h, w = alpha.shape
    while q:
        y, x = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and allowed[yy, xx] and not keep[yy, xx]:
                keep[yy, xx] = True
                q.append((yy, xx))
    return keep


def smooth_inside(rgb, mask, sigma=16):
    """Small masked bilateral filter; excludes hidden background RGB."""
    p = np.pad(rgb.astype(np.float32), ((1, 1), (1, 1), (0, 0)), mode="edge")
    m = np.pad(mask, 1)
    h, w = mask.shape
    center = rgb.astype(np.float32)
    total = np.zeros_like(center)
    weights = np.zeros((h, w), np.float32)
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            neighbor = p[1+dy:1+dy+h, 1+dx:1+dx+w]
            distance = ((center-neighbor)**2).sum(axis=2)
            weight = np.exp(-distance/(2*sigma*sigma)-(dx*dx+dy*dy)/2)
            weight *= m[1+dy:1+dy+h, 1+dx:1+dx+w]
            total += neighbor*weight[..., None]
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
    lms = np.stack([l+.3963377774*a+.2158037573*b,
                    l-.1055613458*a-.0638541728*b,
                    l-.0894841775*a-1.2914855480*b], axis=-1)**3
    linear = lms @ np.array([[4.0767416621, -3.3077115913, .2309699292],
                            [-1.2684380046, 2.6097574011, -.3413193965],
                            [-.0041960863, -.7034186147, 1.7076147010]], np.float32).T
    linear = np.clip(linear, 0, 1)
    s = np.where(linear <= .0031308, 12.92*linear, 1.055*linear**(1/2.4)-.055)
    return np.clip(np.rint(s*255), 0, 255).astype(np.uint8)


def color_finish(rgb, mask):
    lab = to_oklab(smooth_inside(rgb, mask))
    lab[..., 0] = np.clip((lab[..., 0]-.5)*1.04+.507, 0, 1)
    lab[..., 1:] *= 1.08
    return from_oklab(lab)


def learn_palette(samples, count):
    pixels = np.concatenate([rgb[mask] for rgb, mask in samples])
    # Foreground-only fitting: transparent matte never consumes palette slots.
    train = Image.fromarray(pixels.reshape((-1, 1, 3)))
    p = train.quantize(colors=count, method=Image.Quantize.MEDIANCUT,
                       dither=Image.Dither.NONE)
    indices = np.unique(np.asarray(p)).tolist()
    return np.array(p.getpalette(), np.uint8).reshape((-1, 3))[indices]


def palette_map(rgb, mask, palette):
    out = np.zeros((*mask.shape, 4), np.uint8)
    plab = to_oklab(palette)
    pixels = to_oklab(rgb[mask])
    result = []
    for offset in range(0, len(pixels), 4096):
        delta = pixels[offset:offset+4096, None, :]-plab[None, :, :]
        # Preserve light/shadow ordering more strongly than tiny hue shifts.
        delta[..., 0] *= 1.2
        result.append(palette[np.argmin((delta*delta).sum(axis=2), axis=1)])
    if result:
        out[mask, :3] = np.concatenate(result)
    out[mask, 3] = 255
    return out


def font(size):
    for name in ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"]:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def checker(size, step=12):
    yy, xx = np.indices((size[1], size[0]))
    v = ((xx//step + yy//step) % 2)[..., None]
    rgb = np.where(v, np.array([207, 215, 215]), np.array([233, 239, 238]))
    return Image.fromarray(rgb.astype(np.uint8)).convert("RGBA")


def place_preview(canvas, arr, x, y, scale):
    im = Image.fromarray(arr).resize((arr.shape[1]*scale, arr.shape[0]*scale),
                                     Image.Resampling.NEAREST)
    canvas.alpha_composite(im, (x, y))


def comparison(samples, output):
    columns = ["Sheet gốc + alpha gốc", "PNG trong ZIP", "Python · giữ chi tiết", "Python · 128 màu chung"]
    width, colw = 2080, 510
    rows = [(s, 4 if s["slug"] == "platform" else 3) for s in samples]
    heights = [s["source"].shape[0]*scale+100 for s, scale in rows]
    canvas = Image.new("RGBA", (width, 175+sum(heights)), "#14272d")
    d = ImageDraw.Draw(canvas)
    d.text((28, 22), "THỬ NGHIỆM LÀM SẠCH ASSET BẰNG PYTHON", font=font(31), fill="#edf7ef")
    d.text((28, 67), "Cùng kích thước nguồn · phóng nguyên lần bằng Nearest · chưa vẽ lại cấu trúc bị thiếu", font=font(21), fill="#bfd3d0")
    for j, label in enumerate(columns):
        d.text((20+j*colw, 121), label, font=font(23), fill="#e5efb4")
    y = 170
    for s, scale in rows:
        h, w = s["source"].shape[:2]
        for j, key in enumerate(["source", "zip", "detail", "palette128"]):
            x = 20+j*colw
            canvas.alpha_composite(checker((colw-14, h*scale+22)), (x, y))
            place_preview(canvas, s[key], x+(colw-14-w*scale)//2, y+11, scale)
            d.text((x, y+h*scale+31), f'{s["label"]} · {w}×{h} px · xem {scale}×', font=font(19), fill="#edf7ef")
            colors = stats(s[key])["rgb_colors_visible"]
            d.text((x, y+h*scale+58), f'{colors:,} màu RGB trong phần hiện', font=font(17), fill="#a7c4c2")
        y += h*scale+100
    canvas.convert("RGB").save(output/"comparison.png")


def background_check(samples, output):
    # White exposes dark/matte fringes; navy exposes pale fringes and holes.
    canvas = Image.new("RGBA", (1500, 640), "#14272d")
    d = ImageDraw.Draw(canvas)
    d.text((25, 15), "128 màu chung trên nền sáng và tối · PNG xuất giữ nguyên kích thước", font=font(24), fill="white")
    x = 20
    for s in samples:
        a = s["palette128"]
        scale = 2
        w, h = a.shape[1]*scale, a.shape[0]*scale
        for y, color in [(75, "#ffffff"), (365, "#0d202c")]:
            local_scale = max(1, min(scale, 450//a.shape[1], 225//a.shape[0]))
            cell = Image.new("RGBA", (475, 245), color)
            place_preview(cell, a, (475-a.shape[1]*local_scale)//2,
                          (245-a.shape[0]*local_scale)//2, local_scale)
            canvas.alpha_composite(cell, (x, y))
        d.text((x, 45), s["label"], font=font(19), fill="#d0dfd9")
        x += 493
    canvas.convert("RGB").save(output/"background-check.png")


def compact_comparison(samples, output):
    selected = samples[:2]
    height = 135 + sum(s["source"].shape[0]*(4 if s["slug"] == "platform" else 3)+70 for s in selected)
    canvas = Image.new("RGBA", (1050, height), "#14272d")
    d = ImageDraw.Draw(canvas)
    d.text((24, 19), "MẪU THỬ PYTHON · GIỮ KÍCH THƯỚC NGUỒN", font=font(26), fill="white")
    d.text((24, 62), "Cùng hình mẫu, không dựng thêm chi tiết đã mất", font=font(20), fill="#bcd2d0")
    d.text((24, 105), "PNG trong ZIP", font=font(22), fill="#e5efb4")
    d.text((535, 105), "Python từ nguồn · 128 màu chung", font=font(22), fill="#e5efb4")
    y = 146
    for s in selected:
        scale = 4 if s["slug"] == "platform" else 3
        h, w = s["source"].shape[:2]
        for x, key in [(20, "zip"), (535, "palette128")]:
            canvas.alpha_composite(checker((495, h*scale+12)), (x, y))
            place_preview(canvas, s[key], x+(495-w*scale)//2, y+6, scale)
            d.text((x, y+h*scale+22), f'{s["label"]} · {w}×{h} px · {scale}×', font=font(18), fill="#edf7ef")
        y += h*scale+70
    canvas.convert("RGB").save(output/"before-after.png")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sheet", type=Path, required=True)
    p.add_argument("--zip", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    output = args.out
    output.mkdir(parents=True, exist_ok=True)
    sheet = np.array(Image.open(args.sheet).convert("RGBA"))
    audit = {"sheet": stats(sheet), "zip_assets": [], "samples": []}
    samples = []
    with zipfile.ZipFile(args.zip) as z:
        manifest = json.loads(z.read("manifest.json"))
        for name in sorted(z.namelist()):
            if name.startswith("items/") and name.endswith(".png"):
                arr = np.array(Image.open(io.BytesIO(z.read(name))).convert("RGBA"))
                audit["zip_assets"].append({"file": name, **stats(arr)})
        byname = {a["file"]: a for a in manifest["assets"]}
        for number, slug, label in SAMPLES:
            name = f"asset_{number:03d}.png"
            entry = byname[name]
            x0, y0, x1, y1 = entry["source_box"]
            # ZIP dimensions are bbox minus one pixel per edge. Align the
            # experiment to that exact rectangle; keep the original record.
            box = (x0+1, y0+1, x1-1, y1-1)
            src = sheet[box[1]:box[3], box[0]:box[2]].copy()
            old = np.array(Image.open(io.BytesIO(z.read("items/"+name))).convert("RGBA"))
            if old.shape != src.shape:
                raise ValueError(f"Unexpected manifest/crop shape for {name}")
            mask = mask_from_alpha(src[..., 3])
            for ex0, ey0, ex1, ey1 in MANUAL_EXCLUSIONS.get(slug, []):
                mask[ey0:ey1, ex0:ex1] = False
            rgb = color_finish(src[..., :3], mask)
            detail = np.dstack([rgb, mask.astype(np.uint8)*255])
            detail[~mask, :3] = 0
            samples.append(dict(slug=slug, label=label, source=src, zip=old,
                                detail=detail, mask=mask, rgb=rgb, box=box, zip_file=name))
    train = [(s["rgb"], s["mask"]) for s in samples]
    palette = learn_palette(train, 128)
    pal48 = learn_palette(train, 48)
    for s in samples:
        s["palette128"] = palette_map(s["rgb"], s["mask"], palette)
        s["palette48"] = palette_map(s["rgb"], s["mask"], pal48)
        folder = output/s["slug"]
        folder.mkdir(exist_ok=True)
        for key in ["source", "zip", "detail", "palette128", "palette48"]:
            Image.fromarray(s[key]).save(folder/f"{key}.png")
        Image.fromarray(s["mask"].astype(np.uint8)*255).save(folder/"mask.png")
        m = s["mask"]
        for key in ["detail", "palette128", "palette48"]:
            assert s[key].shape == s["source"].shape
            assert np.array_equal(s[key][..., 3] > 0, m)
            assert set(np.unique(s[key][..., 3])) <= {0, 255}
        assert stats(s["palette128"])["rgb_colors_visible"] <= 128
        assert stats(s["palette48"])["rgb_colors_visible"] <= 48
        zm = s["zip"][..., 3] > 0
        audit["samples"].append({"name": s["slug"], "zip_file": s["zip_file"],
            "source_crop": s["box"], "mask_parameters": {"low": 110, "high": 200},
            "manual_exclusions": MANUAL_EXCLUSIONS.get(s["slug"], []),
            "mask_iou_vs_zip": round(float((m & zm).sum()/max(1, (m | zm).sum())), 5),
            "pixels_added_vs_zip": int((m & ~zm).sum()),
            "pixels_removed_vs_zip": int((~m & zm).sum()),
            "variants": {key: stats(s[key]) for key in ["source", "zip", "detail", "palette128", "palette48"]}})
    audit["validation"] = {"same_dimensions_all_variants": True,
                           "same_accepted_mask_all_repaints": True,
                           "binary_alpha_exports": True,
                           "palette_budgets_verified": True,
                           "pixel_art_reconstruction": False,
                           "production_tileset": False}
    (output/"audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    (output/"palette128.hex").write_text("\n".join("#"+"".join(f"{c:02x}" for c in p) for p in palette), encoding="ascii")
    swatches = Image.new("RGB", (512, 256))
    draw = ImageDraw.Draw(swatches)
    for i, c in enumerate(palette):
        x, y = (i%16)*32, (i//16)*32
        draw.rectangle((x, y, x+31, y+31), fill=tuple(int(v) for v in c))
    swatches.save(output/"palette128.png")
    comparison(samples, output)
    background_check(samples, output)
    compact_comparison(samples, output)
    print(json.dumps({"assets_audited": len(audit["zip_assets"]),
                      "zip_max_colors": max(a["rgb_colors_visible"] for a in audit["zip_assets"]),
                      "zip_partial_alpha": sum(a["partial_alpha_pixels"] for a in audit["zip_assets"]),
                      "samples": audit["samples"], "validation": audit["validation"]}, indent=2))


if __name__ == "__main__":
    main()
