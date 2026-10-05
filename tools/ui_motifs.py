import math
from PIL import Image, ImageDraw, ImageFilter
from ui_segments import green_palette, blend



def blank(w,h): return Image.new('RGBA',(w,h))


def tint(color,target,ratio):
    return tuple(round(a+(b-a)*ratio) for a,b in zip(color,target))


def cloud_button(p):
    im=blank(148,58);d=ImageDraw.Draw(im)
    dark=tint(p.gem,p.base,.55);body=tint(p.gem,(221,232,194),.35);light=tint(p.gem,(249,245,206),.75)
    # Connected ruyi heads form the actual silhouette, not a rectangular frame.
    for color,inset in [(p.dark,0),(p.metal,1),(dark,3),(body,4)]:
        d.rounded_rectangle((8+inset,19+inset,125-inset,43-inset),radius=10,fill=color)
        for x,y,r in [(24,21,13),(48,17,12),(75,17,12),(102,21,13)]:
            d.ellipse((x-r+inset,y-r+inset,x+r-inset,y+r-inset),fill=color)
    d.polygon([(112,30),(133,24),(128,34),(113,43),(94,43)],fill=body)
    d.line([(112,30),(130,27),(124,34)],fill=light)
    for x,y in ([(24,21),(49,17),(77,17),(103,23)] if p.s['detail'] else []):
        d.arc((x-8,y-7,x+7,y+7),175,350,fill=light,width=1)
        d.arc((x-4,y-2,x+3,y+4),10,260,fill=dark,width=1)
    d.line((34,37,103,37),fill=dark)
    d.line((38,38,100,38),fill=light)
    if p.s['detail']>=2:
        d.line([(12,32),(17,35),(25,35),(28,33)],fill=light)
        d.line([(105,37),(115,35),(119,32)],fill=dark)
    if p.s['texture']:
        d.line((37,27,94,27),fill=tint(body,light,.35))
    return p.finish(im)


def bamboo_panel(p,w,h):
    im=blank(w,h);d=ImageDraw.Draw(im)
    d.rectangle((13,16,w-21,h-20),fill='#8b7955')
    d.rectangle((15,18,w-23,h-22),fill='#d4c59d')
    d.rectangle((18,21,w-26,h-25),fill='#e0d3ad')
    if p.s['texture']:
        for y in range(26,h-28,4):
            for x in range(24+(y%7),w-28,17):d.point((x,y),fill='#cabb93')
    green=tint(p.gem,p.base,.45);shine=tint(p.gem,(211,217,163),.5);shadow=tint(p.base,(12,31,24),.3)
    for x in (9,w-22):
        d.rectangle((x,10,x+6,h-16),fill=shadow)
        d.rectangle((x+1,10,x+4,h-16),fill=green)
        d.line((x+2,11,x+2,h-18),fill=shine)
        for y in range(22,h-19,22):
            d.line((x-1,y,x+7,y),fill=shadow,width=2)
            d.line((x,y-1,x+6,y-1),fill=shine)
    for y in (12,h-22):
        d.rectangle((10,y,w-18,y+5),fill=shadow)
        d.rectangle((11,y+1,w-19,y+3),fill=green)
        d.line((13,y+1,w-20,y+1),fill=shine)
        for x in range(25,w-24,25):d.line((x,y,x,y+5),fill=shadow)
    # Tied joints and lanceolate bamboo leaves.
    for x,y,sx,sy in [(12,14,1,1),(w-19,14,-1,1),(12,h-20,1,-1),(w-19,h-20,-1,-1)]:
        for k in range(3):d.line((x-3+k,y+4,x+3+k,y-3),fill=p.metal)
        for pts in [[(0,0),(8,2),(17,12),(7,7)],[(1,0),(12,-3),(22,1),(11,2)],[(2,1),(5,10),(2,19),(-1,9)]]:
            points=[(x+sx*a,y+sy*b) for a,b in pts]
            d.polygon(points,fill=green);d.line(points[:3],fill=shine)
    return p.finish(im)


def token(p):
    im=blank(66,102);d=ImageDraw.Draw(im)
    d.arc((21,3,39,20),175,365,fill='#9c4e42',width=2)
    shape=[(30,12),(51,26),(51,70),(42,81),(18,81),(9,70),(9,26)]
    d.polygon(shape,fill=p.dark);d.line(shape+[shape[0]],fill=p.light,width=1)
    d.polygon([(30,17),(46,29),(46,68),(39,76),(21,76),(14,68),(14,29)],fill='#783e32')
    d.line([(16,64),(16,30),(30,21),(44,30)],fill='#b7744f')
    d.line([(18,33),(18,64),(23,70)],fill='#502f2c')
    d.line([(42,33),(42,64),(37,70)],fill='#502f2c')
    if p.s['texture']:
        for x,y in [(20,37),(38,32),(22,49),(40,52)]:d.line((x,y,x,y+8),fill='#874736')
    if p.s['detail']>=2:
        for y in (36,45,54):
            d.line([(11,y),(12,y+2),(11,y+4)],fill=p.metal)
            d.line([(49,y),(48,y+2),(49,y+4)],fill=p.light)
    p.jewel(d,30,28,5)
    # Open face for a game label; a small square seal anchors the lower edge.
    d.rectangle((24,59,36,69),outline=p.metal,width=1)
    d.line([(27,67),(27,62),(30,62),(30,66),(33,66),(33,61)],fill=p.light)
    d.rectangle((28,81,32,84),fill=p.metal)
    for x in range(25,36):d.line((x,85,x,91+abs(x-30)//2),fill='#ae5c49' if x%2 else '#743d37')
    return p.finish(im)


def coin(p):
    im=blank(62,62);d=ImageDraw.Draw(im)
    d.ellipse((5,5,50,50),fill=p.dark);d.ellipse((6,6,49,49),fill=p.metal)
    d.arc((6,6,49,49),180,300,fill=p.light,width=2)
    d.ellipse((10,10,45,45),outline=p.dark,width=2)
    d.arc((12,12,43,43),0,165,fill=p.light,width=1)
    d.rectangle((21,21,34,34),fill=p.dark);d.rectangle((23,23,32,32),fill=(0,0,0,0))
    for x,y,rotation in ([(25,12,0),(38,24,1),(24,38,0),(12,24,1)] if p.s['detail'] else []):
        points=[(0,0),(5,0),(5,2),(2,2),(2,5),(6,5)]
        points=[(x+b,y+a) if rotation else (x+a,y+b) for a,b in points]
        d.line(points,fill=p.dark,width=1)
        d.point((x,y-1),fill=p.light)
    return p.finish(im)


def jade(p):
    im=blank(66,84);d=ImageDraw.Draw(im)
    d.arc((23,3,37,18),175,365,fill=p.metal,width=2)
    d.rounded_rectangle((10,15,50,61),radius=12,fill='#244c44')
    d.rounded_rectangle((12,16,48,59),radius=11,fill=p.gem)
    d.arc((12,16,48,51),175,320,fill='#d0e6be',width=2)
    d.rounded_rectangle((18,23,42,51),radius=8,outline='#497565',width=2)
    d.arc((21,28,38,45),20,300,fill='#d0e6be',width=1)
    d.rectangle((27,32,33,40),fill='#244c44')
    d.rectangle((28,33,32,39),fill=(0,0,0,0))
    if p.s['detail']>=2:
        for x,y in [(15,26),(40,26),(15,46),(40,46)]:
            d.arc((x-2,y-2,x+3,y+3),20,290,fill='#d0e6be')
    if p.s['texture']:
        d.line([(17,22),(18,21),(23,20)],fill='#d0e6be')
        d.line([(41,53),(39,55),(35,56)],fill='#497565')
    d.rectangle((28,61,32,64),fill=p.metal)
    for x in range(24,37):d.line((x,65,x,73-abs(x-30)//2),fill='#ad5d4b' if x%2 else '#683d32')
    return p.finish(im)


def scroll(p):
    im=blank(148,58);d=ImageDraw.Draw(im)
    d.polygon([(13,12),(130,12),(126,21),(130,43),(12,43),(15,30)],fill='#ad926c')
    d.rectangle((18,14,124,41),fill='#e0cda3')
    d.line((23,17,119,17),fill='#b39a72');d.line((23,38,119,38),fill='#b39a72')
    if p.s['detail']:
        for x in (24,111):
            d.line([(x,23),(x,20),(x+5,20),(x+5,23),(x+2,23)],fill='#a68a63')
            d.line([(x,32),(x,35),(x+5,35),(x+5,32),(x+2,32)],fill='#a68a63')
    for x in (10,127):
        d.rounded_rectangle((x,7,x+7,47),radius=2,fill='#423331')
        d.line((x+2,9,x+2,43),fill='#96634a')
        for y in (9,42):d.rectangle((x-2,y,x+9,y+2),fill=p.metal);d.point((x-2,y),fill=p.light)
    return p.finish(im)


def lotus(p):
    im=blank(70,70);d=ImageDraw.Draw(im)
    import math
    cx,cy=31,31
    for i in range(8):
        angle=i*math.pi/4;pts=[]
        for r,a in [(13,angle-.25),(21,angle-.22),(27,angle),(21,angle+.22),(13,angle+.25),(12,angle)]:pts.append((round(cx+r*math.cos(a)),round(cy+r*math.sin(a))))
        d.polygon(pts,fill=tint(p.gem,p.metal,.45));d.line(pts[:3],fill=p.light)
        if p.s['detail']>=2:d.line((cx+round(17*math.cos(angle)),cy+round(17*math.sin(angle)),cx+round(24*math.cos(angle)),cy+round(24*math.sin(angle))),fill=p.metal)
    d.ellipse((12,12,50,50),fill=p.dark);d.ellipse((14,14,48,48),fill=p.base)
    d.arc((15,15,47,47),180,310,fill=p.light,width=1)
    d.ellipse((19,19,43,43),outline=p.gem,width=1)
    return p.finish(im)


def joystick(p, thumb=False):
    style = p.style
    s = p.s
    border = s.get('border', 5)
    detail = s.get('detail', 2)
    enable_shadow = s.get('enableShadow', True)
    shadow_val = s.get('shadow', 3) if enable_shadow else 0
    crest = s.get('crest', True)
    texture = s.get('texture', True)
    show_bg = s.get('showBg', True)

    ink = p.ink
    metal = p.trim
    rail = p.body
    gem = p.gem
    surface = p.base
    light = p.light
    dark = p.dark

    if thumb:
        size = 46
        im = Image.new('RGBA', (size, size))
        cx, cy = 22.5, 22.5
        r_outer = 18.5
        rim_w = max(3.0, min(5.5, 2.5 + (border - 3) * 0.5))
        r_rim = r_outer - rim_w
        r_gem = 6.0

        for y in range(size):
            for x in range(size):
                dx = x - cx
                dy = y - cy
                dist = math.hypot(dx, dy)
                if dist > r_outer:
                    continue
                ldot = -(dx + dy) / (dist * 1.4142) if dist > 0 else 0

                if dist >= r_rim:
                    if dist >= r_outer - 0.9 or dist <= r_rim + 0.7:
                        im.putpixel((x, y), (*ink, 255))
                    elif ldot > 0.25:
                        im.putpixel((x, y), (*light, 255) if ldot > 0.65 else (*metal, 255))
                    elif ldot < -0.25:
                        im.putpixel((x, y), (*dark, 255))
                    else:
                        im.putpixel((x, y), (*metal, 255))
                elif dist > r_gem + 1.5:
                    if ldot > 0.3:
                        col = blend(rail, light, min(0.65, 0.25 + 0.45 * ldot))
                    elif ldot < -0.3:
                        col = blend(rail, dark, min(0.65, 0.25 - 0.45 * ldot))
                    else:
                        col = rail

                    if detail >= 1 and abs(dist - (r_rim + r_gem) / 2) < 0.75:
                        col = blend(col, light if ldot > 0 else dark, 0.35)

                    if texture and (x * 7 + y * 13) % 19 == 0:
                        col = blend(col, gem, 0.22)
                    im.putpixel((x, y), (*col, 255))
                elif dist > r_gem:
                    collar = metal if ldot >= -0.2 else ink
                    im.putpixel((x, y), (*collar, 255))
                else:
                    g_ldot = -(dx + dy) / (dist * 1.4142) if dist > 0 else 0.7
                    if g_ldot > 0.3:
                        col = blend(gem, (255, 255, 255), min(0.7, 0.3 + 0.5 * g_ldot))
                    elif g_ldot < -0.3:
                        col = blend(gem, ink, min(0.7, 0.3 - 0.5 * g_ldot))
                    else:
                        col = gem
                    im.putpixel((x, y), (*col, 255))

        dt = ImageDraw.Draw(im)
        dt.point((int(cx - 2), int(cy - 2)), fill=(255, 255, 255, 255))
        dt.point((int(cx - 1), int(cy - 2)), fill=(255, 255, 255, 200))
        dt.point((int(cx - 2), int(cy - 1)), fill=(255, 255, 255, 200))

        if crest:
            for ox, oy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
                px = int(round(cx + ox * (r_gem + 1)))
                py = int(round(cy + oy * (r_gem + 1)))
                dt.point((px, py), fill=metal)
                if ox <= 0 and oy <= 0:
                    dt.point((px, py), fill=light)

        if shadow_val > 0:
            sh = Image.new('RGBA', (size, size))
            alpha = im.getchannel('A')
            expanded = alpha.filter(ImageFilter.MaxFilter(3))
            sh.paste((*ink, min(90, 35 + shadow_val * 14)), (0, 0), expanded)
            res = Image.new('RGBA', (size, size))
            res.alpha_composite(sh, (0, 0))
            res.alpha_composite(im, (0, 0))
            return res
        return im

    else:
        size = 116
        im = Image.new('RGBA', (size, size))
        cx, cy = 57.5, 57.5
        r_outer = 51.6
        rim_w = max(4.0, min(9.0, 3.0 + (border - 3) * 1.0))
        r_inner = r_outer - rim_w
        r_throw = 30.0
        r_dead = 14.0

        for y in range(size):
            for x in range(size):
                dx = x - cx
                dy = y - cy
                dist = math.hypot(dx, dy)
                if dist > r_outer:
                    continue
                ldot = -(dx + dy) / (dist * 1.4142) if dist > 0 else 0

                if dist >= r_inner:
                    if dist >= r_outer - 1.0 or dist <= r_inner + 0.8:
                        im.putpixel((x, y), (*ink, 255))
                    elif dist >= r_outer - 2.2:
                        if ldot > 0.2: im.putpixel((x, y), (*light, 255))
                        elif ldot < -0.2: im.putpixel((x, y), (*dark, 255))
                        else: im.putpixel((x, y), (*metal, 255))
                    elif dist <= r_inner + 2.0:
                        if ldot > 0.25: im.putpixel((x, y), (*ink, 220))
                        elif ldot < -0.25: im.putpixel((x, y), (*light, 190))
                        else: im.putpixel((x, y), (*dark, 210))
                    else:
                        if ldot > 0.3: col = blend(rail, light, 0.4)
                        elif ldot < -0.3: col = blend(rail, dark, 0.45)
                        else: col = rail
                        if texture and (x * 7 + y * 13) % 17 == 0:
                            col = blend(col, gem if style == 'jade' else metal, 0.25)
                        im.putpixel((x, y), (*col, 255))
                elif show_bg:
                    dish_bg = blend(surface, ink, 0.35)
                    dish_sh = blend(surface, ink, 0.65)
                    dish_hi = blend(surface, light, 0.15)
                    if ldot > 0.25:
                        col = blend(dish_bg, dish_sh, min(0.55, 0.2 + 0.35 * ldot))
                    elif ldot < -0.25:
                        col = blend(dish_bg, dish_hi, min(0.35, 0.1 - 0.25 * ldot))
                    else:
                        col = dish_bg

                    if detail >= 1:
                        if abs(dist - r_throw) < 0.75:
                            col = blend(col, metal, 0.35 if detail >= 2 else 0.2)
                        elif detail >= 2 and abs(dist - r_dead) < 0.75:
                            col = blend(col, gem, 0.3)
                        elif detail >= 3 and abs(dist - 22.0) < 0.6:
                            col = blend(col, light, 0.2)

                    if detail >= 2:
                        if (abs(dx) < 0.75 or abs(dy) < 0.75) and dist > r_dead and dist < r_throw + 4:
                            if (int(dist) % 4) < 2:
                                col = blend(col, light if detail >= 3 else metal, 0.3)
                        elif detail >= 3 and abs(abs(dx) - abs(dy)) < 0.85 and dist > r_dead + 2 and dist < r_throw:
                            if (int(dist) % 4) < 2:
                                col = blend(col, gem, 0.25)

                    if texture and (x * 11 + y * 7) % 29 == 0:
                        col = blend(col, gem, 0.12)
                    im.putpixel((x, y), (*col, 240))

        db = ImageDraw.Draw(im)
        if crest:
            clasp_r = max(2, min(4, int(rim_w / 2)))
            cardinals = [
                (57.5, cy - r_outer + rim_w / 2, 0, -1),
                (cx + r_outer - rim_w / 2, 57.5, 1, 0),
                (57.5, cy + r_outer - rim_w / 2, 0, 1),
                (cx - r_outer + rim_w / 2, 57.5, -1, 0),
            ]
            for kx, ky, sx, sy in cardinals:
                ix, iy = int(round(kx)), int(round(ky))
                if style == 'bamboo':
                    db.rectangle((ix - clasp_r, iy - clasp_r, ix + clasp_r, iy + clasp_r), fill=metal, outline=ink)
                    db.point((ix, iy), fill=gem)
                    db.point((ix - 1, iy - 1), fill=light)
                elif style == 'wood':
                    db.ellipse((ix - clasp_r, iy - clasp_r, ix + clasp_r, iy + clasp_r), fill=metal, outline=ink)
                    db.point((ix, iy), fill=gem)
                    db.point((ix - 1, iy - 1), fill=light)
                else: # jade
                    db.rectangle((ix - clasp_r, iy - clasp_r, ix + clasp_r, iy + clasp_r), fill=metal, outline=ink)
                    db.point((ix, iy), fill=gem)
                    db.point((ix - 1, iy - 1), fill=(255, 255, 255))

            if detail >= 2:
                diag_dist = r_outer - rim_w / 2
                for angle in [math.pi/4, 3*math.pi/4, 5*math.pi/4, 7*math.pi/4]:
                    ix = int(round(cx + diag_dist * math.cos(angle)))
                    iy = int(round(cy + diag_dist * math.sin(angle)))
                    db.rectangle((ix - 1, iy - 1, ix + 1, iy + 1), fill=metal)
                    db.point((ix, iy), fill=gem if style == 'jade' else light)

        if shadow_val > 0:
            sh = Image.new('RGBA', (size, size))
            alpha = im.getchannel('A')
            expanded = alpha.filter(ImageFilter.MaxFilter(3))
            sh.paste((*ink, min(90, 35 + shadow_val * 14)), (0, 0), expanded)
            res = Image.new('RGBA', (size, size))
            res.alpha_composite(sh, (0, 0))
            res.alpha_composite(im, (0, 0))
            return res
        return im


PRIMARY_NAMES = {'cloud-command': 'Vân lệnh · mây cuộn', 'bamboo-panel': 'Trúc thư · khung trúc',
 'token-command': 'Môn phái · lệnh bài', 'coin-command': 'Cổ tệ · đồng xu',
 'jade-command': 'Ngọc bội · phù ngọc', 'scroll-command': 'Chiếu thư · cuộn giấy',
 'lotus-command': 'Liên hoa · ô kỹ năng', 'joystick-base': 'Bàn xoay điều khiển · joystick',
 'joystick-thumb': 'Núm xoay · joystick', 'bar-track': 'Khí mạch · thanh HUD',
 'crest': 'Huy hiệu đỉnh · chạm khắc',
 'corner-tl': 'Góc chạm ↖ · L-Bracket', 'corner-tr': 'Góc chạm ↗ · L-Bracket',
 'corner-bl': 'Góc chạm ↙ · L-Bracket', 'corner-br': 'Góc chạm ↘ · L-Bracket'}


def unique_assets(p,s):
    return {'cloud-command':(cloud_button(p),'button'), 'bamboo-panel':(bamboo_panel(p,s['width'],s['height']),'panel'),
            'token-command':(token(p),'button'),'coin-command':(coin(p),'button'),
            'jade-command':(jade(p),'button'),'scroll-command':(scroll(p),'button'),
            'lotus-command':(lotus(p),'slot'),'joystick-base':(joystick(p),'joystick'),
            'joystick-thumb':(joystick(p,True),'joystick')}
