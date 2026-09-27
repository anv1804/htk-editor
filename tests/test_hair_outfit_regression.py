"""User's blue robe, long brown hair, green band, and reduced corner logo."""
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from gemini_logo import restore_corner_logo
from repair_outfit_ui import process_request,encode_png,decode_image

ROOT = Path(__file__).parent/'fixtures/hair_outfit'


class HairOutfitRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Image.open(ROOT/'base.png').convert('RGBA')
        cls.source = Image.open(ROOT/'outfit.png').convert('RGBA')
        cls.response = process_request(dict(base=encode_png(cls.base),outfit=encode_png(cls.source),
            rows=7,cols=4,composition='cutout',colors=32,paint=4,outline=True,cleanup=0))
        cls.layers = {key:decode_image(cls.response[key]) for key in
                      ['image','baseLayer','outfitLayer','headwearLayer','mask']}

    def test_three_exported_layers_reassemble_exactly(self):
        layers=self.layers
        composite=Image.alpha_composite(Image.alpha_composite(layers['baseLayer'],layers['outfitLayer']),layers['headwearLayer'])
        np.testing.assert_array_equal(np.asarray(composite),np.asarray(layers['image']))
        clothes=np.asarray(layers['outfitLayer'])[:,:,3]>0
        hair=np.asarray(layers['headwearLayer'])[:,:,3]>0
        self.assertFalse(np.any(clothes & hair))
        original=np.asarray(self.base); exported=np.asarray(layers['baseLayer'])
        np.testing.assert_array_equal(exported[original[:,:,3]>0],original[original[:,:,3]>0])
        self.assertEqual([p['id'] for p in self.response['report']['layers']],['base','outfit','headwear'])

    def test_exposed_palms_use_exact_base_pixels_and_cuffs_remain_outfit(self):
        for frame, points in [(0,[(20,47),(21,46),(21,47),(43,47),(44,47)]),
                              (3,[(23,45),(24,45),(23,46)]),
                              (22,[(20,47),(21,47),(43,47)])]:
            x,y=frame%4*64,frame//4*64
            for px,py in points:
                p=(x+px,y+py)
                with self.subTest(frame=frame+1,pixel=p):
                    self.assertEqual(self.layers['image'].getpixel(p),self.base.getpixel(p))
                    self.assertEqual(self.layers['outfitLayer'].getpixel(p)[3],0)
                    self.assertEqual(self.layers['headwearLayer'].getpixel(p)[3],0)
        for p in [(21,43),(20,44),(43,43),(42,44)]:
            self.assertEqual(self.layers['outfitLayer'].getpixel(p)[3],255,p)

    def test_band_underside_and_long_tress_are_headwear_not_clothing(self):
        for frame,points in [(0,[(31,25),(32,26)]), (22,[(25,27),(26,27),(27,27)]),
                             (27,[(27,28),(32,28),(24,40),(25,41),(23,41)])]:
            x,y=frame%4*64,frame//4*64
            for px,py in points:
                p=(x+px,y+py)
                with self.subTest(frame=frame+1,pixel=p):
                    self.assertEqual(self.layers['headwearLayer'].getpixel(p)[3],255)
                    self.assertEqual(self.layers['outfitLayer'].getpixel(p)[3],0)
        # Face interiors remain base, never part of an exported head accessory.
        for p in [(31,30),(32,31),(34,32)]:
            self.assertEqual(self.layers['headwearLayer'].getpixel(p)[3],0)

    def test_hair_palette_retains_green_band_within_total_color_budget(self):
        self.assertLessEqual(self.response['paletteColors'],32)
        hair=np.asarray(self.layers['headwearLayer'])[:64,:64].astype(int)
        green=(hair[:,:,1]>hair[:,:,2]+15)&(hair[:,:,0]<hair[:,:,1]+25)&(hair[:,:,3]>0)
        self.assertGreater(green.sum(),12)

    def test_actual_reduced_logo_is_restored_once_in_last_frame_only(self):
        restored,report=restore_corner_logo(self.source)
        self.assertEqual(report['status'],'restored')
        self.assertGreater(report['correctedPixels'],40)
        source=np.asarray(self.source); output=np.asarray(restored)
        changed=np.any(source!=output,axis=2)
        ys,xs=np.nonzero(changed)
        self.assertTrue((ys>=384).all() and (xs>=192).all())
        self.assertTrue((ys<420).all())
        np.testing.assert_array_equal(source[:,:,3],output[:,:,3])
        self.assertEqual(restore_corner_logo(restored)[1]['correctedPixels'],0)
        self.assertEqual(self.response['report']['logoCleanup']['correctedPixels'],report['correctedPixels'])

    def test_unmarked_poses_do_not_trigger_corner_cleanup(self):
        # Put each of the other 27 poses at the final frame's coordinates.
        # The same hair, band, and costume must not be mistaken for a logo.
        for frame in range(27):
            x,y=frame%4*64,frame//4*64
            control=self.source.copy()
            control.paste(self.source.crop((x,y,x+64,y+64)),(192,384))
            with self.subTest(frame=frame+1):
                output,report=restore_corner_logo(control)
                self.assertEqual(report['correctedPixels'],0)
                np.testing.assert_array_equal(np.asarray(output),np.asarray(control))
