import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from test_layer_composition import fixture
from repair_outfit_sprite import repair_sheet, repaint, garment_edge_mask


class CutoutWorkflowTests(unittest.TestCase):
    def test_warm_clothing_shadows_do_not_expose_base_torso_or_arm(self):
        for shadow, highlight in [((220,201,170,255),(220,212,184,255)),
                                  ((188,165,135,255),(188,178,151,255)),
                                  ((237,213,181,255),(237,227,196,255))]:
            with self.subTest(shadow=shadow):
                base, outfit = fixture()
                outfit.paste(highlight, (5,11,19,24))
                outfit.paste(shadow, (6,15,8,19))
                outfit.paste(shadow, (10,16,15,21))
                result, _ = repair_sheet(base, outfit, rows=1, cols=1, colors=0,
                    background_threshold=36, skin_expand=0, outline=False,
                    composition='cutout', cleanup=0, accessories=True)
                self.assertEqual(result.getpixel((6,17)),shadow)
                self.assertEqual(result.getpixel((12,18)),shadow)
                self.assertEqual(result.getpixel((12,5)),base.getpixel((12,5)))

    def test_actual_raised_sleeve_collar_pixels_survive_skin_cut(self):
        root = Path(__file__).parent/'fixtures/outfit_occlusion'
        base = Image.open(root/'base.png').convert('RGBA').crop((192,0,256,64))
        outfit = Image.open(root/'outfit.png').convert('RGBA').crop((192,0,256,64))
        result, _ = repair_sheet(base,outfit,rows=1,cols=1,colors=0,
            background_threshold=36,skin_expand=0,outline=False,
            composition='cutout',cleanup=0,accessories=True)
        for point in [(37,35),(37,36)]:
            self.assertEqual(result.getpixel(point),outfit.getpixel(point))

    def test_connected_cream_collar_is_retained_without_protecting_central_face(self):
        # A collar continuation beside the chin must win over warm skin color.
        from repair_outfit_sprite import collar_material_mask
        head = np.zeros((32, 32), bool)
        head[4:17, 10:22] = True
        rgb = np.zeros((32, 32, 3), np.uint8)
        fg = np.zeros((32, 32), bool)
        cloth = np.zeros_like(fg)
        rgb[15:21, 10:13] = [244, 232, 206]
        fg[15:21, 10:13] = True
        cloth[19:21, 10:13] = True
        rgb[15:17, 15:18] = [244, 232, 206]
        fg[15:17, 15:18] = True
        protected = collar_material_mask(rgb, fg, head, cloth)
        self.assertTrue(protected[16:21, 10:13].all())
        self.assertFalse(protected[15:17, 15:18].any())

    def test_bright_outer_hem_has_a_border_but_thin_ribbon_keeps_color(self):
        rgb = np.full((16, 16, 3), 235, np.uint8)
        fabric = np.zeros((16, 16), bool)
        fabric[5:13, 4:12] = True
        fabric[3, 2:10] = True
        edges = garment_edge_mask(rgb, fabric, fabric, np.zeros_like(fabric))
        self.assertTrue(edges[12, 5:11].all())
        self.assertFalse(edges[11, 5:11].any())
        self.assertFalse(edges[3].any())

    def test_missing_grey_sole_edge_is_rebuilt_without_growing_shape(self):
        rgba = np.zeros((12, 12, 4), np.uint8)
        fabric = np.zeros((12, 12), bool)
        fabric[3:10, 2:10] = True
        rgba[fabric] = [190, 210, 205, 255]
        rgba[9, 2:10, :3] = [140, 155, 150]
        result, contour = repaint(rgba, np.zeros_like(fabric), fabric,
                                  colors=0, paint=0, outline=True,
                                  cell_size=(12, 12), conservative=True)
        self.assertTrue(contour[9, 4:8].all())
        np.testing.assert_array_equal(result[:, :, 3], rgba[:, :, 3])
        np.testing.assert_array_equal(result[8, 4:8], rgba[8, 4:8])

    def test_only_continuous_source_seams_become_ink(self):
        rgb = np.full((16, 16, 3), 190, np.uint8)
        fabric = np.ones((16, 16), bool)
        rgb[5:10, 8] = 65
        rgb[5, 3] = 65
        mask = garment_edge_mask(rgb, fabric, fabric, np.zeros_like(fabric))
        self.assertTrue(mask[5:10, 8].all())
        self.assertFalse(mask[5, 3])

    def test_cutout_keeps_warm_hat_when_accessories_are_enabled(self):
        root = Path(__file__).parent / 'fixtures'
        base = Image.open(root / 'green_outfit/base.png').convert('RGBA').crop((0, 0, 64, 64))
        outfit = Image.open(root / 'tan_outfit.png').convert('RGBA').crop((0, 0, 64, 64))
        result, _ = repair_sheet(base, outfit, rows=1, cols=1, colors=0,
                                composition='cutout', outline=False, cleanup=0,
                                background_threshold=36, skin_expand=0, accessories=True)
        self.assertEqual(result.getpixel((32, 23)), outfit.getpixel((32, 23)))

    def test_short_fabric_panel_between_feet_is_not_inferred_as_background(self):
        base, outfit = fixture()
        color = (65, 95, 160, 255)
        outfit.paste(color, (11, 23, 13, 27))
        result, _ = repair_sheet(base, outfit, rows=1, cols=1, colors=0,
                                composition='cutout', outline=False, cleanup=0,
                                background_threshold=36, skin_expand=0)
        self.assertEqual(result.getpixel((11, 25)), color)

    def test_outline_does_not_blacken_a_light_collar_touching_base(self):
        rgba = np.zeros((9, 9, 4), np.uint8)
        anatomy = np.zeros((9, 9), bool)
        anatomy[1:4, 2:7] = True
        fabric = np.zeros_like(anatomy)
        fabric[4:8, 1:8] = True
        rgba[anatomy] = [246, 184, 139, 255]
        rgba[fabric] = [200, 215, 195, 255]
        result, _ = repaint(rgba, anatomy, fabric, colors=0, paint=0,
                            outline=True, cell_size=(9, 9), conservative=True)
        np.testing.assert_array_equal(result[4, 2:7], rgba[4, 2:7])
        np.testing.assert_array_equal(result[anatomy], rgba[anatomy])

    def test_manual_keep_reveal_erase_remain_authoritative(self):
        base, outfit = fixture()
        mask = Image.new('RGBA', base.size)
        mask.putpixel((10, 15), (255, 80, 80, 255))
        mask.putpixel((10, 5), (70, 155, 255, 255))
        mask.putpixel((12, 15), (0, 255, 0, 255))
        result, _ = repair_sheet(base, outfit, rows=1, cols=1, colors=0,
                                composition='cutout', outline=False, overrides=mask,
                                background_threshold=36, skin_expand=0)
        self.assertEqual(result.getpixel((10, 15)), base.getpixel((10, 15)))
        self.assertEqual(result.getpixel((10, 5)), outfit.getpixel((10, 5)))
        self.assertEqual(result.getpixel((12, 15))[3], 0)
