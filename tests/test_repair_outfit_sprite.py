from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "repair_outfit_sprite.py"
SPEC = importlib.util.spec_from_file_location("repair_outfit_sprite", MODULE_PATH)
assert SPEC and SPEC.loader
repair_outfit_sprite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair_outfit_sprite)


class RepairOutfitSpriteTests(unittest.TestCase):
    def test_small_white_detail_enclosed_by_outline_is_not_background(self) -> None:
        pixels = Image.new("RGBA", (9, 9), (255, 255, 255, 255))
        for x in range(2, 6):
            pixels.putpixel((x, 2), (20, 20, 20, 255))
            pixels.putpixel((x, 5), (20, 20, 20, 255))
        for y in range(2, 6):
            pixels.putpixel((2, y), (20, 20, 20, 255))
            pixels.putpixel((5, y), (20, 20, 20, 255))

        mask = repair_outfit_sprite.foreground_mask(
            repair_outfit_sprite.np.asarray(pixels),
            20,
        )

        self.assertTrue(mask[4, 4])
        self.assertFalse(mask[0, 0])

    def test_large_enclosed_background_hole_is_removed(self) -> None:
        pixels = Image.new("RGBA", (11, 11), (255, 255, 255, 255))
        for x in range(2, 9):
            pixels.putpixel((x, 2), (20, 20, 20, 255))
            pixels.putpixel((x, 8), (20, 20, 20, 255))
        for y in range(2, 9):
            pixels.putpixel((2, y), (20, 20, 20, 255))
            pixels.putpixel((8, y), (20, 20, 20, 255))

        mask = repair_outfit_sprite.foreground_mask(
            repair_outfit_sprite.np.asarray(pixels),
            20,
        )

        self.assertFalse(mask[5, 5])

    def test_repairs_skin_and_eye_from_base(self) -> None:
        base = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
        outfit = Image.new("RGBA", (8, 8), (0, 0, 0, 0))

        skin = (236, 178, 140, 255)
        eye = (38, 31, 29, 255)
        cloth = (120, 190, 210, 255)
        bad_skin = (210, 150, 130, 160)

        for y in range(1, 6):
            for x in range(2, 6):
                base.putpixel((x, y), skin)
                outfit.putpixel((x, y), bad_skin)
        base.putpixel((3, 2), eye)
        outfit.putpixel((3, 2), (170, 150, 145, 160))
        for x in range(1, 7):
            outfit.putpixel((x, 6), cloth)

        repaired, report = repair_outfit_sprite.repair_sheet(
            base,
            outfit,
            rows=1,
            cols=1,
            colors=0,
            background_threshold=10,
            skin_expand=4,
        )

        self.assertEqual(repaired.getpixel((2, 3)), skin)
        self.assertEqual(repaired.getpixel((3, 2)), eye)
        self.assertEqual(repaired.getpixel((1, 6)), cloth)
        self.assertEqual(repaired.getpixel((0, 0))[3], 0)
        self.assertGreater(report[0]["restored_anatomy_pixels"], 0)

    def test_clothing_over_base_skin_is_not_overwritten(self) -> None:
        base = Image.new("RGBA", (8, 12), (0, 0, 0, 0))
        outfit = Image.new("RGBA", (8, 12), (0, 0, 0, 0))
        skin = (236, 178, 140, 255)
        cloth = (30, 120, 170, 255)
        for y in range(1, 11):
            for x in range(2, 6):
                base.putpixel((x, y), skin)
                outfit.putpixel((x, y), skin if y < 5 else cloth)

        repaired, _ = repair_outfit_sprite.repair_frame(
            base,
            outfit,
            background_threshold=10,
            skin_expand=4,
        )

        self.assertEqual(repaired.getpixel((3, 8)), cloth)

    def test_cli_writes_repaired_sheet_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
            outfit = Image.new("RGB", (4, 4), (0, 0, 0))
            base.putpixel((1, 1), (230, 170, 130, 255))
            outfit.putpixel((1, 1), (210, 140, 120))
            outfit.putpixel((2, 2), (90, 160, 190))
            base_path = root / "base.png"
            outfit_path = root / "outfit.png"
            output_path = root / "repaired.png"
            report_path = root / "report.json"
            base.save(base_path)
            outfit.save(outfit_path)

            repair_outfit_sprite.main.__globals__["parse_args"] = lambda: type(
                "Args",
                (),
                {
                    "base": base_path,
                    "outfit": outfit_path,
                    "output": output_path,
                    "rows": 1,
                    "cols": 1,
                    "colors": 0,
                    "background_threshold": 10.0,
                    "skin_expand": 0,
                    "report": report_path,
                },
            )()
            repair_outfit_sprite.main()

            self.assertTrue(output_path.is_file())
            self.assertTrue(report_path.is_file())
            self.assertEqual(Image.open(output_path).convert("RGBA").getpixel((1, 1)), (230, 170, 130, 255))
