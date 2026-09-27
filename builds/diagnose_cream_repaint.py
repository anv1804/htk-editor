"""Local visual QA: separate extraction, contour and palette stages."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from repair_outfit_sprite import repair_sheet, repaint, luminance

root = Path(__file__).resolve().parents[1]
fixture = root/'tests/fixtures/cream_robe'
base = Image.open(fixture/'base.png').convert('RGBA')
source = Image.open(fixture/'outfit.png').convert('RGBA')
raw, _, mask = repair_sheet(base, source, rows=7, cols=4, colors=0,
    background_threshold=32, skin_expand=0, cleanup=0, paint=0,
    outline=False, composition='cutout', accessories=True, return_masks=True)
rgba = np.asarray(raw)
m = np.asarray(mask)
garment = m[:,:,2] == 255
anatomy = (m[:,:,0] == 255) & (m[:,:,1] == 80)
variants = [('Source',np.asarray(source)),('Cut only',rgba)]
for title,paint,outline,colors in [('Outline',0,True,0),('Paint 3',3,True,32),('Paint 4',4,True,32),('Paint 4 no outline',4,False,32)]:
    arr, contour = repaint(rgba, anatomy, garment, colors=colors,paint=paint,
        outline=outline,cell_size=(64,64),conservative=True)
    variants.append((title,arr))
    Image.fromarray(arr).save(root/'builds'/f'diag-cream-{paint}-{outline}.png')
    darkened = garment & ~contour & (luminance(rgba[:,:,:3]) > 120) & (luminance(arr[:,:,:3]) < 95)
    print(title, 'new dark fill pixels',int(darkened.sum()), 'frame1',np.argwhere(darkened[:64,:64]).tolist())
frames = [0,1,5,9]
board = Image.new('RGB',(6*256,len(frames)*280),(29,33,42))
draw = ImageDraw.Draw(board)
for row,frame in enumerate(frames):
    x,y = frame%4*64,frame//4*64
    for col,(title,arr) in enumerate(variants):
        draw.text((col*256+5,row*280+3),f'F{frame+1}: {title}',fill='white')
        tile=Image.fromarray(arr[y:y+64,x:x+64]).resize((256,256),Image.Resampling.NEAREST)
        board.paste(tile,(col*256,row*280+22),tile)
board.save(root/'builds/cream-stage-diagnostic.png')
raw.save(root/'builds/cream-cut-only.png')
mask.save(root/'builds/cream-cut-mask.png')
