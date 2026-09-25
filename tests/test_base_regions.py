"""Regression checks for reviewed head/palm regions on the supplied base."""
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
from repair_outfit_sprite import build_base_profile, reviewed_base_regions, repair_sheet, profile_from_regions


class BaseRegionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with Image.open(Path(__file__).parent / 'fixtures/base_regions/base.png') as image:
            cls.base = image.convert('RGBA')
        cls.profile = build_base_profile(cls.base,rows=7,cols=4)

    def label(self,frame,x,y):
        return self.profile.getpixel(((frame-1)%4*64+x,(frame-1)//4*64+y))

    def test_reported_feet_are_no_longer_palms(self):
        for frame,x,y in [(18,31,52),(26,26,53),(28,24,54)]:
            self.assertEqual(self.label(frame,x,y)[3],0,(frame,x,y))

    def test_folded_palms_are_selected(self):
        for frame,x,y in [(21,33,48),(25,33,45),(26,32,45),(27,36,45),(28,36,43)]:
            self.assertEqual(self.label(frame,x,y),(255,128,0,255),(frame,x,y))

    def test_full_front_finger_outline_is_selected(self):
        self.assertEqual(self.label(1,22,50),(255,128,0,255))
        self.assertEqual(self.label(1,42,50),(255,128,0,255))

    def test_reviewed_regions_only_match_exact_base_and_grid(self):
        self.assertIsNotNone(reviewed_base_regions(self.base,7,4))
        self.assertIsNone(reviewed_base_regions(self.base,14,4))
        changed = self.base.copy()
        changed.putpixel((0,0),(1,2,3,255))
        self.assertIsNone(reviewed_base_regions(changed,7,4))

    def test_square_selection_copies_outline_and_ignores_transparency(self):
        base = Image.new('RGBA',(8,8))
        base.paste((20,30,40,255),(2,2,6,6))
        profile = profile_from_regions(base,1,1,[{'hands':[[1,1,7,7]]}])
        self.assertEqual(profile.getpixel((2,2)),(255,128,0,255))
        self.assertEqual(profile.getpixel((1,1))[3],0)
        with self.assertRaisesRegex(ValueError,'outside'):
            profile_from_regions(base,1,1,[{'hands':[[0,0,9,8]]}])

    def test_pinned_palm_does_not_require_generated_hand_nearby(self):
        outfit = self.base.copy()
        outfit.paste((0,0,0,0),(0,40,64,64))
        result,_ = repair_sheet(self.base,outfit,rows=7,cols=4,colors=0,
            background_threshold=36,skin_expand=0,outline=False,lock_base=True)
        selected = np.asarray(self.profile)[:64,:64,1] == 128
        self.assertTrue(np.array_equal(np.asarray(result)[:64,:64][selected],
                                       np.asarray(self.base)[:64,:64][selected]))


if __name__ == '__main__':
    unittest.main()
