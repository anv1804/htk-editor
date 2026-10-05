"""Reusable 16px frame pieces. Repeat edges; never stretch corner artwork."""
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
    d.rectangle((4,4,43,43),outline=light,width=1)
    return im


def circle_image(size,color):
    """Midpoint circle: opaque, single-colour 1px contour at native resolution."""
    im=Image.new('RGBA',(size,size));cx=cy=size//2
    x=size//2-3;y=0;error=1-x
    while x>=y:
        for dx,dy in ((x,y),(y,x),(-y,x),(-x,y),(-x,-y),(-y,-x),(y,-x),(x,-y)):
            im.putpixel((cx+dx,cy+dy),tuple(color)+(255,))
        y+=1
        if error<0:error+=2*y+1
        else:x-=1;error+=2*(y-x)+1
    return im


def skill_ring(p):return circle_image(64,green_palette(p)[1])


def tile_sheet(p,family):
    # Draw one continuous source, then slice it. Shadows and rail highlights
    # cross slice boundaries continuously; no end caps on repeating edges.
    if family!='bamboo':return simple_frame(p)
    im=Image.new('RGBA',(48,48));d=ImageDraw.Draw(im)
    bamboo=family=='bamboo'
    # Frames have transparent interiors; artwork belongs on a separate layer.
    rail=blend(p.gem,p.base,.4) if bamboo else p.metal
    light=blend(p.gem,(216,228,178),.6) if bamboo else p.light
    dark=blend(p.base,(9,20,15),.45) if bamboo else p.dark
    # Identical rail cross sections at each join (x/y=16 and 32).
    for y in (4,36):
        d.rectangle((4,y,40,y+4),fill=dark)
        d.line((4,y+1,40,y+1),fill=light)
        d.line((4,y+2,40,y+2),fill=rail)
    for x in (4,36):
        d.rectangle((x,4,x+4,40),fill=dark)
        d.line((x+1,4,x+1,40),fill=light)
        d.line((x+2,4,x+2,40),fill=rail)
    if bamboo:
        for x in (8,24,38):
            for y in (4,36):
                d.line((x,y,x,y+4),fill=dark);d.line((x+1,y,x+1,y+4),fill=rail)
        for y in (8,24,38):
            for x in (4,36):
                d.line((x,y,x+4,y),fill=dark);d.line((x,y+1,x+4,y+1),fill=rail)
    else:
        d.rectangle((9,9,35,35),outline=blend(p.gem,p.base,.35))
    for x,y,sx,sy in [(6,6,1,1),(38,6,-1,1),(6,38,1,-1),(38,38,-1,-1)]:
        def pts(values):return [(x+a*sx,y+b*sy) for a,b in values]
        if bamboo:
            for k in range(3):d.line(pts([(-2+k,3),(3+k,-2)]),fill=p.light if k==1 else p.metal)
            if p.s['detail']:
                for leaf in [[(1,2),(8,4),(10,9),(5,6)],[(2,1),(8,0),(12,3),(7,3)]]:
                    d.polygon(pts(leaf),fill=rail);d.line(pts(leaf[:3]),fill=light)
        elif family=='skill':
            d.polygon(pts([(0,0),(7,0),(7,2),(3,3),(2,7),(0,7)]),fill=p.metal)
            d.line(pts([(1,6),(1,1),(6,1)]),fill=p.light)
            if p.s['detail']:d.line(pts([(4,7),(7,7),(7,4),(5,4)]),fill=p.gem)
        elif family=='item':
            d.line(pts([(0,6),(0,0),(6,0)]),fill=p.light,width=1)
            d.point((x+2*sx,y+2*sy),fill=p.gem)
        else:
            d.polygon(pts([(0,2),(2,0),(5,2),(2,5)]),fill=p.dark)
            d.line(pts([(0,2),(2,0),(5,2)]),fill=p.light)
            d.point((x+2*sx,y+2*sy),fill=p.gem)
    return p.finish(im)


def bamboo_parts(p):
    green,light,dark,shade=green_palette(p)
    def finish(image,outline=True):
        alpha=image.getchannel('A');expanded=alpha.filter(ImageFilter.MaxFilter(3)) if outline else alpha
        result=Image.new('RGBA',image.size)
        if p.s['shadow']:
            shadow=Image.new('RGBA',image.size);shadow.paste((8,18,12,95),(0,0),expanded)
            offset=min(2,p.s['shadow']);result.alpha_composite(shadow,(offset,offset))
        if outline:result.paste(dark,(0,0),ImageChops.subtract(expanded,alpha))
        result.alpha_composite(image);return result
    horizontal=Image.new('RGBA',(32,16));d=ImageDraw.Draw(horizontal)
    # Continuous cylinder at both ends of the tile; only one slim raised node.
    # Avoid flared end caps, which made each repeat look like a metal fitting.
    d.rectangle((0,5,31,8),fill=green)
    d.line((0,5,31,5),fill=blend(green,light,.7))
    d.line((0,6,31,6),fill=blend(green,light,.2))
    d.line((0,8,31,8),fill=shade)
    d.line((2,4,2,9),fill=shade)
    d.line((3,4,3,9),fill=green)
    d.point((3,4),fill=light)
    d.line((3,5,3,7),fill=blend(green,light,.5))
    d.point((3,9),fill=shade)
    if p.s['texture']:
        d.line((13,7,18,7),fill=blend(green,light,.3))
        d.point((23,7),fill=shade)
    horizontal=finish(horizontal)
    vertical=horizontal.transpose(Image.Transpose.TRANSPOSE)
    leaves=Image.new('RGBA',(32,32));d=ImageDraw.Draw(leaves)
    # Fine, branching twigs with narrow lanceolate leaves and tapered tips.
    # The branch sprouts at the crossing's inner lip, then bends into the frame.
    # Its short root is covered by the culm instead of forming a detached X.
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
        d.polygon(polygon,fill=green)
        d.line(polygon[:3],fill=shade)
        d.line(vein,fill=blend(green,light,.48))
        if p.s['detail']:d.point(vein[0],fill=light)
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
            if family=='bamboo':assets[key]['kind']='legacy'
    for part,image in bamboo_parts(p).items():
        assets[f'piece-bamboo-{part}']={'image':image,'kind':'piece','margins':None,'family':'bamboo','part':part,
                                      'name':{'horizontal':'Một đốt tre ngang','vertical':'Một đốt tre dọc','leaves':'Cụm lá góc · lớp phủ'}[part]}
    assets['piece-skill-ring']={'image':skill_ring(p),'kind':'legacy','margins':None,'family':'skill','part':'ring','name':'Vòng chiêu · nguồn cũ'}
    for key in list(assets):
        if key.startswith('piece-skill-') and key!='piece-skill-ring':assets[key]['kind']='legacy'
    for key,(name,family,w,h,kind) in FRAME_SPECS.items():
        recipe={'family':family,'cell':16,'pieces':{part:f'piece-{family}-{part}' for part,_,_ in POSITIONS}}
        if family=='bamboo':recipe.update(mode='bamboo',pieces={part:f'piece-bamboo-{part}' for part in ('horizontal','vertical','leaves')})
        if family=='skill':recipe.update(mode='circle',pieces={},color=list(green_palette(p)[1]))
        if kind=='scrollbar':recipe.update(mode='outline',pieces={},color=list(green_palette(p)[1]),inset=[11,2] if key.endswith('-v') else [2,11])
        if kind=='inventory':recipe['inventory']=True
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
    if recipe.get('mode')=='circle':return circle_image(min(w,h),recipe['color'])
    if recipe.get('mode')=='outline':
        im=Image.new('RGBA',(w,h));ix,iy=recipe['inset']
        ImageDraw.Draw(im).rectangle((ix,iy,w-ix-1,h-iy-1),outline=tuple(recipe['color']),width=1)
        return im
    if recipe.get('mode')=='ring':return assets[recipe['pieces']['ring']]['image'].resize((w,h),Image.Resampling.NEAREST)
    im=Image.new('RGBA',(w,h))
    for key,x,y,tw,th,fx,fy in placements(recipe,w,h):
        part=assets[key]['image'].crop((0,0,tw,th))
        if fx:part=part.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if fy:part=part.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        im.alpha_composite(part,(x,y))
    if recipe.get('inventory'):
        slot=compose(assets,assets['frame-item']['recipe'],40,40)
        for x,y,_,_ in inventory_cells(w,h):im.alpha_composite(slot,(x,y))
    return im


def refresh_frames(assets):
    for asset in assets.values():
        if asset.get('recipe'):asset['image']=compose(assets,asset['recipe'],*asset['image'].size)
