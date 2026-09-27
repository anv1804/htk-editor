import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from gemini_logo import alpha_template, match_score, restore_corner_logo
from repair_outfit_ui import process_request, encode_png, decode_image


def marked_sheet(size=48, margin=32, template='bg_48.png', width=256, height=448):
    original = np.full((height, width, 4), (255, 255, 255, 255), np.uint8)
    x, y = width - margin - size, height - margin - size
    # Fabric, seams, and a skin-colored hand continue under the logo. It must
    # restore the source colors, not paint an empty square or sample one color.
    original[y-3:y+size+3, x-3:x+size+3, :3] = [42, 89, 74]
    original[y+size//2:y+size//2+3, x-3:x+size+3, :3] = [18, 25, 32]
    original[y+size//4:y+size//2, x+size//2:x+size, :3] = [245, 185, 139]
    alpha = alpha_template(template, size)
    marked = original.copy()
    patch = marked[y:y+size, x:x+size, :3]
    patch[:] = np.rint(patch * (1-alpha[:, :, None]) + 255*alpha[:, :, None])
    return Image.fromarray(original), Image.fromarray(marked), (x, y, size)


class GeminiLogoTests(unittest.TestCase):
    def test_actual_gemini_overlay_matches_without_treating_cloth_as_the_logo(self):
        path = Path(__file__).parent/'fixtures/gemini_logo/real-overlay-patch.png'
        with Image.open(path) as image:
            patch = np.array(image.convert('RGBA'))
        alpha = alpha_template('bg_96_20260520.png',96)
        self.assertGreater(match_score(patch,alpha),.5)
        fixed = patch.copy()
        fixed[:,:,:3] = np.rint(np.clip((patch[:,:,:3]-255*alpha[:,:,None])/(1-alpha[:,:,None]),0,255))
        self.assertLess(match_score(fixed,alpha),.12)

    def test_overlay_is_unblended_without_changing_silhouette_or_pixels_elsewhere(self):
        for size, margin, template in [(48,32,'bg_48.png'), (16,11,'bg_48.png'),
                                       (19,37,'bg_96_20260520.png'), (36,96,'bg_36_v2.bin')]:
            with self.subTest(size=size, template=template):
                original, source, (x,y,n) = marked_sheet(size,margin,template,
                    width=512 if size==36 else 256, height=768 if size==36 else 448)
                fixed, report = restore_corner_logo(source)
                self.assertEqual(report['status'], 'restored')
                np.testing.assert_array_equal(np.asarray(fixed)[:,:,3], np.asarray(source)[:,:,3])
                outside = np.ones((source.height,source.width),bool); outside[y:y+n,x:x+n] = False
                np.testing.assert_array_equal(np.asarray(fixed)[outside], np.asarray(source)[outside])
                self.assertLessEqual(np.abs(np.asarray(fixed).astype(int)-np.asarray(original)).max(), 2)
                self.assertGreater(report['correctedPixels'], 0)
                self.assertEqual(restore_corner_logo(fixed)[1]['correctedPixels'], 0)

    def test_no_logo_leaves_existing_outfits_byte_identical(self):
        root = Path(__file__).parent/'fixtures'
        for path in [root/'tan_outfit.png', *root.glob('*/outfit.png')]:
            if path.parent.name == 'hair_outfit':
                continue  # Positive, downsampled watermark fixture.
            with self.subTest(path=path):
                with Image.open(path) as image:
                    image = image.convert('RGBA')
                fixed, report = restore_corner_logo(image)
                np.testing.assert_array_equal(np.asarray(fixed),np.asarray(image))
                self.assertEqual(report['correctedPixels'],0)

    def test_ordinary_corner_details_and_transparency_are_not_a_logo(self):
        original, _, _ = marked_sheet()
        for image in [original, Image.new('RGBA',(256,448)), Image.new('RGBA',(256,448),'white')]:
            fixed, report = restore_corner_logo(image)
            np.testing.assert_array_equal(np.asarray(fixed),np.asarray(image))
            self.assertEqual(report['correctedPixels'],0)

    def test_off_mode_and_manual_masks_are_authoritative(self):
        _, source, (x,y,n) = marked_sheet()
        fixed, report = restore_corner_logo(source,mode='off')
        self.assertIs(fixed,source)
        self.assertEqual(report['status'],'disabled')
        protected = np.zeros((448,256),bool)
        protected[y:y+n,x:x+n//2] = True
        fixed, report = restore_corner_logo(source,protected=protected)
        np.testing.assert_array_equal(np.asarray(fixed)[protected],np.asarray(source)[protected])
        self.assertGreater(report['correctedPixels'],0)
        self.assertEqual(source.getpixel((x+24,y+24))[3],255)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            restore_corner_logo(Image.new('RGBA',(64,64)),mode='erase-everything')

    def test_api_exports_use_restored_source_and_report_settings(self):
        original, source, (x,y,n) = marked_sheet()
        payload = dict(base=encode_png(Image.new('RGBA',original.size)),outfit=encode_png(source),
                       rows=7,cols=4,colors=0,paint=0,outline=False,cleanup=0,composition='cutout')
        response = process_request(payload)
        report = response['report']['logoCleanup']
        self.assertEqual(report['status'],'restored')
        self.assertEqual(response['report']['settings']['logoCleanup'],'auto')
        layer = np.asarray(decode_image(response['outfitLayer']))
        # Sample a colored sleeve away from a skin patch or segmented edges.
        np.testing.assert_allclose(layer[y+n//2+5,x+n//2,:3],np.asarray(original)[y+n//2+5,x+n//2,:3],atol=2)
        off = process_request({**payload,'logoCleanup':'off'})
        self.assertEqual(off['report']['logoCleanup']['status'],'disabled')
        self.assertNotEqual(response['outfitLayer'],off['outfitLayer'])
        self.assertEqual(decode_image(response['image']).size,source.size)


if __name__ == '__main__':
    unittest.main()
