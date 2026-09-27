"""Regressions for source gloves/boots mistaken for the base's bare limbs."""
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from repair_outfit_ui import process_request,encode_png,decode_image

ROOT=Path(__file__).parent/'fixtures'


class CoveredEquipmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=Image.open(ROOT/'hair_outfit/base.png').convert('RGBA')
        cls.results={}
        for name in ('leather-gloves-boots','dark-armor','embroidered-robe','gold-robe'):
            source=Image.open(ROOT/'covered_equipment'/f'{name}.png').convert('RGBA')
            cls.results[name]=process_request(dict(base=encode_png(cls.base),outfit=encode_png(source),
                rows=7,cols=4,colors=0,outline=False,cleanup=0,composition='cutout'))

    def test_brown_gloves_and_boots_remain_covered(self):
        points=[(21,46),(21,47),(22,48),(40,46),(41,47),(27,57),(27,58),(35,57),(36,58)]
        for name in ('leather-gloves-boots','dark-armor'):
            layer=decode_image(self.results[name]['outfitLayer'])
            for p in points:
                with self.subTest(source=name,pixel=p):
                    self.assertEqual(layer.getpixel(p)[3],255)

    def test_warm_armor_and_embroidery_do_not_reveal_naked_torso(self):
        for name in ('dark-armor','embroidered-robe','gold-robe'):
            layer=decode_image(self.results[name]['outfitLayer'])
            for p in [(30,38),(32,39),(34,40),(31,49),(33,51)]:
                with self.subTest(source=name,pixel=p):
                    self.assertEqual(layer.getpixel(p)[3],255)

    def test_bald_equipment_sources_do_not_create_a_hair_asset(self):
        for name,result in self.results.items():
            self.assertFalse(np.asarray(decode_image(result['headwearLayer']))[:,:,3].any(),name)

    def test_closed_robe_lapels_and_inner_panel_survive_side_and_raised_arm_poses(self):
        # Source annotations: ivory piping, its dark seam, and burgundy cloth.
        # Frame 1 alone missed the large chest holes in frames 3/4/6/7/8.
        source=Image.open(ROOT/'covered_equipment/embroidered-robe.png').convert('RGBA')
        layer=decode_image(self.results['embroidered-robe']['outfitLayer'])
        annotations={
            2:[(31,38),(31,39),(32,40),(37,38)],
            3:[(30,36),(30,37),(31,39),(37,37),(37,38),(36,38)],
            5:[(27,37),(28,38),(35,37),(35,38),(31,39),(32,40)],
            6:[(29,37),(30,39),(36,37),(36,38),(33,39)],
            7:[(29,37),(30,39),(36,37),(36,38),(33,39)],
        }
        for frame,points in annotations.items():
            for x,y in points:
                p=(frame%4*64+x,frame//4*64+y)
                with self.subTest(frame=frame+1,pixel=(x,y)):
                    self.assertEqual(layer.getpixel(p),source.getpixel(p))

    def test_actual_small_neck_openings_still_use_base_skin(self):
        result=self.results['embroidered-robe']
        layer=decode_image(result['outfitLayer']);image=decode_image(result['image'])
        for frame,points in {0:[(30,36),(31,36),(32,36)],
                             2:[(33,36)],3:[(33,35),(34,36)]}.items():
            for x,y in points:
                p=(frame%4*64+x,frame//4*64+y)
                with self.subTest(frame=frame+1,pixel=(x,y)):
                    self.assertEqual(layer.getpixel(p)[3],0)
                    self.assertEqual(image.getpixel(p),self.base.getpixel(p))

    def test_shifted_source_temple_does_not_export_as_a_floating_outfit_strip(self):
        for name,result in self.results.items():
            outfit=decode_image(result['outfitLayer'])
            for p in [(41,27),(42,29),(43,192+25),(44,192+30),
                      (128+23,31),(26,384+31)]:
                self.assertEqual(outfit.getpixel(p)[3],0,(name,p))

    def test_each_export_still_recomposes_exactly_and_preserves_base_colors(self):
        original=np.asarray(self.base)
        for name,result in self.results.items():
            base=decode_image(result['baseLayer'])
            outfit=decode_image(result['outfitLayer']);hair=decode_image(result['headwearLayer'])
            assembled=Image.alpha_composite(Image.alpha_composite(base,outfit),hair)
            np.testing.assert_array_equal(assembled,decode_image(result['image']),err_msg=name)
            np.testing.assert_array_equal(np.asarray(base)[original[:,:,3]>0],original[original[:,:,3]>0])


if __name__=='__main__':
    unittest.main()
