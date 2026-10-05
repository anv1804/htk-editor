"""Build a reproducible UI v2 contact sheet and native Godot package."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from ui_forge import build, settings, export_zip
from ui_segments import FRAME_SPECS
from ui_motifs import PRIMARY_NAMES


def main():
    output=Path(__file__).resolve().parents[1]/'builds'/'ui-forge'
    output.mkdir(parents=True,exist_ok=True)
    assets=build(settings({}))
    ids=list(FRAME_SPECS)+['background-jade','background-paper','background-cloth',
                         'joystick-base','joystick-thumb','piece-bamboo-horizontal',
                         'piece-bamboo-vertical','piece-bamboo-leaves','bar-track']
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',15)
    title=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',26)
    cols=4;tile_w=424;tile_h=320
    sheet=Image.new('RGB',(cols*tile_w,104+((len(ids)+cols-1)//cols)*tile_h),'#111c19')
    draw=ImageDraw.Draw(sheet)
    draw.text((28,20),'HKT / THANH TRÚC · UI v2',font=title,fill='#dce8c9')
    draw.text((28,61),'Khung trong suốt · vòng 1 px · nền độc lập · không icon',font=font,fill='#91ac99')
    for index,key in enumerate(ids):
        asset=assets[key];image=asset['image'];col=index%cols;row=index//cols
        x=col*tile_w;y=104+row*tile_h
        draw.rectangle((x+10,y+8,x+tile_w-10,y+tile_h-10),fill='#172622',outline='#293b31')
        scale=max(1,min(3,400//image.width,264//image.height))
        rendered=image.resize((image.width*scale,image.height*scale),Image.Resampling.NEAREST)
        sheet.paste(rendered,(x+(tile_w-rendered.width)//2,y+12+(264-rendered.height)//2),rendered)
        draw.text((x+24,y+284),asset.get('name',PRIMARY_NAMES.get(key,key)),font=font,fill='#bfcea8')
        native=output/'v2-assets';native.mkdir(exist_ok=True)
        image.save(native/f'{key}.png')
    sheet.save(output/'ui-v2-components.png')
    (output/'hkt-ui-godot.zip').write_bytes(export_zip({}))
    print(f'Generated {len(ids)} native assets: {output}')


if __name__=='__main__':main()
