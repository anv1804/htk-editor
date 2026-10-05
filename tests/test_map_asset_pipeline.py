import base64
import io
import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import zipfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import map_asset_pipeline as pipeline


def image(a):
    return pipeline.encode(Image.fromarray(np.asarray(a, np.uint8)))


def archive(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, value in entries.items():
            z.writestr(name, value)
    return 'data:application/zip;base64,' + base64.b64encode(out.getvalue()).decode()


def png(a):
    out = io.BytesIO()
    Image.fromarray(a).save(out, 'PNG')
    return out.getvalue()


class MapAssetPipelineTests(unittest.TestCase):
    def run_item(self, a, settings=None, **extra):
        result = pipeline.process({'items': [{'image': image(a), **extra}], 'settings': settings or {}})
        return np.array(pipeline.decode(result['items'][0]['image'])), result

    def test_native_dimensions_and_neutral_colors_are_lossless(self):
        rng = np.random.default_rng(7)
        a = rng.integers(0, 256, (7, 13, 4), dtype=np.uint8)
        a[..., 3] = 255
        before = a.copy()
        out, _ = self.run_item(a, dict(smooth=0, chroma=1, contrast=1, colors=0))
        np.testing.assert_array_equal(out, a)
        np.testing.assert_array_equal(a, before)

    def test_hysteresis_keeps_separate_leaves_and_connected_weak_edges(self):
        a = np.zeros((9, 12, 4), np.uint8)
        a[..., :3] = [50, 190, 100]
        a[2:6, 2:6, 3] = 250
        a[2, 6, 3] = 130
        a[1, 9, 3] = 250  # separated leaf must not be discarded
        a[7, 10, 3] = 130  # weak isolated speck is rejected
        out, _ = self.run_item(a)
        self.assertEqual(out[2, 6, 3], 255)
        self.assertEqual(out[1, 9, 3], 255)
        self.assertEqual(out[7, 10, 3], 0)
        self.assertEqual(out.shape, a.shape)

    def test_transparent_matte_does_not_bleed_into_color(self):
        a = np.zeros((5, 5, 4), np.uint8)
        a[..., :3] = [255, 0, 255]
        a[2, 2] = [45, 120, 78, 255]
        out, _ = self.run_item(a, dict(smooth=32, chroma=1, contrast=1))
        np.testing.assert_array_equal(out[2, 2], a[2, 2])
        self.assertEqual(np.count_nonzero(out[..., 3]), 1)

    def test_manual_mask_can_restore_and_erase_without_growing_elsewhere(self):
        a = np.full((7, 9, 4), [70, 100, 55, 255], np.uint8)
        a[3, 4, 3] = 20
        edits = np.zeros_like(a)
        edits[3, 4] = [0, 255, 0, 255]
        edits[1, 1] = [255, 0, 0, 255]
        out, _ = self.run_item(a, overrides=image(edits))
        self.assertEqual(out[3, 4, 3], 255)
        self.assertEqual(out[1, 1, 3], 0)
        self.assertEqual(np.count_nonzero(out[..., 3]), 62)

    def test_preserve_mode_retains_every_alpha_value(self):
        a = np.zeros((4, 8, 4), np.uint8)
        a[..., :3] = [45, 120, 200]
        a[..., 3] = np.arange(32).reshape(4, 8)*8
        out, _ = self.run_item(a, dict(alphaMode='preserve', colors=8))
        np.testing.assert_array_equal(out[..., 3], a[..., 3])

    def test_batch_palette_is_shared_and_deterministic(self):
        rng = np.random.default_rng(10)
        arrays = [rng.integers(0, 256, (18, 21, 4), dtype=np.uint8) for _ in range(2)]
        for a in arrays:
            a[..., 3] = 255
        body = {'items': [{'id':str(i), 'image':image(a)} for i,a in enumerate(arrays)], 'settings': {'colors': 16}}
        result = pipeline.process(body)
        self.assertEqual(result, pipeline.process(body))
        palette = {tuple(c) for c in result['palette']}
        self.assertLessEqual(len(palette), 16)
        for r in result['items']:
            a = np.array(pipeline.decode(r['image']))
            self.assertTrue({tuple(c) for c in a[..., :3].reshape(-1, 3)} <= palette)
            self.assertTrue(np.all(a[..., 3] == 255))

    def test_empty_item_and_invalid_settings(self):
        a = np.zeros((3, 5, 4), np.uint8)
        out, result = self.run_item(a, dict(colors=64))
        self.assertFalse(out.any())
        self.assertEqual(result['items'][0]['report']['visiblePixels'], 0)
        for settings in [dict(alphaLow=210, alphaHigh=110), dict(chroma=float('nan')), dict(colors=1)]:
            with self.assertRaises(ValueError):
                self.run_item(a, settings)

    def test_crop_preserves_raw_rgba_including_hidden_rgb(self):
        a = np.arange(8*10*4, dtype=np.uint8).reshape((8, 10, 4))
        a[3, 4] = [60, 80, 90, 0]
        r = pipeline.extract_crop(dict(image=image(a), crop=dict(x=2,y=2,w=5,h=4)))
        np.testing.assert_array_equal(np.array(pipeline.decode(r['image'])), a[2:6,2:7])
        with self.assertRaises(ValueError):
            pipeline.extract_crop(dict(image=image(a), crop=dict(x=9,y=0,w=2,h=3)))

    def test_zip_reloads_source_pixels_with_margin_alignment(self):
        sheet = np.arange(12*14*4, dtype=np.uint8).reshape(12,14,4)
        old = np.full((4, 5, 4), [20, 20, 20, 255], np.uint8)
        manifest = {'source_size':[14,12], 'assets':[{'file':'asset_001.png','source_box':[2,3,9,9]}]}
        z = archive({'items/asset_001.png':png(old), 'preview_sheet.png':png(sheet), 'manifest.json':json.dumps(manifest)})
        result = pipeline.import_zip(dict(archive=z, sheet=image(sheet)))
        self.assertEqual(len(result['items']),1)
        np.testing.assert_array_equal(np.array(pipeline.decode(result['items'][0]['image'])), sheet[4:8,3:8])
        self.assertTrue(result['items'][0]['fromSheet'])
        with self.assertRaises(ValueError):
            pipeline.import_zip(dict(archive=z, sheet=image(sheet[:5])))

    def test_export_roundtrip_native_images_and_pivots(self):
        a = np.full((7, 13, 4), [50,100,200,255], np.uint8)
        raw = pipeline.export_zip({'items':[dict(image=image(a),name='../gate',pivot=[4,7])]})
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertTrue(all('..' not in name for name in z.namelist()))
            manifest = json.loads(z.read('manifest.json'))
            self.assertFalse(manifest['resampled'])
            self.assertEqual(manifest['assets'][0]['pivot'], [4,7])
        loaded = pipeline.import_zip({'archive':'data:application/zip;base64,'+base64.b64encode(raw).decode()})
        self.assertEqual(loaded['items'][0]['pivot'], [4,7])
        np.testing.assert_array_equal(np.array(pipeline.decode(loaded['items'][0]['image'])),a)

    def test_source_crop_at_sheet_edge_has_asymmetric_margin(self):
        a = np.arange(10*12*4, dtype=np.uint8).reshape(10,12,4)
        old = np.zeros((5,6,4),np.uint8)
        manifest = {'source_size':[12,10], 'assets':[{'file':'edge.png','source_box':[2,4,10,10]}]}
        z = archive({'items/edge.png':png(old), 'manifest.json':json.dumps(manifest)})
        result = pipeline.import_zip(dict(archive=z,sheet=image(a)))
        np.testing.assert_array_equal(np.array(pipeline.decode(result['items'][0]['image'])),a[5:10,3:9])


class MapAssetHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from http.server import ThreadingHTTPServer
        from repair_outfit_ui import RepairHandler
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), RepairHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, route, body):
        return urlopen(Request(f'http://127.0.0.1:{self.server.server_port}/api/map-assets/{route}',
                               data=json.dumps(body).encode(), headers={'Content-Type':'application/json'}), timeout=20)

    def test_process_crop_export_and_import_routes(self):
        a = np.full((5,9,4),[80,150,65,255],np.uint8)
        body = {'items':[{'name':'grass','image':image(a)}]}
        with self.post('process',body) as response:
            result=json.load(response)
            self.assertEqual(result['items'][0]['width'],9)
        with self.post('crop',dict(image=image(a),crop=dict(x=1,y=1,w=3,h=2))) as response:
            self.assertEqual(json.load(response)['height'],2)
        with self.post('export',body) as response:
            self.assertEqual(response.headers['Content-Type'],'application/zip')
            archive_url='data:application/zip;base64,'+base64.b64encode(response.read()).decode()
        with self.post('import',dict(archive=archive_url)) as response:
            self.assertEqual(len(json.load(response)['items']),1)
        with self.assertRaises(HTTPError) as ctx:
            self.post('process',{'items':[]})
        self.assertEqual(ctx.exception.code,400)


if __name__ == '__main__':
    unittest.main()
