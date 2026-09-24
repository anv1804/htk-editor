#!/usr/bin/env python3
"""Repair outfit sprite sheets by reusing anatomy from a clean base sheet.

The tool assumes the base and outfit sheets share the same grid. It keeps the
outfit pixels, but replaces skin, facial dark details, and other anatomy pixels
with the clean base sprite so generated clothes do not smear hands, eyes, or
skin tones. Output is RGBA with binary alpha and an optional compact palette.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, type=Path, help="Clean base sprite sheet")
    parser.add_argument("--outfit", required=True, type=Path, help="Outfit sprite sheet to repair")
    parser.add_argument("--output", required=True, type=Path, help="Repaired RGBA PNG sheet")
    parser.add_argument("--rows", type=int, default=7)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--colors", type=int, default=64, help="0 disables color cleanup")
    parser.add_argument("--background-threshold", type=float, default=36.0)
    parser.add_argument("--skin-expand", type=int, default=1)
    parser.add_argument("--report", type=Path, help="Optional JSON repair report")
    return parser.parse_args()


def load_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def largest_component(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    seen = np.zeros(mask.shape, dtype=bool)
    best: list[tuple[int, int]] = []
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        queue = deque([(int(y), int(x))])
        seen[y, x] = True
        component: list[tuple[int, int]] = []
        while queue:
            cy, cx = queue.popleft()
            component.append((cy, cx))
            for ny in range(max(0, cy - 1), min(height, cy + 2)):
                for nx in range(max(0, cx - 1), min(width, cx + 2)):
                    if mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        queue.append((ny, nx))
        if len(component) > len(best):
            best = component
    output = np.zeros(mask.shape, dtype=bool)
    if best:
        ys, xs = zip(*best)
        output[np.asarray(ys), np.asarray(xs)] = True
    return output


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask.copy()
    output = mask.copy()
    for _ in range(radius):
        padded = np.pad(output, 1, constant_values=False)
        grown = np.zeros(output.shape, dtype=bool)
        for dy in range(3):
            for dx in range(3):
                grown |= padded[dy : dy + output.shape[0], dx : dx + output.shape[1]]
        output = grown
    return output


def clean_mask(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask, 1, constant_values=False)
    neighbors = np.zeros(mask.shape, dtype=np.uint8)
    for dy in range(3):
        for dx in range(3):
            if dx == 1 and dy == 1:
                continue
            neighbors += padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    cleaned = mask.copy()
    cleaned[mask & (neighbors <= 1)] = False
    cleaned[(~mask) & (neighbors >= 7)] = True
    return cleaned


def foreground_mask(rgba: np.ndarray, threshold: float) -> np.ndarray:
    alpha = rgba[:, :, 3]
    if np.count_nonzero(alpha < 250) > alpha.size // 32:
        return alpha >= 128

    rgb = rgba[:, :, :3].astype(np.float32)
    corners = np.array(
        [rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]],
        dtype=np.float32,
    )
    background = np.median(corners, axis=0)
    distance = np.linalg.norm(rgb - background, axis=2)
    background_candidate = distance <= threshold

    # Only background-colored pixels connected to a cell edge are removable.
    # This preserves white highlights, eyes, and light clothing enclosed by the
    # character outline instead of deleting every pixel close to corner white.
    height, width = background_candidate.shape
    exterior = np.zeros(background_candidate.shape, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        for y in (0, height - 1):
            if background_candidate[y, x] and not exterior[y, x]:
                exterior[y, x] = True
                queue.append((y, x))
    for y in range(height):
        for x in (0, width - 1):
            if background_candidate[y, x] and not exterior[y, x]:
                exterior[y, x] = True
                queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for ny in range(max(0, y - 1), min(height, y + 2)):
            for nx in range(max(0, x - 1), min(width, x + 2)):
                if background_candidate[ny, nx] and not exterior[ny, nx]:
                    exterior[ny, nx] = True
                    queue.append((ny, nx))

    # Remove large near-background holes enclosed by looped cloth or limbs,
    # including their antialiasing. Tiny white highlights remain foreground.
    enclosed = background_candidate & ~exterior
    seen = np.zeros(enclosed.shape, dtype=bool)
    exact_background = distance <= min(6.0, threshold)
    for start_y, start_x in zip(*np.nonzero(enclosed)):
        if seen[start_y, start_x]:
            continue
        component: list[tuple[int, int]] = []
        queue = deque([(int(start_y), int(start_x))])
        seen[start_y, start_x] = True
        exact_count = 0
        while queue:
            y, x = queue.popleft()
            component.append((y, x))
            exact_count += int(exact_background[y, x])
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if enclosed[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        queue.append((ny, nx))
        if len(component) >= 8 and exact_count / len(component) >= 0.25:
            ys, xs = zip(*component)
            exterior[np.asarray(ys), np.asarray(xs)] = True
    return ~exterior


def skin_mask(rgba: np.ndarray, fg: np.ndarray) -> np.ndarray:
    rgb = rgba[:, :, :3].astype(np.int16)
    r = rgb[:, :, 0]
    g = rgb[:, :, 1]
    b = rgb[:, :, 2]
    return fg & (r >= 145) & (g >= 80) & (b >= 55) & (r > g + 18) & (g > b + 8)


def anatomy_restore_mask(
    base_rgba: np.ndarray,
    base_fg: np.ndarray,
    outfit_rgba: np.ndarray,
    outfit_fg: np.ndarray,
    expand: int,
) -> np.ndarray:
    """Restore anatomy while preserving clothes that cover the base skin."""
    base_skin = skin_mask(base_rgba, base_fg)
    ys, _ = np.nonzero(base_fg)
    if not len(ys):
        return np.zeros(base_fg.shape, dtype=bool)
    top = int(ys.min())
    height = int(ys.max() - top + 1)
    # On chibi sheets the head occupies roughly the first 40% of the body
    # height. Going lower reaches shoulders/chest in leaning poses and paints
    # the unclothed base over collars and robes.
    head_limit = top + max(1, int(round(height * 0.40)))
    head_zone = np.arange(base_fg.shape[0])[:, None] <= head_limit

    head_skin = base_skin & head_zone
    rgb = base_rgba[:, :, :3].astype(np.int16)
    luminance = (rgb[:, :, 0] * 299 + rgb[:, :, 1] * 587 + rgb[:, :, 2] * 114) // 1000
    dark_details = base_fg & dilate(head_skin, 1) & (luminance < 95)
    return (head_skin | dark_details) & base_fg


def normalize_outfit_skin(
    output: np.ndarray,
    base_rgba: np.ndarray,
    base_fg: np.ndarray,
    outfit_rgba: np.ndarray,
    outfit_fg: np.ndarray,
) -> None:
    """Normalize exposed outfit skin colors without changing its silhouette."""
    base_skin = skin_mask(base_rgba, base_fg)
    outfit_skin = skin_mask(outfit_rgba, outfit_fg)
    palette = np.unique(base_rgba[:, :, :3][base_skin], axis=0)
    if not len(palette) or not np.any(outfit_skin):
        return
    colors = outfit_rgba[:, :, :3][outfit_skin].astype(np.int32)
    candidates = palette.astype(np.int32)
    distances = np.sum((colors[:, None, :] - candidates[None, :, :]) ** 2, axis=2)
    output[:, :, :3][outfit_skin] = palette[np.argmin(distances, axis=1)]


def enhance_outfit_outline(
    output: np.ndarray,
    outfit_rgba: np.ndarray,
    outfit_fg: np.ndarray,
) -> int:
    """Turn the outer edge of clothing into a clean one-pixel outline."""
    outfit_skin = skin_mask(outfit_rgba, outfit_fg)
    cloth = outfit_fg & ~dilate(outfit_skin, 1)
    padded = np.pad(outfit_fg, 1, constant_values=False)
    surrounded = np.ones(outfit_fg.shape, dtype=bool)
    for dy in range(3):
        for dx in range(3):
            surrounded &= padded[dy : dy + outfit_fg.shape[0], dx : dx + outfit_fg.shape[1]]
    boundary = cloth & ~surrounded
    if not np.any(boundary):
        return 0

    rgb = outfit_rgba[:, :, :3].astype(np.int32)
    luminance = (rgb[:, :, 0] * 299 + rgb[:, :, 1] * 587 + rgb[:, :, 2] * 114) // 1000
    dark_cloth = cloth & (luminance < 95)
    if np.any(dark_cloth):
        outline_color = np.median(rgb[dark_cloth], axis=0).astype(np.uint8)
        outline_color = np.minimum(outline_color, np.array([58, 66, 70], dtype=np.uint8))
    else:
        outline_color = np.array([42, 52, 58], dtype=np.uint8)
    output[:, :, :3][boundary] = outline_color
    return int(np.count_nonzero(boundary))


def snap_to_palette(image: Image.Image, colors: int) -> Image.Image:
    if colors <= 0:
        return image
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    mask = rgba[:, :, 3] >= 128
    if not np.any(mask):
        return image
    rgb = rgba[:, :, :3].copy()
    opaque = rgb[mask]
    sample = Image.fromarray(opaque.reshape(1, -1, 3), mode="RGB")
    quantized = sample.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette = np.asarray(quantized.getpalette(), dtype=np.uint8).reshape(-1, 3)
    mapped = palette[np.asarray(quantized).reshape(-1)]
    rgb[mask] = mapped
    output = np.zeros_like(rgba)
    output[:, :, :3] = rgb
    output[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(output, mode="RGBA")


def repair_frame(
    base: Image.Image,
    outfit: Image.Image,
    *,
    background_threshold: float,
    skin_expand: int,
) -> tuple[Image.Image, dict[str, int]]:
    base_rgba = np.asarray(base.convert("RGBA"), dtype=np.uint8)
    outfit_rgba = np.asarray(outfit.convert("RGBA"), dtype=np.uint8)
    base_fg = foreground_mask(base_rgba, background_threshold)
    outfit_fg = foreground_mask(outfit_rgba, background_threshold)
    restore = anatomy_restore_mask(
        base_rgba,
        base_fg,
        outfit_rgba,
        outfit_fg,
        skin_expand,
    )

    output = np.zeros_like(outfit_rgba)
    output[outfit_fg] = outfit_rgba[outfit_fg]
    output[:, :, 3] = np.where(outfit_fg, 255, 0).astype(np.uint8)
    normalize_outfit_skin(output, base_rgba, base_fg, outfit_rgba, outfit_fg)
    outlined_pixels = enhance_outfit_outline(output, outfit_rgba, outfit_fg)
    output[restore] = base_rgba[restore]
    output[:, :, 3] = np.where(outfit_fg | restore, 255, 0).astype(np.uint8)
    return Image.fromarray(output, mode="RGBA"), {
        "outfit_pixels": int(np.count_nonzero(outfit_fg)),
        "restored_anatomy_pixels": int(np.count_nonzero(restore)),
        "outlined_outfit_pixels": outlined_pixels,
    }


def repair_sheet(
    base: Image.Image,
    outfit: Image.Image,
    *,
    rows: int,
    cols: int,
    colors: int,
    background_threshold: float,
    skin_expand: int,
) -> tuple[Image.Image, list[dict[str, int]]]:
    if base.size != outfit.size:
        raise ValueError(f"Base and outfit sizes differ: {base.size} vs {outfit.size}")
    if base.width % cols or base.height % rows:
        raise ValueError("Sheet size is not divisible by the requested grid")

    cell_width = base.width // cols
    cell_height = base.height // rows
    output = Image.new("RGBA", base.size, (0, 0, 0, 0))
    report: list[dict[str, int]] = []
    for row in range(rows):
        for col in range(cols):
            box = (
                col * cell_width,
                row * cell_height,
                (col + 1) * cell_width,
                (row + 1) * cell_height,
            )
            frame, stats = repair_frame(
                base.crop(box),
                outfit.crop(box),
                background_threshold=background_threshold,
                skin_expand=skin_expand,
            )
            output.paste(frame, box)
            stats.update({"row": row, "col": col})
            report.append(stats)
    return snap_to_palette(output, colors), report


def main() -> None:
    args = parse_args()
    repaired, report = repair_sheet(
        load_rgba(args.base),
        load_rgba(args.outfit),
        rows=args.rows,
        cols=args.cols,
        colors=args.colors,
        background_threshold=args.background_threshold,
        skin_expand=args.skin_expand,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    repaired.save(args.output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({"frames": report}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
