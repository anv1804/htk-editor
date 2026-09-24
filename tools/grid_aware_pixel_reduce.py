#!/usr/bin/env python3
"""Reduce an AI sprite grid to crisp indexed pixel art.

The reducer treats every destination pixel as an exact source-area sample,
then snaps the result to one shared palette and a binary alpha mask. This
avoids the partially transparent, high-color fringe produced by Lanczos.
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
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--cell-size", type=int, default=64)
    parser.add_argument("--subject-height", type=int, default=51)
    parser.add_argument("--feet-y", type=int, default=59)
    parser.add_argument("--colors", type=int, default=28)
    parser.add_argument("--background-threshold", type=float, default=88.0)
    parser.add_argument("--coverage-threshold", type=float, default=0.34)
    parser.add_argument("--duration", type=int, default=180)
    return parser.parse_args()


def largest_component(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
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
                    if not seen[ny, nx] and mask[ny, nx]:
                        seen[ny, nx] = True
                        queue.append((ny, nx))
        if len(component) > len(best):
            best = component
    result = np.zeros_like(mask, dtype=bool)
    if best:
        ys, xs = zip(*best)
        result[np.asarray(ys), np.asarray(xs)] = True
    return result


def extract_subject(cell: Image.Image, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    rgba = np.asarray(cell.convert("RGBA"), dtype=np.uint8)
    rgb = rgba[:, :, :3].astype(np.float32)
    if np.count_nonzero(rgba[:, :, 3] < 128) > rgba.shape[0] * rgba.shape[1] // 8:
        mask = largest_component(rgba[:, :, 3] >= 128)
    else:
        key = np.array([255.0, 0.0, 255.0], dtype=np.float32)
        distance = np.linalg.norm(rgb - key, axis=2)
        mask = largest_component(distance > threshold)
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError("No foreground subject found in a grid cell")
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return rgb[y0:y1, x0:x1].astype(np.uint8), mask[y0:y1, x0:x1]


def box_reduce(rgb: np.ndarray, mask: np.ndarray, size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Area-reduce premultiplied color and return color plus coverage."""
    width, height = size
    alpha = mask.astype(np.float32)
    premul = rgb.astype(np.float32) * alpha[:, :, None]
    coverage = np.asarray(
        Image.fromarray(alpha, mode="F").resize((width, height), Image.Resampling.BOX),
        dtype=np.float32,
    )
    channels = []
    for channel in range(3):
        channels.append(
            np.asarray(
                Image.fromarray(premul[:, :, channel], mode="F").resize(
                    (width, height), Image.Resampling.BOX
                ),
                dtype=np.float32,
            )
        )
    reduced_premul = np.stack(channels, axis=2)
    reduced = reduced_premul / np.maximum(coverage[:, :, None], 1e-6)
    return np.clip(np.rint(reduced), 0, 255).astype(np.uint8), coverage


def clean_mask(mask: np.ndarray) -> np.ndarray:
    """Remove true one-pixel debris and fill fully enclosed one-pixel holes."""
    padded = np.pad(mask, 1, constant_values=False)
    neighbors = np.zeros(mask.shape, dtype=np.uint8)
    for dy in range(3):
        for dx in range(3):
            if dx == 1 and dy == 1:
                continue
            neighbors += padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    cleaned = mask.copy()
    cleaned[mask & (neighbors == 0)] = False
    cleaned[(~mask) & (neighbors == 8)] = True
    return largest_component(cleaned)


def make_palette(colors: np.ndarray, count: int) -> np.ndarray:
    samples = Image.fromarray(colors.reshape(1, -1, 3), mode="RGB")
    quantized = samples.quantize(
        colors=count,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    raw = np.asarray(quantized.getpalette(), dtype=np.uint8).reshape(-1, 3)
    used = sorted(set(np.asarray(quantized).reshape(-1).tolist()))
    return raw[used]


def map_palette(rgb: np.ndarray, mask: np.ndarray, palette: np.ndarray) -> np.ndarray:
    output = np.zeros(mask.shape, dtype=np.uint8)
    points = rgb[mask].astype(np.int32)
    candidates = palette.astype(np.int32)
    mapped = np.empty(len(points), dtype=np.uint8)
    for start in range(0, len(points), 50000):
        chunk = points[start : start + 50000]
        distances = ((chunk[:, None, :] - candidates[None, :, :]) ** 2).sum(axis=2)
        mapped[start : start + len(chunk)] = np.argmin(distances, axis=1).astype(np.uint8) + 1
    output[mask] = mapped
    return output


def majority_reduce(
    indexed: np.ndarray,
    source_mask: np.ndarray,
    size: tuple[int, int],
    coverage_threshold: float,
) -> np.ndarray:
    """Reduce by selecting the dominant pre-quantized source color per pixel."""
    target_width, target_height = size
    source_height, source_width = source_mask.shape
    output = np.zeros((target_height, target_width), dtype=np.uint8)
    for target_y in range(target_height):
        y0 = int(np.floor(target_y * source_height / target_height))
        y1 = max(y0 + 1, int(np.ceil((target_y + 1) * source_height / target_height)))
        for target_x in range(target_width):
            x0 = int(np.floor(target_x * source_width / target_width))
            x1 = max(x0 + 1, int(np.ceil((target_x + 1) * source_width / target_width)))
            local_mask = source_mask[y0:y1, x0:x1]
            if local_mask.mean() < coverage_threshold:
                continue
            values = indexed[y0:y1, x0:x1][local_mask]
            if len(values):
                counts = np.bincount(values, minlength=256)
                counts[0] = 0
                output[target_y, target_x] = int(np.argmax(counts))
    cleaned = clean_mask(output > 0)
    output[~cleaned] = 0
    return output


def normalize_outline(indexed: np.ndarray, palette: np.ndarray) -> np.ndarray:
    mask = indexed > 0
    padded = np.pad(mask, 1, constant_values=False)
    interior_neighbors = np.ones(mask.shape, dtype=bool)
    for dy in range(3):
        for dx in range(3):
            if dx == 1 and dy == 1:
                continue
            interior_neighbors &= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
    boundary = mask & ~interior_neighbors
    luminance = palette @ np.array([0.2126, 0.7152, 0.0722])
    outline_index = int(np.argmin(luminance)) + 1
    result = indexed.copy()
    result[boundary] = outline_index
    return result


def save_indexed(path: Path, indices: np.ndarray, palette: np.ndarray) -> Image.Image:
    image = Image.fromarray(indices, mode="P")
    flat_palette = [0, 0, 0]
    flat_palette.extend(palette.reshape(-1).tolist())
    flat_palette.extend([0] * (768 - len(flat_palette)))
    image.putpalette(flat_palette)
    image.info["transparency"] = 0
    image.save(path, transparency=0, optimize=False)
    return image


def main() -> None:
    args = parse_args()
    source = Image.open(args.input).convert("RGBA")
    cell_width = source.width // args.cols
    cell_height = source.height // args.rows
    subjects: list[tuple[np.ndarray, np.ndarray]] = []
    for row in range(args.rows):
        for col in range(args.cols):
            box = (
                col * cell_width,
                row * cell_height,
                (col + 1) * cell_width,
                (row + 1) * cell_height,
            )
            subjects.append(extract_subject(source.crop(box), args.background_threshold))

    max_height = max(rgb.shape[0] for rgb, _mask in subjects)
    shared_scale = args.subject_height / max_height
    palette_samples: list[np.ndarray] = []
    for rgb, mask in subjects:
        samples = rgb[mask]
        palette_samples.append(samples)
        skin = samples[
            (samples[:, 0] > samples[:, 1] + 8)
            & (samples[:, 1] > samples[:, 2] + 4)
            & (samples[:, 0] > 110)
        ]
        if len(skin):
            palette_samples.extend([skin, skin])

    palette = make_palette(np.concatenate(palette_samples, axis=0), args.colors)
    frames: list[np.ndarray] = []
    frame_images: list[Image.Image] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for index, (rgb, mask) in enumerate(subjects, start=1):
        target_width = max(1, int(round(rgb.shape[1] * shared_scale)))
        target_height = max(1, int(round(rgb.shape[0] * shared_scale)))
        source_indexed = map_palette(rgb, mask, palette)
        subject = majority_reduce(
            source_indexed,
            mask,
            (target_width, target_height),
            args.coverage_threshold,
        )
        canvas = np.zeros((args.cell_size, args.cell_size), dtype=np.uint8)
        height, width = subject.shape
        paste_x = int(round((args.cell_size - width) / 2))
        paste_y = args.feet_y - height + 1
        if paste_x < 0 or paste_y < 0 or paste_x + width > args.cell_size or paste_y + height > args.cell_size:
            raise ValueError(f"Frame {index} does not fit the requested cell")
        canvas[paste_y : paste_y + height, paste_x : paste_x + width] = subject
        frames.append(canvas)
        frame_images.append(save_indexed(args.output_dir / f"idle-{index}.png", canvas, palette))

    sheet = np.zeros((args.rows * args.cell_size, args.cols * args.cell_size), dtype=np.uint8)
    for index, frame in enumerate(frames):
        row, col = divmod(index, args.cols)
        y, x = row * args.cell_size, col * args.cell_size
        sheet[y : y + args.cell_size, x : x + args.cell_size] = frame
    sheet_image = save_indexed(args.output_dir / "sheet-indexed.png", sheet, palette)
    sheet_image.convert("RGBA").resize(
        (sheet_image.width * 4, sheet_image.height * 4), Image.Resampling.NEAREST
    ).save(args.output_dir / "sheet-preview-4x.png")

    strip = np.concatenate(frames, axis=1)
    save_indexed(args.output_dir / "strip-indexed.png", strip, palette)
    frame_images[0].save(
        args.output_dir / "animation.gif",
        save_all=True,
        append_images=frame_images[1:],
        duration=args.duration,
        loop=0,
        disposal=2,
        transparency=0,
    )

    metadata = {
        "input": str(args.input),
        "rows": args.rows,
        "cols": args.cols,
        "cell_size": args.cell_size,
        "subject_height": args.subject_height,
        "feet_y": args.feet_y,
        "palette_colors": len(palette),
        "alpha_levels": [0, 255],
        "reduction": "palette-first dominant-color voting on a shared destination grid",
        "coverage_threshold": args.coverage_threshold,
        "outline": "preserved from the pre-quantized source without contour overpainting",
    }
    (args.output_dir / "pipeline-meta.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
