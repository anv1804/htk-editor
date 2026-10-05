"""Reusable 16px frame pieces. Repeat edges; never stretch corner artwork."""
import math
from PIL import Image, ImageDraw, ImageFilter, ImageChops

CELL = 16
POSITIONS = [('tl',0,0),('top',1,0),('tr',2,0),('left',0,1),('center',1,1),('right',2,1),('bl',0,2),('bottom',1,2),('br',2,2)]
PART_NAMES = dict(tl='Góc trên trái',top='Đốt cạnh trên',tr='Góc trên phải',left='Đốt cạnh trái',center='Nền lặp',right='Đốt cạnh phải',bl='Góc dưới trái',bottom='Đốt cạnh dưới',br='Góc dưới phải')
FAMILIES = {'bamboo':'Trúc thư','button':'Nút sơn ngọc','skill':'Khung chiêu','item':'Khung vật phẩm'}
FRAME_SPECS = {
    'frame-panel':('Bảng trúc ghép','bamboo',224,176,'panel'),
    'frame-button':('Khung nút','button',112,40,'button'),
    'frame-skill':('Khung chiêu','skill',56,56,'skill'),
    'frame-item':('Khung item','item',40,40,'item'),
    'inventory-board':('Bảng túi đồ','bamboo',248,216,'inventory'),
    'inventory-frame':('Khung túi đồ · không ô','bamboo',248,216,'panel'),
    'chat-frame':('Khung chat','button',280,112,'panel'),
    'chat-input':('Khung nhập chat','button',240,32,'button'),
    'text-panel':('Bảng chữ (ghi text)','text-panel',240,80,'panel'),
    'bar-track':('Khí mạch · thanh HUD & Nút','bar',164,24,'button'),
    'equipment-preview':('Khung nhân vật đang mặc','bamboo',152,248,'panel'),
    'equipment-slot':('Ô trang bị','item',48,48,'item'),
    'equipment-details':('Bảng thuộc tính trang bị','bamboo',208,248,'panel'),
    'tooltip-frame':('Khung tooltip','button',160,104,'panel'),
    'dialog-frame':('Khung hội thoại','bamboo',400,104,'panel'),
    'modal-frame':('Khung xác nhận','bamboo',272,160,'panel'),
    'list-row':('Khung dòng danh sách','button',200,36,'button'),
    'tab-frame':('Khung tab','button',80,32,'button'),
    'scroll-track-v':('Rãnh cuộn dọc','button',32,160,'scrollbar'),
    'scroll-grabber-v':('Con trượt dọc','button',32,40,'scrollbar'),
    'scroll-track-h':('Rãnh cuộn ngang','button',160,32,'scrollbar'),
    'scroll-grabber-h':('Con trượt ngang','button',40,32,'scrollbar'),
}


def blend(a,b,t):return tuple(round(x+(y-x)*t) for x,y in zip(a,b))


def green_palette(p):
    green=blend(p.gem,(85,112,59),.55)
    light=blend(green,(211,215,157),.65)
    dark=blend(green,(22,43,27),.65)
    return green,light,dark,blend(green,dark,.45)


def simple_frame(p):
    green,light,dark,shade=green_palette(p)
    im=Image.new('RGBA',(48,48));d=ImageDraw.Draw(im)
    d.rectangle((4,4,43,43),outline=light,width=max(1,p.s['border']-4))
    return im


def circle_image(size,color,stroke=1):
    """Midpoint circle: opaque, single-colour 1px contour at native resolution."""
    im=Image.new('RGBA',(size,size));cx=cy=size//2
    x=size//2-3;y=0;error=1-x
    while x>=y:
        for dx,dy in ((x,y),(y,x),(-y,x),(-x,y),(-x,-y),(-y,-x),(y,-x),(x,-y)):
            px,py=cx+dx,cy+dy
            for oy in range(-((stroke-1)//2),stroke//2+1):
                for ox in range(-((stroke-1)//2),stroke//2+1):
                    im.putpixel((px+ox,py+oy),tuple(color)+(255,))
        y+=1
        if error<0:error+=2*y+1
        else:x-=1;error+=2*(y-x)+1
    return im


def skill_ring(p):
    return ornate_ring(64, {'palette': [list(c) for c in frame_palette(p, 'bamboo')],
                            'border': p.s['border'], 'detail': p.s['detail'],
                            'shadow': p.s['shadow'], 'texture': p.s['texture'],
                            'crest': p.s['crest'], 'corner': p.s['corner'],
                            'frameStyle': 'bamboo'})


def frame_palette(p, style):
    return [p.rail, p.light, p.outline, p.trim, p.gem]



def rail_parts(p, style):
    """Continuous rails plus a separate corner cap, all at native resolution."""
    rail, light, ink, trim, gem = frame_palette(p, style)
    thickness = p.s['border']; top = 6-thickness//2; bottom = top+thickness-1
    im = Image.new('RGBA', (32, 16)); d = ImageDraw.Draw(im)
    d.rectangle((0, top - 1, 31, bottom + 1), fill=ink)
    d.rectangle((0, top, 31, bottom), fill=rail)
    d.line((0, top, 31, top), fill=light)
    d.line((0, bottom, 31, bottom), fill=blend(rail, ink, .45))
    if p.s['texture']:
        if style == 'wood':
            d.line([(0, top + 2), (7, top + 2), (10, top + 1), (15, top + 1)], fill=blend(rail, light, .35))
            d.line([(16, bottom - 1), (20, bottom - 2), (24, bottom - 2), (28, bottom - 1), (31, bottom - 1)], fill=blend(rail, ink, .35))
        elif style == 'bamboo':
            d.line((3, top - 1, 3, bottom + 1), fill=ink)
            d.line((4, top - 1, 4, bottom + 1), fill=trim)
        else:
            d.line((9, top + 1, 15, top + 1), fill=trim)
            d.point((23, bottom - 1), fill=gem)
    if p.s['detail'] >= 2:
        d.line((0, bottom - 1, 31, bottom - 1), fill=blend(rail, trim, .25))
    cap = Image.new('RGBA', (16, 16))
    c = ImageDraw.Draw(cap)
    
    # Base clean mitered corner intersection
    c.rectangle((top, top, 15, bottom), fill=rail)
    c.rectangle((top, top, bottom, 15), fill=rail)
    c.line([(top - 1, 15), (top - 1, top - 1), (15, top - 1)], fill=ink)
    c.line([(bottom + 1, 15), (bottom + 1, bottom + 1), (15, bottom + 1)], fill=ink)
    c.line([(top, 15), (top, top), (15, top)], fill=light)
    c.line([(bottom, 15), (bottom, bottom), (15, bottom)], fill=blend(rail, ink, 0.45))
    c.line([(top, top), (bottom, bottom)], fill=blend(rail, ink, 0.25))
    
    # Ornate solid corner plate if crest is enabled
    if p.s.get('crest', True):
        corner_style = p.s.get('corner', 'cloud' if style == 'wood' else ('fret' if style == 'jade' else 'leaves'))
        detail = p.s.get('detail', 2)
        arm_len = min(15, bottom + 3)
        bx0 = max(0, top - 1)
        by0 = max(0, top - 1)

        # Solid L-plate body in trim
        c.rectangle((bx0, by0, arm_len, bottom + 1), fill=trim)
        c.rectangle((bx0, by0, bottom + 1, arm_len), fill=trim)

        # Outer dark contour and highlight
        c.line([(bx0, arm_len), (bx0, by0), (arm_len, by0)], fill=ink)
        c.line([(bx0 + 1, arm_len), (bx0 + 1, by0 + 1), (arm_len, by0 + 1)], fill=light)

        # Inner step down
        c.line([(bottom + 1, arm_len), (bottom + 1, bottom + 1), (arm_len, bottom + 1)], fill=ink)
        c.line([(bottom, arm_len - 1), (bottom, bottom), (arm_len - 1, bottom)], fill=blend(trim, ink, 0.45))

        # End clasps on the arms
        c.line([(arm_len, by0), (arm_len, bottom + 1)], fill=light)
        c.line([(bx0, arm_len), (bottom + 1, arm_len)], fill=light)

        # Themed engraving on the corner plate
        if detail >= 1:
            if corner_style == 'cloud':
                c.line([(bx0 + 2, by0 + 4), (bx0 + 3, by0 + 2), (bx0 + 5, by0 + 2), (bx0 + 6, by0 + 4), (bx0 + 4, by0 + 5)], fill=light)
                c.point((bx0 + 3, by0 + 3), fill=blend(trim, ink, 0.6))
                if arm_len > bottom + 1:
                    c.point((arm_len - 1, by0 + 2), fill=light)
                    c.point((bx0 + 2, arm_len - 1), fill=light)
            elif corner_style == 'fret':
                c.line([(bx0 + 2, bottom), (bx0 + 2, by0 + 2), (bottom, by0 + 2)], fill=light)
                c.line([(bx0 + 4, bottom - 1), (bx0 + 4, by0 + 4), (bottom - 1, by0 + 4)], fill=blend(trim, ink, 0.5))
            elif corner_style == 'cut':
                c.line([(bx0 + 1, bottom + 1), (bottom + 1, by0 + 1)], fill=light)
                c.point((bx0 + 2, by0 + 2), fill=ink)
            else: # leaves
                c.line([(bx0 + 2, arm_len - 2), (bx0 + 3, by0 + 3), (arm_len - 2, by0 + 2)], fill=light)
                c.point((bx0 + 4, by0 + 2), fill=blend(trim, ink, 0.5))
                c.point((bx0 + 2, by0 + 4), fill=blend(trim, ink, 0.5))

        # Central gleaming jewel
        if detail >= 1:
            gx = (bx0 + bottom) // 2
            gy = (by0 + bottom) // 2
            c.point((gx, gy - 1), fill=trim)
            c.point((gx - 1, gy), fill=trim)
            c.point((gx + 1, gy), fill=ink)
            c.point((gx, gy + 1), fill=ink)
            c.point((gx, gy), fill=gem)
            c.point((gx - 1, gy - 1), fill=(255, 255, 255))
        if detail >= 3:
            c.point((bx0, by0), fill=(255, 255, 250))
            
    return {'rail-h': im, 'rail-v': im.transpose(Image.Transpose.TRANSPOSE), 'corner': cap}


def btn_thickness(p):
    return max(2, min(5, p.s.get('border', 5) // 2 + 2))


def btn_layers(p, T):
    """Outer->inner colour of every 1px ring: ink, highlight, body, shade, metal, ink."""
    ink, rail, trim = p.outline, p.rail, p.trim
    hi = blend(rail, p.light, .6)
    shade = blend(rail, ink, .35)
    body = [rail] * max(0, T - 2) + [shade]
    return [ink, hi] + body + [trim, ink]


def btn_parts(p, style):
    """Rails styled like the HUD bar: sit flush on the canvas edge so nothing is off-centre."""
    T = btn_thickness(p); cols = btn_layers(p, T)
    ink, rail, trim, light = p.outline, p.rail, p.trim, p.light
    im = Image.new('RGBA', (32, 16)); d = ImageDraw.Draw(im)
    for o, col in enumerate(cols):
        d.line((0, o, 31, o), fill=tuple(col) + (255,))
    if p.s['texture'] and T >= 3:
        mid = blend(rail, ink, .5)
        if style == 'bamboo':
            for x in (7, 23):
                d.line((x, 1, x, T), fill=mid); d.point((x + 1, 1), fill=trim)
        elif style == 'wood':
            d.line((3, 2, 11, 2), fill=blend(rail, light, .3)); d.line((17, T, 27, T), fill=mid)
        else:
            d.line((6, 1, 11, 1), fill=blend(light, (255, 255, 255), .5)); d.point((22, 2), fill=p.gem)
    return {'rail-h': im, 'rail-v': im.transpose(Image.Transpose.TRANSPOSE), 'corner': btn_corner(p, 16)}


def btn_corner(p, size=16):
    """Mitred L-corner with chamfered outside, plus a jewelled boss sized from rail thickness."""
    T = btn_thickness(p); cols = btn_layers(p, T)
    ink, trim, gem = p.outline, p.trim, p.gem
    im = Image.new('RGBA', (size, size))
    for y in range(size):
        for x in range(size):
            o = min(x, y)
            if o < len(cols): im.putpixel((x, y), tuple(cols[o]) + (255,))
    for xy in ((0, 0), (1, 0), (0, 1)): im.putpixel(xy, (0, 0, 0, 0))
    im.putpixel((1, 1), tuple(ink) + (255,))
    if p.s.get('crest', True):
        P = T + 6
        hi = blend(trim, (255, 255, 235), .55); sh = blend(trim, ink, .4)
        for y in range(P):
            for x in range(P):
                if x == 0 or y == 0 or x == P - 1 or y == P - 1: c = ink
                elif x == 1 or y == 1: c = hi
                elif x == P - 2 or y == P - 2: c = sh
                else: c = trim
                im.putpixel((x, y), tuple(c) + (255,))
        for xy in ((0, 0), (1, 0), (0, 1), (P - 1, P - 1)): im.putpixel(xy, (0, 0, 0, 0))
        im.putpixel((1, 1), tuple(ink) + (255,))
        if p.s.get('detail', 2) >= 1:
            c = (P - 1) // 2
            im.putpixel((c, c), tuple(gem) + (255,))
            im.putpixel((c - 1, c), tuple(blend(gem, (255, 255, 255), .45)) + (255,))
            im.putpixel((c, c - 1), tuple(blend(gem, (255, 255, 255), .45)) + (255,))
            im.putpixel((c + 1, c), tuple(blend(gem, ink, .45)) + (255,))
            im.putpixel((c, c + 1), tuple(blend(gem, ink, .45)) + (255,))
            im.putpixel((c - 1, c - 1), (255, 255, 255, 255))
    return im


def btn_backgrounds(p):
    """Button face (soft top-lit gradient) and dark text-panel face."""
    face = blend(p.base, p.rail, .38); ink = p.outline
    bg = Image.new('RGBA', (16, 16)); d = ImageDraw.Draw(bg)
    for y in range(16):
        t = round(y / 15 * 4) / 4
        d.line((0, y, 15, y), fill=blend(blend(face, p.light, .10), blend(face, ink, .45), t) + (255,))
    txt = Image.new('RGBA', (16, 16), blend(p.base, ink, .45) + (255,))
    return {'bg': bg, 'text-bg': txt}


def bar_parts(p, style):
    """Modular pieces for the sleek HUD bar & button:
    - piece-bar-rail-h: Repeating horizontal body rail (32x8)
    - piece-bar-rail-v: Repeating vertical body rail (8x32)
    - piece-bar-corner: Mitred sleek corner (8x8)
    - piece-bar-bg: Cavity / text background (32x32)
    """
    ink = tuple(p.outline) + (255,)
    rail = tuple(p.rail) + (255,)
    light = tuple(p.light) + (255,)
    trim = tuple(p.trim) + (255,)
    shade = tuple(p.dark) + (255,)

    # 1. rail-h (32x8)
    rh = Image.new('RGBA', (32, 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(rh)
    d.line((0, 0, 31, 0), fill=ink)
    d.line((0, 1, 31, 1), fill=light)
    d.line((0, 2, 31, 2), fill=rail)
    d.line((0, 3, 31, 3), fill=rail)
    d.line((0, 4, 31, 4), fill=ink)

    if p.s.get('texture', True):
        mid = blend(p.rail, p.outline, 0.4) + (255,)
        if style == 'bamboo':
            for x in (11, 27):
                d.line((x, 1, x, 3), fill=mid)
        elif style == 'wood':
            d.line((4, 2, 12, 2), fill=blend(p.rail, p.light, 0.3) + (255,))
            d.line((18, 3, 26, 3), fill=mid)
        else:
            d.line((8, 1, 14, 1), fill=blend(p.light, (255, 255, 255), 0.5) + (255,))

    # 2. rail-v (8x32)
    rv = rh.transpose(Image.Transpose.TRANSPOSE)

    # 3. corner (8x8)
    corner = Image.new('RGBA', (8, 8), (0, 0, 0, 0))
    cols = [ink, light, rail, rail, ink]
    for y in range(8):
        for x in range(8):
            o = min(x, y)
            if o < len(cols):
                corner.putpixel((x, y), cols[o])

    corner.putpixel((0, 0), (0, 0, 0, 0))
    corner.putpixel((1, 0), ink)
    corner.putpixel((0, 1), ink)
    corner.putpixel((1, 1), ink)

    if p.s.get('crest', True):
        corner.putpixel((2, 2), trim)

    # 4. bg (32x32)
    bg_col = dict(bamboo=(13, 23, 19, 230), wood=(25, 17, 13, 230), jade=(11, 23, 28, 230)).get(style, (16, 24, 20, 230))
    bg = Image.new('RGBA', (32, 32), bg_col)

    return {
        'rail-h': rh,
        'rail-v': rv,
        'corner': corner,
        'bg': bg,
    }


def ornate_ring(size, recipe):
    """Native pixel bands and four ornament clusters with 3D directional lighting; shared with canvas renderer."""
    im = Image.new('RGBA', (size, size))
    if 'palette' in recipe and recipe['palette']:
        colors = [tuple(c) for c in recipe['palette']]
    else:
        c = tuple(recipe.get('color', (176, 196, 152)))
        colors = [
            c,                                      # 0: rail / body
            blend(c, (255, 250, 220), 0.55),        # 1: light / highlight
            blend(c, (10, 16, 14), 0.8),            # 2: ink / dark outline
            blend(c, (230, 200, 130), 0.4),         # 3: trim / gold
            blend(c, (70, 160, 130), 0.3)           # 4: gem
        ]
    rail, light, ink, trim, gem = colors[:5]
    center = (size - 1) / 2.0
    radius = size / 2.0 - 5.0
    border_val = recipe.get('border', 5)
    width = max(2, min(border_val, max(3, size // 4)))
    detail = recipe.get('detail', 2)
    style = recipe.get('frameStyle', 'bamboo')
    has_crest = recipe.get('crest', True)
    
    for y in range(size):
        for x in range(size):
            dx = x - center
            dy = y - center
            distance = math.hypot(dx, dy)
            if distance == 0:
                continue
            depth = radius - distance
            color = None
            
            if 0 <= depth < width:
                ldot = -(dx + dy) / (distance * 1.4142)
                if depth < 1:
                    color = ink
                elif depth >= width - 1:
                    color = ink
                elif depth < 2:
                    if ldot > 0.35:
                        color = (255, 252, 230) if ldot > 0.8 else light
                    elif ldot < -0.3:
                        color = blend(rail, ink, 0.45)
                    else:
                        color = rail
                elif depth >= width - 2:
                    if ldot < -0.3:
                        color = blend(rail, light, 0.5)
                    elif ldot > 0.3:
                        color = blend(rail, ink, 0.6)
                    else:
                        color = rail
                else:
                    mid_factor = 1.0 - abs(depth - (width / 2.0)) / (width / 2.0)
                    if ldot > 0.3:
                        color = blend(rail, light, 0.35 + 0.35 * mid_factor)
                    elif ldot < -0.3:
                        color = blend(rail, ink, 0.45)
                    else:
                        color = rail
                    if recipe.get('texture') and (x * 7 + y * 11) % 17 == 0:
                        color = gem
            elif width <= depth < width + 1.8:
                ldot = -(dx + dy) / (distance * 1.4142)
                if ldot > 0.2:
                    color = (*ink[:3], int(90 * ldot))
            
            if color is not None:
                if len(color) == 4:
                    im.putpixel((x, y), color)
                else:
                    im.putpixel((x, y), tuple(color) + (255,))

    d = ImageDraw.Draw(im)
    mid = int(round(center))
    
    if has_crest:
        clasp_r = max(1, min(3, int(width // 2)))
        cardinals = [
            (mid, int(round(center - radius + width / 2.0))),
            (int(round(center + radius - width / 2.0)), mid),
            (mid, int(round(center + radius - width / 2.0))),
            (int(round(center - radius + width / 2.0)), mid),
        ]
        for cx, cy in cardinals:
            for oy in range(-clasp_r, clasp_r + 1):
                for ox in range(-clasp_r, clasp_r + 1):
                    metric = abs(ox) + abs(oy)
                    if metric <= clasp_r:
                        c = ink if metric == clasp_r else trim
                        d.point((cx + ox, cy + oy), fill=tuple(c) + (255,))
            d.point((cx, cy), fill=tuple(gem) + (255,))
            if clasp_r >= 2:
                d.point((cx - 1, cy - 1), fill=(255, 255, 255, 255))
                d.point((cx + 1, cy + 1), fill=tuple(ink) + (255,))
        
    if detail >= 1 and has_crest:
        count = 4 + detail * 4
        for i in range(count):
            if i % (count // 4) == 0:
                continue
            angle = (i + 0.5) * math.tau / count
            cx = int(round(center + (radius - width / 2.0) * math.cos(angle)))
            cy = int(round(center + (radius - width / 2.0) * math.sin(angle)))
            if style == 'bamboo':
                for oy in (-1, 0, 1):
                    for ox in (-1, 0, 1):
                        if abs(ox) + abs(oy) <= 1:
                            d.point((cx + ox, cy + oy), fill=tuple(trim) + (255,))
                d.point((cx, cy), fill=tuple(light) + (255,))
            elif recipe.get('corner') == 'cloud':
                d.point((cx, cy), fill=tuple(trim) + (255,))
                d.point((cx - 1, cy - 1), fill=tuple(light) + (255,))
            else:
                d.point((cx, cy), fill=tuple(gem) + (255,))
                d.point((cx - 1, cy), fill=tuple(light) + (255,))

    if recipe.get('shadow'):
        offset = min(2, recipe['shadow'])
        shadow = Image.new('RGBA', im.size)
        alpha = im.getchannel('A')
        shadow.paste((*ink[:3], min(140, 45 + recipe['shadow'] * 25)), (0, 0), alpha)
        result = Image.new('RGBA', im.size)
        result.alpha_composite(shadow, (offset, offset))
        result.alpha_composite(im)
        return result
    return im


def make_item_sheet(p):
    """9-slice sheet for item frames with progressive detail levels.

    detail=0  → Flat minimal slot: flat solid rail + clean flat cavity + 1px ink border
    detail=1  → Chi tiết hơn 1 chút: 2.5D beveled rails + cavity inset shadow & rim light
    detail=2  → 1 chút nữa: full 3D raised rails + cavity grain + L-shaped metal brackets
    detail=3  → 1 chút nữa.....: ornate antique brackets with gem inlays & glints + filigree rails + double cavity depth
    border    → controls rail thickness (3..8 mapped cleanly to 1..4 px)
    shadow    → drop shadow offset behind the frame
    crest     → toggles corner brackets on/off (at detail >= 2)
    texture   → toggles cavity & rail texture grain pattern
    """
    im = Image.new('RGBA', (48, 48))
    d = ImageDraw.Draw(im)

    style = p.s.get('frameStyle', 'bamboo')
    border = p.s.get('border', 5)
    detail = p.s.get('detail', 2)
    shadow = p.s.get('shadow', 0)
    has_crest = p.s.get('crest', True)
    has_texture = p.s.get('texture', True)

    # --- Palette ---
    rail = p.rail
    trim = p.trim
    ink = p.outline
    light = p.light
    dark = p.dark
    mid = blend(rail, light, 0.25)
    gem_col = p.jewel_col
    cavity = p.base
    cavity_shadow = blend(cavity, ink, 0.6)
    cavity_light = blend(cavity, light, 0.2)

    # --- Rail thickness from border setting ---
    # border 3 → 1px, 4..5 → 2px, 6..7 → 3px, 8 → 4px
    thickness = 1 if border <= 3 else (2 if border <= 5 else (3 if border <= 7 else 4))
    outer = 2                       # outer edge start
    inner = outer + thickness       # inner edge of rail
    far = 47 - outer                # outer edge end
    far_inner = far - thickness     # inner edge of rail (opposite side)

    # ═══════════════════════════════════════════════
    #  DETAIL 0 — Flat Minimalist Slot
    # ═══════════════════════════════════════════════
    if detail == 0:
        # Flat dark cavity bed inside
        d.rectangle((inner, inner, far_inner, far_inner), fill=cavity)
        # Flat solid rail
        d.rectangle((outer, outer, far, far), outline=rail, width=thickness)
        # Clean 1px dark ink border on the outside
        d.rectangle((outer - 1, outer - 1, far + 1, far + 1), outline=ink, width=1)
        if shadow:
            return _item_shadow(im, ink, shadow, p)
        return p.finish(im)

    # ═══════════════════════════════════════════════
    #  DETAIL >= 1 — Cavity Bed with Depth
    # ═══════════════════════════════════════════════
    d.rectangle((inner, inner, far_inner, far_inner), fill=cavity)

    if has_texture and detail >= 2:
        for y in range(inner, far_inner + 1):
            for x in range(inner, far_inner + 1):
                if (x * 13 + y * 23) % 29 == 0:
                    d.point((x, y), fill=blend(cavity, p.gem, 0.12))

    # Cavity inset shadow (top + left darker, bottom + right lighter)
    d.line((inner, inner, far_inner, inner), fill=cavity_shadow)
    d.line((inner, inner, inner, far_inner), fill=cavity_shadow)
    d.line((inner, far_inner, far_inner, far_inner), fill=cavity_light)
    d.line((far_inner, inner, far_inner, far_inner), fill=cavity_light)

    if detail >= 3:
        # Double cavity depth for ornate level
        d.line((inner + 1, inner + 1, far_inner - 1, inner + 1), fill=blend(cavity, cavity_shadow, 0.45))
        d.line((inner + 1, inner + 1, inner + 1, far_inner - 1), fill=blend(cavity, cavity_shadow, 0.45))

    # ═══════════════════════════════════════════════
    #  DETAIL 1 — Chi Tiết Hơn 1 Chút (2.5D Beveled Rail)
    # ═══════════════════════════════════════════════
    if detail == 1:
        # Top rail: light on top, dark on bottom
        d.rectangle((outer, outer, far, inner - 1), fill=rail)
        d.line((outer, outer, far, outer), fill=light)
        d.line((outer, inner - 1, far, inner - 1), fill=dark)
        # Bottom rail: dark on top, ink on bottom
        d.rectangle((outer, far_inner + 1, far, far), fill=rail)
        d.line((outer, far_inner + 1, far, far_inner + 1), fill=dark)
        d.line((outer, far, far, far), fill=ink)
        # Left rail: light on left, dark on right
        d.rectangle((outer, outer, inner - 1, far), fill=rail)
        d.line((outer, outer, outer, far), fill=light)
        d.line((inner - 1, outer, inner - 1, far), fill=dark)
        # Right rail: dark on left, ink on right
        d.rectangle((far_inner + 1, outer, far, far), fill=rail)
        d.line((far_inner + 1, outer, far_inner + 1, far), fill=dark)
        d.line((far, outer, far, far), fill=ink)
        # 1px ink frame outline
        d.rectangle((outer - 1, outer - 1, far + 1, far + 1), outline=ink, width=1)

        if shadow:
            return _item_shadow(im, ink, shadow, p)
        return p.finish(im)

    # ═══════════════════════════════════════════════
    #  DETAIL >= 2 — 1 Chút Nữa (Full 3D Raised Rails)
    # ═══════════════════════════════════════════════

    # Top rail
    d.rectangle((outer, outer, far, inner - 1), fill=rail)
    d.line((outer, outer, far, outer), fill=ink)
    if thickness >= 2:
        d.line((outer, outer + 1, far, outer + 1), fill=light)
    if thickness >= 3:
        d.line((outer, inner - 2, far, inner - 2), fill=mid)
    d.line((outer, inner - 1, far, inner - 1), fill=dark)

    # Bottom rail
    d.rectangle((outer, far_inner + 1, far, far), fill=rail)
    d.line((outer, far_inner + 1, far, far_inner + 1), fill=dark)
    if thickness >= 3:
        d.line((outer, far - 1, far, far - 1), fill=mid)
    if thickness >= 2:
        d.line((outer, far - (1 if thickness < 3 else 0), far, far - (1 if thickness < 3 else 0)), fill=dark)
    d.line((outer, far, far, far), fill=ink)

    # Left rail
    d.rectangle((outer, outer, inner - 1, far), fill=rail)
    d.line((outer, outer, outer, far), fill=ink)
    if thickness >= 2:
        d.line((outer + 1, outer, outer + 1, far), fill=light)
    if thickness >= 3:
        d.line((inner - 2, outer, inner - 2, far), fill=mid)
    d.line((inner - 1, outer, inner - 1, far), fill=dark)

    # Right rail
    d.rectangle((far_inner + 1, outer, far, far), fill=rail)
    d.line((far_inner + 1, outer, far_inner + 1, far), fill=dark)
    if thickness >= 3:
        d.line((far - 1, outer, far - 1, far), fill=mid)
    if thickness >= 2:
        d.line((far - (1 if thickness < 3 else 0), outer, far - (1 if thickness < 3 else 0), far), fill=dark)
    d.line((far, outer, far, far), fill=ink)

    # Texture grain on rails (detail >= 2)
    if has_texture and thickness >= 2:
        if style == 'wood':
            grain_y = outer + 1 + (thickness - 2)
            for x in range(outer + 2, far - 1, 5):
                d.point((x, grain_y), fill=blend(rail, light, 0.35))
                if x + 1 <= far - 1:
                    d.point((x + 1, grain_y), fill=blend(rail, light, 0.2))
        elif style == 'jade':
            for x in range(outer + 4, far - 3, 7):
                d.point((x, outer + max(1, thickness // 2)), fill=blend(rail, gem_col, 0.28))

    # ═══════════════════════════════════════════════
    #  Corner Brackets (controlled by crest, detail >= 2)
    # ═══════════════════════════════════════════════
    if has_crest:
        corners = [
            (outer, outer, 1, 1),       # top-left
            (far, outer, -1, 1),        # top-right
            (outer, far, 1, -1),        # bottom-left
            (far, far, -1, -1)          # bottom-right
        ]
        for cx, cy, sx, sy in corners:
            bracket_size = thickness + 1

            if detail >= 3:
                # ═══════════════════════════════════════════════
                #  DETAIL 3 — 1 Chút Nữa..... (Ornate Antique with Gem Glint)
                # ═══════════════════════════════════════════════
                # Dual-layer metal L-bracket
                for i in range(bracket_size + 2):
                    d.point((cx + i * sx, cy), fill=trim)
                    d.point((cx, cy + i * sy), fill=trim)
                for i in range(1, bracket_size + 1):
                    d.point((cx + i * sx, cy + sy), fill=trim)
                    d.point((cx + sx, cy + i * sy), fill=trim)
                # Bracket contour
                d.point((cx + (bracket_size + 1) * sx, cy + sy), fill=ink)
                d.point((cx + sx, cy + (bracket_size + 1) * sy), fill=ink)
                # Top-left corner specular highlight
                d.point((cx, cy), fill=(255, 252, 230) if (sx == 1 and sy == 1) else light)
                # 3D Gem / Rivet Inlay at corner center
                gx, gy = cx + 2 * sx, cy + 2 * sy
                d.point((gx, gy), fill=gem_col)
                # Specular white sparkle
                d.point((gx - (sx if sx > 0 else 0), gy - (sy if sy > 0 else 0)), fill=(255, 255, 255))
                # Shadow drop under gem
                d.point((gx + (sx if sx > 0 else 0), gy + (sy if sy > 0 else 0)), fill=ink)
            else:
                # DETAIL 2 — Clean L-bracket
                for i in range(bracket_size):
                    d.point((cx + i * sx, cy), fill=trim)
                    d.point((cx, cy + i * sy), fill=trim)
                d.point((cx, cy), fill=light)

    if shadow:
        return _item_shadow(im, ink, shadow, p)
    return p.finish(im)


def _item_shadow(im, ink, shadow, p):
    """Apply drop shadow behind item frame."""
    sh = Image.new('RGBA', (48, 48))
    alpha = im.getchannel('A')
    expanded = alpha.filter(ImageFilter.MaxFilter(3))
    sh.paste((*ink, min(90, 40 + shadow * 15)), (0, 0), expanded)
    result = Image.new('RGBA', (48, 48))
    offset = min(2, shadow)
    result.alpha_composite(sh, (offset, offset))
    result.alpha_composite(im)
    return p.finish(result)


def item_parts(p):
    """Modular item slot parts: rail-h (32x16), rail-v (16x32), corner cap (16x16), and cavity bg (32x32)."""
    style = p.s.get('frameStyle', 'bamboo')
    border = p.s.get('border', 5)
    detail = p.s.get('detail', 2)
    shadow = p.s.get('shadow', 0)
    has_crest = p.s.get('crest', True)
    has_texture = p.s.get('texture', True)
    corner_type = p.s.get('corner', 'cloud' if style == 'wood' else ('fret' if style == 'jade' else 'leaves'))

    rail = p.rail
    trim = p.trim
    ink = p.outline
    light = p.light
    dark = p.dark
    mid = blend(rail, light, 0.25)
    gem_col = p.jewel_col
    cavity = p.base
    cavity_shadow = blend(cavity, ink, 0.6)
    cavity_light = blend(cavity, light, 0.2)

    thickness = 1 if border <= 3 else (2 if border <= 5 else (3 if border <= 7 else 4))
    rail_top = 2
    rail_bot = rail_top + thickness - 1

    # --- 1. Horizontal Rail (piece-item-rail-h: 32x16) ---
    rail_h = Image.new('RGBA', (32, 16))
    dh = ImageDraw.Draw(rail_h)
    dh.line((0, rail_top - 1, 31, rail_top - 1), fill=ink)
    dh.rectangle((0, rail_top, 31, rail_bot), fill=rail)
    if detail == 0:
        pass
    elif detail == 1:
        dh.line((0, rail_top, 31, rail_top), fill=light)
        dh.line((0, rail_bot, 31, rail_bot), fill=dark)
    else:
        dh.line((0, rail_top, 31, rail_top), fill=ink)
        if thickness >= 2:
            dh.line((0, rail_top + 1, 31, rail_top + 1), fill=light)
        if thickness >= 3:
            dh.line((0, rail_bot - 1, 31, rail_bot - 1), fill=mid)
        dh.line((0, rail_bot, 31, rail_bot), fill=dark)
    dh.line((0, rail_bot + 1, 31, rail_bot + 1), fill=ink)

    if has_texture and detail >= 2 and thickness >= 2:
        if style == 'wood':
            for x in range(2, 31, 5):
                dh.point((x, rail_top + 1), fill=blend(rail, light, 0.35))
                if x + 1 < 32:
                    dh.point((x + 1, rail_top + 1), fill=blend(rail, light, 0.2))
        elif style == 'jade':
            for x in range(4, 30, 7):
                dh.point((x, rail_top + max(1, thickness // 2)), fill=blend(rail, gem_col, 0.28))
        elif style == 'bamboo':
            for x in range(3, 31, 8):
                dh.point((x, rail_top), fill=blend(rail, trim, 0.4))

    # --- 2. Vertical Rail (piece-item-rail-v: 16x32) ---
    rail_v = rail_h.transpose(Image.Transpose.TRANSPOSE)

    # --- 3. Corner Cap (piece-item-corner: 16x16) ---
    corner = Image.new('RGBA', (16, 16))
    dc = ImageDraw.Draw(corner)
    dc.rectangle((rail_top, rail_top, 15, rail_bot), fill=rail)
    dc.rectangle((rail_top, rail_top, rail_bot, 15), fill=rail)
    dc.line([(rail_top - 1, 15), (rail_top - 1, rail_top - 1), (15, rail_top - 1)], fill=ink)
    dc.line([(rail_bot + 1, 15), (rail_bot + 1, rail_bot + 1), (15, rail_bot + 1)], fill=ink)
    if detail == 1:
        dc.line([(rail_top, 15), (rail_top, rail_top), (15, rail_top)], fill=light)
        dc.line([(rail_bot, 15), (rail_bot, rail_bot), (15, rail_bot)], fill=dark)
    elif detail >= 2:
        dc.line([(rail_top, 15), (rail_top, rail_top), (15, rail_top)], fill=ink)
        if thickness >= 2:
            dc.line([(rail_top + 1, 15), (rail_top + 1, rail_top + 1), (15, rail_top + 1)], fill=light)
        dc.line([(rail_bot, 15), (rail_bot, rail_bot), (15, rail_bot)], fill=dark)
        dc.line([(rail_top, rail_top), (rail_bot, rail_bot)], fill=blend(rail, ink, 0.35))

    if has_crest and detail >= 2:
        bracket_size = thickness + 2
        cx, cy = rail_top, rail_top
        if detail >= 3:
            for i in range(bracket_size + 2):
                dc.point((cx + i, cy), fill=trim)
                dc.point((cx, cy + i), fill=trim)
            for i in range(1, bracket_size + 1):
                dc.point((cx + i, cy + 1), fill=trim)
                dc.point((cx + 1, cy + i), fill=trim)
            dc.point((cx + bracket_size + 1, cy + 1), fill=ink)
            dc.point((cx + 1, cy + bracket_size + 1), fill=ink)
            dc.point((cx, cy), fill=(255, 252, 230))
            gx, gy = cx + 2, cy + 2
            dc.point((gx, gy), fill=gem_col)
            dc.point((gx - 1, gy - 1), fill=(255, 255, 255))
            dc.point((gx + 1, gy + 1), fill=ink)
            if corner_type == 'cloud':
                dc.point((cx + bracket_size + 2, cy), fill=trim)
                dc.point((cx, cy + bracket_size + 2), fill=trim)
            elif corner_type == 'fret':
                dc.point((cx + bracket_size, cy + 2), fill=trim)
                dc.point((cx + 2, cy + bracket_size), fill=trim)
        else:
            for i in range(bracket_size):
                dc.point((cx + i, cy), fill=trim)
                dc.point((cx, cy + i), fill=trim)
            dc.point((cx, cy), fill=light)

    # --- 4. Background / Cavity (piece-item-bg: 32x32) ---
    bg = Image.new('RGBA', (32, 32), cavity)
    dbg = ImageDraw.Draw(bg)
    if has_texture and detail >= 2:
        for y in range(32):
            for x in range(32):
                if (x * 13 + y * 23) % 29 == 0:
                    dbg.point((x, y), fill=blend(cavity, p.gem, 0.12))
    if detail >= 1:
        dbg.line((0, 0, 31, 0), fill=cavity_shadow)
        dbg.line((0, 0, 0, 31), fill=cavity_shadow)
        dbg.line((0, 31, 31, 31), fill=cavity_light)
        dbg.line((31, 0, 31, 31), fill=cavity_light)
    if detail >= 3:
        dbg.line((1, 1, 30, 1), fill=blend(cavity, cavity_shadow, 0.45))
        dbg.line((1, 1, 1, 30), fill=blend(cavity, cavity_shadow, 0.45))

    return {
        'rail-h': rail_h,
        'rail-v': rail_v,
        'corner': corner,
        'bg': bg,
    }



def tile_sheet(p, family):
    if family == 'item':
        return make_item_sheet(p)
    im = Image.new('RGBA', (48, 48))
    d = ImageDraw.Draw(im)
    bamboo = family == 'bamboo'
    rail = blend(p.gem, p.base, 0.4) if bamboo else p.metal
    light = blend(p.gem, (216, 228, 178), 0.6) if bamboo else p.light
    dark = blend(p.base, (9, 20, 15), 0.45) if bamboo else p.dark
    for y in (4, 36):
        d.rectangle((4, y, 40, y + 4), fill=dark)
        d.line((4, y + 1, 40, y + 1), fill=light)
        d.line((4, y + 2, 40, y + 2), fill=rail)
    for x in (4, 36):
        d.rectangle((x, 4, x + 4, 40), fill=dark)
        d.line((x + 1, 4, x + 1, 40), fill=light)
        d.line((x + 2, 4, x + 2, 40), fill=rail)
    if bamboo:
        for x in (8, 24, 38):
            for y in (4, 36):
                d.line((x, y, x, y + 4), fill=dark)
                d.line((x + 1, y, x + 1, y + 4), fill=rail)
        for y in (8, 24, 38):
            for x in (4, 36):
                d.line((x, y, x + 4, y), fill=dark)
                d.line((x, y + 1, x + 4, y + 1), fill=rail)
    else:
        d.rectangle((9, 9, 35, 35), outline=blend(p.gem, p.base, 0.35))
    for x, y, sx, sy in [(6, 6, 1, 1), (38, 6, -1, 1), (6, 38, 1, -1), (38, 38, -1, -1)]:
        def pts(values):
            return [(x + a * sx, y + b * sy) for a, b in values]
        if bamboo:
            for k in range(3):
                d.line(pts([(-2 + k, 3), (3 + k, -2)]), fill=p.light if k == 1 else p.metal)
            if p.s['detail']:
                for leaf in [[(1, 2), (8, 4), (10, 9), (5, 6)], [(2, 1), (8, 0), (12, 3), (7, 3)]]:
                    d.polygon(pts(leaf), fill=rail)
                    d.line(pts(leaf[:3]), fill=light)
        elif family == 'skill':
            d.polygon(pts([(0, 0), (7, 0), (7, 2), (3, 3), (2, 7), (0, 7)]), fill=p.metal)
            d.line(pts([(1, 6), (1, 1), (6, 1)]), fill=p.light)
            if p.s['detail']:
                d.line(pts([(4, 7), (7, 7), (7, 4), (5, 4)]), fill=p.gem)
        elif family == 'item':
            d.line(pts([(0, 6), (0, 0), (6, 0)]), fill=p.light, width=1)
            d.point((x + 2 * sx, y + 2 * sy), fill=p.gem)
        else:
            d.polygon(pts([(0, 2), (2, 0), (5, 2), (2, 5)]), fill=p.dark)
            d.line(pts([(0, 2), (2, 0), (5, 2)]), fill=p.light)
            d.point((x + 2 * sx, y + 2 * sy), fill=p.gem)
    return p.finish(im)


def bamboo_parts(p):
    rail, light, ink, trim, gem = frame_palette(p, 'bamboo')
    shade = blend(rail, ink, 0.6)
    def finish(image,outline=True):
        alpha=image.getchannel('A');expanded=alpha.filter(ImageFilter.MaxFilter(3)) if outline else alpha
        result=Image.new('RGBA',image.size)
        if p.s.get('shadow') and p.s.get('enableShadow', True):
            shadow=Image.new('RGBA',image.size);shadow.paste((*ink[:3],min(90,40+p.s['shadow']*15)),(0,0),expanded)
            offset=min(2,p.s['shadow']);result.alpha_composite(shadow,(offset,offset))
        if outline:result.paste(ink,(0,0),ImageChops.subtract(expanded,alpha))
        result.alpha_composite(image);return result
    horizontal=Image.new('RGBA',(32,16));d=ImageDraw.Draw(horizontal)
    # Continuous cylinder at both ends of the tile; only one slim raised node.
    # Avoid flared end caps, which made each repeat look like a metal fitting.
    thickness=p.s['border']-1;top=5-(thickness-4)//2;bottom=top+thickness-1
    d.rectangle((0,top,31,bottom),fill=rail)
    d.line((0,top,31,top),fill=blend(rail,light,.7))
    d.line((0,top+1,31,top+1),fill=blend(rail,light,.25))
    d.line((0,bottom,31,bottom),fill=shade)
    d.line((2,top-1,2,bottom+1),fill=shade)
    d.line((3,top-1,3,bottom+1),fill=trim)
    d.point((3,top-1),fill=light)
    d.line((3,top,3,bottom-1),fill=blend(trim,light,.5))
    d.point((3,bottom+1),fill=shade)
    if p.s['texture']:
        d.line((13,top+2,18,top+2),fill=blend(rail,light,.3))
        d.point((23,top+2),fill=shade)
    horizontal=finish(horizontal)
    vertical=horizontal.transpose(Image.Transpose.TRANSPOSE)
    leaves=Image.new('RGBA',(32,32));d=ImageDraw.Draw(leaves)
    d.line([(6,7),(8,8),(10,11),(13,14),(18,17)],fill=shade)
    d.line([(8,8),(10,9),(14,9)],fill=shade)
    d.line([(10,11),(9,15),(10,20)],fill=shade)
    leaf_shapes=[
        ([(9,9),(14,6),(20,5),(26,6),(20,7),(14,9)],[(12,8),(19,6),(24,6)]),
        ([(14,12),(19,11),(24,13),(28,17),(23,15),(19,14)],[(17,12),(22,13),(26,15)]),
        ([(14,15),(19,16),(23,20),(26,25),(21,21),(17,19)],[(16,16),(20,19),(24,23)]),
        ([(9,12),(7,17),(7,22),(5,28),(5,21),(6,16)],[(8,15),(6,22),(5,26)]),
        ([(10,18),(13,21),(14,26),(13,29),(11,25),(10,22)],[(11,20),(12,24),(13,27)]),
    ]
    for polygon,vein in leaf_shapes:
        d.polygon(polygon,fill=rail)
        d.line(polygon[:3],fill=shade)
        if p.s['crest']:d.line(vein,fill=blend(rail,light,.48))
        if p.s['detail']:d.point(vein[0],fill=light)
    if p.s['corner']=='cloud':
        d.line([(4,10),(4,6),(7,4),(10,5),(10,8),(8,9),(7,7)],fill=light)
    elif p.s['corner']=='fret':
        d.line([(4,11),(4,4),(11,4),(11,8),(8,8)],fill=light)
    elif p.s['corner']=='cut':
        d.line([(4,9),(4,6),(6,4),(9,4)],fill=light)
    # Leaves already carry their own dark contour: expanding the alpha would
    # turn the narrow tips into the blocky foliage the reference does not have.
    return {'horizontal':horizontal,'vertical':vertical,'leaves':finish(leaves,False)}


def add_segments(assets,p):
    for family in FAMILIES:
        sheet=tile_sheet(p,family)
        for part,x,y in POSITIONS:
            key=f'piece-{family}-{part}'
            assets[key]={'image':sheet.crop((x*16,y*16,x*16+16,y*16+16)), 'kind':'piece','margins':None,
                         'name':f'{FAMILIES[family]} / {PART_NAMES[part]}','family':family,'part':part}
            if family in ('bamboo','item','button'):assets[key]['kind']='legacy'
    for part,image in bamboo_parts(p).items():
        assets[f'piece-bamboo-{part}']={'image':image,'kind':'piece','margins':None,'family':'bamboo','part':part,
                                      'name':{'horizontal':'Một đốt tre ngang','vertical':'Một đốt tre dọc','leaves':'Cụm lá góc · lớp phủ'}[part]}
    for part,image in item_parts(p).items():
        assets[f'piece-item-{part}']={'image':image,'kind':'piece','margins':None,'family':'item','part':part,
                                    'name':{'rail-h':'Thanh ngang viền','rail-v':'Thanh dọc viền','corner':'Cụm góc viền','bg':'Nền ô (lòng khung)'}[part]}
    assets['piece-skill-ring']={'image':skill_ring(p),'kind':'legacy','margins':None,'family':'skill','part':'ring','name':'Vòng chiêu · nguồn cũ'}
    for key in list(assets):
        if key.startswith('piece-skill-') and key!='piece-skill-ring':assets[key]['kind']='legacy'
    for style in ('bamboo','wood','jade'):
        for part,image in rail_parts(p,style).items():
            assets[f'piece-{style}-{part}']={'image':image,'kind':'piece','margins':None,
                'name':f'{dict(bamboo="Trúc",wood="Gỗ",jade="Ngọc")[style]} / {dict({"rail-h":"Thanh ngang","rail-v":"Thanh dọc","corner":"Góc phủ"})[part]}',
                'family':style,'part':part}
    btn_names={'rail-h':'Thanh ngang','rail-v':'Thanh dọc','corner':'Cụm góc ngọc','bg':'Nền nút','text-bg':'Nền bảng chữ'}
    for part,image in {**btn_parts(p,p.s['frameStyle']),**btn_backgrounds(p)}.items():
        assets[f'piece-btn-{part}']={'image':image,'kind':'piece','margins':None,'family':'button','part':part,
                                    'name':f'Nút & bảng chữ / {btn_names[part]}'}
    bar_names={'rail-h':'Thanh ngang','rail-v':'Thanh dọc','corner':'Cụm góc','bg':'Nền lòng thanh'}
    for part,image in bar_parts(p,p.s['frameStyle']).items():
        assets[f'piece-bar-{part}']={'image':image,'kind':'piece','margins':None,'family':'bar','part':part,
                                    'name':f'Khí mạch / {bar_names[part]}'}
    for key,(name,family,w,h,kind) in FRAME_SPECS.items():
        style=p.s['frameStyle']
        enable_shadow = p.s.get('enableShadow', True)
        shadow_val = p.s.get('shadow', 3) if enable_shadow else 0
        palette_list = [list(c) for c in frame_palette(p, style)]
        if family=='bar':
            pieces={'rail-h':'piece-bar-rail-h','rail-v':'piece-bar-rail-v','corner':'piece-bar-corner','bg':'piece-bar-bg'}
            recipe={'family':'bar','cell':8,'mode':'bar','showBg':p.s.get('showBg',False),
                    'shadow':0,'enableShadow':False,'palette':palette_list,'pieces':pieces}
        elif family=='button':
            T=btn_thickness(p)
            pieces={part:f'piece-btn-{part}' for part in ('rail-h','rail-v','corner')}
            recipe={'family':'button','cell':16,'mode':'rails',
                    'shadow':0,'enableShadow':False,'palette':palette_list,'pieces':pieces}
        elif family=='text-panel':
            T=btn_thickness(p)
            pieces={part:f'piece-btn-{part}' for part in ('rail-h','rail-v','corner')}
            pieces['bg']='piece-btn-text-bg'
            recipe={'family':'text-panel','cell':16,'mode':'rails','cavity':T+3,'showBg':p.s.get('showBg',True),
                    'shadow':0,'enableShadow':False,'palette':palette_list,'pieces':pieces}
        elif family=='item':

            recipe={'family':'item','cell':16,'mode':'item',
                    'showBg':p.s.get('showBg',True),'border':p.s.get('border',5),
                    'shadow':shadow_val,'enableShadow':enable_shadow,'palette':palette_list,
                    'pieces':{part:f'piece-item-{part}' for part in ('corner','rail-h','rail-v','bg')}}
        elif style=='bamboo':
            recipe={'family':family,'cell':16,'shadow':shadow_val,'enableShadow':enable_shadow,'palette':palette_list,
                    'pieces':{part:f'piece-{family}-{part}' for part,_,_ in POSITIONS}}
            if family=='bamboo':
                recipe.update(mode='bamboo',pieces={part:f'piece-bamboo-{part}' for part in ('horizontal','vertical','leaves')})
            if family=='skill':
                recipe.update(mode='circle',pieces={},palette=palette_list,
                    border=p.s['border'],detail=p.s['detail'],shadow=shadow_val,enableShadow=enable_shadow,texture=p.s['texture'],crest=p.s['crest'],corner=p.s['corner'],frameStyle='bamboo',color=list(p.light),stroke=max(1,p.s['border']-4))
        else:
            recipe={'family':style,'cell':16,'mode':'rails','shadow':shadow_val,'enableShadow':enable_shadow,'palette':palette_list,
                    'pieces':{part:f'piece-{style}-{part}' for part in ('rail-h','rail-v','corner')}}
            if key=='frame-panel':w,h=p.s['width'],p.s['height']
            if family=='skill':recipe.update(mode='ornate',pieces={},palette=palette_list,
                border=p.s['border'],detail=p.s['detail'],shadow=shadow_val,enableShadow=enable_shadow,texture=p.s['texture'],crest=p.s['crest'],corner=p.s['corner'],frameStyle=style)
        if kind=='scrollbar':recipe.update(mode='outline',pieces={},color=list(p.light),inset=[11,2] if key.endswith('-v') else [2,11])
        if kind=='inventory':recipe['inventory']=True
        if key=='frame-panel' and style!='bamboo':name=dict(wood='Khung gỗ · góc mây',jade='Khung ngọc ghép')[style]
        assets[key]={'image':Image.new('RGBA',(w,h)),'kind':kind,'margins':[16]*4,'name':name,'recipe':recipe}
    refresh_frames(assets)
    # Tileable backgrounds are independent layers; no frame has a baked fill.
    for key,name,color in [('background-jade','Nền ngọc tối',p.base),
                           ('background-paper','Nền giấy trúc',blend(p.light,(225,216,173),.8)),
                           ('background-cloth','Nền vải xanh',blend(p.base,p.gem,.15))]:
        im=Image.new('RGBA',(32,32),tuple(color)+(255,));d=ImageDraw.Draw(im)
        if p.s['texture']:
            for y in range(32):
                for x in range(32):
                    if (x*17+y*31)%43==0:d.point((x,y),fill=blend(color,(0,0,0),.06))
        assets[key]={'image':im,'kind':'background','margins':None,'name':name,
                     'recipe':{'family':'background','cell':32,'mode':'tile','pieces':{'tile':f'{key}-tile'}}}
        assets[f'{key}-tile']={'image':im.copy(),'kind':'piece','margins':None,'name':f'{name} / tile','family':'background','part':'tile'}


def placements(recipe,w,h):
    c=16;parts=recipe['pieces'];out=[]
    if recipe.get('mode')=='item':
        show_bg = recipe.get('showBg', True)
        border = recipe.get('border', 5)
        thickness = 1 if border <= 3 else (2 if border <= 5 else (3 if border <= 7 else 4))
        cavity_start = 2 + thickness + 1
        cw, ch = 16, 16
        if show_bg and 'bg' in parts:
            bw = w - cavity_start * 2
            bh = h - cavity_start * 2
            if bw > 0 and bh > 0:
                out.append((parts['bg'], cavity_start, cavity_start, bw, bh, False, False))
        for x in range(cw, w - cw, 32):
            length = min(32, w - cw - x)
            if length > 0:
                out.append((parts['rail-h'], x, 0, length, 16, False, False))
                out.append((parts['rail-h'], x, h - 16, length, 16, False, True))
        for y in range(ch, h - ch, 32):
            length = min(32, h - ch - y)
            if length > 0:
                out.append((parts['rail-v'], 0, y, 16, length, False, False))
                out.append((parts['rail-v'], w - 16, y, 16, length, True, False))
        for x, y, fx, fy in [(0, 0, False, False), (w - cw, 0, True, False), (0, h - ch, False, True), (w - cw, h - ch, True, True)]:
            out.append((parts['corner'], x, y, cw, ch, fx, fy))
        return out
    if recipe.get('mode')=='bar':
        cw, ch = 8, 8
        show_bg = recipe.get('showBg', False)
        if show_bg and 'bg' in parts:
            bw = w - 8
            bh = h - 8
            if bw > 0 and bh > 0:
                out.append((parts['bg'], 4, 4, bw, bh, False, False))
        for x in range(cw, w - cw, 32):
            length = min(32, w - cw - x)
            if length > 0:
                out.append((parts['rail-h'], x, 0, length, 8, False, False))
                out.append((parts['rail-h'], x, h - 8, length, 8, False, True))
        for y in range(ch, h - ch, 32):
            length = min(32, h - ch - y)
            if length > 0:
                out.append((parts['rail-v'], 0, y, 8, length, False, False))
                out.append((parts['rail-v'], w - 8, y, 8, length, True, False))
        for x, y, fx, fy in [(0, 0, False, False), (w - cw, 0, True, False), (0, h - ch, False, True), (w - cw, h - ch, True, True)]:
            out.append((parts['corner'], x, y, cw, ch, fx, fy))
        return out
    if recipe.get('mode')=='rails':
        cw, ch = 16, 16
        if 'bg' in parts and recipe.get('showBg', True):
            cv = recipe.get('cavity', 3)
            if w - cv * 2 > 0 and h - cv * 2 > 0:
                out.append((parts['bg'], cv, cv, w - cv * 2, h - cv * 2, False, False))
        for x in range(cw, w - cw, 32):
            length = min(32, w - cw - x)
            if length > 0:
                out.append((parts['rail-h'], x, 0, length, 16, False, False))
                out.append((parts['rail-h'], x, h - 16, length, 16, False, True))
        for y in range(ch, h - ch, 32):
            length = min(32, h - ch - y)
            if length > 0:
                out.append((parts['rail-v'], 0, y, 16, length, False, False))
                out.append((parts['rail-v'], w - 16, y, 16, length, True, False))
        for x, y, fx, fy in [(0, 0, False, False), (w - cw, 0, True, False), (0, h - ch, False, True), (w - cw, h - ch, True, True)]:
            out.append((parts['corner'], x, y, cw, ch, fx, fy))
        return out
    if recipe.get('mode')=='ring':return [(parts['ring'],0,0,w,h,False,False)]
    if recipe.get('mode')=='tile':
        return [(parts['tile'],x,y,min(32,w-x),min(32,h-y),False,False) for y in range(0,h,32) for x in range(0,w,32)]
    if recipe.get('mode')=='bamboo':
        for x in range(4,w-4,32):
            length=min(32,w-4-x)
            out.extend([(parts['horizontal'],x,0,length,16,False,False),(parts['horizontal'],x,h-13,length,16,False,False)])
        for y in range(4,h-4,32):
            length=min(32,h-4-y)
            out.extend([(parts['vertical'],0,y,16,length,False,False),(parts['vertical'],w-13,y,16,length,False,False)])
        # Leaf overlays contain no rails. One leaf texture is mirrored at corners.
        for x,y,fx,fy in [(0,0,False,False),(w-32,0,True,False),(0,h-32,False,True),(w-32,h-32,True,True)]:
            out.append((parts['leaves'],x,y,32,32,fx,fy))
        return out
    for y in range(c,h-c,c):
        for x in range(c,w-c,c):out.append((parts['center'],x,y,min(c,w-c-x),min(c,h-c-y)))
    for x in range(c,w-c,c):
        out.extend([(parts['top'],x,0,min(c,w-c-x),c),(parts['bottom'],x,h-c,min(c,w-c-x),c)])
    for y in range(c,h-c,c):
        out.extend([(parts['left'],0,y,c,min(c,h-c-y)),(parts['right'],w-c,y,c,min(c,h-c-y))])
    for part,x,y in [('tl',0,0),('tr',w-c,0),('bl',0,h-c),('br',w-c,h-c)]:out.append((parts[part],x,y,c,c))
    return [(*item,False,False) for item in out]


def inventory_cells(w,h):
    size=40;gap=4;cols=max(1,(w-32+gap)//(size+gap));rows=max(1,(h-68+gap)//(size+gap))
    left=(w-(cols*44-4))//2
    return [(left+col*44,38+row*44,size,size) for row in range(rows) for col in range(cols)]


def compose(assets,recipe,w,h):
    if recipe.get('mode') in ('ornate','circle'):return ornate_ring(min(w,h),recipe)
    if recipe.get('mode')=='outline':
        im=Image.new('RGBA',(w,h));ix,iy=recipe['inset']
        ImageDraw.Draw(im).rectangle((ix,iy,w-ix-1,h-iy-1),outline=tuple(recipe['color']),width=1)
        return im
    if recipe.get('mode')=='ring':return assets[recipe['pieces']['ring']]['image'].resize((w,h),Image.Resampling.NEAREST)
    im=Image.new('RGBA',(w,h))
    for key,x,y,tw,th,fx,fy in placements(recipe,w,h):
        if key not in assets: continue
        part=assets[key]['image']
        if key.endswith('-bg'):
            if tw > 0 and th > 0:
                part = part.resize((tw, th), Image.Resampling.NEAREST)
        else:
            part = part.crop((0,0,min(tw,part.width),min(th,part.height)))
        if fx:part=part.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if fy:part=part.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        im.alpha_composite(part,(x,y))
    if recipe.get('inventory'):
        slot=compose(assets,assets['frame-item']['recipe'],40,40)
        for x,y,_,_ in inventory_cells(w,h):im.alpha_composite(slot,(x,y))
    if recipe.get('enableShadow', True) and recipe.get('shadow', 0) > 0 and recipe.get('mode') in ('item', 'rails', 'bamboo', 'bar'):
        shadow_val = recipe.get('shadow', 0)
        sh = Image.new('RGBA', (w, h))
        alpha = im.getchannel('A')
        expanded = alpha.filter(ImageFilter.MaxFilter(3))
        sh.paste((8, 14, 12, min(90, 40 + shadow_val * 15)), (0, 0), expanded)
        res = Image.new('RGBA', (w, h))
        if recipe.get('mode') == 'item':
            res.alpha_composite(sh, (0, 0))
        else:
            offset = min(2, shadow_val)
            res.alpha_composite(sh, (offset, offset))
        res.alpha_composite(im)
        im = res
    return im


def refresh_frames(assets):
    for asset in assets.values():
        if asset.get('recipe'):asset['image']=compose(assets,asset['recipe'],*asset['image'].size)
