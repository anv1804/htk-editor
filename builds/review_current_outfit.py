"""Generate a local visual comparison for the supplied outfit fixtures."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from repair_outfit_sprite import load_rgba, repair_sheet

cases = [('blue', Path(r'C:/Users/Admin/Downloads/SpriteSheet 2.png'),
          Path(r'C:/Users/Admin/Downloads/image-1790244457640-o9l66qzcn4r.png')),
         ('green', ROOT/'tests/fixtures/green_outfit/base.png', ROOT/'tests/fixtures/green_outfit/outfit.png'),
         ('tan', ROOT/'tests/fixtures/green_outfit/base.png', ROOT/'tests/fixtures/tan_outfit.png'),
         ('cream', Path(r'C:/Users/Admin/Downloads/SpriteSheet 2.png'), ROOT/'tests/fixtures/cream_robe/outfit.png')]
for name,bp,op in cases:
    base,outfit=load_rgba(bp),load_rgba(op)
    result,report,mask=repair_sheet(base,outfit,rows=7,cols=4,colors=32,
        background_threshold=36,skin_expand=0,paint=3,composition='cutout',outline=True,cleanup=0,
        accessories=True,return_masks=True)
    pixels,labels=np.array(result),np.array(mask)
    direct=np.all(labels[:,:,:3]==[255,80,80],axis=2)
    assert np.array_equal(pixels[direct],np.array(base)[direct])
    assert set(np.unique(pixels[:,:,3])) <= {0,255}
    colors=len(np.unique(pixels[pixels[:,:,3]>0,:3],axis=0))
    assert colors <= 32
    layer=result.copy(); lp=np.array(layer)
    lp[direct]=0; layer=Image.fromarray(lp)
    result.save(ROOT/f'builds/repair-{name}-latest.png')
    layer.save(ROOT/f'builds/repair-{name}-outfit.png')
    board=Image.new('RGB',(1024,1120),(37,42,48)); draw=ImageDraw.Draw(board)
    for row,frame in enumerate((0,3,20,24) if name == 'cream' else (0,4,5,14)):
        x,y=frame%4*64,frame//4*64
        for col,(title,im) in enumerate((('Base',base),('Source',outfit),('Cut outfit',layer),('Result',result))):
            draw.text((col*256+6,row*280+5),f'{title} / {frame+1}',fill='white')
            tile=im.crop((x,y,x+64,y+64)).resize((256,256),Image.Resampling.NEAREST)
            board.paste(tile,(col*256,row*280+24),tile)
    board.save(ROOT/f'builds/repair-{name}-review.png')
    print(name, len(report), 'frames;', colors, 'colors;',int(direct.sum()),'exact base pixels')
