"""Make a nearest-neighbor comparison board without changing input sheets."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--outfit', type=Path, required=True)
    parser.add_argument('--result', type=Path)
    parser.add_argument('--previous', type=Path, help='Optional previous output for before/after review')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--frames', default='0,4,5,13,17,27')
    parser.add_argument('--cols', type=int, default=4)
    parser.add_argument('--rows', type=int, default=7)
    parser.add_argument('--scale', type=int, default=4)
    args = parser.parse_args()
    sources = [('Base', args.base), ('Outfit', args.outfit)]
    if args.previous:
        sources.append(('Before', args.previous))
    if args.result:
        sources.append(('After' if args.previous else 'Result', args.result))
    images = [(title, Image.open(path).convert('RGBA')) for title, path in sources]
    width, height = images[0][1].size
    cw, ch = width // args.cols, height // args.rows
    frames = [int(n) for n in args.frames.split(',')]
    tile_w, tile_h = cw * args.scale, ch * args.scale
    board = Image.new('RGB', (len(images) * tile_w, len(frames) * (tile_h + 22)), '#171b21')
    draw = ImageDraw.Draw(board)
    for row, index in enumerate(frames):
        box = (index % args.cols * cw, index // args.cols * ch,
               (index % args.cols + 1) * cw, (index // args.cols + 1) * ch)
        for col, (title, sheet) in enumerate(images):
            x, y = col * tile_w, row * (tile_h + 22)
            draw.text((x + 6, y + 4), f'{title} / frame {index + 1}', fill='#ffffff')
            for cy in range(0, tile_h, 16):
                for cx in range(0, tile_w, 16):
                    color = '#303740' if (cx // 16 + cy // 16) % 2 else '#414952'
                    draw.rectangle((x+cx, y+22+cy, x+cx+15, y+22+cy+15), fill=color)
            frame = sheet.crop(box).resize((tile_w, tile_h), Image.Resampling.NEAREST)
            board.paste(frame, (x, y + 22), frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    board.save(args.output)


if __name__ == '__main__':
    main()
