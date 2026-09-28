import base64
import importlib.util
import io
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("repair_outfit_ui", TOOLS / "repair_outfit_ui.py")
repair_outfit_ui = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(repair_outfit_ui)


def data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class RepairOutfitUiTests(unittest.TestCase):
    def test_bundled_green_guide_is_used_without_upload(self) -> None:
        with Image.open(repair_outfit_ui.DEFAULT_BASE_PATH) as image:
            base = image.convert('RGBA')
        with Image.open(repair_outfit_ui.DEFAULT_GREEN_BASE_PATH) as image:
            guide = image.convert('RGBA')
        outfit = np.array(guide)
        for row in range(7):
            for col in range(4):
                y, x = row * 64, col * 64
                outfit[y+36:y+55, x+25:x+40] = [45, 85, 150, 255]
        result = repair_outfit_ui.process_request({
            'base': data_url(base), 'outfit': data_url(Image.fromarray(outfit)),
            'rows': 7, 'cols': 4, 'colors': 0,
            'backgroundThreshold': 36, 'composition': 'cutout',
            'logoCleanup': 'off', 'outline': False, 'paint': 0, 'cleanup': 0,
        })
        self.assertEqual(result['report']['greenBaseSource'], 'bundled')
        self.assertGreater(result['report']['greenMarkerPixels'], 0)
        image = repair_outfit_ui.decode_image(result['image'])
        self.assertEqual(image.getpixel((31, 24)), base.getpixel((31, 24)))

    def test_green_base_is_forwarded_and_validated(self) -> None:
        from test_layer_composition import fixture
        base, _ = fixture()
        guide = np.array(base)
        guide[guide[:, :, 3] > 0] = [117, 174, 35, 255]
        outfit = guide.copy()
        outfit[10:24, 7:17] = [48, 105, 175, 255]
        payload = {
            "base": data_url(base),
            "greenBase": data_url(Image.fromarray(guide)),
            "outfit": data_url(Image.fromarray(outfit)),
            "rows": 1, "cols": 1, "colors": 0,
            "backgroundThreshold": 36, "composition": "cutout",
        }
        result = repair_outfit_ui.process_request(payload)
        image = repair_outfit_ui.decode_image(result["image"])
        self.assertEqual(image.getpixel((10, 4)), base.getpixel((10, 4)))
        self.assertEqual(image.getpixel((12, 17)), tuple(outfit[17, 12]))
        payload["greenBase"] = data_url(Image.fromarray(guide[:8, :8]))
        with self.assertRaisesRegex(ValueError, "Green base must match"):
            repair_outfit_ui.process_request(payload)

    def test_process_request_returns_png(self) -> None:
        base = np.zeros((8, 8, 4), dtype=np.uint8)
        base[2:7, 2:6] = [235, 155, 120, 255]
        base[3, 3] = [35, 25, 22, 255]
        outfit = base.copy()
        outfit[2:4, 2:6] = [210, 175, 155, 255]
        outfit[5:7, 2:6] = [30, 120, 170, 255]

        result = repair_outfit_ui.process_request(
            {
                "base": data_url(Image.fromarray(base, "RGBA")),
                "outfit": data_url(Image.fromarray(outfit, "RGBA")),
                "rows": 1,
                "cols": 1,
                "colors": 0,
                "skinExpand": 1,
                "backgroundThreshold": 36,
            }
        )

        self.assertTrue(result["image"].startswith("data:image/png;base64,"))
        self.assertEqual(result["frameCount"], 1)
        self.assertGreater(result["restoredPixels"], 0)

    def test_rejects_invalid_grid(self) -> None:
        with self.assertRaisesRegex(ValueError, "Rows and columns"):
            repair_outfit_ui.process_request({"base": "x", "outfit": "x", "rows": 0})


if __name__ == "__main__":
    unittest.main()
