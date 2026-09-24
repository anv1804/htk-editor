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
