import { drawOrnateRing, type RingStyle } from './ui-ornament';
export type Recipe={family:string;cell:number;pieces:Record<string,string>;inventory?:boolean;mode?:string;color?:number[];inset?:number[];stroke?:number;showBg?:boolean;cavity?:number} & Partial<RingStyle>;
export type PartImage={image:CanvasImageSource;recipe?:Recipe|null};
export const partNames:Record<string,string>={'cap-l':'Đầu bịt trái','cap-r':'Đầu bịt phải','rail-h':'Thanh ngang','rail-v':'Thanh dọc',corner:'Cụm góc',bg:'Nền ô (lòng khung)',ring:'Vòng chiêu',horizontal:'Tre ngang',vertical:'Tre dọc',leaves:'Lá phủ góc',tl:'Góc ↖',top:'Đốt trên',tr:'Góc ↗',left:'Đốt trái',center:'Nền',right:'Đốt phải',bl:'Góc ↙',bottom:'Đốt dưới',br:'Góc ↘'};
export function inventoryCells(w:number,h:number){
  const cols=Math.max(1,Math.floor((w-28)/44)),rows=Math.max(1,Math.floor((h-64)/44));
  const left=Math.floor((w-(cols*44-4))/2),cells:{x:number;y:number}[]=[];
  for(let row=0;row<rows;row++)for(let col=0;col<cols;col++)cells.push({x:left+col*44,y:38+row*44});
  return cells;
}
export function drawAssembly(ctx:CanvasRenderingContext2D,recipe:Recipe,w:number,h:number,get:(id:string)=>PartImage|undefined){
  const c=16;
  if(recipe.mode==='ornate'||recipe.mode==='circle'){
    const style: RingStyle = {
      palette: recipe.palette ?? [
        recipe.color ?? [76, 111, 48],
        [220, 235, 185],
        [10, 16, 14],
        [215, 185, 110],
        [70, 160, 130]
      ],
      border: recipe.border ?? 5,
      detail: recipe.detail ?? 0,
      shadow: recipe.shadow ?? 0,
      enableShadow: recipe.enableShadow ?? true,
      texture: recipe.texture ?? true,
      crest: recipe.crest ?? true,
      corner: recipe.corner ?? 'leaves',
      frameStyle: recipe.frameStyle ?? 'bamboo'
    };
    drawOrnateRing(ctx, Math.min(w, h), style);
    return;
  }
  if(recipe.mode==='outline'){
    const [ix=2,iy=2]=recipe.inset??[];ctx.fillStyle=`rgb(${(recipe.color??[176,196,152]).join(',')})`;
    ctx.fillRect(ix,iy,w-2*ix,1);ctx.fillRect(ix,h-iy-1,w-2*ix,1);ctx.fillRect(ix,iy,1,h-2*iy);ctx.fillRect(w-ix-1,iy,1,h-2*iy);return;
  }
  if(recipe.mode==='tile'){
    const tile=get(recipe.pieces.tile!);if(tile)for(let y=0;y<h;y+=32)for(let x=0;x<w;x+=32){const tw=Math.min(32,w-x),th=Math.min(32,h-y);ctx.drawImage(tile.image,0,0,tw,th,x,y,tw,th);}return;
  }
  if(recipe.mode==='ring'){const ring=get(recipe.pieces.ring!);if(ring)ctx.drawImage(ring.image,0,0,w,h);return;}

  const needsLayer = recipe.enableShadow !== false && (recipe.shadow ?? 0) > 0 && (recipe.mode === 'item' || recipe.mode === 'rails' || recipe.mode === 'bamboo' || recipe.mode === 'bar');
  const targetCanvas = needsLayer ? document.createElement('canvas') : null;
  if (targetCanvas) { targetCanvas.width = w; targetCanvas.height = h; }
  const dest = targetCanvas ? targetCanvas.getContext('2d')! : ctx;

  const part=(key:string,x:number,y:number,tw=c,th=c)=>{const a=get(recipe.pieces[key]!);if(a&&tw>0&&th>0)dest.drawImage(a.image,0,0,tw,th,x,y,tw,th);};

  if(recipe.mode==='item'){
    const showBg=recipe.showBg??true;const border=recipe.border??5;
    const thickness=border<=3?1:(border<=5?2:(border<=7?3:4));
    const cavityStart=recipe.cavity??2+thickness+1;
    if(showBg&&recipe.pieces.bg){
      const bg=get(recipe.pieces.bg);
      if(bg){
        const bw=w-cavityStart*2,bh=h-cavityStart*2;
        if(bw>0&&bh>0)dest.drawImage(bg.image,0,0,(bg.image as any).width||32,(bg.image as any).height||32,cavityStart,cavityStart,bw,bh);
      }
    }
    for(let x=16;x<w-16;x+=32){
      const len=Math.min(32,w-16-x);
      if(len>0){
        part('rail-h',x,0,len,16);
        dest.save();dest.translate(x,h);dest.scale(1,-1);part('rail-h',0,0,len,16);dest.restore();
      }
    }
    for(let y=16;y<h-16;y+=32){
      const len=Math.min(32,h-16-y);
      if(len>0){
        part('rail-v',0,y,16,len);
        dest.save();dest.translate(w,y);dest.scale(-1,1);part('rail-v',0,0,16,len);dest.restore();
      }
    }
    for(const [x,y,fx,fy] of [[0,0,false,false],[w-16,0,true,false],[0,h-16,false,true],[w-16,h-16,true,true]] as [number,number,boolean,boolean][]){
      dest.save();dest.translate(x+(fx?16:0),y+(fy?16:0));dest.scale(fx?-1:1,fy?-1:1);part('corner',0,0,16,16);dest.restore();
    }
  } else if(recipe.mode==='rails'){
    if((recipe.showBg??true)&&recipe.pieces.bg){
      const bg=get(recipe.pieces.bg),cv=recipe.cavity??3,bw=w-cv*2,bh=h-cv*2;
      if(bg&&bw>0&&bh>0)dest.drawImage(bg.image,0,0,(bg.image as any).width||16,(bg.image as any).height||16,cv,cv,bw,bh);
    }
    for(let x=16;x<w-16;x+=32){
      const length=Math.min(32,w-16-x);
      part('rail-h',x,0,length,16);
      dest.save();dest.translate(x,h);dest.scale(1,-1);part('rail-h',0,0,length,16);dest.restore();
    }
    for(let y=16;y<h-16;y+=32){
      const length=Math.min(32,h-16-y);
      part('rail-v',0,y,16,length);
      dest.save();dest.translate(w,y);dest.scale(-1,1);part('rail-v',0,0,16,length);dest.restore();
    }
    for(const [x,y,fx,fy] of [[0,0,false,false],[w-16,0,true,false],[0,h-16,false,true],[w-16,h-16,true,true]] as [number,number,boolean,boolean][]){
      dest.save();dest.translate(x+(fx?16:0),y+(fy?16:0));dest.scale(fx?-1:1,fy?-1:1);part('corner',0,0,16,16);dest.restore();
    }
  } else if(recipe.mode==='bar'){
    const cw = 8, ch = 8;
    if((recipe.showBg??false)&&recipe.pieces.bg){
      const bg=get(recipe.pieces.bg);
      const cv=recipe.cavity??4,bw=w-cv*2,bh=h-cv*2;
      if(bg&&bw>0&&bh>0)dest.drawImage(bg.image,0,0,(bg.image as any).width||32,(bg.image as any).height||32,cv,cv,bw,bh);
    }
    for(let x=cw;x<w-cw;x+=32){
      const length=Math.min(32,w-cw-x);
      if(length>0){
        part('rail-h',x,0,length,8);
        dest.save();dest.translate(x,h);dest.scale(1,-1);part('rail-h',0,0,length,8);dest.restore();
      }
    }
    for(let y=ch;y<h-ch;y+=32){
      const length=Math.min(32,h-ch-y);
      if(length>0){
        part('rail-v',0,y,8,length);
        dest.save();dest.translate(w,y);dest.scale(-1,1);part('rail-v',0,0,8,length);dest.restore();
      }
    }
    for(const [x,y,fx,fy] of [[0,0,false,false],[w-cw,0,true,false],[0,h-ch,false,true],[w-cw,h-ch,true,true]] as [number,number,boolean,boolean][]){
      dest.save();dest.translate(x+(fx?cw:0),y+(fy?ch:0));dest.scale(fx?-1:1,fy?-1:1);part('corner',0,0,cw,ch);dest.restore();
    }
  } else if(recipe.mode==='bamboo'){
    for(let x=4;x<w-4;x+=32){const length=Math.min(32,w-4-x);part('horizontal',x,0,length,16);part('horizontal',x,h-13,length,16);}
    for(let y=4;y<h-4;y+=32){const length=Math.min(32,h-4-y);part('vertical',0,y,16,length);part('vertical',w-13,y,16,length);}
    for(const [x,y,fx,fy] of [[0,0,false,false],[w-32,0,true,false],[0,h-32,false,true],[w-32,h-32,true,true]] as [number,number,boolean,boolean][]){
      dest.save();dest.translate(x+(fx?32:0),y+(fy?32:0));dest.scale(fx?-1:1,fy?-1:1);part('leaves',0,0,32,32);dest.restore();
    }
  } else {
    for(let y=c;y<h-c;y+=c)for(let x=c;x<w-c;x+=c)part('center',x,y,Math.min(c,w-c-x),Math.min(c,h-c-y));
    for(let x=c;x<w-c;x+=c){part('top',x,0,Math.min(c,w-c-x));part('bottom',x,h-c,Math.min(c,w-c-x));}
    for(let y=c;y<h-c;y+=c){part('left',0,y,c,Math.min(c,h-c-y));part('right',w-c,y,c,Math.min(c,h-c-y));}
    part('tl',0,0);part('tr',w-c,0);part('bl',0,h-c);part('br',w-c,h-c);
  }

  if(recipe.inventory){
    const slot=get('frame-item');
    if(slot?.recipe)for(const cell of inventoryCells(w,h)){
      dest.save();dest.translate(cell.x,cell.y);drawAssembly(dest,slot.recipe,40,40,get);dest.restore();
    }
  }

  if(targetCanvas){
    const shadowCanvas = document.createElement('canvas');
    shadowCanvas.width = w; shadowCanvas.height = h;
    const sc = shadowCanvas.getContext('2d')!;
    sc.drawImage(targetCanvas, 0, 0);
    sc.globalCompositeOperation = 'source-in';
    const ink = recipe.palette?.[2] ?? [8, 14, 12];
    sc.fillStyle = `rgba(${ink.join(',')},${Math.min(70, 20 + (recipe.shadow ?? 3) * 10) / 255})`;
    sc.fillRect(0, 0, w, h);
    const offset = recipe.mode === 'item' ? 0 : 1;
    ctx.drawImage(shadowCanvas, offset, offset);
    ctx.drawImage(targetCanvas, 0, 0);
  }
}
