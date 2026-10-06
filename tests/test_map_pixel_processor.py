import io
import json
import base64
from pathlib import Path
import sys
import unittest
import zipfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from map_asset_pipeline import encode, decode
from map_pixel_processor import process, options, Cancelled, palette_samples, palette_from
from map_scene_bundle import import_bundle


def data(a):
    return encode(Image.fromarray(a.astype(np.uint8)))


class MapPixelTests(unittest.TestCase):
    def test_shared_palette_alpha_and_dimensions_survive_batch(self):
        rng = np.random.default_rng(3)
        images = [rng.integers(0, 256, (15, 19, 4), dtype=np.uint8) for _ in range(2)]
        body = {'items': [{'id': str(i), 'image': data(a)} for i, a in enumerate(images)], 'settings': {'colors': 32}}
        before = json.dumps(body)
        result = process(body)
        palette = set(map(tuple, result['palette']))
        for src, item in zip(images, result['items']):
            out = np.array(decode(item['image']))
            self.assertEqual(src.shape, out.shape)
            np.testing.assert_array_equal(out[..., 3], src[..., 3])
            self.assertTrue(set(map(tuple, out[out[..., 3] > 0, :3])) <= palette)
        self.assertEqual(before, json.dumps(body))
        self.assertFalse(result['semanticLayersCreated'])

    def test_odd_sized_grid_has_exact_dimensions_and_solid_blocks(self):
        rng = np.random.default_rng(8)
        a = rng.integers(0, 256, (17, 23, 4), dtype=np.uint8); a[..., 3] = 255
        result = process({'items': [{'id': 'map', 'image': data(a)}], 'settings': {'grid': 2, 'colors': 32}})
        out = np.array(decode(result['items'][0]['image']))
        self.assertEqual(out.shape, a.shape)
        np.testing.assert_array_equal(out[:16:2, :22:2], out[1:16:2, 1:22:2])

    def test_transparent_matte_cannot_introduce_magenta(self):
        a = np.full((12, 12, 4), [255, 0, 255, 0], np.uint8); a[3:9, 3:9] = [30, 130, 65, 255]
        r = process({'items': [{'id': 'a', 'image': data(a)}]})
        out = np.array(decode(r['items'][0]['image']))
        self.assertTrue(np.all(out[out[..., 3] == 0, :3] == 0))
        np.testing.assert_array_equal(out[5, 5], [30, 130, 65, 255])

    def test_empty_image_and_precise_cancellation(self):
        a = np.zeros((3, 5, 4), np.uint8)
        body = {'items': [{'id': 'a', 'image': data(a)}]}
        self.assertFalse(np.array(decode(process(body)['items'][0]['image'])).any())
        with self.assertRaises(Cancelled):
            process(body, cancelled=lambda: True)
        with self.assertRaises(TimeoutError):
            process(body, deadline_seconds=-1)

    def test_rejects_bad_options_and_duplicate_ids(self):
        for config in [{'colors': 0}, {'grid': 1.5}, {'passes': True}, {'strength': float('nan')}, {'alpha': 'auto'}]:
            with self.assertRaises(ValueError):
                options(config)
        a = data(np.full((2, 2, 4), 255, np.uint8))
        with self.assertRaises(ValueError):
            process({'items': [{'id': 'same', 'image': a}, {'id': 'same', 'image': a}]})

    def test_rare_pink_palette_accent_survives_green_map(self):
        import cv2
        green = np.tile(np.array([[35, 130, 70]], np.uint8), (100000, 1))
        pink = np.tile(np.array([[220, 70, 180]], np.uint8), (12, 1))
        sample = palette_samples(np.concatenate([green, pink]), cv2)
        palette = palette_from([sample], 16, lambda: None)
        self.assertTrue(any(c[0] > 180 and c[2] > 130 and c[1] < 100 for c in palette))


class MapBundleTests(unittest.TestCase):
    def bundle(self, path='layers/a.png'):
        png = io.BytesIO(); Image.new('RGBA', (7, 5), (30, 100, 80, 253)).save(png, 'PNG')
        out = io.BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            z.writestr('pack/layout.json', json.dumps({'canvas': {'width': 7, 'height': 5}, 'layers': [{'file': path}], 'objects': []}))
            z.writestr('pack/layers/a.png', png.getvalue())
        return {'archive': 'data:application/zip;base64,' + base64.b64encode(out.getvalue()).decode()}, png.getvalue()

    def test_bundle_preserves_original_png_bytes(self):
        payload, png = self.bundle(); result = import_bundle(payload)
        self.assertEqual(base64.b64decode(result['images']['layers/a.png'].split(',')[1]), png)

    def test_bundle_rejects_path_escape_and_missing_files(self):
        for path in ['../a.png', '/a.png', 'layers/missing.png']:
            with self.assertRaises(ValueError):
                import_bundle(self.bundle(path)[0])


if __name__ == '__main__':
    unittest.main()
