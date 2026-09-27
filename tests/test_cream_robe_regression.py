"""User's cream/green robe: neck shadows, collar highlights and exposed palms."""
import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from repair_outfit_sprite import repair_sheet, consolidate_palette_islands

ROOT = Path(__file__).parent/'fixtures/cream_robe'


class CreamRobeRegressionTests(unittest.TestCase):
    def test_full_sheet_cloth_over_base_body_never_becomes_skin_or_base_ink(self):
        base=Image.open(ROOT/'base.png').convert('RGBA')
        outfit=Image.open(ROOT/'outfit.png').convert('RGBA')
        result,_,mask=repair_sheet(base,outfit,rows=7,cols=4,colors=0,
            background_threshold=32,skin_expand=0,composition='cutout',
            outline=False,cleanup=0,accessories=True,return_masks=True)
        # Human-reviewed cloth in the reported sheet: waist, diagonal folds,
        # hems, and sleeves. The nude base has skin/ink at these coordinates.
        # Check the exported layer ownership as well as the composite color.
        checks=[
            (1,[(32,45),(33,45),(30,48),(31,48),(31,49),(31,50),
                (32,50),(33,52),(33,53)]),
            (5,[(28,44),(29,44),(33,44),(29,45),(32,45),(34,45),
                (33,53),(34,53),(33,54)]),
            (9,[(35,51),(35,52),(35,53),(35,54),(36,45)]),
        ]
        for frame,points in checks:
            for x,y in points:
                point=(frame%4*64+x,frame//4*64+y)
                with self.subTest(frame=frame+1,point=(x,y)):
                    self.assertEqual(result.getpixel(point),outfit.getpixel(point))
                    self.assertEqual(mask.getpixel(point),(70,155,255,255))
        # Real skin must still be removed from the standalone outfit layer.
        for frame,points in [(0,[(29,35),(21,47),(21,48),(22,49)]),
                             (20,[(31,36),(32,36),(33,36)])]:
            for x,y in points:
                point=(frame%4*64+x,frame//4*64+y)
                with self.subTest(skin_frame=frame+1,point=(x,y)):
                    self.assertEqual(result.getpixel(point),base.getpixel(point))
                    self.assertEqual(mask.getpixel(point),(255,80,80,255))

    def test_pale_hem_pixels_near_but_outside_base_skin_are_not_cut(self):
        base=Image.open(ROOT/'base.png').convert('RGBA')
        outfit=Image.open(ROOT/'outfit.png').convert('RGBA')
        checks=[
            (0,[(33,54),(39,55)]),
            (1,[(31,51),(32,52),(32,53),(23,55),(24,55)]),
        ]
        for frame,points in checks:
            x=frame%4*64; y=frame//4*64
            b=base.crop((x,y,x+64,y+64)); o=outfit.crop((x,y,x+64,y+64))
            result,_=repair_sheet(b,o,rows=1,cols=1,colors=0,
                background_threshold=36,skin_expand=0,composition='cutout',
                outline=False,cleanup=0,accessories=True)
            for point in points:
                with self.subTest(frame=frame+1,point=point):
                    self.assertEqual(result.getpixel(point),o.getpixel(point))

    def test_source_jaw_shadow_removed_but_collar_and_palms_preserved(self):
        base=Image.open(ROOT/'base.png').convert('RGBA')
        outfit=Image.open(ROOT/'outfit.png').convert('RGBA')
        checks = [
            (0, [(29,35),(30,35),(33,35),(21,47),(20,47),(21,48),(22,49),(41,48)], [(25,36),(21,44),(22,45)]),
            # Frame 2: pale cuffs and their dark green rims are garment,
            # including the pixels directly beside the exposed palms.
            (1, [], [(20,44),(21,44),(22,44),(19,46),(19,47),
                     (41,44),(42,44),(43,46),(44,47)]),
            (20, [(31,36),(32,36),(33,36)], [(27,37)]),
            (24, [(33,36)], [(30,37)]),
        ]
        for frame, skin, fabric in checks:
            with self.subTest(frame=frame+1):
                x,y=frame%4*64,frame//4*64
                b=base.crop((x,y,x+64,y+64)); o=outfit.crop((x,y,x+64,y+64))
                result,_=repair_sheet(b,o,rows=1,cols=1,colors=0,
                    background_threshold=36,skin_expand=0,composition='cutout',
                    outline=False,accessories=True,cleanup=0)
                for p in skin:
                    self.assertEqual(result.getpixel(p),b.getpixel(p))
                for p in fabric:
                    self.assertEqual(result.getpixel(p),o.getpixel(p))

    def test_palette_cleanup_merges_near_color_dot_not_dark_seam(self):
        rgb=np.full((12,12,3),[220,215,190],np.uint8)
        rgb[3,3]=[200,200,175]
        rgb[7,3:8]=[60,65,45]
        fill=np.ones((12,12),bool)
        result=consolidate_palette_islands(rgb,fill,(12,12))
        np.testing.assert_array_equal(result[3,3],rgb[3,4])
        np.testing.assert_array_equal(result[7,3:8],rgb[7,3:8])
        self.assertTrue(set(map(tuple,result.reshape(-1,3))) <= set(map(tuple,rgb.reshape(-1,3))))

    def test_palette_cleanup_never_edits_locked_pixels(self):
        rgb=np.full((8,16,3),[220,215,190],np.uint8)
        rgb[3,7]=[200,200,175]
        fill=np.ones((8,16),bool); fill[3,7]=False
        result=consolidate_palette_islands(rgb,fill,(8,8))
        np.testing.assert_array_equal(result[~fill],rgb[~fill])
