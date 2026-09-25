"""Spatial cleanup must preserve pixel strokes, masks and frame boundaries."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
from repair_outfit_sprite import coherent_fabric, shade_materials


class FabricCoherenceTests(unittest.TestCase):
    def setUp(self):
        self.rgb = np.full((16,16,3),[170,195,200],np.uint8)
        self.fill = np.ones((16,16),bool)

    def test_weak_isolated_spot_is_removed(self):
        self.rgb[8,8] = [140,160,170]
        result = coherent_fabric(self.rgb,self.fill,(16,16))
        np.testing.assert_array_equal(result[8,8],result[8,7])

    def test_connected_single_pixel_stroke_survives(self):
        self.rgb[3:13,8] = [140,160,170]
        result = coherent_fabric(self.rgb,self.fill,(16,16))
        np.testing.assert_array_equal(result[4:12,8],self.rgb[4:12,8])

    def test_high_contrast_highlight_survives(self):
        self.rgb[8,8] = [255,255,255]
        result = coherent_fabric(self.rgb,self.fill,(16,16))
        np.testing.assert_array_equal(result[8,8],self.rgb[8,8])

    def test_locked_pixels_and_palette_are_preserved(self):
        self.rgb[8,8] = [140,160,170]
        self.fill[8,8] = False
        result = coherent_fabric(self.rgb,self.fill,(16,16))
        np.testing.assert_array_equal(result,self.rgb)

    def test_neighbors_cannot_cross_cells(self):
        self.rgb[:,8:] = [140,160,170]
        self.rgb[8,7] = [140,160,170]
        isolated = coherent_fabric(self.rgb[:,:8],self.fill[:,:8],(8,16))
        sheet = coherent_fabric(self.rgb,self.fill,(8,16))
        np.testing.assert_array_equal(sheet[:,:8],isolated)

    def test_near_identical_tones_collapse_without_palette_inflation(self):
        yy,xx = np.indices(self.fill.shape)
        self.rgb += ((yy+xx)%3)[...,None].astype(np.uint8)*3
        result = shade_materials(self.rgb,self.fill,6,(16,16))
        self.assertEqual(len(np.unique(result.reshape(-1,3),axis=0)),1)


if __name__ == '__main__':
    unittest.main()
