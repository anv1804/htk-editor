export type Recipe={family:string;cell:number;pieces:Record<string,string>;inventory?:boolean;mode?:string;color?:number[];inset?:number[]};
export type PartImage={image:CanvasImageSource;recipe?:Recipe|null};
export const partNames:Record<string,string>={ring:'Vòng chiêu',horizontal:'Tre ngang',vertical:'Tre dọc',leaves:'Lá phủ góc',tl:'Góc ↖',top:'Đốt trên',tr:'Góc ↗',left:'Đốt trái',center:'Nền',right:'Đốt phải',bl:'Góc ↙',bottom:'Đốt dưới',br:'Góc ↘'};
export function inventoryCells(w:number,h:number){
  const cols=Math.max(1,Math.floor((w-28)/44)),rows=Math.max(1,Math.floor((h-64)/44));
  const left=Math.floor((w-(cols*44-4))/2),cells:{x:number;y:number}[]=[];
  for(let row=0;row<rows;row++)for(let col=0;col<cols;col++)cells.push({x:left+col*44,y:38+row*44});
  return cells;
}
export function drawAssembly(ctx:CanvasRenderingContext2D,recipe:Recipe,w:number,h:number,get:(id:string)=>PartImage|undefined){
  const c=16;
  if(recipe.mode==='circle'){
    const size=Math.min(w,h),cx=Math.floor(size/2),cy=cx;let x=cx-3,y=0,error=1-x;
    ctx.fillStyle=`rgb(${(recipe.color??[176,196,152]).join(',')})`;
    while(x>=y){for(const [dx,dy] of [[x,y],[y,x],[-y,x],[-x,y],[-x,-y],[-y,-x],[y,-x],[x,-y]])ctx.fillRect(cx+dx!,cy+dy!,1,1);y++;if(error<0)error+=2*y+1;else{x--;error+=2*(y-x)+1;}}
    return;
  }
  if(recipe.mode==='outline'){
    const [ix=2,iy=2]=recipe.inset??[];ctx.fillStyle=`rgb(${(recipe.color??[176,196,152]).join(',')})`;
    ctx.fillRect(ix,iy,w-2*ix,1);ctx.fillRect(ix,h-iy-1,w-2*ix,1);ctx.fillRect(ix,iy,1,h-2*iy);ctx.fillRect(w-ix-1,iy,1,h-2*iy);return;
  }
  if(recipe.mode==='tile'){
    const tile=get(recipe.pieces.tile!);if(tile)for(let y=0;y<h;y+=32)for(let x=0;x<w;x+=32){const tw=Math.min(32,w-x),th=Math.min(32,h-y);ctx.drawImage(tile.image,0,0,tw,th,x,y,tw,th);}return;
  }
  const part=(key:string,x:number,y:number,tw=c,th=c)=>{const a=get(recipe.pieces[key]!);if(a&&tw>0&&th>0)ctx.drawImage(a.image,0,0,tw,th,x,y,tw,th);};
  if(recipe.mode==='ring'){const ring=get(recipe.pieces.ring!);if(ring)ctx.drawImage(ring.image,0,0,w,h);return;}
  if(recipe.mode==='bamboo'){
    for(let x=4;x<w-4;x+=32){const length=Math.min(32,w-4-x);part('horizontal',x,0,length,16);part('horizontal',x,h-13,length,16);}
    for(let y=4;y<h-4;y+=32){const length=Math.min(32,h-4-y);part('vertical',0,y,16,length);part('vertical',w-13,y,16,length);}
    for(const [x,y,fx,fy] of [[0,0,false,false],[w-32,0,true,false],[0,h-32,false,true],[w-32,h-32,true,true]] as [number,number,boolean,boolean][]){
      ctx.save();ctx.translate(x+(fx?32:0),y+(fy?32:0));ctx.scale(fx?-1:1,fy?-1:1);part('leaves',0,0,32,32);ctx.restore();
    }
  }else{
  for(let y=c;y<h-c;y+=c)for(let x=c;x<w-c;x+=c)part('center',x,y,Math.min(c,w-c-x),Math.min(c,h-c-y));
  for(let x=c;x<w-c;x+=c){part('top',x,0,Math.min(c,w-c-x));part('bottom',x,h-c,Math.min(c,w-c-x));}
  for(let y=c;y<h-c;y+=c){part('left',0,y,c,Math.min(c,h-c-y));part('right',w-c,y,c,Math.min(c,h-c-y));}
  part('tl',0,0);part('tr',w-c,0);part('bl',0,h-c);part('br',w-c,h-c);
  }
  if(recipe.inventory){const slot=get('frame-item');if(slot?.recipe)for(const cell of inventoryCells(w,h)){ctx.save();ctx.translate(cell.x,cell.y);drawAssembly(ctx,slot.recipe,40,40,get);ctx.restore();}}
}
