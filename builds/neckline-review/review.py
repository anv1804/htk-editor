"""Reproduce the purple-robe neckline review against the running editor API."""
import json,sys,urllib.request
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from repair_outfit_ui import encode_png,decode_image
DEST=Path(__file__).parent
base=Image.open(ROOT/'tests/fixtures/hair_outfit/base.png')
source=Image.open(ROOT/'tests/fixtures/covered_equipment/embroidered-robe.png').convert('RGBA')
payload=dict(base=encode_png(base),outfit=encode_png(source),rows=7,cols=4,
             colors=-1,paint=4,cleanup=0,composition='cutout')
request=urllib.request.Request('http://127.0.0.1:8765/api/repair',
    data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=120) as response: result=json.load(response)
assert result['report']['processingRevision']=='source-neckline-25'
for key in ('image','baseLayer','outfitLayer','headwearLayer','mask'):
    decode_image(result[key]).save(DEST/(key+'.png'))
(DEST/'report.json').write_text(json.dumps(result['report'],indent=2),encoding='utf8')
old=Image.open(ROOT/'builds/reusable-layers/embroidered-robe/image.png')
new=decode_image(result['image'])
# All poses are visible, including collar occlusions in raised-arm animations.
canvas=Image.new('RGB',(1024,1008),'#252b35');draw=ImageDraw.Draw(canvas)
for frame in range(28):
    x,y=frame%4*64,frame//4*64;ox=frame%4*256;oy=frame//4*144
    draw.text((ox+8,oy+4),f'F{frame+1} - Source / Result',fill='#d2dce8')
    for col,im in enumerate((source,new)):
        tile=im.crop((x,y,x+64,y+64)).resize((128,128),Image.Resampling.NEAREST)
        canvas.paste(tile,(ox+col*128,oy+16),tile)
canvas.save(DEST/'full-sheet-review.png')
canvas=Image.new('RGB',(768,920),'#252b35');draw=ImageDraw.Draw(canvas)
for row,frame in enumerate((2,3,5,6)):
    x,y=frame%4*64,frame//4*64
    for col,im in enumerate((source,old,new)):
        draw.text((col*256+12,row*230+8),f'F{frame+1} - '+('SOURCE','BEFORE','AFTER')[col],fill='#d2dce8')
        tile=im.crop((x+18,y+25,x+46,y+50)).resize((224,200),Image.Resampling.NEAREST)
        canvas.paste(tile,(col*256+16,row*230+26),tile)
canvas.save(DEST/'neckline-before-after.png')
print('HTTP API OK:',result['report']['processingRevision'],result['frameCount'],'frames;',result['paletteColors'],'colors')
