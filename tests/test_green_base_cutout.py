import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from test_layer_composition import fixture
from repair_outfit_sprite import base_head_mask, clean_outfit, foreground_mask, green_marker_cutout, green_marker_palette, repair_sheet, skin_mask


class GreenBaseCutoutTests(unittest.TestCase):
    def test_bundled_bases_share_exact_frame_geometry(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base = np.array(Image.open(root / 'default-base.png').convert('RGBA'))
        guide = np.array(Image.open(root / 'default-green-base.png').convert('RGBA'))
        head = Image.open(root / 'default-head-base.png').convert('RGBA')
        body = Image.open(root / 'default-body-base.png').convert('RGBA')
        self.assertEqual(base.shape, (448, 256, 4))
        np.testing.assert_array_equal(base[:, :, 3], guide[:, :, 3])
        self.assertEqual(head.size, (256, 448))
        self.assertEqual(body.size, (256, 448))
        self.assertGreater(len(green_marker_palette(Image.fromarray(guide))), 1)

    def test_separate_head_body_remove_old_face_pixels_without_cutting_a_raised_sleeve(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base_sheet = Image.open(root / 'default-base.png').convert('RGBA')
        guide_sheet = Image.open(root / 'default-green-base.png').convert('RGBA')
        head_sheet = Image.open(root / 'default-head-base.png').convert('RGBA')
        body_sheet = Image.open(root / 'default-body-base.png').convert('RGBA')
        outfit_sheet = Image.open(Path(__file__).parent / 'fixtures/green_collar/outfit-poses.png').convert('RGBA')
        front_result = None
        for col, frame in enumerate((2, 4, 12, 24)):
            x, y = frame % 4 * 64, frame // 4 * 64
            box = (x, y, x + 64, y + 64)
            head = head_sheet.crop(box)
            body = body_sheet.crop(box)
            source = outfit_sheet.crop((col * 64, 0, (col + 1) * 64, 64))
            result, _, mask = repair_sheet(base_sheet.crop(box), source,
                green_base=guide_sheet.crop(box), head_base=head, body_base=body,
                rows=1, cols=1, colors=0, background_threshold=36,
                skin_expand=0, outline=False, cleanup=3, paint=0,
                composition='cutout', accessories=True, return_masks=True)
            head_pixels = np.asarray(head)
            result_pixels = np.asarray(result)
            owned = (head_pixels[:, :, 3] > 0) & np.all(
                np.asarray(mask)[:, :, :3] == [255, 80, 80], axis=2)
            with self.subTest(frame=frame + 1):
                self.assertGreater(int(owned.sum()), 200)
                np.testing.assert_array_equal(result_pixels[owned], head_pixels[owned])
            if frame == 2:
                front_result = result
            if frame == 4:
                self.assertEqual(mask.getpixel((30, 35)), (70, 155, 255, 255))
        # F3's old base face had three pixels outside both supplied layers.
        for point in ((22, 28), (26, 33), (38, 34)):
            self.assertEqual(front_result.getpixel(point)[3], 0)

    def test_normal_skin_source_does_not_replace_its_head_from_optional_layer(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        box = (0, 0, 64, 64)
        base = Image.open(root / 'default-base.png').convert('RGBA').crop(box)
        guide = Image.open(root / 'default-green-base.png').convert('RGBA').crop(box)
        head = Image.open(root / 'default-head-base.png').convert('RGBA').crop(box)
        body = Image.open(root / 'default-body-base.png').convert('RGBA').crop(box)
        source = base.copy()
        source.paste((30, 56, 88, 255), (18, 37, 47, 55))
        options = dict(green_base=guide, rows=1, cols=1, colors=0,
            background_threshold=36, skin_expand=0, outline=False,
            cleanup=0, paint=0, composition='cutout')
        old, _ = repair_sheet(base, source, **options)
        with_refs, _ = repair_sheet(base, source, head_base=head, body_base=body, **options)
        np.testing.assert_array_equal(np.asarray(with_refs), np.asarray(old))

    def make_sheets(self):
        base, _ = fixture()
        standard = np.array(base)
        standard[5, 11] = [42, 60, 73, 255]
        green = standard.copy()
        visible = green[:, :, 3] > 0
        green[visible] = [117, 174, 35, 255]
        green[5, 11] = [42, 60, 73, 255]
        source = green.copy()
        source[10:24, 7:17] = [48, 105, 175, 255]
        source[5, 11] = [42, 60, 73, 255]
        return Image.fromarray(standard), Image.fromarray(green), Image.fromarray(source)

    def test_green_face_hands_and_feet_reveal_standard_base(self):
        base, guide, source = self.make_sheets()
        result, reports, mask = repair_sheet(base, source, green_base=guide,
            rows=1, cols=1, colors=0, background_threshold=36,
            skin_expand=0, outline=False, cleanup=0, paint=0,
            composition='cutout', return_masks=True)
        for point in [(10, 4), (11, 5), (6, 17), (17, 17), (8, 27), (15, 27)]:
            with self.subTest(point=point):
                self.assertEqual(result.getpixel(point), base.getpixel(point))
        self.assertEqual(result.getpixel((12, 17)), source.getpixel((12, 17)))
        self.assertEqual(mask.getpixel((10, 4)), (255, 80, 80, 255))
        self.assertGreater(reports[0]['green_marker_pixels'], 20)

    def test_green_key_preserves_gray_collar_panels_over_the_skin_guide(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base = Image.open(root / 'default-base.png').convert('RGBA').crop((0, 0, 64, 64))
        guide = Image.open(root / 'default-green-base.png').convert('RGBA').crop((0, 0, 64, 64))
        source = Image.open(Path(__file__).parent / 'fixtures/green_collar/outfit-front.png').convert('RGBA')
        result, _, mask = repair_sheet(base, source, green_base=guide,
            rows=1, cols=1, colors=0, background_threshold=36,
            skin_expand=0, outline=False, cleanup=0, paint=0,
            composition='cutout', accessories=True, return_masks=True)
        # Source jacket/lapel pixels overlap the bare-body guide. Their cool,
        # low-chroma fabric must remain Outfit while the green face is replaced.
        collar = [(27, 36), (28, 36), (35, 37), (29, 38), (33, 38), (34, 38)]
        for point in collar:
            with self.subTest(point=point):
                self.assertEqual(result.getpixel(point), source.getpixel(point))
                self.assertEqual(mask.getpixel(point), (70, 155, 255, 255))
        self.assertEqual(result.getpixel((32, 25)), base.getpixel((32, 25)))

    def test_large_green_fabric_panel_is_not_cut(self):
        base, guide, source = self.make_sheets()
        pixels = np.array(source)
        pixels[12:22, 9:15] = [117, 174, 35, 255]
        source = Image.fromarray(pixels)
        result, _ = repair_sheet(base, source, green_base=guide,
            rows=1, cols=1, colors=0, background_threshold=36,
            skin_expand=0, outline=False, cleanup=0, paint=0,
            composition='cutout')
        self.assertEqual(result.getpixel((12, 17)), source.getpixel((12, 17)))
        self.assertEqual(result.getpixel((10, 4)), base.getpixel((10, 4)))

    def test_green_guide_does_not_key_a_scarf_below_a_normal_skin_face(self):
        base, guide, source = self.make_sheets()
        source.paste(base.crop((8, 2, 16, 9)), (8, 2))
        scarf = (117, 174, 35, 255)
        source.paste(scarf, (7, 9, 17, 14))
        result, _, mask = repair_sheet(base, source, green_base=guide,
            rows=1, cols=1, colors=0, background_threshold=36,
            skin_expand=0, outline=False, cleanup=0, paint=0,
            composition='cutout', return_masks=True)
        self.assertEqual(result.getpixel((12, 9)), scarf)
        self.assertEqual(mask.getpixel((12, 9)), (70, 155, 255, 255))

    def test_green_face_aperture_stops_at_dark_collar_and_lapel_edges(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base = np.array(Image.open(root / 'default-base.png').convert('RGBA').crop((0, 0, 64, 64)))
        guide = Image.open(root / 'default-green-base.png').convert('RGBA').crop((0, 0, 64, 64))
        source = np.array(Image.open(Path(__file__).parent / 'fixtures/green_collar/outfit-front.png').convert('RGBA'))
        cut = green_marker_cutout(base, np.array(guide), source[:, :, :3],
            foreground_mask(source, 36), foreground_mask(base, 36),
            green_marker_palette(guide), 36)
        for x, y in [(24, 34), (25, 34), (38, 34), (39, 34), (26, 35),
                     (37, 35), (37, 36), (27, 36), (28, 36), (29, 38)]:
            with self.subTest(point=(x, y)):
                self.assertFalse(cut[y, x])
        self.assertTrue(cut[25, 32])
        self.assertTrue(cut[37, 31])

    def test_raised_collar_keeps_its_material_while_enclosed_eyes_are_cut(self):
        for color in [(18, 27, 39, 255), (25, 27, 29, 255),
                      (234, 225, 199, 255), (184, 205, 200, 255)]:
            with self.subTest(color=color):
                base, guide, source = self.make_sheets()
                source.paste(color, (7, 9, 17, 14))
                result, _, mask = repair_sheet(base, source, green_base=guide,
                    rows=1, cols=1, colors=0, background_threshold=36,
                    skin_expand=0, outline=False, cleanup=0, paint=0,
                    composition='cutout', return_masks=True)
                for point in [(9, 9), (12, 9), (14, 9), (12, 10)]:
                    self.assertEqual(result.getpixel(point), color)
                    self.assertEqual(mask.getpixel(point), (70, 155, 255, 255))
                self.assertEqual(result.getpixel((11, 5)), base.getpixel((11, 5)))

    def test_source_collar_and_sleeve_seams_survive_across_poses(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base = Image.open(root / 'default-base.png').convert('RGBA')
        guide = Image.open(root / 'default-green-base.png').convert('RGBA')
        poses = Image.open(Path(__file__).parent / 'fixtures/green_collar/outfit-poses.png').convert('RGBA')
        checks = [
            (2, [(26, 34), (25, 35), (38, 36)]),
            (4, [(21, 30), (22, 30), (23, 30), (28, 30), (29, 30),
                 (38, 33), (39, 33), (30, 34), (31, 34), (32, 34),
                 (30, 35), (37, 35), (36, 36)]),
            (12, [(26, 35), (28, 35), (26, 36), (38, 40), (39, 41)]),
            (24, [(28, 35), (29, 35), (27, 36), (30, 36), (31, 37), (38, 39)]),
        ]
        for col, (frame, points) in enumerate(checks):
            x, y = frame % 4 * 64, frame // 4 * 64
            box = (x, y, x+64, y+64)
            source = poses.crop((col*64, 0, (col+1)*64, 64))
            rgb, _, _ = clean_outfit(np.array(source), 36, 3)
            result, _, mask = repair_sheet(base.crop(box), source,
                green_base=guide.crop(box), rows=1, cols=1, colors=0,
                background_threshold=36, skin_expand=0, outline=False,
                cleanup=3, paint=0, composition='cutout', accessories=True,
                return_masks=True)
            for px, py in points:
                with self.subTest(frame=frame+1, point=(px, py)):
                    self.assertEqual(mask.getpixel((px, py)), (70, 155, 255, 255))
                    np.testing.assert_array_equal(result.getpixel((px, py))[:3], rgb[py, px])

    def test_uncovered_green_head_and_neck_still_reveal_standard_skin(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base = Image.open(root / 'default-base.png').convert('RGBA')
        guide = Image.open(root / 'default-green-base.png').convert('RGBA')
        for frame in [0, 2, 4, 12, 24]:
            x, y = frame % 4 * 64, frame // 4 * 64
            box = (x, y, x+64, y+64)
            b = np.array(base.crop(box))
            head = base_head_mask(b, foreground_mask(b, 36))
            hy, hx = np.nonzero(head)
            yy, xx = np.indices(head.shape)
            neck = (yy > hy.max()) & (yy <= hy.max()+4)
            neck &= abs(xx-(hx.min()+hx.max())/2) <= (np.ptp(hx)+1)*.25
            neck &= skin_mask(b, foreground_mask(b, 36))
            result, _ = repair_sheet(base.crop(box), guide.crop(box),
                green_base=guide.crop(box), rows=1, cols=1, colors=0,
                background_threshold=36, skin_expand=0, outline=False,
                cleanup=0, paint=0, composition='cutout')
            with self.subTest(frame=frame+1):
                np.testing.assert_array_equal(np.array(result)[head | neck], b[head | neck])

    def test_connected_green_skin_patch_is_cut_without_clipping_blue_sleeve(self):
        base, guide, source = self.make_sheets()
        pixels = np.array(source)
        pixels[14:21, 5:9] = [117, 174, 35, 255]
        source = Image.fromarray(pixels)
        result, _ = repair_sheet(base, source, green_base=guide,
            rows=1, cols=1, colors=0, background_threshold=36,
            skin_expand=0, outline=False, cleanup=0, paint=0,
            composition='cutout')
        for point in [(6, 17), (8, 17)]:
            with self.subTest(point=point):
                self.assertEqual(result.getpixel(point), base.getpixel(point))
        self.assertEqual(result.getpixel((12, 17)), source.getpixel((12, 17)))

    def test_manual_keep_overrides_green_key(self):
        base, guide, source = self.make_sheets()
        override = Image.new('RGBA', base.size)
        override.putpixel((10, 4), (0, 0, 255, 255))
        result, _ = repair_sheet(base, source, green_base=guide,
            rows=1, cols=1, colors=0, background_threshold=36,
            skin_expand=0, outline=False, cleanup=0, paint=0,
            composition='cutout', overrides=override)
        self.assertEqual(result.getpixel((10, 4)), source.getpixel((10, 4)))

    def test_rejects_wrong_size_or_non_green_guide(self):
        base, guide, source = self.make_sheets()
        options = dict(rows=1, cols=1, colors=0, background_threshold=36,
                       skin_expand=0, composition='cutout')
        with self.assertRaisesRegex(ValueError, 'Green base must match'):
            repair_sheet(base, source, green_base=guide.crop((0, 0, 8, 8)), **options)
        with self.assertRaisesRegex(ValueError, 'green skin palette'):
            repair_sheet(base, source, green_base=Image.new('RGBA', base.size), **options)

    def test_green_marker_uses_landmark_when_skin_highlight_is_too_pale(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base_sheet = Image.open(root / 'default-base.png').convert('RGBA')
        guide_sheet = Image.open(root / 'default-green-base.png').convert('RGBA')
        box = (0, 4 * 64, 64, 5 * 64)
        base, guide = base_sheet.crop(box), guide_sheet.crop(box)
        source = np.array(guide)
        result = green_marker_cutout(np.array(base), np.array(guide), source[:, :, :3],
            foreground_mask(source, 36), foreground_mask(np.array(base), 36),
            green_marker_palette(guide_sheet), 36)
        self.assertTrue(result[36, 11])

    def test_small_green_hand_folded_over_torso_is_removed(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base_sheet = Image.open(root / 'default-base.png').convert('RGBA')
        guide_sheet = Image.open(root / 'default-green-base.png').convert('RGBA')
        box = (2 * 64, 0, 3 * 64, 64)
        base, guide = np.array(base_sheet.crop(box)), np.array(guide_sheet.crop(box))
        source = np.zeros_like(guide)
        source[43:47, 21:27] = guide[43:47, 21:27]
        result = green_marker_cutout(base, guide, source[:, :, :3],
            foreground_mask(source, 36), foreground_mask(base, 36),
            green_marker_palette(guide_sheet), 36)
        self.assertTrue(result[44, 24])

    def test_compact_hand_marker_keeps_its_dark_green_shadows_in_the_cut(self):
        root = Path(__file__).resolve().parents[1] / 'assets'
        base_sheet = Image.open(root / 'default-base.png').convert('RGBA')
        guide_sheet = Image.open(root / 'default-green-base.png').convert('RGBA')
        box = (64, 2 * 64, 128, 3 * 64)
        base = np.array(base_sheet.crop(box))
        guide = np.array(guide_sheet.crop(box))
        source = np.zeros_like(guide)
        source[42:47, 29:36] = guide[42:47, 29:36]
        base_fg = foreground_mask(base, 36)
        base_skin = skin_mask(base, base_fg)
        source[42:47, 29:36][~base_skin[42:47, 29:36]] = 0
        source[44, 34] = [87, 122, 54, 255]
        source[44, 29] = [102, 124, 78, 255]
        source[45, 28] = [14, 16, 13, 255]
        cut = green_marker_cutout(base, guide, source[:, :, :3],
            source[:, :, 3] >= 128, base_fg,
            green_marker_palette(guide_sheet), 36)
        self.assertFalse(base_skin[44, 34])
        self.assertTrue(cut[44, 34])
        self.assertTrue(cut[44, 29])
        self.assertTrue(cut[45, 28])


if __name__ == '__main__':
    unittest.main()
