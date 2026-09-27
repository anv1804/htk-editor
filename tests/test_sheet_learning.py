import unittest
from pathlib import Path
import numpy as np
from PIL import Image
from repair_outfit_ui import process_request,encode_png,decode_image
from repair_outfit_sprite import refine_sheet_headwear,material_outline_color,components,fit_source_palette
from test_layer_composition import fixture

ROOT=Path(__file__).parent/'fixtures/hair_outfit'


class SheetLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=Image.open(ROOT/'base.png').convert('RGBA')
        cls.source=Image.open(ROOT/'outfit.png').convert('RGBA')
        cls.result=process_request(dict(base=encode_png(cls.base),outfit=encode_png(cls.source),
            rows=7,cols=4,colors=-1,paint=4,cleanup=0,composition='cutout'))
        cls.layers={key:decode_image(cls.result[key]) for key in ['image','baseLayer','outfitLayer','headwearLayer']}

    def test_tress_behind_raised_sleeve_and_scarf_belongs_to_hair(self):
        for f,points in [(4,[(20,38),(21,42),(22,43)]),(12,[(20,39),(20,40),(19,42)])]:
            for px,py in points:
                p=(f%4*64+px,f//4*64+py)
                with self.subTest(frame=f+1,pixel=p):
                    self.assertEqual(self.layers['headwearLayer'].getpixel(p)[3],255)
                    self.assertEqual(self.layers['outfitLayer'].getpixel(p)[3],0)

    def test_auto_palette_and_layers_preserve_base_and_recompose(self):
        self.assertLessEqual(self.result['paletteColors'],self.result['report']['learning']['automaticPaletteBudget'])
        composite=Image.alpha_composite(Image.alpha_composite(self.layers['baseLayer'],self.layers['outfitLayer']),self.layers['headwearLayer'])
        np.testing.assert_array_equal(np.asarray(composite),np.asarray(self.layers['image']))
        original=np.asarray(self.base);b=np.asarray(self.layers['baseLayer'])
        np.testing.assert_array_equal(b[original[:,:,3]>0],original[original[:,:,3]>0])

    def test_separating_scarf_does_not_leave_outline_dust_in_hair(self):
        for f in (4,12):
            x,y=f%4*64,f//4*64
            tile=np.asarray(self.layers['headwearLayer'].crop((x,y,x+64,y+64)))
            self.assertTrue(all(len(points)>3 for points in components(tile[:,:,3]>0)),f+1)

    def test_body_ribbon_including_dark_and_neutral_rim_stays_in_outfit(self):
        # The dark join at the crown and grey outer rim used to remain in
        # Hair after only the blue center of the scarf was reassigned.
        for f,points in [(12,[(19,23),(23,22),(24,23),(24,35)]),
                         (17,[(18,32),(19,32),(20,32),(21,32),(21,35)])]:
            for px,py in points:
                p=(f%4*64+px,f//4*64+py)
                with self.subTest(frame=f+1,pixel=(px,py)):
                    self.assertEqual(self.layers['headwearLayer'].getpixel(p)[3],0)
                    self.assertEqual(self.layers['outfitLayer'].getpixel(p)[3],255)

    def test_closed_hair_silhouette_does_not_fill_face_or_collect_lower_hand(self):
        for f,points in [(8,[(32,27),(35,28),(33,30)]),(13,[(19,46),(21,46),(23,45)])]:
            for px,py in points:
                p=(f%4*64+px,f//4*64+py)
                self.assertEqual(self.layers['headwearLayer'].getpixel(p)[3],0,(f+1,px,py))

    def test_exported_layers_have_no_unconfirmed_detached_dust(self):
        for name in ('headwearLayer','outfitLayer'):
            for f in range(28):
                x,y=f%4*64,f//4*64
                tile=np.asarray(self.layers[name].crop((x,y,x+64,y+64)))
                self.assertTrue(all(len(p)>3 for p in components(tile[:,:,3]>0)),(name,f+1))

    def test_occluded_neutral_black_hair_is_not_limited_to_brown_palette(self):
        source=np.array(self.source);rgb=source[:,:,:3].astype(int)
        r,g,b=rgb.transpose(2,0,1)
        brown=(r>=g+5)&(g>=b-12)&(r>=b+5)&(r<145)
        gray=np.rint(rgb.mean(axis=2)*.65).astype(np.uint8)
        source[brown,:3]=np.repeat(gray[brown,None],3,axis=1)
        mask,_=refine_sheet_headwear(self.base,Image.fromarray(source),rows=7,cols=4,threshold=36,cleanup=0)
        self.assertTrue(mask[64+42,21])
        self.assertTrue(mask[192+40,20])

    def test_iterations_are_bounded_and_do_not_train_on_predictions(self):
        info=self.result['report']['learning']
        self.assertGreater(info['recoveredHairPixels'],0)
        self.assertLessEqual(info['iterations'],info['maxIterations'])
        self.assertEqual(info['confirmedSamples'],0)
        self.assertIn('predictions-not-retrained',info['training'])
        kwargs=dict(rows=7,cols=4,threshold=36,cleanup=0)
        first,report=refine_sheet_headwear(self.base,self.source,**kwargs)
        second,again=refine_sheet_headwear(self.base,self.source,**kwargs)
        np.testing.assert_array_equal(first,second)
        self.assertEqual(report,again)

    def test_outline_uses_dark_recurrent_ink_not_light_fabric_shadows(self):
        rgba=np.zeros((10,10,4),np.uint8);rgba[:,:,:3]=[68,78,76]
        rgba[:2,:,:3]=[24,29,34]
        ink=material_outline_color(rgba,np.ones((10,10),bool),np.array([39,25,32]))
        np.testing.assert_array_equal(ink,[24,29,34])


class ConfirmedMemoryTests(unittest.TestCase):
    def request(self,**extra):
        base,outfit=fixture();outfit.paste((51,42,37,255),(7,0,17,5))
        return process_request(dict(base=encode_png(base),outfit=encode_png(outfit),rows=1,cols=1,colors=0,outline=False,**extra))

    def test_current_correction_overrides_remembered_label_and_paint_is_exact(self):
        memory=Image.new('RGBA',(24,32));memory.putpixel((10,1),(255,200,0,255))
        active=Image.new('RGBA',(24,32));active.putpixel((10,1),(0,0,255,255))
        color=Image.new('RGBA',(24,32));color.putpixel((10,1),(80,66,52,255))
        result=self.request(learnedOverrides=encode_png(memory),overrides=encode_png(active),retouch=encode_png(color))
        self.assertEqual(decode_image(result['headwearLayer']).getpixel((10,1))[3],0)
        self.assertEqual(decode_image(result['outfitLayer']).getpixel((10,1)),(80,66,52,255))
        self.assertEqual(result['report']['learning']['rememberedMaskPixels'],1)
        self.assertEqual(result['report']['learning']['rememberedPaintPixels'],0)

    def test_new_erase_clears_old_remembered_paint(self):
        memory=Image.new('RGBA',(24,32));memory.putpixel((10,1),(80,66,52,255))
        active=Image.new('RGBA',(24,32));active.putpixel((10,1),(0,255,0,255))
        result=self.request(overrides=encode_png(active),learnedRetouch=encode_png(memory))
        self.assertEqual(decode_image(result['image']).getpixel((10,1))[3],0)

    def test_incompatible_saved_grid_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'dimensions'):
            self.request(learnedOverrides=encode_png(Image.new('RGBA',(12,12))))


class MaterialPaletteTests(unittest.TestCase):
    def test_small_blue_ribbon_and_green_band_keep_their_hues_at_low_budget(self):
        rgb=np.zeros((32,32,3),np.uint8)
        yy,xx=np.indices((32,32))
        shade=((xx+yy)%11)*5
        rgb[:]=np.stack([50+shade,40+shade,34+shade],axis=2)
        rgb[4:7,4:20]=[97,137,108]
        rgb[12,4:8]=[89,134,151]
        fill=np.ones((32,32),bool)
        for budget in (4,8,16):
            result=fit_source_palette(rgb,fill,budget,(32,32),redraw=True)
            ribbon=result[12,4:8].astype(int);band=result[4:7,4:20].astype(int)
            self.assertTrue(np.all(ribbon[:,2]>ribbon[:,1]+8),budget)
            self.assertTrue(np.all(band[:,:,1]>band[:,:,2]+15),budget)
            self.assertLessEqual(len(np.unique(result.reshape(-1,3),axis=0)),budget)

    def test_palette_cannot_borrow_pixels_from_another_layer_or_frame(self):
        rgb=np.full((8,16,3),[160,180,205],np.uint8)
        rgb[:,8:]=[150,180,150]
        fill=np.zeros((8,16),bool);fill[:,:8]=True
        before=rgb.copy()
        result=fit_source_palette(rgb,fill,4,(8,8),redraw=True)
        np.testing.assert_array_equal(result[~fill],before[~fill])
        np.testing.assert_array_equal(result[fill],before[fill])
