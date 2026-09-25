import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from test_layer_composition import fixture
from repair_outfit_sprite import headwear_mask, repair_sheet
from repair_outfit_ui import process_request, encode_png, decode_image


class V3LayersTests(unittest.TestCase):
    def test_tan_suit_and_straw_hat_are_not_erased_as_skin(self):
        root = Path(__file__).parent / 'fixtures'
        base = Image.open(root / 'green_outfit' / 'base.png').convert('RGBA')
        outfit = Image.open(root / 'tan_outfit.png').convert('RGBA')
        result, _, mask = repair_sheet(base,outfit,rows=7,cols=4,colors=0,
            background_threshold=36,skin_expand=0,outline=False,
            composition='layers',accessories=True,return_masks=True)
        labels = np.array(mask)
        for frame in (0,4,14):
            x,y = frame%4*64,frame//4*64
            tile = labels[y:y+64,x:x+64,:3]
            self.assertGreater(np.all(tile == [255,200,0],axis=2).sum(), 65)
            self.assertGreater(np.all(tile == [70,155,255],axis=2).sum(), 100)
            self.assertEqual(result.size, base.size)

    def test_real_green_sheet_edge_changes_only_reveal_base(self):
        root = Path(__file__).parent / 'fixtures' / 'green_outfit'
        base = Image.open(root / 'base.png').convert('RGBA')
        outfit = Image.open(root / 'outfit.png').convert('RGBA')
        options = dict(rows=7, cols=4, colors=0, background_threshold=36,
                       skin_expand=0, composition='layers', outline=False)
        old = np.array(repair_sheet(base, outfit, **options)[0])
        new = np.array(repair_sheet(base, outfit, accessories=True, **options)[0])
        changed = np.any(old != new, axis=2)
        self.assertGreater(changed.sum(), 0)
        b = np.array(base)
        visible = changed & (b[:,:,3] >= 128)
        np.testing.assert_array_equal(new[visible], b[visible])
        self.assertTrue(np.all(new[changed & ~visible,3] == 0))

    def request(self, base, outfit, **kwargs):
        return process_request(dict(base=encode_png(base), outfit=encode_png(outfit),
                                    rows=1, cols=1, colors=0, outline=False, **kwargs))

    def test_bald_source_has_no_headwear(self):
        base, outfit = fixture()
        self.assertFalse(headwear_mask(base, outfit).any())

    def test_crown_and_band_are_one_layer_without_skin(self):
        base, outfit = fixture()
        outfit.paste((51,42,37,255), (7,0,17,5))
        outfit.paste((65,116,55,255), (7,5,17,7))
        data = self.request(base, outfit)
        hair = decode_image(data['headwearLayer'])
        clothing = decode_image(data['outfitLayer'])
        self.assertEqual(hair.size, base.size)
        self.assertEqual(clothing.size, base.size)
        for point in [(10,1),(10,5)]:
            self.assertEqual(hair.getpixel(point), outfit.getpixel(point))
            self.assertEqual(clothing.getpixel(point)[3], 0)
        self.assertEqual(hair.getpixel((10,9))[3], 0)
        self.assertFalse(np.any((np.array(hair)[:,:,3] > 0) & (np.array(clothing)[:,:,3] > 0)))
        composite = Image.alpha_composite(Image.alpha_composite(base, clothing), hair)
        np.testing.assert_array_equal(np.array(composite), np.array(decode_image(data['image'])))

    def test_manual_classification_and_retouch_are_exported(self):
        base, outfit = fixture()
        labels = Image.new('RGBA', base.size)
        labels.putpixel((10,18), (255,200,0,255))
        labels.putpixel((8,27), (0,0,255,255))
        paint = Image.new('RGBA', base.size)
        paint.putpixel((10,18), (21,37,50,255))
        data = self.request(base, outfit, overrides=encode_png(labels), retouch=encode_png(paint))
        self.assertEqual(decode_image(data['headwearLayer']).getpixel((10,18)), (21,37,50,255))
        self.assertEqual(decode_image(data['outfitLayer']).getpixel((8,27)), outfit.getpixel((8,27)))

    def test_bare_toe_fringe_snaps_but_boot_stays(self):
        base, outfit = fixture()
        outfit.paste((49,32,29,255), (11,27,12,30))
        data = self.request(base, outfit)
        self.assertEqual(decode_image(data['image']).getpixel((11,28))[3], 0)
        outfit.paste((55,91,110,255), (7,24,12,30))
        data = self.request(base, outfit)
        self.assertEqual(decode_image(data['image']).getpixel((11,28)), (55,91,110,255))

    def test_multiframe_mask_does_not_shift_coordinates(self):
        base, outfit = fixture()
        outfit.paste((51,42,37,255), (7,0,17,5))
        b = Image.new('RGBA', (48,32)); b.paste(base,(24,0))
        o = Image.new('RGBA', (48,32)); o.paste(outfit,(24,0))
        result, _, mask = repair_sheet(b,o,rows=1,cols=2,colors=0,
            background_threshold=36,skin_expand=0,outline=False,
            composition='layers',accessories=True,return_masks=True)
        self.assertEqual(mask.getpixel((34,1)), (255,200,0,255))
        self.assertEqual(result.getpixel((10,1))[3], 0)
