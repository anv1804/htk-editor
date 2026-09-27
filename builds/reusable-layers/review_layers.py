from pathlib import Path
import sys,json,zipfile
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from repair_outfit_ui import process_request,encode_png,decode_image

DEST=Path(__file__).parent
FIX=ROOT/'tests/fixtures'
base=Image.open(FIX/'hair_outfit/base.png').convert('RGBA')
sources={'hair':FIX/'hair_outfit/outfit.png'}
sources.update({p.stem:p for p in (FIX/'covered_equipment').glob('*.png')})
layers={}
for name,path in sources.items():
    target=DEST/name;target.mkdir(exist_ok=True)
    result=process_request(dict(base=encode_png(base),outfit=encode_png(Image.open(path)),
        rows=7,cols=4,colors=-1,paint=4,cleanup=0,composition='cutout'))
    layers[name]={key:decode_image(result[key]) for key in ('baseLayer','outfitLayer','headwearLayer','image')}
    for key,image in layers[name].items():image.save(target/(key+'.png'))
    (target/'report.json').write_text(json.dumps(result['report'],indent=2),encoding='utf8')
    print(name,result['paletteColors'],flush=True)

def board(rows,columns,path):
    canvas=Image.new('RGB',(len(columns)*264,len(rows)*280+24),'#292f39')
    draw=ImageDraw.Draw(canvas)
    for i,label in enumerate(columns):draw.text((i*264+8,7),label,fill='#c6d2e0')
    for row,(label,frame,images) in enumerate(rows):
        draw.text((8,row*280+28),label,fill='#c6d2e0')
        x,y=frame%4*64,frame//4*64
        for col,image in enumerate(images):
            tile=image.crop((x,y,x+64,y+64)).convert('RGBA').resize((256,256),Image.Resampling.NEAREST)
            canvas.paste(tile,(col*264+4,row*280+44),tile)
    canvas.save(DEST/path)

hair=layers['hair'];source=Image.open(sources['hair'])
board([(f'Frame {f+1}',f,[source,hair['outfitLayer'],hair['headwearLayer'],hair['image']])
    for f in (0,4,8,12,13,17,27)],['SOURCE','OUTFIT','HAIR + BAND','COMPOSITE'],'comparison.png')
gear=[]
for name in sources:
    if name=='hair':continue
    outfit=layers[name]
    combined=Image.alpha_composite(Image.alpha_composite(outfit['baseLayer'],outfit['outfitLayer']),hair['headwearLayer'])
    combined.save(DEST/name/'with-hair.png')
    # Swapping an outfit must not mutate the reusable source hair asset.
    foreground=np.asarray(hair['headwearLayer'])[:,:,3]>0
    np.testing.assert_array_equal(np.asarray(combined)[foreground],np.asarray(hair['headwearLayer'])[foreground])
    gear.append((name,0,[Image.open(sources[name]),outfit['outfitLayer'],outfit['image'],combined]))
board(gear,['SOURCE','OUTFIT','COMPOSITE','SAME HAIR / NEW OUTFIT'],'equipment.png')
board([(f'{name} / frame {f+1}',f,[hair['headwearLayer'],layers[name]['outfitLayer'],Image.open(DEST/name/'with-hair.png')])
       for name in ('dark-armor','leather-gloves-boots') for f in (4,12)],
      ['REUSABLE HAIR','NEW OUTFIT','SWAP: VISIBLE PIXELS ONLY'],'swaps.png')

with zipfile.ZipFile(DEST/'reusable-character-layers.zip','w',zipfile.ZIP_DEFLATED) as bundle:
    bundle.write(DEST/'hair/baseLayer.png','base.png')
    bundle.write(DEST/'hair/headwearLayer.png','hair.png')
    for name in layers:
        bundle.write(DEST/name/'outfitLayer.png',f'outfits/{"blue-robe" if name=="hair" else name}.png')
        bundle.write(DEST/name/'report.json',f'reports/{name}.json')
    bundle.writestr('layout.json',json.dumps(dict(width=256,height=448,rows=7,cols=4,
        frameWidth=64,frameHeight=64,order=['base','outfit','hair'],trimmed=False,
        samePoseLayoutRequired=True,hiddenRegionsReconstructed=False),indent=2))
    bundle.writestr('README.txt','Ghép base.png + một PNG trong outfits/ + hair.png.\n'
        'Giữ nguyên kích thước sheet 256 x 448 và bố cục 4 cột x 7 hàng.\n'
        'Các lớp có cùng tọa độ frame. Không tự cắt gọn riêng từng ảnh.\n'
        'Chỉ có pixel nhìn thấy trong nguồn: tóc khuất sau áo chưa được dựng bổ sung.\n'
        'Kiểm tra lại vùng che khuất nếu ghép với kiểu áo khác.\n')
