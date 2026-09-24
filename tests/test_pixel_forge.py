from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from hkt_pixel_forge.build import assemble
from hkt_pixel_forge.cli import expand_glob
from hkt_pixel_forge.images import pad_without_resampling
from hkt_pixel_forge.images import save_lossless_sprite
from hkt_pixel_forge.qc import animation_report, inspect_frame
from hkt_pixel_forge.contracts import ActionContract
from hkt_pixel_forge.providers import ingest_frames
from hkt_pixel_forge.review import REVIEW_CHECKS, save_review_record, verify_review_record


def sprite(path: Path, *, partial_alpha: bool = False) -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    color = (80, 120, 140, 128 if partial_alpha else 255)
    for y in range(20, 60):
        for x in range(24, 40):
            image.putpixel((x, y), color)
    image.save(path)
    return image


class PixelForgeTests(unittest.TestCase):
    def test_expand_glob_supports_absolute_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "frame-00.png").touch()
            self.assertEqual(expand_glob(str(root / "frame-*.png")), [root / "frame-00.png"])

    def test_padding_preserves_every_source_pixel(self) -> None:
        image = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        image.putpixel((3, 4), (12, 34, 56, 255))
        padded = pad_without_resampling(image, top=2, down=3, left=4, right=5)
        self.assertEqual(padded.size, (17, 13))
        self.assertEqual(padded.getpixel((7, 6)), (12, 34, 56, 255))

    def test_qc_rejects_partial_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "frame.png"
            sprite(path, partial_alpha=True)
            report = inspect_frame(path, width=64, height=64, palette_size=24, anchor_y=59)
            self.assertFalse(report.valid)
            self.assertIn("alpha is not binary", report.errors)

    def test_qc_rejects_wrong_frame_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "frame.png"
            sprite(path)
            report = animation_report([path], width=64, height=64, palette_size=0,
                                      anchor_y=59, loop=False, expected_frames=4)
            self.assertFalse(report["valid"])
            self.assertIn("expected 4 frames, got 1", report["errors"])

    def test_lossless_sheet_does_not_quantize_many_colors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sheet.png"
            image = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
            for index in range(300):
                image.putpixel((index % 20, index // 20), (index % 256, index // 256, 73, 255))
            self.assertEqual(save_lossless_sprite(image, path), "RGBA")
            self.assertEqual(list(Image.open(path).convert("RGBA").getdata()), list(image.getdata()))

    def test_approval_is_bound_to_frame_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "frame.png"
            sprite(path)
            record = root / "review.json"
            save_review_record([path], record, reviewer="tester", checks=list(REVIEW_CHECKS))
            self.assertTrue(verify_review_record([path], record))
            image = Image.open(path).convert("RGBA")
            image.putpixel((25, 25), (20, 40, 60, 255))
            image.save(path)
            self.assertFalse(verify_review_record([path], record))

    def test_animation_build_writes_final_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = []
            for index in range(4):
                path = root / f"frame-{index}.png"
                sprite(path)
                paths.append(path)
            report = animation_report(
                paths,
                width=64,
                height=64,
                palette_size=24,
                anchor_y=59,
                loop=True,
            )
            self.assertTrue(report["valid"])
            output = root / "build"
            manifest = assemble(paths, columns=4, colors=24, fps=8, loop=True, output_dir=output)
            self.assertEqual(manifest["frame_count"], 4)
            self.assertTrue((output / "spritesheet.png").is_file())
            self.assertTrue((output / "preview.gif").is_file())
            self.assertTrue((output / "final_outputs.json").is_file())

    def test_provider_ingest_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = []
            for index in range(2):
                path = root / f"source-{index}.png"
                sprite(path)
                paths.append(path)
            contract = ActionContract(
                character_id="test",
                action="idle",
                source="source.png",
                canvas_width=64,
                canvas_height=64,
                content_offset_x=0,
                content_offset_y=0,
                anchor_x=32,
                anchor_y=59,
                frames=2,
                fps=8,
                loop=True,
                padding={"top": 0, "down": 0, "left": 0, "right": 0},
            )
            output = root / "ingested"
            manifest = ingest_frames(paths, contract=contract, output_dir=output, provider="test")
            self.assertFalse(manifest["resampled"])
            self.assertEqual(paths[0].read_bytes(), (output / "frame-00.png").read_bytes())


if __name__ == "__main__":
    unittest.main()
