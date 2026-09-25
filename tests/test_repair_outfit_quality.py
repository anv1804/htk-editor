"""Behavior checks for layer priority, crisp output and artist corrections."""
import sys
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from repair_outfit_sprite import repair_sheet, clean_outfit, luminance, build_base_profile, load_base_profile, repaint
from repair_outfit_ui import process_request, encode_png, decode_image, analyze_base


def fixture():
    base = np.zeros((28, 28, 4), np.uint8)
    base[3:11, 10:18] = [39, 25, 32, 255]
    base[4:10, 11:17] = [255, 202, 158, 255]
    base[7, 13] = [255, 245, 220, 255]
    base[7, 14] = [39, 25, 32, 255]
    base[12:24, 11:17] = [176, 93, 61, 255]
    base[14:20, 4:8] = [39, 25, 32, 255]
    base[15:19, 5:7] = [255, 202, 158, 255]
    outfit = np.zeros_like(base)
    outfit[3:11, 10:19] = [50, 40, 35, 255]
    outfit[4:10, 11:18] = [230, 180, 145, 255]
    for y in range(11, 24):
        for x in range(7, 21):
            outfit[y, x] = [60+x*4, 100+y*3, 140+x*2, 255]
    outfit[14:20, 4:8] = [50, 40, 35, 255]
    outfit[15:19, 5:7] = [230, 180, 145, 255]
    outfit[24, 25] = [100, 150, 180, 255]  # isolated debris
    outfit[23:25, 1:3] = [60, 110, 140, 255]  # real detached 4px detail
    return Image.fromarray(base), Image.fromarray(outfit)


def run(base, outfit, **kwargs):
    options = dict(rows=1, cols=1, colors=16, background_threshold=36,
                   skin_expand=0, return_masks=True)
    options.update(kwargs)
    return repair_sheet(base, outfit, **options)


class QualityTests(unittest.TestCase):
    def test_palette_locks_base_and_does_not_put_bare_torso_over_cloth(self):
        base, outfit = fixture()
        result, frames, mask = run(base, outfit)
        pixels, labels = np.asarray(result), np.asarray(mask)
        restored = (labels[:, :, 0] == 255) & (labels[:, :, 3] > 0)
        self.assertTrue(np.array_equal(pixels[restored], np.asarray(base)[restored]))
        self.assertEqual(result.getpixel((14, 7)), base.getpixel((14, 7)))
        self.assertEqual(result.getpixel((5, 17)), base.getpixel((5, 17)))
        self.assertNotEqual(result.getpixel((14, 20)), base.getpixel((14, 20)))
        self.assertEqual(result.getpixel((18, 5))[3], 0, 'old head outline must disappear')
        self.assertLessEqual(len(np.unique(pixels[pixels[:, :, 3] > 0, :3], axis=0)), 16)
        self.assertEqual(set(np.unique(pixels[:, :, 3])), {0, 255})
        self.assertGreater(frames[0]['outlined_outfit_pixels'], 0)

    def test_noise_cleanup_preserves_detached_accessory(self):
        base, outfit = fixture()
        result, _, _ = run(base, outfit)
        self.assertEqual(result.getpixel((25, 24))[3], 0)
        self.assertEqual(result.getpixel((1, 23))[3], 255)

    def test_manual_corrections_override_automatic_layers_and_cleanup(self):
        base, outfit = fixture()
        correction = Image.new('RGBA', base.size)
        correction.putpixel((14, 20), (255, 0, 0, 255))
        correction.putpixel((14, 7), (0, 255, 0, 255))
        correction.putpixel((13, 7), (0, 0, 255, 255))
        correction.putpixel((25, 24), (0, 0, 255, 255))
        result, _, _ = run(base, outfit, overrides=correction, colors=0, outline=False)
        self.assertEqual(result.getpixel((14, 20)), base.getpixel((14, 20)))
        self.assertEqual(result.getpixel((14, 7)), (0, 0, 0, 0))
        self.assertEqual(result.getpixel((13, 7)), outfit.getpixel((13, 7)))
        self.assertEqual(result.getpixel((25, 24)), outfit.getpixel((25, 24)))

    def test_replacement_does_not_leave_an_isolated_skin_fragment(self):
        base, outfit = fixture()
        base.putpixel((24, 15), (255, 202, 158, 255))
        for y in (14, 15):
            for x in (23, 24):
                outfit.putpixel((x, y), (230, 180, 145, 255))
        result, _, _ = run(base, outfit)
        self.assertEqual(result.getpixel((24, 15))[3], 0)

    def test_white_matte_is_removed_without_shrinking_solid_shape(self):
        image = np.full((12, 12, 4), 255, np.uint8)
        image[3:9, 3:9, :3] = 220  # weak antialiased halo
        image[4:8, 4:8, :3] = [30, 60, 90]
        _, foreground, _ = clean_outfit(image, 36, 3)
        self.assertEqual(int(foreground.sum()), 16)
        self.assertTrue(np.all(foreground[4:8, 4:8]))

    def test_invalid_budget_reports_error_instead_of_recoloring_face(self):
        base, outfit = fixture()
        with self.assertRaisesRegex(ValueError, 'preserve base anatomy'):
            run(base, outfit, colors=2)

    def test_outline_cannot_cross_frame_boundary(self):
        base = Image.new('RGBA', (16, 8))
        outfit = Image.new('RGBA', base.size)
        for y in range(2, 6):
            for x in range(5, 8):
                outfit.putpixel((x, y), (80, 150, 190, 255))
        result, _, _ = run(base, outfit, cols=2)
        self.assertEqual(result.getpixel((7, 3)), (39, 25, 32, 255))
        self.assertEqual(result.getpixel((8, 3)), (0, 0, 0, 0))

    def test_light_pixels_are_not_classified_as_dark_due_to_overflow(self):
        self.assertGreater(float(luminance(np.array([[255, 230, 200]], np.uint8))[0]), 200)

    def test_api_returns_mask_and_actual_palette_report(self):
        base, outfit = fixture()
        response = process_request(dict(base=encode_png(base), outfit=encode_png(outfit),
                                        rows=1, cols=1, colors=16))
        self.assertLessEqual(response['paletteColors'], 16)
        self.assertEqual(response['report']['version'], 6)
        self.assertTrue(response['report']['baseColorsLocked'])
        self.assertEqual(decode_image(response['mask']).size, base.size)
        self.assertGreater(response['outlinedPixels'], 0)

    def test_invalid_override_size_fails_clearly(self):
        base, outfit = fixture()
        with self.assertRaisesRegex(ValueError, 'Correction mask'):
            run(base, outfit, overrides=Image.new('RGBA', (1, 1)))

    def test_wide_sleeve_covers_the_forearm_up_to_its_cuff(self):
        base, outfit = fixture()
        skin, cloth = (255, 202, 158, 255), (135, 185, 190, 255)
        for y in range(14, 18):
            for x in range(2, 12):
                base.putpixel((x, y), skin)
        for y in range(13, 22):
            for x in range(4, 12):
                outfit.putpixel((x, y), cloth)
        for y in range(14, 18):
            for x in range(2, 4):
                outfit.putpixel((x, y), (230, 180, 145, 255))
        result, _, _ = run(base, outfit, colors=0, outline=False)
        self.assertEqual(result.getpixel((2, 16)), skin)
        for y in range(13, 22):
            for x in range(4, 12):
                self.assertEqual(result.getpixel((x, y)), cloth, (x, y))

    def test_sleeve_in_front_of_face_is_not_replaced_by_base_skin(self):
        base, outfit = fixture()
        cloth = (135, 185, 190, 255)
        for y in range(8, 16):
            for x in range(9, 14):
                outfit.putpixel((x, y), cloth)
        result, _, _ = run(base, outfit, colors=0, outline=False)
        for y in range(8, 16):
            for x in range(9, 14):
                self.assertEqual(result.getpixel((x, y)), cloth)
        self.assertEqual(result.getpixel((14, 7)), base.getpixel((14, 7)))

    def test_neck_aperture_stays_connected_and_uses_only_base_skin_colors(self):
        base, outfit = fixture()
        for y in range(10, 14):
            for x in range(12, 16):
                outfit.putpixel((x, y), (230, 180, 145, 255))
        result, report, _ = run(base, outfit, colors=16)
        base_colors = {tuple(pixel) for pixel in np.asarray(base).reshape(-1, 4)}
        for y in range(10, 14):
            self.assertEqual(result.getpixel((14, y))[3], 255)
            self.assertIn(result.getpixel((14, y)), base_colors)
        self.assertGreater(report[0]['reconstructed_skin_pixels'], 0)

    def test_thin_colored_ribbon_is_not_painted_entirely_black(self):
        base = Image.new('RGBA', (20, 20))
        outfit = Image.new('RGBA', base.size)
        cloth = (145, 195, 200, 255)
        for x in range(2, 16):
            outfit.putpixel((x, 14), cloth)
        result, _, _ = run(base, outfit, colors=0)
        self.assertEqual(result.getpixel((8, 14)), cloth)
        self.assertEqual(np.count_nonzero(np.asarray(result)[:, :, 3]), 14)

    def test_reconstructed_neck_has_hard_alpha_even_with_soft_base_edges(self):
        base, outfit = fixture()
        pixels = np.array(base)
        pixels[pixels[:,:,3] > 0,3] = 180
        for y in range(10, 14):
            for x in range(12, 16):
                outfit.putpixel((x, y), (230, 180, 145, 255))
        result, report, _ = run(Image.fromarray(pixels), outfit)
        self.assertGreater(report[0]['reconstructed_skin_pixels'], 0)
        self.assertEqual(set(np.unique(np.asarray(result)[:,:,3])), {0,255})


class ReportedPoseRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parent / 'fixtures' / 'outfit_occlusion'
        cls.base = Image.open(root / 'base.png').convert('RGBA')
        cls.outfit = Image.open(root / 'outfit.png').convert('RGBA')
        cls.result, cls.report, cls.mask = run(cls.base, cls.outfit, cols=4, colors=0, outline=False)

    def test_reported_wide_sleeves_and_hem_keep_the_source_pixels(self):
        # (crop column, x, y): manually selected cloth locations covered by
        # bare base arms/feet in the reported output, not head/eye pixels.
        samples = [(1,25,41), (1,25,42), (1,29,58),
                   (2,44,33), (2,43,34), (2,40,35), (2,40,36),
                   (3,18,33), (3,16,34), (3,42,34), (3,44,35), (3,23,37)]
        for col, x, y in samples:
            with self.subTest(col=col, x=x, y=y):
                point = (col*64+x, y)
                self.assertEqual(self.result.getpixel(point), self.outfit.getpixel(point))

    def test_reported_neck_gaps_are_opaque(self):
        for col, x, y in [(0,31,36), (0,32,36), (1,33,35), (3,30,36)]:
            with self.subTest(col=col, x=x, y=y):
                self.assertEqual(self.result.getpixel((col*64+x, y))[3], 255)

    def test_restored_skin_and_reconstructed_skin_stay_in_base_palette(self):
        result, _, mask = run(self.base, self.outfit, cols=4, colors=16)
        pixels, labels = np.asarray(result), np.asarray(mask)
        direct = np.all(labels[:,:,:3] == [255,80,80], axis=2)
        rebuilt = np.all(labels[:,:,:3] == [240,190,60], axis=2)
        self.assertTrue(np.array_equal(pixels[direct], np.asarray(self.base)[direct]))
        colors = {tuple(pixel) for pixel in np.asarray(self.base).reshape(-1,4)}
        self.assertTrue(all(tuple(pixel) in colors for pixel in pixels[rebuilt]))
        self.assertLessEqual(len(np.unique(pixels[pixels[:,:,3]>0,:3],axis=0)),16)


class PinnedBaseAndPaintTests(unittest.TestCase):
    def test_broad_fabric_shadow_is_not_stamped_into_a_solid_ink_block(self):
        rgba=np.zeros((16,16,4),np.uint8)
        rgba[2:14,2:14]=[125,175,140,255]
        rgba[6:9,6:9]=[46,70,48,255]
        garment=rgba[:,:,3]>0
        result,contours=repaint(rgba,np.zeros_like(garment),garment,
            colors=16,paint=3,outline=True,cell_size=(16,16))
        self.assertFalse(np.any(contours[6:9,6:9]))
        self.assertFalse(np.any(np.all(result[6:9,6:9,:3]==[39,25,32],axis=2)))

    def test_saved_profile_round_trip_and_mismatched_base_rejection(self):
        base,_ = fixture()
        result = analyze_base(dict(base=encode_png(base),rows=1,cols=1))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'base-anatomy.json'
            path.write_text(json.dumps(dict(version=1,baseId=result['baseId'],mask=result['profile'])),encoding='utf-8')
            profile = load_base_profile(path,base,1,1)
            self.assertEqual(profile.tobytes(),decode_image(result['profile']).tobytes())
            altered=base.copy(); altered.putpixel((0,0),(255,0,0,255))
            with self.assertRaisesRegex(ValueError,'different base'):
                load_base_profile(path,altered,1,1)

    def test_base_profile_is_stable_and_identified_by_pixels_and_grid(self):
        base, _ = fixture()
        payload = dict(base=encode_png(base), rows=1, cols=1)
        first = analyze_base(payload)
        second = analyze_base(payload)
        self.assertEqual(first,second)
        changed = base.copy(); changed.putpixel((1,1),(255,0,0,255))
        self.assertNotEqual(first['baseId'],analyze_base(dict(payload,base=encode_png(changed)))['baseId'])
        self.assertNotEqual(first['baseId'],analyze_base(dict(payload,cols=2))['baseId'])

    def test_edited_palm_stays_at_base_coordinates_for_different_outfits(self):
        base, outfit = fixture()
        profile = build_base_profile(base,rows=1,cols=1)
        # Explicitly approved palm; it must not follow a generated hand offset.
        for y in range(15,19):
            for x in range(5,7):
                profile.putpixel((x,y),(255,128,0,255))
        for shift in (0,3):
            alternate = outfit.copy()
            for y in range(14,21):
                for x in range(3,11):
                    alternate.putpixel((x,y),(120,175,185,255))
            for y in range(15,19):
                for x in range(5+shift,7+shift):
                    alternate.putpixel((x,y),(225,160,125,255))
            result,_,_ = run(base,alternate,base_profile=profile,paint=3)
            for y in range(15,19):
                for x in range(5,7):
                    self.assertEqual(result.getpixel((x,y)),base.getpixel((x,y)))

    def test_profile_edit_can_remove_an_incorrect_hand_selection(self):
        base,outfit = fixture()
        profile = Image.new('RGBA',base.size)
        profile.putpixel((5,17),(255,128,0,255))
        # Retain a head seed so the body is interpretable.
        profile.paste(build_base_profile(base,rows=1,cols=1))
        profile.putpixel((5,17),(255,128,0,255))
        outfit.putpixel((5,17),(120,175,185,255))
        selected,_,_ = run(base,outfit,base_profile=profile,colors=0,outline=False)
        profile.putpixel((5,17),(0,0,0,0))
        removed,_,_ = run(base,outfit,base_profile=profile,colors=0,outline=False)
        self.assertEqual(selected.getpixel((5,17)),base.getpixel((5,17)))
        self.assertEqual(removed.getpixel((5,17)),outfit.getpixel((5,17)))

    def test_manual_color_is_locked_through_repaint_and_export(self):
        base,outfit = fixture()
        manual = Image.new('RGBA',base.size)
        color = (78,95,162,255)
        manual.putpixel((13,19),color)
        result,_,mask = run(base,outfit,retouch=manual,paint=3)
        self.assertEqual(result.getpixel((13,19)),color)
        self.assertEqual(mask.getpixel((13,19)),(180,80,230,255))
        self.assertLessEqual(len(np.unique(np.asarray(result)[np.asarray(result)[:,:,3]>0,:3],axis=0)),16)

    def test_repaint_keeps_silhouette_and_builds_distinct_shadow_levels(self):
        base = Image.new('RGBA',(24,24))
        outfit = Image.new('RGBA',base.size)
        for y in range(3,21):
            for x in range(3,21):
                v = 125+y*4+(x%2)*3
                outfit.putpixel((x,y),(v-35,v,v+5,255))
        result,_,_ = run(base,outfit,paint=3,outline=False,colors=16)
        pixels = np.asarray(result)
        self.assertTrue(np.array_equal(pixels[:,:,3],np.asarray(outfit)[:,:,3]))
        colors = np.unique(pixels[pixels[:,:,3]>0,:3],axis=0)
        self.assertLessEqual(len(colors),6)
        self.assertGreater(float(np.ptp(luminance(colors))),40)

    def test_invalid_profile_and_paint_dimensions_are_rejected(self):
        base,outfit = fixture()
        with self.assertRaisesRegex(ValueError,'Base profile'):
            run(base,outfit,base_profile=Image.new('RGBA',(1,1)))
        with self.assertRaisesRegex(ValueError,'Retouch layer'):
            run(base,outfit,retouch=Image.new('RGBA',(1,1)))

    def test_repaint_preserves_internal_belt_and_fold_lines(self):
        base = Image.new('RGBA',(24,24))
        outfit = Image.new('RGBA',base.size)
        for y in range(3,21):
            for x in range(3,21):
                outfit.putpixel((x,y),(175,205,215,255))
        for x in range(4,20):
            outfit.putpixel((x,11),(38,57,65,255))
        for y in range(12,20):
            outfit.putpixel((12,y),(38,57,65,255))
        result,_,_ = run(base,outfit,paint=3)
        for point in [(7,11),(12,16)]:
            self.assertLess(float(luminance(np.array(result.getpixel(point)[:3]))),60)
        self.assertGreater(float(luminance(np.array(result.getpixel((7,10))[:3]))),160)
        self.assertTrue(np.array_equal(np.array(result)[:,:,3],np.array(outfit)[:,:,3]))

    def test_flat_fabric_does_not_acquire_artificial_shadow_patches(self):
        base = Image.new('RGBA',(24,24))
        outfit = Image.new('RGBA',base.size)
        for y in range(3,21):
            for x in range(3,21):
                value = (x+y)%3
                outfit.putpixel((x,y),(180+value,210+value,220+value,255))
        result,_,_ = run(base,outfit,paint=3,outline=False)
        pixels = np.array(result)
        self.assertLess(float(np.ptp(luminance(pixels[pixels[:,:,3]>0,:3]))),8)


if __name__ == '__main__':
    unittest.main()
