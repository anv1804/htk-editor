import io
import hashlib
import json
import re
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ui_forge as forge


class UIForgeTests(unittest.TestCase):
    def test_restored_bamboo_frames_and_controls(self):
        original=forge.build(forge.settings({}))
        self.assertEqual(original['frame-panel']['recipe']['mode'],'bamboo')
        self.assertEqual(original['frame-button']['recipe']['family'],'button')
        self.assertEqual(original['frame-skill']['recipe']['mode'],'circle')
        self.assertEqual(set(original['frame-panel']['recipe']['pieces']),{'horizontal','vertical','leaves'})
        self.assertEqual(original['piece-bamboo-leaves']['image'].size,(32,32))
        for control,value in [('border',8),('detail',0),('shadow',0),('corner','fret'),
                              ('crest',False),('texture',False),('frameStyle','jade')]:
            changed=forge.build(forge.settings({control:value}))
            with self.subTest(control=control):
                self.assertTrue(any(hashlib.sha256(original[key]['image'].tobytes()).digest()!=hashlib.sha256(changed[key]['image'].tobytes()).digest()
                                    for key in ('frame-panel','frame-button','frame-skill','frame-item')))

    def test_rail_corners_are_separate_and_repeat_without_scaling(self):
        from ui_segments import compose, placements
        for style in ('wood','jade'):
            assets=forge.build(forge.settings({'frameStyle':style}))
            recipe=assets['frame-button']['recipe']
            pieces=placements(recipe,173,53)
            self.assertEqual(set(recipe['pieces']),{'rail-h','rail-v','corner'})
            self.assertEqual(len([p for p in pieces if p[0].endswith('-corner')]),4)
            for key,x,y,w,h,*_ in pieces:
                self.assertLessEqual(w,assets[key]['image'].width)
                self.assertLessEqual(h,assets[key]['image'].height)
            image=compose(assets,recipe,173,53)
            self.assertEqual(image.getpixel((86,26))[3],0)
            self.assertGreater(image.getpixel((86,2))[3],0)

    def test_regeneration_keeps_selection_ids_and_native_ring_export(self):
        payload={'settings':{'frameStyle':'wood'},'layout':[{'id':'selected-skill','asset':'frame-skill','width':72,'height':72}]}
        generated=forge.generate(payload)
        self.assertEqual(generated['layout'][0]['id'],'selected-skill')
        with zipfile.ZipFile(io.BytesIO(forge.export_zip(payload))) as archive:
            from PIL import Image
            im=Image.open(io.BytesIO(archive.read('ui_forge/frame-skill-native-72x72-texture.png')))
            self.assertEqual(im.size,(72,72))
            self.assertEqual(im.getpixel((36,36))[3],0)
            for path in re.findall(r'path="res://([^\"]+)"',archive.read('ui_forge/HUD.tscn').decode()):
                self.assertIn(path,archive.namelist())
            self.assertIn('ui_forge/frame-pieces-strip.png', archive.namelist())
            self.assertIn('ui_forge/frame-pieces-slices.txt', archive.namelist())
            strip_im = Image.open(io.BytesIO(archive.read('ui_forge/frame-pieces-strip.png')))
            self.assertGreater(strip_im.width, 0)
            self.assertGreater(strip_im.height, 0)

    def test_rejects_unbounded_or_malformed_settings(self):
        for config in [{'width':10000}, {'height':float('nan')}, {'detail':True},
                       {'shadow':-1}, {'surface':'url(x)'}, {'crest':'false'},
                       {'corner':'unknown'}, {'width':125.5}]:
            with self.subTest(config=config), self.assertRaises(ValueError):
                forge.settings({'settings':config})

    def test_assets_have_valid_margins_and_uncropped_alpha_at_extremes(self):
        for border in (3,8):
            s=forge.settings({'border':border,'shadow':5,'width':96,'height':80})
            assets=forge.build(s)
            for key,value in assets.items():
                with self.subTest(border=border,asset=key):
                    image=value['image']; alpha=image.getchannel('A')
                    bounds=alpha.getbbox()
                    # Repeating pieces intentionally reach tile boundaries;
                    # frame centers intentionally contain no pixels.
                    if value.get('recipe') or value['kind'] in ('piece','legacy'):
                        continue
                    self.assertIsNotNone(bounds)
                    self.assertGreater(bounds[0],0);self.assertGreater(bounds[1],0)
                    self.assertLess(bounds[2],image.width);self.assertLess(bounds[3],image.height)
                    if value['margins']:
                        l,t,r,b=value['margins']
                        self.assertLess(l+r,image.width);self.assertLess(t+b,image.height)

    def test_states_differ_and_geometry_is_deterministic(self):
        a=forge.build(forge.settings({}));b=forge.build(forge.settings({}))
        for key in a: self.assertEqual(a[key]['image'].tobytes(),b[key]['image'].tobytes())
        self.assertEqual(len({a[f'button-{state}']['image'].tobytes() for state in ('normal','hover','pressed','disabled')}),4)

    def test_export_roundtrip_and_all_godot_texture_references_resolve(self):
        payload={'settings':{'gem':'#225577'},'layout':[
            {'asset':'button-normal','x':101,'y':74,'label':'Tu luyện "A"'},
            {'asset':'bar-track','x':-99,'y':800,'fill':'bar-health-fill','value':0}]}
        with zipfile.ZipFile(io.BytesIO(forge.export_zip(payload))) as z:
            manifest=json.loads(z.read('ui_forge/preset.json'))
            self.assertEqual(manifest['layout'][0]['x'],101)
            self.assertEqual(manifest['layout'][0]['label'],'Tu luyện "A"')
            self.assertEqual(manifest['layout'][1]['y'],336)
            self.assertEqual(manifest['layout'][1]['value'],0)
            for name in ('ui_forge/HUD.tscn','ui_forge/theme.tres'):
                for resource_id in re.findall(r'id="([^\"]+)"',z.read(name).decode()):
                    self.assertRegex(resource_id,r'^[a-zA-Z0-9_]+$')
                for path in re.findall(r'path="res://([^\"]+)"',z.read(name).decode()):
                    self.assertIn(path,z.namelist())
            restored=forge.generate(manifest)
            self.assertEqual(restored['settings']['gem'],'#225577')
            self.assertEqual(len(restored['layout']),2)

    def test_invalid_layout_never_silently_exports(self):
        for nodes in [[{'asset':'missing'}],[{'asset':'panel','x':float('inf')}],
                      [{'asset':'panel','fill':'bar-health-fill'}],
                      [{'asset':'bar-track','fill':'bar-mana-fill','value':101}],
                      [{'asset':'panel','label':'x'*65}], [{'asset':'panel'}]*101]:
            with self.subTest(nodes=nodes[:1]),self.assertRaises(ValueError):
                forge.export_zip({'layout':nodes})

    def test_modular_item_frame_and_bg_toggle(self):
        # 1. Check recipe has mode 'item' and 4 distinct pieces
        assets_bg = forge.build(forge.settings({'showBg': True}))
        item_recipe = assets_bg['frame-item']['recipe']
        self.assertEqual(item_recipe['mode'], 'item')
        self.assertEqual(set(item_recipe['pieces'].keys()), {'corner', 'rail-h', 'rail-v', 'bg'})
        for key in ('piece-item-corner', 'piece-item-rail-h', 'piece-item-rail-v', 'piece-item-bg'):
            self.assertIn(key, assets_bg)
            self.assertEqual(assets_bg[key]['kind'], 'piece')

        # 2. When showBg is True: center pixel of 40x40 frame is opaque cavity (alpha == 255)
        im_bg = assets_bg['frame-item']['image']
        self.assertEqual(im_bg.getpixel((20, 20))[3], 255)

        # 3. When showBg is False: center pixel is completely transparent (alpha == 0)
        assets_nobg = forge.build(forge.settings({'showBg': False}))
        im_nobg = assets_nobg['frame-item']['image']
        self.assertEqual(im_nobg.getpixel((20, 20))[3], 0)
        # Rails and corners are still rendered (non-zero alpha at outer rail)
        self.assertGreater(im_nobg.getpixel((20, 2))[3], 0)
        self.assertGreater(im_nobg.getpixel((2, 20))[3], 0)

    def test_enable_shadow_toggle(self):
        s_on = forge.settings({'enableShadow': True, 'shadow': 3})
        s_off = forge.settings({'enableShadow': False, 'shadow': 3})
        self.assertTrue(s_on['enableShadow'])
        self.assertFalse(s_off['enableShadow'])
        
        assets_on = forge.build(s_on)
        assets_off = forge.build(s_off)
        
        self.assertTrue(assets_on['frame-panel']['recipe']['enableShadow'])
        self.assertFalse(assets_off['frame-panel']['recipe']['enableShadow'])
        
        # Images with shadow ON should differ from shadow OFF
        for key in ('frame-panel', 'frame-skill', 'frame-item', 'joystick-base', 'joystick-thumb'):
            hash_on = hashlib.sha256(assets_on[key]['image'].tobytes()).digest()
            hash_off = hashlib.sha256(assets_off[key]['image'].tobytes()).digest()
            self.assertNotEqual(hash_on, hash_off, f'{key} should differ when shadow is toggled')

    def test_themed_joysticks_across_all_styles(self):
        for style in ('bamboo', 'wood', 'jade'):
            assets = forge.build(forge.settings({'frameStyle': style}))
            base = assets['joystick-base']['image']
            thumb = assets['joystick-thumb']['image']
            self.assertEqual(base.size, (116, 116))
            self.assertEqual(thumb.size, (46, 46))
            # Center of thumb has gem highlight (non-zero alpha)
            self.assertGreater(thumb.getpixel((22, 22))[3], 200)
            # Center of base dish has non-zero alpha
            self.assertGreater(base.getpixel((58, 58))[3], 200)

    def test_wood_and_jade_corners_clean_and_contained(self):
        from ui_segments import rail_parts
        for style in ('wood', 'jade', 'bamboo'):
            s = forge.settings({'frameStyle': style, 'border': 5, 'detail': 2})
            p = forge.Painter(s)
            parts = rail_parts(p, style)
            corner_im = parts['corner']
            self.assertEqual(corner_im.size, (16, 16))
            # The corner must have solid geometry at corner plate (4, 4)
            self.assertGreater(corner_im.getpixel((4, 4))[3], 0)

    def test_modular_contours_stay_one_pixel_when_settings_increase(self):
        from ui_segments import bar_parts, item_parts, btn_parts
        for style in ('bamboo','wood','jade'):
            for border in (3,5,8):
                for detail in (0,3):
                    p=forge.Painter(forge.settings({'frameStyle':style,'border':border,'detail':detail,'shadow':5}))
                    for parts in (bar_parts(p,style),item_parts(p),btn_parts(p,style)):
                        im=parts['rail-h']
                        pixels=[im.getpixel((16,y)) for y in range(im.height) if im.getpixel((16,y))[3]]
                        self.assertEqual(pixels[0][:3],p.outline)
                        self.assertEqual(pixels[-1][:3],p.outline)
                        self.assertEqual(sum(c[:3]==p.outline for c in pixels),2)

    def test_bar_settings_change_artwork_without_expanding_outline(self):
        from ui_segments import bar_parts
        base={'showBg':False,'frameStyle':'bamboo'}
        versions=[]
        for control,value in [('border',8),('detail',3),('shadow',5),('corner','cloud')]:
            p=forge.Painter(forge.settings({**base,control:value}))
            versions.append(bar_parts(p,p.style))
        original=bar_parts(forge.Painter(forge.settings(base)),'bamboo')
        for parts in versions:
            self.assertNotEqual(b''.join(v.tobytes() for v in parts.values()),b''.join(v.tobytes() for v in original.values()))
        shadow=versions[2]
        self.assertEqual(shadow['rail-h'].getchannel('A').tobytes(),original['rail-h'].getchannel('A').tobytes())
        self.assertEqual(shadow['corner'].getchannel('A').tobytes(),original['corner'].getchannel('A').tobytes())

    def test_unified_palette_and_outline_setting(self):
        # 1. Custom outline and rail propagate
        s = forge.settings({'rail': '#335522', 'outline': '#112211', 'frameStyle': 'bamboo'})
        self.assertEqual(s['rail'], '#335522')
        self.assertEqual(s['outline'], '#112211')
        assets = forge.build(s)
        # Check skill ring palette contains the custom colors
        palette = assets['frame-skill']['recipe']['palette']
        self.assertEqual(palette[0], [0x33, 0x55, 0x22]) # rail
        self.assertEqual(palette[2], [0x11, 0x22, 0x11]) # outline / ink
        # Check item frame palette matches
        item_palette = assets['frame-item']['recipe']['palette']
        self.assertEqual(item_palette[0], [0x33, 0x55, 0x22])
        self.assertEqual(item_palette[2], [0x11, 0x22, 0x11])


    def test_text_panel_modular_and_godot_export(self):
        for style in ('bamboo', 'wood', 'jade'):
            assets = forge.build(forge.settings({'frameStyle': style, 'showBg': True}))
            self.assertIn('text-panel', assets)
            recipe = assets['text-panel']['recipe']
            self.assertEqual(recipe['mode'], 'rails')
            self.assertEqual(recipe['family'], 'text-panel')
            self.assertEqual(set(recipe['pieces'].keys()), {'rail-h', 'rail-v', 'corner', 'bg'})
            im = assets['text-panel']['image']
            self.assertEqual(im.size, (240, 80))
            # Center cavity is opaque when showBg is True
            self.assertEqual(im.getpixel((120, 40))[3], 255)

        # showBg toggle check
        assets_nobg = forge.build(forge.settings({'showBg': False}))
        im_nobg = assets_nobg['text-panel']['image']
        self.assertEqual(im_nobg.getpixel((120, 40))[3], 0)

        # Godot export with long multi-line label
        long_text = 'Tu tiên giả: Đạo tâm như thiết, vạn kiếp bất diệt.\nBạch Y Tiên Tử truyền thụ kiếm quyết sơ phong tại đây.'
        payload = {
            'settings': {'frameStyle': 'jade'},
            'layout': [{'asset': 'text-panel', 'x': 50, 'y': 100, 'width': 300, 'height': 120, 'label': long_text}]
        }
        zip_bytes = forge.export_zip(payload)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            hud_scene = z.read('ui_forge/HUD.tscn').decode('utf-8')
            self.assertIn('autowrap_mode = 2', hud_scene)
            self.assertIn('horizontal_alignment = 0', hud_scene)
            self.assertIn('vertical_alignment = 0', hud_scene)
            self.assertIn('Tu tiên giả', hud_scene)

    def test_bar_track_modular_pieces_and_button_export(self):
        for style in ('bamboo', 'wood', 'jade'):
            assets = forge.build(forge.settings({'frameStyle': style, 'showBg': False}))
            self.assertIn('bar-track', assets)
            bt = assets['bar-track']
            self.assertEqual(bt['kind'], 'button')
            recipe = bt['recipe']
            self.assertEqual(recipe['mode'], 'bar')
            self.assertEqual(set(recipe['pieces'].keys()), {'rail-h', 'rail-v', 'corner', 'bg'})
            for k in ('piece-bar-rail-h', 'piece-bar-rail-v', 'piece-bar-corner', 'piece-bar-bg'):
                self.assertIn(k, assets)
                self.assertEqual(assets[k]['kind'], 'piece')
            # Center cavity is transparent when showBg is False
            im_nobg = bt['image']
            self.assertEqual(im_nobg.size, (164, 24))
            self.assertEqual(im_nobg.getpixel((80, 11))[3], 0)

            # Test vertical scaling (e.g. height=40, height=80)
            from ui_segments import compose
            im_tall = compose(assets, recipe, 112, 40)
            self.assertEqual(im_tall.size, (112, 40))
            # Outer rail exists at bottom
            self.assertGreater(im_tall.getpixel((56, 39))[3], 0)
            # Center is transparent when showBg is False
            self.assertEqual(im_tall.getpixel((56, 20))[3], 0)

            # Test vertical bar
            im_vert = compose(assets, recipe, 32, 80)
            self.assertEqual(im_vert.size, (32, 80))
            self.assertGreater(im_vert.getpixel((0, 40))[3], 0)
            self.assertGreater(im_vert.getpixel((31, 40))[3], 0)

        # Center cavity is opaque when showBg is True
        assets_bg = forge.build(forge.settings({'frameStyle': 'bamboo', 'showBg': True}))
        im_bg = assets_bg['bar-track']['image']
        self.assertGreater(im_bg.getpixel((80, 11))[3], 200)

        # Godot export as a button with label and fill
        payload = {
            'settings': {'frameStyle': 'bamboo'},
            'layout': [{'asset': 'bar-track', 'x': 20, 'y': 30, 'width': 164, 'height': 24, 'label': 'Nạp Khí', 'fill': 'bar-health-fill', 'value': 80}]
        }
        zip_bytes = forge.export_zip(payload)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            hud_scene = z.read('ui_forge/HUD.tscn').decode('utf-8')
            self.assertIn('ExtResource("frame_button_script")', hud_scene)
            self.assertIn('Nạp Khí', hud_scene)
            self.assertIn('ExtResource("bar_health_fill")', hud_scene)


if __name__=='__main__': unittest.main()


