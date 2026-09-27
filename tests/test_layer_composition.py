import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
from repair_outfit_sprite import repair_sheet
from repair_outfit_ui import process_request, encode_png, decode_image


def fixture():
    base = Image.new('RGBA',(24,32))
    base.paste((246,184,139,255),(8,2,16,11))
    base.paste((234,165,122,255),(9,11,15,24))
    base.paste((234,165,122,255),(5,14,8,21))
    base.paste((234,165,122,255),(16,14,19,21))
    base.paste((246,184,139,255),(7,24,11,30))
    base.paste((246,184,139,255),(13,24,17,30))
    outfit = base.copy()
    outfit.paste((50,109,57,255),(7,10,17,24))
    outfit.paste((222,168,132,255),(7,24,11,30))
    outfit.paste((222,168,132,255),(13,24,17,30))
    return base,outfit


def run(base,outfit,**kwargs):
    return repair_sheet(base,outfit,rows=1,cols=1,colors=0,background_threshold=36,
        skin_expand=0,outline=False,composition='layers',**kwargs)[0]


class LayerCompositionTests(unittest.TestCase):
    def test_hanging_robe_between_bare_feet_is_preserved_across_material_colors(self):
        for color in [(50,109,57,255),(65,95,160,255),(155,60,175,255),(220,220,205,255)]:
            with self.subTest(color=color):
                base,outfit=fixture()
                outfit.paste(color,(11,20,13,29))
                result=run(base,outfit,accessories=True)
                self.assertEqual(result.getpixel((11,27)),color)
                self.assertEqual(result.getpixel((8,27)),base.getpixel((8,27)))

    def test_neutral_toe_and_heel_halos_removed_across_clothing_colors(self):
        for color in [(50,109,57,255),(65,95,160,255),(155,60,175,255),(220,220,205,255)]:
            with self.subTest(color=color):
                base,outfit=fixture()
                outfit.paste(color,(7,10,17,24))
                outfit.paste((125,121,118,255),(5,27,7,30))
                outfit.paste((125,121,118,255),(17,27,19,30))
                result=run(base,outfit,accessories=True)
                self.assertEqual(result.getpixel((5,28))[3],0)
                self.assertEqual(result.getpixel((18,28))[3],0)
                self.assertEqual(result.getpixel((8,27)),base.getpixel((8,27)))

    def test_boots_do_not_get_trimmed_to_bare_foot_shape(self):
        for color in [(45,45,50,255),(65,95,160,255),(155,60,175,255),(220,220,205,255)]:
            with self.subTest(color=color):
                base,outfit=fixture()
                outfit.paste(color,(5,24,12,31))
                outfit.paste(color,(13,24,19,31))
                result=run(base,outfit,accessories=True)
                self.assertEqual(result.getpixel((5,28)),color)
                self.assertEqual(result.getpixel((18,28)),color)

    def test_small_white_matte_cluster_beside_bare_heel_is_removed(self):
        base,outfit=fixture()
        outfit.paste((212,207,204,255),(5,27,7,30))
        result=run(base,outfit,accessories=True)
        self.assertEqual(result.getpixel((5,28))[3],0)
        self.assertEqual(result.getpixel((8,28)),base.getpixel((8,28)))

    def test_reported_green_heel_has_no_detached_white_matte(self):
        root=Path(__file__).parent/'fixtures'/'green_outfit'
        base=Image.open(root/'base.png').convert('RGBA').crop((0,64,64,128))
        outfit=Image.open(root/'outfit.png').convert('RGBA').crop((0,64,64,128))
        result=run(base,outfit,accessories=True)
        self.assertEqual(result.getpixel((29,56))[3],0)

    def test_skin_cutout_does_not_fill_over_colored_cuff_detail(self):
        base,outfit=fixture()
        outfit.paste((222,168,132,255),(4,14,8,21))
        outfit.putpixel((6,17),(50,109,57,255))
        result=run(base,outfit)
        self.assertEqual(result.getpixel((6,17)),outfit.getpixel((6,17)))

    def test_blue_cream_robe_does_not_protect_its_source_fists_as_tan_fabric(self):
        root=Path(__file__).parent/'fixtures'/'outfit_occlusion'
        base=Image.open(root/'base.png').convert('RGBA').crop((0,0,64,64))
        outfit=Image.open(root/'outfit.png').convert('RGBA').crop((0,0,64,64))
        result=run(base,outfit,accessories=True)
        for point in [(21,49),(22,49),(41,49)]:
            self.assertEqual(result.getpixel(point),base.getpixel(point))
        for point in [(21,43),(24,43),(32,55)]:
            self.assertEqual(result.getpixel(point),outfit.getpixel(point))

    def test_outfit_face_palette_removes_differently_colored_hands(self):
        base,outfit=fixture()
        source_skin=(185,125,90,255)
        outfit.paste(source_skin,(8,2,16,10))
        outfit.paste(source_skin,(5,14,7,21))
        outfit.paste(source_skin,(17,14,19,21))
        result=run(base,outfit)
        for point in [(5,17),(18,18)]:
            self.assertEqual(result.getpixel(point),base.getpixel(point))
        self.assertEqual(result.getpixel((7,17)),outfit.getpixel((7,17)))

    def test_source_hand_outside_base_is_cut_without_moving_the_palm(self):
        base,outfit=fixture()
        source_skin=(185,125,90,255)
        outfit.paste(source_skin,(8,2,16,10))
        outfit.paste(source_skin,(3,15,7,19))
        result=run(base,outfit)
        self.assertEqual(result.getpixel((3,17))[3],0)
        self.assertEqual(result.getpixel((5,17)),base.getpixel((5,17)))

    def test_dark_skin_next_to_cloth_is_not_repainted_as_fabric(self):
        base,outfit=fixture()
        for point in [(6,17),(8,26),(14,27),(14,9)]:
            base.putpixel(point,(104,51,43,255))
            outfit.putpixel(point,(100,56,42,255))
        result=run(base,outfit)
        for point in [(6,17),(8,26),(14,27),(14,9)]:
            self.assertEqual(result.getpixel(point),base.getpixel(point))

    def test_brown_belt_near_skin_does_not_reveal_bare_torso(self):
        base,outfit=fixture()
        outfit.paste((100,65,40,255),(7,20,17,22))
        result=run(base,outfit)
        self.assertEqual(result.getpixel((9,20)),outfit.getpixel((9,20)))

    def test_bare_feet_show_original_base(self):
        base,outfit=fixture()
        result=run(base,outfit)
        for point in [(8,27),(15,27),(6,18)]:
            self.assertEqual(result.getpixel(point),base.getpixel(point))
        self.assertEqual(result.getpixel((10,18)),outfit.getpixel((10,18)))

    def test_trousers_and_sleeves_still_cover_the_base(self):
        base,outfit=fixture()
        cloth=(50,109,57,255)
        outfit.paste(cloth,(5,14,19,30))
        result=run(base,outfit)
        for point in [(8,27),(15,27),(6,18)]:
            self.assertEqual(result.getpixel(point),cloth)

    def test_cut_reveals_base_and_empty_base_stays_transparent(self):
        base,outfit=fixture()
        outfit.paste((50,109,57,255),(18,22,22,27))
        cuts=Image.new('RGBA',base.size)
        cuts.putpixel((10,18),(255,0,0,255))
        cuts.putpixel((20,24),(255,0,0,255))
        result=run(base,outfit,overrides=cuts)
        self.assertEqual(result.getpixel((10,18)),base.getpixel((10,18)))
        self.assertEqual(result.getpixel((20,24)),(0,0,0,0))

    def test_skin_colored_clothing_can_be_manually_kept(self):
        base,outfit=fixture()
        keep=Image.new('RGBA',base.size)
        keep.putpixel((8,27),(0,0,255,255))
        result=run(base,outfit,overrides=keep)
        self.assertEqual(result.getpixel((8,27)),outfit.getpixel((8,27)))

    def test_pinned_palm_does_not_override_sleeve_in_layer_mode(self):
        base,outfit=fixture()
        profile=Image.new('RGBA',base.size)
        profile.paste((255,128,0,255),(7,14,12,20))
        result=run(base,outfit,base_profile=profile,lock_base=True)
        self.assertEqual(result.getpixel((10,18)),outfit.getpixel((10,18)))

    def test_api_exports_transparent_outfit_layer(self):
        base,outfit=fixture()
        result=process_request(dict(base=encode_png(base),outfit=encode_png(outfit),
            rows=1,cols=1,colors=0,outline=False))
        layer=decode_image(result['outfitLayer'])
        self.assertEqual(result['report']['composition'],'layers')
        self.assertEqual(layer.getpixel((8,27))[3],0)
        self.assertEqual(layer.getpixel((10,18)),outfit.getpixel((10,18)))
        self.assertTrue(np.any(np.asarray(layer)[:,:,3]))

    def test_reported_green_frame_keeps_dark_anatomy_with_repaint(self):
        root=Path(__file__).parent/'fixtures'/'green_outfit'
        base=Image.open(root/'base.png').convert('RGBA')
        outfit=Image.open(root/'outfit.png').convert('RGBA')
        # Raised hand beside head, arm edge, and bent-leg shadow, frame 15.
        points=[(40,29),(41,31),(24,38),(26,50),(25,51)]
        results=[]
        for colors in (0,32):
            result,_=repair_sheet(base,outfit,rows=7,cols=4,colors=colors,
                background_threshold=36,skin_expand=0,paint=3,composition='layers')
            for x,y in points:
                point=(128+x,192+y)
                self.assertEqual(result.getpixel(point),base.getpixel(point))
            results.append(np.asarray(result))
        np.testing.assert_array_equal(results[0][:,:,3],results[1][:,:,3])

    def test_green_frame_restores_base_head_edge_and_between_leg_gap(self):
        root=Path(__file__).parent/'fixtures'/'green_outfit'
        base=Image.open(root/'base.png').convert('RGBA')
        outfit=Image.open(root/'outfit.png').convert('RGBA')
        result=run(base.crop((0,0,64,64)),outfit.crop((0,0,64,64)))
        for point in [(30,15),(31,15),(38,34)]:
            self.assertEqual(result.getpixel(point),base.getpixel(point))
        self.assertEqual(result.getpixel((31,51))[3],0)
        self.assertEqual(result.getpixel((32,52))[3],0)

    def test_off_center_gap_clears_residue_but_preserves_a_covering_robe(self):
        base,outfit=fixture()
        base.paste((0,0,0,0),(0,24,24,32))
        base.paste((246,184,139,255),(2,24,5,30))
        base.paste((246,184,139,255),(8,24,11,30))
        outfit.paste(base.crop((0,24,24,32)),(0,24))
        outfit.paste((46,40,33,255),(5,25,8,28))
        result=run(base,outfit)
        self.assertEqual(result.getpixel((6,26))[3],0)
        for point in [(3,26),(9,26)]:
            self.assertEqual(result.getpixel(point),base.getpixel(point))
        outfit.paste((50,109,57,255),(2,23,12,31))
        result=run(base,outfit)
        self.assertEqual(result.getpixel((6,26)),(50,109,57,255))

    def test_shaded_face_edge_matches_base_even_over_bright_skin(self):
        root=Path(__file__).parent/'fixtures'/'green_outfit'
        base=Image.open(root/'base.png').convert('RGBA').crop((128,64,192,128))
        outfit=Image.open(root/'outfit.png').convert('RGBA').crop((128,64,192,128))
        result=run(base,outfit)
        self.assertEqual(result.getpixel((25,31)),base.getpixel((25,31)))


if __name__ == '__main__':
    unittest.main()
