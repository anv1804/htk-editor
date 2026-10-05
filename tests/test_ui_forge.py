import io
import json
import re
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ui_forge as forge


class UIForgeTests(unittest.TestCase):
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


if __name__=='__main__': unittest.main()
