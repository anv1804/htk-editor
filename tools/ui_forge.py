"""Original parameter-driven pixel UI, rendered on an integer grid with Pillow."""
from __future__ import annotations

import base64
import io
import json
import math
import re
import zipfile

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from ui_motifs import unique_assets, PRIMARY_NAMES
from ui_segments import add_segments, refresh_frames, FRAME_SPECS, placements, inventory_cells, compose, green_palette, btn_corner, decorative_corner

STYLE_DEFAULTS = {
    'bamboo': dict(surface='#14221a', rail='#4c6f30', metal='#d7b96e', outline='#0a100e', gem='#46a082'),
    'wood': dict(surface='#1a1310', rail='#6e4027', metal='#e6b969', outline='#140c09', gem='#d74628'),
    'jade': dict(surface='#0f1a1a', rail='#2e7270', metal='#dae8ee', outline='#0a1414', gem='#50dcd2')
}

DEFAULTS = dict(surface='#14221a', rail='#4c6f30', metal='#d7b96e', outline='#0a100e', gem='#46a082',
                width=216, height=156, border=5, detail=2, shadow=3,
                corner='leaves', crest=True, texture=True, showBg=True, enableShadow=True, frameStyle='bamboo')


def settings(payload):
    if not isinstance(payload, dict):
        raise ValueError('Cấu hình phải là một object JSON.')
    source = payload.get('settings', payload)
    if not isinstance(source, dict):
        raise ValueError('Cấu hình không hợp lệ.')
    s = DEFAULTS.copy()
    if 'frameStyle' in source:
        if source['frameStyle'] not in ('bamboo', 'wood', 'jade'):
            raise ValueError('Chất liệu khung không hợp lệ.')
        s['frameStyle'] = source['frameStyle']
    style_def = STYLE_DEFAULTS.get(s['frameStyle'], STYLE_DEFAULTS['bamboo'])
    for key in ('surface', 'metal', 'gem', 'rail', 'outline'):
        value = source.get(key, style_def.get(key, s.get(key)))
        if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            raise ValueError(f'Màu {key} cần có dạng #RRGGBB.')
        s[key] = value
    for key, lo, hi in [('width',96,400),('height',80,280),('border',3,8),
                        ('detail',0,3),('shadow',0,5)]:
        value = source.get(key,s[key])
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value != int(value) or not lo <= value <= hi:
            raise ValueError(f'{key} cần là số nguyên trong khoảng {lo}–{hi}.')
        s[key] = int(value)
    for key in ('crest','texture','showBg','enableShadow'):
        value=source.get(key,s[key])
        if not isinstance(value,bool): raise ValueError(f'{key} cần là true/false.')
        s[key]=value
    if source.get('corner',s['corner']) not in ('cloud','fret','cut','leaves'):
        raise ValueError('Kiểu góc không hợp lệ.')
    s['corner']=source.get('corner',s['corner'])
    return s


def rgb(hex_color):
    return tuple(int(hex_color[i:i+2],16) for i in (1,3,5))


def mix(color, target, ratio):
    return tuple(round(a+(b-a)*ratio) for a,b in zip(color,target))


def box(d, xy, color, cut=2):
    x,y,r,b=xy
    d.polygon([(x+cut,y),(r-cut,y),(r,y+cut),(r,b-cut),
               (r-cut,b),(x+cut,b),(x,b-cut),(x,y+cut)],fill=color)


class Painter:
    def __init__(self, s):
        self.s = s
        self.style = s.get('frameStyle', 'bamboo')
        defaults = STYLE_DEFAULTS.get(self.style, STYLE_DEFAULTS['bamboo'])
        self.base = rgb(s.get('surface', defaults['surface']))
        self.surface = self.base
        self.rail = rgb(s.get('rail', defaults['rail']))
        self.metal = rgb(s.get('metal', defaults['metal']))
        self.outline = rgb(s.get('outline', defaults['outline']))
        self.gem = rgb(s.get('gem', defaults['gem']))

        self.ink = self.outline
        self.trim = self.metal
        self.body = self.rail
        self.light = mix(self.rail, (250, 246, 215), .58)
        self.dark = mix(self.rail, self.ink, .65)
        self.body_light = mix(self.rail, self.light, .5)
        self.body_dark = mix(self.rail, self.ink, .62)
        self.jewel_col = self.gem
        self.jewel_sec = mix(self.gem, (255, 255, 255), .55)
        self.jewel_sparkle = (255, 255, 255)

    def finish(self, im):
        alpha = im.getchannel('A')
        expanded = alpha.filter(ImageFilter.MaxFilter(3))
        result = Image.new('RGBA', im.size)
        if self.s['shadow'] and self.s.get('enableShadow', True):
            sh = Image.new('RGBA', im.size)
            sh.paste((*self.ink, min(70, 20 + self.s['shadow'] * 10)), (0, 0), alpha)
            result.alpha_composite(sh, (1, 1))
        result.paste(self.ink, (0, 0), ImageChops.subtract(expanded, alpha))
        result.alpha_composite(im)
        return result

    def jewel(self, d, x, y, r=5, gem_override=None):
        gem_c = gem_override or self.jewel_col
        d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=self.dark)
        d.line([(x - r, y), (x, y - r), (x + r, y)], fill=self.light)
        r2 = max(1, r - 2)
        d.polygon([(x, y - r2), (x + r2, y), (x, y + r2), (x - r2, y)], fill=gem_c)
        d.polygon([(x, y - r2), (x, y), (x - r2, y)], fill=mix(gem_c, (255, 255, 255), .42))
        d.polygon([(x, y), (x + r2, y), (x, y + r2)], fill=mix(gem_c, self.ink, .52))
        d.point((x, y - r2 + 1), fill=self.jewel_sparkle)

    def engraving(self, d, points):
        d.line([(x + 1, y + 1) for x, y in points], fill=self.dark, width=2)
        d.line(points, fill=self.trim, width=2)
        d.line([(x, y - 1) for x, y in points], fill=self.light, width=1)

    def corner(self):
        return decorative_corner(self)

    def crest(self):
        """Themed 80x44 header crest matching bamboo, wood, and jade with adjustable parameters."""
        im = Image.new('RGBA', (80, 44))
        d = ImageDraw.Draw(im)
        cx = 39
        detail = self.s.get('detail', 2)

        # Symmetrical wings (max x offset 31 so 39+31=70, safely within 80px)
        for sign in (-1, 1):
            if self.style == 'bamboo':
                culm = [(cx + sign * x, y) for x, y in [(5, 21), (11, 18), (17, 20), (22, 17), (27, 19), (31, 22)]]
                d.line([(x + 1, y + 1) for x, y in culm], fill=self.dark, width=2)
                d.line(culm, fill=self.trim, width=2)
                d.line([(x, y - 1) for x, y in culm], fill=self.light, width=1)
                # Bamboo leaves
                l1 = [(cx + sign * 11, 17), (cx + sign * 16, 13), (cx + sign * 21, 15), (cx + sign * 15, 18)]
                l2 = [(cx + sign * 22, 16), (cx + sign * 27, 12), (cx + sign * 31, 15), (cx + sign * 26, 18)]
                d.polygon(l1, fill=self.body_light)
                d.line(l1[:3], fill=self.light)
                d.polygon(l2, fill=self.body_light)
                d.line(l2[:3], fill=self.light)
                if detail >= 2:
                    l3 = [(cx + sign * x, y) for x, y in [(12, 25), (17, 23), (22, 26), (26, 24)]]
                    d.line(l3, fill=self.trim, width=1)
                if detail >= 3:
                    d.point((cx + sign * 21, 15), fill=(255, 255, 255))
                    d.point((cx + sign * 31, 15), fill=(255, 255, 255))
            elif self.style == 'wood':
                pts = [(cx + sign * x, y) for x, y in [(5, 22), (10, 17), (16, 19), (21, 15), (26, 18), (31, 22)]]
                d.line([(x + 1, y + 1) for x, y in pts], fill=self.dark, width=2)
                d.line(pts, fill=self.trim, width=2)
                d.line([(x, y - 1) for x, y in pts], fill=self.light, width=1)
                if detail >= 2:
                    pts2 = [(cx + sign * x, y) for x, y in [(11, 26), (16, 23), (21, 25), (25, 24)]]
                    d.line(pts2, fill=self.light, width=1)
                    d.line([(x, y + 1) for x, y in pts2], fill=self.dark, width=1)
                if detail >= 3:
                    d.point((cx + sign * 21, 15), fill=self.light)
                    d.point((cx + sign * 31, 22), fill=(255, 255, 255))
            else:  # jade
                pts = [(cx + sign * x, y) for x, y in [(5, 21), (11, 17), (16, 19), (21, 15), (26, 18), (31, 21)]]
                d.line([(x + 1, y + 1) for x, y in pts], fill=self.dark, width=2)
                d.line(pts, fill=self.trim, width=2)
                d.line([(x, y - 1) for x, y in pts], fill=self.light, width=1)
                # Inlaid jade feathers
                f1 = [(cx + sign * 11, 16), (cx + sign * 16, 11), (cx + sign * 21, 14), (cx + sign * 15, 18)]
                f2 = [(cx + sign * 22, 14), (cx + sign * 27, 10), (cx + sign * 31, 13), (cx + sign * 26, 17)]
                d.polygon(f1, fill=self.body)
                d.line(f1[:3], fill=self.light)
                d.polygon(f2, fill=self.body)
                d.line(f2[:3], fill=self.light)
                if detail >= 2:
                    pts2 = [(cx + sign * x, y) for x, y in [(11, 26), (16, 23), (21, 25), (26, 23)]]
                    d.line(pts2, fill=self.light, width=1)
                if detail >= 3:
                    d.point((cx + sign * 16, 11), fill=(255, 255, 255))
                    d.point((cx + sign * 27, 10), fill=(255, 255, 255))

        # Central Cartouche Medallion
        cart = [(cx, 3), (cx + 5, 11), (cx + 4, 16), (cx + 11, 21), (cx + 4, 28), (cx, 34),
                (cx - 4, 28), (cx - 11, 21), (cx - 4, 16), (cx - 5, 11)]
        d.polygon(cart, fill=self.body_dark)
        d.line(cart + [cart[0]], fill=self.dark, width=2)
        d.line([(cx, 4), (cx - 4, 11), (cx - 4, 16), (cx - 10, 21), (cx, 33), (cx + 10, 21), (cx + 4, 16), (cx + 4, 11), (cx, 4)], fill=self.light)

        # Central Jewels
        if detail >= 1:
            self.jewel(d, cx, 21, 8, self.jewel_col)
            self.jewel(d, cx, 10, 4, self.jewel_sec)

        return self.finish(im)

    def frame(self,w,h,state='normal',small=False):
        im=Image.new('RGBA',(w,h)); d=ImageDraw.Draw(im)
        off=1 if state=='pressed' else 0
        x,y,r,b=4,4+off,w-9,h-9+off
        layers=[self.ink,self.light,self.trim,self.dark,self.ink,self.trim,self.dark,self.ink]
        n=min(self.s['border'],(r-x-4)//2,(b-y-4)//2)
        for i in range(n):
            box(d,(x+i,y+i,r-i,b-i),layers[i],max(1,4-i//2))
        fill=mix(self.body,(255,255,230),.18) if state=='hover' else mix(self.body,self.ink,.35) if state=='pressed' else self.body
        box(d,(x+n,y+n,r-n,b-n),fill,2)
        d.line([(x+2,b-3),(x+2,y+2),(r-3,y+2)],fill=self.light)
        d.line([(x+3,b-1),(r-1,b-1),(r-1,y+3)],fill=self.ink)
        # Quantized surface sheen, entirely inside the frame.
        if self.s['texture']:
            for yy in range(y+n+3,b-n-2):
                col=mix(fill,(4,5,13),.12*(yy-y)/(b-y))
                d.line((x+n+3,yy,r-n-3,yy),fill=col)
            for xx,yy in [(x+n+2,y+n+2),(r-n-9,b-n-9)]:
                for dy in range(7):
                    for dx in range(7-dy):
                        if (dx+dy)%2==0: d.point((xx+dx,yy+dy),fill=mix(fill,self.trim,.10))
        if not small and self.s['detail']:
            cap=self.corner()
            im.alpha_composite(cap,(x,y))
            im.alpha_composite(cap.transpose(Image.Transpose.FLIP_LEFT_RIGHT),(r-25,y))
            im.alpha_composite(cap.transpose(Image.Transpose.FLIP_TOP_BOTTOM),(x,b-25))
            im.alpha_composite(cap.transpose(Image.Transpose.ROTATE_180),(r-25,b-25))
        else:
            for cx,cy in [(x+3,y+3),(r-3,y+3),(x+3,b-3),(r-3,b-3)]:
                d.point((cx,cy),fill=self.light)
                d.point((cx+1,cy+1),fill=self.trim)
        if small and self.s['detail']:
            self.jewel(d,x+5,(y+b)//2,3); self.jewel(d,r-5,(y+b)//2,3)
        result=self.finish(im)
        if state=='disabled':
            grey=result.convert('L').convert('RGBA'); grey.putalpha(result.getchannel('A'))
            result=Image.blend(result,grey,.82)
            dark=result.point(lambda v:int(v*.68)); dark.putalpha(result.getchannel('A')); result=dark
        return result


def build(s):
    p=Painter(s); assets={}
    def add(name,im,kind,margin=None,name_label=None):
        entry={'image':im,'kind':kind,'margins':margin}
        if name_label: entry['name']=name_label
        assets[name]=entry
    add('panel',p.frame(s['width'],s['height']),'panel',[32]*4)
    for state in ('normal','hover','pressed','disabled'):
        add(f'button-{state}',p.frame(112,36,state,True),'button',[19,14,19,14])
        add(f'slot-{state}',p.frame(44,44,state,True),'slot',[16]*4)
    add('tab-active',p.frame(86,32,'hover',True),'tab',[18,12,18,12])
    add('tab-idle',p.frame(86,32,'pressed',True),'tab',[18,12,18,12])
    add('scroll-track',p.frame(28,160,small=True),'scrollbar',[12,14,12,14])
    add('scroll-thumb',p.frame(28,38,small=True),'scrollbar',[12,14,12,14])
    for direction in ('up','down','close'):
        im=p.frame(32,32,small=True); d=ImageDraw.Draw(im)
        if direction=='close':
            d.line((11,10,18,17),fill=p.light,width=1);d.line((18,10,11,17),fill=p.light,width=1)
        else:
            yy=1 if direction=='down' else -1
            d.line([(10,14-yy*3),(14,14+yy*2),(18,14-yy*3)],fill=p.light,width=2)
        add(f'icon-{direction}',im,'icon')
    for name,color in [('health',(172,66,77)),('mana',(70,139,166)),('cultivation',p.gem)]:
        im=Image.new('RGBA',(164,24));d=ImageDraw.Draw(im)
        for y in range(9,13): d.line((17,y,136,y),fill=mix(color,p.light,.4) if y==9 else mix(color,p.ink,.3) if y==12 else color)
        add(f'bar-{name}-fill',im,'fill')
    style_label = dict(bamboo='Trúc', wood='Gỗ', jade='Ngọc').get(s['frameStyle'], 'Trúc')
    add('crest', p.crest() if s['crest'] else Image.new('RGBA', (80, 44)), 'ornament', name_label=f'Huy hiệu đỉnh · {style_label}')
    cap = p.corner()
    for name, transform, sym in [('tl', None, '↖'), ('tr', Image.Transpose.FLIP_LEFT_RIGHT, '↗'),
                                ('bl', Image.Transpose.FLIP_TOP_BOTTOM, '↙'), ('br', Image.Transpose.ROTATE_180, '↘')]:
        im = Image.new('RGBA', (36, 36))
        c_trans = cap if transform is None else cap.transpose(transform)
        im.alpha_composite(c_trans, (4, 4))
        add(f'corner-{name}', im, 'ornament', name_label=f'Góc chạm {sym} · {style_label}')
    for key,(image,kind) in unique_assets(p,s).items(): add(key,image,kind)
    for key in ('cloud-command','token-command','coin-command','jade-command','scroll-command','lotus-command','bamboo-panel'):
        assets[key]['kind']='ornament'
    add_segments(assets,p)
    return assets


def png(im):
    data=io.BytesIO();im.save(data,format='PNG');return data.getvalue()


def generate(payload):
    s=settings(payload); assets=build(s)
    apply_edits(payload,assets)
    if s['frameStyle']=='bamboo':
        pieces=['piece-bamboo-horizontal','piece-bamboo-vertical','piece-bamboo-leaves']
    else:
        pieces=[f'piece-{s["frameStyle"]}-{part}' for part in ('rail-h','rail-v','corner')]
    primary=pieces+list(FRAME_SPECS)+['joystick-base','joystick-thumb','bar-track','crest','corner-tl','corner-tr','corner-bl','corner-br','background-jade','background-paper','background-cloth']
    primary=list(dict.fromkeys(primary))
    ordered=primary.copy()
    ordered += [key for key in assets if key not in ordered]
    return {'schema':4,'settings':s,'canvas':canvas_size(payload),'layout':layout(payload,s,assets),'assets':[dict(id=k,width=v['image'].width,height=v['image'].height,
                kind=v['kind'],name=v.get('name',PRIMARY_NAMES.get(k,k)),primary=k in primary,
                recipe=v.get('recipe'),family=v.get('family'),part=v.get('part'),
                margins=v['margins'],url='data:image/png;base64,'+base64.b64encode(png(v['image'])).decode()) for k in ordered for v in [assets[k]]]}


def apply_edits(payload,assets):
    edits=payload.get('edits',{})
    if not isinstance(edits,dict) or len(edits)>len(assets): raise ValueError('Bản sửa pixel không hợp lệ.')
    for key,url in edits.items():
        if key in FRAME_SPECS:raise ValueError('Hãy vẽ từng mảnh của khung ghép, không vẽ đè ảnh tổng.')
        if key not in assets or not isinstance(url,str) or len(url)>2_000_000 or not url.startswith('data:image/png;base64,'):
            raise ValueError('Ảnh sửa cần là PNG của một thành phần trong bộ UI.')
        try:
            raw=base64.b64decode(url.split(',',1)[1],validate=True)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format!='PNG' or image.size!=assets[key]['image'].size:
                    raise ValueError('Kích thước ảnh sửa khác mẫu. Khôi phục mẫu trước khi đổi kích thước.')
                image.load();assets[key]['image']=image.convert('RGBA')
        except ValueError: raise
        except Exception as exc: raise ValueError('Không đọc được PNG đã sửa.') from exc
    refresh_frames(assets)


def canvas_size(payload):
    value=payload.get('canvas',[640,360])
    if value not in ([640,360],[800,360],[780,360]):raise ValueError('Tỉ lệ màn hình không hợp lệ.')
    return list(value)


def default_layout(s,canvas=None):
    w,h=canvas or [640,360]
    return [dict(asset='bar-track',x=20,y=18,fill='bar-health-fill',value=78),
            dict(asset='bar-track',x=20,y=40,fill='bar-mana-fill',value=62),
            dict(asset='inventory-board',x=(w-248)//2,y=62,width=248,height=216,label='Túi đồ'),
            dict(asset='frame-button',x=w-128,y=20,width=108,height=40,label='Nhân vật'),
            dict(asset='frame-button',x=(w-96)//2,y=234,width=96,height=36,label='Sắp xếp'),
            dict(asset='frame-skill',x=w-80,y=h-80,width=64,height=64),
            dict(asset='frame-skill',x=w-140,y=h-76,width=48,height=48),
            dict(asset='frame-skill',x=w-116,y=h-136,width=48,height=48),
            dict(asset='frame-skill',x=w-60,y=h-148,width=44,height=44),
            dict(asset='frame-item',x=148,y=h-60,width=40,height=40,label='Dược'),
            dict(asset='frame-item',x=192,y=h-60,width=40,height=40),
            dict(asset='joystick-base',x=24,y=h-112,width=88,height=88)]


def layout(payload, s, assets):
    screen=canvas_size(payload)
    nodes=payload.get('layout',default_layout(s,screen))
    if not isinstance(nodes,list) or len(nodes)>100: raise ValueError('Bố cục tối đa 100 thành phần.')
    result=[]
    for i,n in enumerate(nodes):
        if not isinstance(n,dict) or n.get('asset') not in assets: raise ValueError('Thành phần không hợp lệ.')
        node_id=n.get('id',f'node{i}')
        if not isinstance(node_id,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',node_id):
            raise ValueError('Mã thành phần không hợp lệ.')
        item={'id':node_id,'asset':n['asset']}
        asset=assets[n['asset']]
        for dim,limit,base in [('width',screen[0],asset['image'].width),('height',screen[1],asset['image'].height)]:
            val=n.get(dim,base)
            minimum=(184 if dim=='width' else 156) if n['asset']=='inventory-board' else (16 if n['asset']=='bar-track' and dim=='height' else 32)
            if isinstance(val,bool) or not isinstance(val,int) or not minimum<=val<=limit:
                if 'recipe' in asset or n['asset']=='joystick-base':raise ValueError('Kích thước khung vượt giới hạn màn hình.')
                val=base
            item[dim]=val if 'recipe' in asset or n['asset']=='joystick-base' else base
        if n['asset']=='frame-skill':
            size=min(item['width'],item['height']);item['width']=size;item['height']=size
        if n['asset']=='joystick-base':
            size=max(64,min(116,item['width']));item['width']=size;item['height']=size
        item['locked']=bool(n.get('locked',False));item['visible']=bool(n.get('visible',True))
        for axis,limit in [('x',screen[0]),('y',screen[1])]:
            val=n.get(axis,0)
            if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val): raise ValueError('Vị trí không hợp lệ.')
            extent=item['width'] if axis=='x' else item['height']
            item[axis]=max(0,min(limit-extent,round(val)))
        if 'label' in n and n['asset']!='frame-skill':
            limit = 512 if n['asset'] == 'text-panel' else 64
            if not isinstance(n['label'],str) or len(n['label'])>limit: raise ValueError(f'Nhãn tối đa {limit} ký tự.')
            item['label']=n['label']
        if 'fill' in n:
            if n['fill'] not in ('bar-health-fill','bar-mana-fill','bar-cultivation-fill') or n['asset']!='bar-track': raise ValueError('Thanh trạng thái không hợp lệ.')
            value=n.get('value',75)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100: raise ValueError('Giá trị thanh cần từ 0 đến 100.')
            item.update(fill=n['fill'],value=value)
        result.append(item)
    return result


def godot_theme(assets):
    keys=['panel','button-normal','button-hover','button-pressed','button-disabled']
    lines=[f'[gd_resource type="Theme" load_steps={len(keys)*2+1} format=3]','']
    for key in keys: lines.append(f'[ext_resource type="Texture2D" path="res://ui_forge/{key}.png" id="{key}"]')
    for key in keys:
        lines+=['',f'[sub_resource type="StyleBoxTexture" id="{key}"]',f'texture = ExtResource("{key}")','draw_center = false','axis_stretch_horizontal = 1','axis_stretch_vertical = 1']
        for side,value in zip(('left','top','right','bottom'),assets[key]['margins']):
            lines.append(f'texture_margin_{side} = {float(value)}')
            lines.append(f'content_margin_{side} = {float(10 if key.startswith("button") else 26)}')
    lines+=['','[resource]','default_font_size = 12','Panel/styles/panel = SubResource("panel")']
    for state in ('normal','hover','pressed','disabled'):
        lines.append(f'Button/styles/{state} = SubResource("button-{state}")')
    lines+=['Button/colors/font_color = Color(0.96, 0.89, 0.73, 1)','Button/colors/font_hover_color = Color(1, 0.95, 0.83, 1)']
    return resource_ids('\n'.join(lines)+'\n')


def resource_ids(text):
    # Godot resource IDs accept alphanumerics and underscores, unlike PNG names.
    text=re.sub(r'id="([a-zA-Z0-9_-]+)"',lambda m:'id="'+m[1].replace('-','_')+'"',text)
    return re.sub(r'(ExtResource|SubResource)\("([a-zA-Z0-9_-]+)"\)',
                  lambda m:m[1]+'("'+m[2].replace('-','_')+'")',text)


def godot_scene(nodes,assets,screen=None):
    screen=screen or [640,360]
    nodes=[n for n in nodes if n.get('visible',True)]
    used=sorted({n['asset'] for n in nodes}|{n['fill'] for n in nodes if 'fill' in n})
    for n in nodes:
        if assets[n['asset']].get('recipe'):
            used.extend(assets[n['asset']]['recipe']['pieces'].values())
            if n['asset']=='inventory-board':used.extend(assets['frame-item']['recipe']['pieces'].values())
    used=sorted(set(used))
    has_joy=any(n['asset']=='joystick-base' for n in nodes)
    if has_joy and 'joystick-thumb' not in used:used.append('joystick-thumb')
    lines=[f'[gd_scene load_steps={len(used)+6+int(has_joy)} format=3]','']
    for key in used: lines.append(f'[ext_resource type="Texture2D" path="res://ui_forge/{key}.png" id="{key}"]')
    if has_joy: lines.append('[ext_resource type="Script" path="res://ui_forge/joystick.gd" id="joystick_script"]')
    for axis in ('v','h'):lines.append(f'[ext_resource type="PackedScene" path="res://ui_forge/Scroll_{axis}.tscn" id="scroll_{axis}"]')
    lines+=['[ext_resource type="Theme" path="res://ui_forge/theme.tres" id="theme"]',
            '[ext_resource type="Script" path="res://ui_forge/frame_button.gd" id="frame_button_script"]',
            '[sub_resource type="StyleBoxEmpty" id="empty_style"]','',
            '[node name="GeneratedHUD" type="CanvasLayer"]','', '[node name="Root" type="Control" parent="."]',
            'layout_mode = 0',f'offset_right = {float(screen[0])}',f'offset_bottom = {float(screen[1])}',
            'mouse_filter = 2','texture_filter = 1','theme = ExtResource("theme")']
    def button_style():
        return ['script = ExtResource("frame_button_script")']+[f'theme_override_styles/{state} = SubResource("empty_style")' for state in ('normal','hover','pressed','disabled','focus')]
    def pieces(parent,recipe,w,h):
        for j,(part,x,y,tw,th,fx,fy) in enumerate(placements(recipe,w,h)):
            lines.extend(['',f'[node name="Part{j}" type="TextureRect" parent="{parent}"]',
                          f'offset_left = {float(x)}',f'offset_top = {float(y)}',f'offset_right = {float(x+tw)}',f'offset_bottom = {float(y+th)}',
                          'expand_mode = 1',f'stretch_mode = {0 if recipe.get("mode")=="ring" else 1}','mouse_filter = 2',f'flip_h = {str(fx).lower()}',f'flip_v = {str(fy).lower()}',f'texture = ExtResource("{part}")'])
    for i,n in enumerate(nodes):
        key=n['asset']; w=n.get('width',assets[key]['image'].width);h=n.get('height',assets[key]['image'].height)
        recipe=assets[key].get('recipe')
        kind='Button' if assets[key]['kind'] in ('button','skill','item') and recipe else 'Control' if recipe or key=='joystick-base' else 'TextureProgressBar' if 'fill' in n else 'Button' if key=='button-normal' else 'NinePatchRect' if key=='panel' else 'TextureRect'
        declaration=f'[node name="Element{i}" type="{kind}" parent="Root"]'
        lines+=['',declaration,'layout_mode = 0',
                f'offset_left = {float(n["x"])}',f'offset_top = {float(n["y"])}',
                f'offset_right = {float(n["x"]+(116 if key=="joystick-base" else w))}',f'offset_bottom = {float(n["y"]+(116 if key=="joystick-base" else h))}']
        if recipe:
            if kind=='Button':lines.extend(button_style())
            else:lines.append('mouse_filter = 2')
            parent=f'Root/Element{i}';pieces(parent,recipe,w,h)
            if 'fill' in n:
                lines.extend(['',f'[node name="Progress" type="TextureProgressBar" parent="{parent}"]',
                              'offset_left = 6.0','offset_top = 4.0',
                              f'offset_right = {float(w - 6)}',f'offset_bottom = {float(h - 4)}',
                              f'texture_progress = ExtResource("{n["fill"]}")',
                              f'value = {float(n["value"])}','mouse_filter = 2'])
            if recipe.get('inventory'):
                for j,(sx,sy,sw,sh) in enumerate(inventory_cells(w,h)):
                    lines.extend(['',f'[node name="Slot{j}" type="Button" parent="{parent}"]',
                                  f'offset_left = {float(sx)}',f'offset_top = {float(sy)}',f'offset_right = {float(sx+sw)}',f'offset_bottom = {float(sy+sh)}']+button_style())
                    pieces(f'{parent}/Slot{j}',assets['frame-item']['recipe'],sw,sh)
            if n.get('label'):
                if key == 'text-panel':
                    lines.extend(['',f'[node name="Caption" type="Label" parent="{parent}"]',
                                  'offset_left = 14.0', 'offset_top = 12.0',
                                  f'offset_right = {float(w - 14)}', f'offset_bottom = {float(h - 12)}',
                                  'mouse_filter = 2', 'horizontal_alignment = 0', 'vertical_alignment = 0',
                                  'autowrap_mode = 2',
                                  'theme_override_font_sizes/font_size = 11',
                                  'theme_override_colors/font_color = Color(0.91, 0.93, 0.85, 1)',
                                  f'text = {json.dumps(n["label"],ensure_ascii=False)}'])
                else:
                    lines.extend(['',f'[node name="Caption" type="Label" parent="{parent}"]',
                                  f'offset_right = {float(w)}',f'offset_bottom = {float(38 if recipe.get("inventory") else h)}',
                                  'mouse_filter = 2','horizontal_alignment = 1','vertical_alignment = 1',
                                  'theme_override_font_sizes/font_size = 10',
                                  'theme_override_colors/font_color = Color(0.86, 0.9, 0.79, 1)',
                                  f'text = {json.dumps(n["label"],ensure_ascii=False)}'])
        elif key=='joystick-base':
            lines.append(f'scale = Vector2({w/116}, {h/116})')
            lines += ['script = ExtResource("joystick_script")',
                      '',f'[node name="Base" type="TextureRect" parent="Root/Element{i}"]',
                      'mouse_filter = 2',f'texture = ExtResource("{key}")','',
                      f'[node name="Thumb" type="TextureRect" parent="Root/Element{i}"]',
                      'offset_left = 35.0','offset_top = 35.0','mouse_filter = 2','texture = ExtResource("joystick-thumb")']
        elif kind=='TextureProgressBar':
            lines += [f'texture_under = ExtResource("{key}")',f'texture_progress = ExtResource("{n["fill"]}")',f'value = {float(n["value"])}','mouse_filter = 2']
        elif kind=='Button': lines += [f'text = {json.dumps(n.get("label",""),ensure_ascii=False)}']
        else:
            lines += [f'{"texture_normal" if kind=="TextureButton" else "texture"} = ExtResource("{key}")']
            if kind!='TextureButton':lines.append('mouse_filter = 2')
            if kind=='NinePatchRect':
                for side,v in zip(('left','top','right','bottom'),assets[key]['margins']): lines.append(f'patch_margin_{side} = {v}')
            if n.get('label'):
                lines+=['',f'[node name="Caption" type="Label" parent="Root/Element{i}"]','layout_mode = 0',
                        'offset_left = 0.0','offset_top = 0.0',f'offset_right = {float(w-8)}',f'offset_bottom = {float(h-8)}',
                        'theme_override_font_sizes/font_size = 11',
                        f'text = {json.dumps(n["label"],ensure_ascii=False)}','horizontal_alignment = 1','vertical_alignment = 1','mouse_filter = 2']
                if key in ('cloud-command','scroll-command','bamboo-panel'):lines.append('theme_override_colors/font_color = Color(0.204, 0.247, 0.208, 1)')
                else:lines.append('theme_override_colors/font_color = Color(0.957, 0.882, 0.753, 1)')
    return resource_ids('\n'.join(lines)+'\n')


def godot_scroll_scene(axis):
    w,h=(32,160) if axis=='v' else (160,32)
    lines=['[gd_scene load_steps=6 format=3]',
           f'[ext_resource type="Texture2D" path="res://ui_forge/scroll-track-{axis}.png" id="track"]',
           f'[ext_resource type="Texture2D" path="res://ui_forge/scroll-grabber-{axis}.png" id="grabber"]',
           '[ext_resource type="Texture2D" path="res://ui_forge/empty-scroll-arrow.png" id="empty"]']
    for name in ('track','grabber'):
        lines+=['',f'[sub_resource type="StyleBoxTexture" id="{name}_style"]',f'texture = ExtResource("{name}")','draw_center = false']
        for side in ('left','right','top','bottom'):
            margin=12 if (axis=='v' and side in ('left','right')) or (axis=='h' and side in ('top','bottom')) else 3
            lines.append(f'texture_margin_{side} = {float(margin)}')
    lines+=['',f'[node name="Scroll_{axis}" type="{ "VScrollBar" if axis=="v" else "HScrollBar"}"]',
            f'offset_right = {float(w)}',f'offset_bottom = {float(h)}','texture_filter = 1','page = 25.0','value = 40.0']
    for name in ('scroll','scroll_focus'):lines.append(f'theme_override_styles/{name} = SubResource("track_style")')
    for name in ('grabber','grabber_highlight','grabber_pressed'):lines.append(f'theme_override_styles/{name} = SubResource("grabber_style")')
    for name in ('increment','increment_highlight','increment_pressed','decrement','decrement_highlight','decrement_pressed'):lines.append(f'theme_override_icons/{name} = ExtResource("empty")')
    return '\n'.join(lines)+'\n'


def export_zip(payload):
    s=settings(payload);assets=build(s);apply_edits(payload,assets);nodes=layout(payload,s,assets)
    screen=canvas_size(payload)
    manifest={'version':3,'settings':s,'layout':nodes,'edits':payload.get('edits',{}),'canvas':screen,
              'assets':{k:{'size':list(v['image'].size),'margins':v['margins'],'kind':v['kind'],'recipe':v.get('recipe')} for k,v in assets.items()}}
    # Bake procedural contours at each instance's exact dimensions. Godot never
    # scales a small circle texture into a thicker, jagged outline.
    scene_nodes=[]
    for n in nodes:
        item=n.copy();asset=assets[n['asset']];recipe=asset.get('recipe',{})
        if recipe.get('mode') in ('circle','ornate','outline'):
            w,h=n['width'],n['height'];key=f'{n["asset"]}-native-{w}x{h}';texture=f'{key}-texture'
            assets[texture]={'image':compose(assets,recipe,w,h),'kind':'piece','margins':None}
            assets[key]={**asset,'image':assets[texture]['image'],'recipe':{'family':recipe['family'],'cell':16,'mode':'ring','pieces':{'ring':texture}}}
            item['asset']=key
        scene_nodes.append(item)
    # The default Theme is also green and hollow, so new Godot controls match.
    for key in ('panel','button-normal','button-hover','button-pressed','button-disabled'):
        source='frame-panel' if key=='panel' else 'frame-button'
        assets[key]={**assets[source],'margins':[16]*4}
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as z:
        for key,v in assets.items(): z.writestr(f'ui_forge/{key}.png',png(v['image']))
        panel_recipe = assets.get('frame-panel', {}).get('recipe')
        if panel_recipe and 'pieces' in panel_recipe:
            piece_keys = [k for k in panel_recipe['pieces'].values() if k in assets]
            if piece_keys:
                strip_w = sum(assets[k]['image'].width for k in piece_keys)
                strip_h = max(assets[k]['image'].height for k in piece_keys)
                strip_img = Image.new('RGBA', (strip_w, strip_h), (0, 0, 0, 0))
                cur_x = 0
                slice_lines = [f"# Godot 4 AtlasTexture Rect2 Slices ({strip_w}x{strip_h})"]
                for k in piece_keys:
                    part_img = assets[k]['image']
                    strip_img.paste(part_img, (cur_x, 0), part_img)
                    slice_lines.append(f"{k}: Rect2({cur_x}, 0, {part_img.width}, {part_img.height})")
                    cur_x += part_img.width
                z.writestr('ui_forge/frame-pieces-strip.png', png(strip_img))
                z.writestr('ui_forge/frame-pieces-slices.txt', '\n'.join(slice_lines) + '\n')
        z.writestr('ui_forge/theme.tres',godot_theme(assets))
        z.writestr('ui_forge/HUD.tscn',godot_scene(scene_nodes,assets,screen))
        z.writestr('ui_forge/joystick.gd',JOYSTICK_SCRIPT)
        z.writestr('ui_forge/frame_button.gd',FRAME_BUTTON_SCRIPT)
        z.writestr('ui_forge/empty-scroll-arrow.png',png(Image.new('RGBA',(1,1))))
        for axis in ('v','h'):z.writestr(f'ui_forge/Scroll_{axis}.tscn',godot_scroll_scene(axis))
        z.writestr('ui_forge/ASSEMBLY.txt',f'Canvas: {screen[0]}x{screen[1]}. Set your project viewport to this size and use canvas_items stretch with aspect keep.\nBamboo frames use three transparent pieces: one 32x16 horizontal internode, one 16x32 vertical internode, and one 32x32 leaf overlay mirrored at four corners. Other frame families use independent 16px pieces. All frame interiors are transparent.\nThe HUD scene contains editable TextureRect pieces and real Buttons for skills, items, and every inventory slot.\nFrame previews are also provided as PNG; edit the pieces to preserve resizing.\nClouds, seals, coins and pendants are decorative TextureRects with mouse_filter IGNORE.\n')
        z.writestr('ui_forge/preset.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('ui_forge/README.txt','HKT UI Forge / Xianxia v2\n\nCopy ui_forge into your Godot 4 project root.\nOpen HUD.tscn or instantiate it in your game. Base canvas: 640x360.\nUse integer scaling (2x for 1280x720), Nearest filter, and integer positions.\nFrame and button interiors are transparent. Background tiles are separate layers.\nSkill circles are baked at each instance size with one opaque 1px contour, no shadow or fill. Resize in UI Forge and export again.\nConnect Button.pressed to gameplay actions.\nThe joystick handles mouse and touch; connect direction_changed(Vector2) to movement.\nJoystick direction resets on release or window focus loss. Positive Y points down.\nScroll_v.tscn / Scroll_h.tscn are functional VScrollBar / HScrollBar scenes. Connect value_changed to your content. HUD tracks and grabbers remain separate artwork layers for manual assembly.\nEquipment previews and chat frames are empty containers; connect character data and chat logic in your game.\nProgress bars contain sample values. Bind values to your character data.\nImport preset.json in UI Forge to continue editing, including hand-painted pixel overrides.\nArtwork is generated from geometry; reference sheet pixels are not included.\n')
    return result.getvalue()


FRAME_BUTTON_SCRIPT='''extends Button
func _ready() -> void:
    mouse_entered.connect(func(): modulate = Color(1.15, 1.15, 1.15))
    mouse_exited.connect(func(): modulate = Color.WHITE)
    button_down.connect(func(): modulate = Color(0.72, 0.78, 0.74))
    button_up.connect(func(): modulate = Color.WHITE)
'''


JOYSTICK_SCRIPT='''extends Control
## Connect direction_changed to your character movement input.
signal direction_changed(value: Vector2)
@export var radius: float = 30.0
var direction: Vector2 = Vector2.ZERO
var _finger: int = -2
@onready var thumb: TextureRect = $Thumb
var _rest := Vector2(35, 35)

func _gui_input(event: InputEvent) -> void:
    if _finger != -2:
        return
    if event is InputEventScreenTouch and event.pressed:
        _finger = event.index
        _update_stick(event.position)
        accept_event()
    elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
        _finger = -1
        _update_stick(event.position)
        accept_event()

func _input(event: InputEvent) -> void:
    if _finger == -2:
        return
    if event is InputEventScreenTouch and event.index == _finger and not event.pressed:
        _release()
    elif event is InputEventScreenDrag and event.index == _finger:
        _update_stick(get_global_transform_with_canvas().affine_inverse() * event.position)
    elif _finger == -1 and event is InputEventMouseMotion:
        _update_stick(get_global_transform_with_canvas().affine_inverse() * event.position)
    elif _finger == -1 and event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
        _release()

func _update_stick(point: Vector2) -> void:
    var offset := (point - Vector2(54, 54)).limit_length(maxf(radius, 1.0))
    thumb.position = _rest + offset
    direction = offset / maxf(radius, 1.0)
    direction_changed.emit(direction)

func _release() -> void:
    _finger = -2
    direction = Vector2.ZERO
    thumb.position = _rest
    direction_changed.emit(direction)

func _notification(what: int) -> void:
    if what == NOTIFICATION_WM_WINDOW_FOCUS_OUT and is_instance_valid(thumb):
        _release()
'''
