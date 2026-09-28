"""Spatial cleanup must preserve pixel strokes, masks and frame boundaries."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
from repair_outfit_sprite import coherent_fabric, shade_materials, clean_parallel_outline, repaint, thin_contour, components, fit_source_palette, luminance, shade_supported_seams


class FabricCoherenceTests(unittest.TestCase):
    def test_crisp_mode_does_not_turn_midtones_into_ink_or_clip_highlights(self):
        values=np.arange(60,241,15,dtype=np.uint8)
        rgb=np.repeat(np.repeat(values[None,:,None],3,axis=2),8,axis=0)
        result=fit_source_palette(rgb,np.ones(rgb.shape[:2],bool),32,
                                  (rgb.shape[1],8),redraw=True)
        before,after=luminance(rgb),luminance(result)
        self.assertLessEqual(float(np.abs(after-before).max()),16)
        self.assertTrue(np.all(after[before >= 120] >= 105))
        self.assertTrue(np.all(np.diff(after[0]) >= 0))
        self.assertTrue(set(map(tuple,result.reshape(-1,3))) <= set(map(tuple,rgb.reshape(-1,3))))

    def test_crisp_mode_preserves_locked_anatomy_and_alpha(self):
        rgba=np.zeros((16,16,4),np.uint8)
        fabric=np.zeros((16,16),bool); fabric[4:14,3:13]=True
        anatomy=np.zeros_like(fabric); anatomy[1:4,5:11]=True
        rgba[fabric]=[220,215,180,255]; rgba[7:10,7:9]=[130,135,110,255]
        rgba[anatomy]=[244,175,138,255]
        result,_=repaint(rgba,anatomy,fabric,colors=16,paint=4,
                          outline=True,cell_size=(16,16),conservative=True)
        np.testing.assert_array_equal(result[anatomy],rgba[anatomy])
        np.testing.assert_array_equal(result[:,:,3],rgba[:,:,3])

    def test_crisp_mode_gives_green_cloth_more_depth_within_palette_budget(self):
        rgba=np.zeros((16,16,4),np.uint8)
        anatomy=np.zeros((16,16),bool); anatomy[4:14,2:4]=True
        fabric=np.zeros_like(anatomy); fabric[4:14,4:14]=True
        rgba[anatomy]=[244,175,138,255]
        rgba[fabric]=[95,130,70,255]
        rgba[5:7,6:11]=[120,160,92,255]
        rgba[9:11,5:13]=[70,96,52,255]
        original,_=repaint(rgba,anatomy,fabric,colors=16,paint=3,
                           outline=True,cell_size=(16,16),conservative=True)
        crisp,_=repaint(rgba,anatomy,fabric,colors=16,paint=4,
                        outline=True,cell_size=(16,16),conservative=True)
        spread=lambda image:float(luminance(image[5,8,:3])-luminance(image[9,8,:3]))
        self.assertGreater(spread(crisp),spread(original))
        self.assertGreater(int(crisp[7,8,1])-int(crisp[7,8,0]),
                           int(original[7,8,1])-int(original[7,8,0]))
        np.testing.assert_array_equal(crisp[anatomy],rgba[anatomy])
        np.testing.assert_array_equal(crisp[:,:,3],rgba[:,:,3])
        self.assertLessEqual(len(np.unique(crisp[crisp[:,:,3]>0,:3],axis=0)),16)

    def test_continuous_belt_seam_casts_one_pixel_shadow(self):
        source=np.full((12,12,3),[95,130,70],np.uint8)
        fabric=np.zeros((12,12),bool); fabric[2:10,2:10]=True
        source[5,3:9]=[45,65,30]
        source[8,3:9]=[78,110,55]
        fill=fabric.copy(); fill[5,3:9]=False
        result=shade_supported_seams(source,source,fabric,fill,
            np.zeros_like(fabric),fabric,(12,12))
        self.assertTrue(np.all(result[6,4:8] == [78,110,55]))
        np.testing.assert_array_equal(result[4,4:8],source[4,4:8])
        isolated=source.copy(); isolated[5,3:9]=[95,130,70]; isolated[5,6]=[45,65,30]
        np.testing.assert_array_equal(shade_supported_seams(isolated,isolated,fabric,fill,
            np.zeros_like(fabric),fabric,(12,12))[6,6],isolated[6,6])

    def test_source_palette_preserves_more_than_two_material_hues(self):
        palette=np.array([[190,45,55],[50,175,75],[45,80,195],[205,170,45],
                          [155,60,175],[35,180,185],[210,135,75],[115,120,130]],np.uint8)
        rgb=np.repeat(palette[None],8,axis=0)
        result=fit_source_palette(rgb,np.ones((8,8),bool),16,(8,8))
        np.testing.assert_array_equal(result,rgb)

    def test_palette_budget_is_used_to_retain_source_shading(self):
        values=np.arange(40,232,12,dtype=np.uint8)
        rgb=np.repeat(np.stack([values,values,values],axis=1)[None],8,axis=0)
        fill=np.ones(rgb.shape[:2],bool)
        fine=fit_source_palette(rgb,fill,16,(16,8))
        coarse=fit_source_palette(rgb,fill,6,(16,8))
        self.assertGreater(len(np.unique(fine.reshape(-1,3),axis=0)),6)
        self.assertLess(np.mean((fine.astype(float)-rgb)**2),np.mean((coarse.astype(float)-rgb)**2))

    def test_cuff_uses_base_outline_without_adding_a_second_dark_row(self):
        rgba=np.zeros((16,16,4),np.uint8)
        skin=np.zeros((16,16),bool); skin[3:13,3:8]=True
        cloth=np.zeros_like(skin); cloth[3:13,8:14]=True
        rgba[skin]=[245,185,140,255]; rgba[3:13,7]=[39,25,32,255]
        rgba[cloth]=[160,190,200,255]; rgba[3:13,8]=[50,40,45,255]
        result,_=repaint(rgba,skin,cloth,colors=0,paint=3,outline=True,cell_size=(16,16))
        np.testing.assert_array_equal(result[skin],rgba[skin])
        self.assertGreater(int(result[7,8,1]),110)
        np.testing.assert_array_equal(result[:,:,3],rgba[:,:,3])

    def test_missing_cuff_edge_is_drawn_on_cloth_not_on_skin(self):
        rgba=np.zeros((16,16,4),np.uint8)
        skin=np.zeros((16,16),bool); skin[3:13,3:8]=True
        cloth=np.zeros_like(skin); cloth[3:13,8:14]=True
        rgba[skin]=[245,185,140,255]; rgba[cloth]=[160,190,200,255]
        result,_=repaint(rgba,skin,cloth,colors=0,paint=3,outline=True,cell_size=(16,16))
        self.assertLess(int(result[7,8,1]),80)
        np.testing.assert_array_equal(result[skin],rgba[skin])

    def test_thinning_keeps_outline_loop_connected_without_solid_corner_blocks(self):
        ring=np.zeros((16,16),bool); ring[2:14,2:14]=True; ring[4:12,4:12]=False
        result=thin_contour(ring)
        self.assertEqual(len(components(result)),1)
        self.assertFalse(np.any(result[:-1,:-1]&result[1:,:-1]&result[:-1,1:]&result[1:,1:]))
        self.assertFalse(result[8,8])

    def test_parallel_inner_outline_is_repainted_without_erasing_outer_edge(self):
        for gap in (1,2):
            rgb=np.full((12,12,3),[160,190,200],np.uint8)
            fabric=np.ones((12,12),bool)
            contour=np.zeros((12,12),bool); contour[:,2]=True
            rgb[:,2]=[30,25,35]; rgb[2:10,2+gap]=[50,45,55]
            result=clean_parallel_outline(rgb,fabric,contour)
            np.testing.assert_array_equal(result[2:10,2+gap],rgb[2:10,7])
            np.testing.assert_array_equal(result[:,2],rgb[:,2])

    def test_dark_panel_and_perpendicular_fold_are_preserved(self):
        rgb=np.full((12,12,3),[160,190,200],np.uint8)
        fabric=np.ones((12,12),bool)
        contour=np.zeros((12,12),bool); contour[:,2]=True
        rgb[:,2]=[30,25,35]; rgb[5,3:10]=[50,45,55]
        np.testing.assert_array_equal(clean_parallel_outline(rgb,fabric,contour),rgb)
        rgb[:,3:]=[50,45,55]
        np.testing.assert_array_equal(clean_parallel_outline(rgb,fabric,contour),rgb)

    def test_outline_cleanup_cannot_sample_across_a_transparent_gap(self):
        rgb=np.full((12,12,3),[160,190,200],np.uint8)
        fabric=np.ones((12,12),bool); fabric[:,3]=False
        contour=np.zeros((12,12),bool); contour[:,2]=True
        rgb[:,4]=[50,45,55]
        np.testing.assert_array_equal(clean_parallel_outline(rgb,fabric,contour),rgb)

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
