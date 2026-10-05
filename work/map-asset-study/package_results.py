"""Verify saved demo PNGs and package only the intended deliverables."""
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image

root = Path(__file__).resolve().parent
out = root / "output"
swatches = np.array(Image.open(out / "palette128.png"))[::32, ::32, :]
palette = {tuple(p) for p in swatches.reshape(-1, 3)}
checked = 0
for slug in ["platform", "gate", "bamboo"]:
    folder = out / slug
    mask = np.array(Image.open(folder / "mask.png")) > 0
    original_size = Image.open(folder / "source.png").size
    for name, limit in [("detail", None), ("palette128", 128), ("palette48", 48)]:
        im = Image.open(folder / (name + ".png"))
        a = np.array(im)
        assert im.size == original_size
        assert np.array_equal(a[:, :, 3] > 0, mask)
        assert set(np.unique(a[:, :, 3])) <= {0, 255}
        colors = {tuple(c) for c in a[mask, :3]}
        if limit:
            assert len(colors) <= limit
        if name == "palette128":
            assert colors <= palette
        checked += 1

paths = [root / n for n in ["study.py", "package_results.py", "NGHIEN_CUU.md"]]
paths += [out / n for n in ["comparison.png", "before-after.png", "background-check.png",
                            "palette128.hex", "palette128.png", "audit.json"]]
paths += [p for slug in ["platform", "gate", "bamboo"] for p in (out / slug).glob("*.png")]
bundle = root / "python-map-asset-study.zip"
with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
    for p in paths:
        z.write(p, p.relative_to(root).as_posix())
with zipfile.ZipFile(bundle) as z:
    assert z.testzip() is None
print(f"Verified {checked} exported PNGs. Package: {bundle}; {len(paths)} files; {bundle.stat().st_size} bytes.")
