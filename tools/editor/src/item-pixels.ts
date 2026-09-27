/** Pure pixel operations for the item workbench. Never reads outfit state. */
export type Raster = { width: number; height: number; data: Uint8ClampedArray };
export type PixelPoint = { x: number; y: number };
export const copyRaster = (r: Raster): Raster => ({ width:r.width, height:r.height, data:new Uint8ClampedArray(r.data) });

export function pixelBounds(r: Raster) {
  let left=r.width, top=r.height, right=-1, bottom=-1;
  for (let y=0;y<r.height;y++) for (let x=0;x<r.width;x++) if (r.data[(y*r.width+x)*4+3]) {
    left=Math.min(left,x); right=Math.max(right,x); top=Math.min(top,y); bottom=Math.max(bottom,y);
  }
  return right<0 ? null : { x:left,y:top,w:right-left+1,h:bottom-top+1 };
}

/** Remove only border-connected background; enclosed highlights are retained. */
export function removeBorderBackground(r: Raster, color: readonly number[], tolerance: number): Raster {
  const out=copyRaster(r), seen=new Uint8Array(r.width*r.height), queue:number[]=[];
  const add=(i:number)=>{ if (!seen[i]) { seen[i]=1; queue.push(i); } };
  for (let x=0;x<r.width;x++) { add(x); add((r.height-1)*r.width+x); }
  for (let y=0;y<r.height;y++) { add(y*r.width); add(y*r.width+r.width-1); }
  for (let at=0;at<queue.length;at++) {
    const i=queue[at]!, p=i*4;
    if (r.data[p+3] && [0,1,2].some(c=>Math.abs(r.data[p+c]!-color[c]!)>tolerance)) continue;
    out.data.fill(0,p,p+4);
    if (i%r.width) add(i-1);
    if (i%r.width<r.width-1) add(i+1);
    if (i>=r.width) add(i-r.width);
    if (i<r.width*(r.height-1)) add(i+r.width);
  }
  return out;
}

export function pixelLine(a: PixelPoint,b: PixelPoint): PixelPoint[] {
  let {x,y}=a; const dx=Math.abs(b.x-x),dy=-Math.abs(b.y-y),sx=x<b.x?1:-1,sy=y<b.y?1:-1;
  let error=dx+dy; const points:PixelPoint[]=[];
  for (;;) {
    points.push({x,y}); if (x===b.x && y===b.y) return points;
    const twice=2*error; if(twice>=dy) { error+=dy; x+=sx; } if(twice<=dx) { error+=dx; y+=sy; }
  }
}

/** Median cut with population weighting; palette entries are real source colors. */
export function reduceItemPalette(r: Raster, budget: number): Raster {
  const out=copyRaster(r);
  const histogram=new Map<number,{rgb:number[];count:number}>();
  for(let i=0;i<r.data.length;i+=4) if(r.data[i+3]) {
    const rgb=[r.data[i]!,r.data[i+1]!,r.data[i+2]!];
    const key=(rgb[0]!>>3)<<10|(rgb[1]!>>3)<<5|(rgb[2]!>>3);
    const entry=histogram.get(key); if(entry) entry.count++; else histogram.set(key,{rgb,count:1});
  }
  let boxes=[Array.from(histogram.values())];
  if(!boxes[0]!.length) return out;
  const spread=(box:typeof boxes[number])=>[0,1,2].map(c=>Math.max(...box.map(e=>e.rgb[c]!))-Math.min(...box.map(e=>e.rgb[c]!)));
  while(boxes.length<budget) {
    let best=-1,score=-1;
    boxes.forEach((b,i)=>{ const s=Math.max(...spread(b))*Math.sqrt(b.reduce((a,e)=>a+e.count,0)); if(b.length>1&&s>score){score=s;best=i;} });
    if(best<0) break;
    const box=boxes.splice(best,1)[0]!, range=spread(box),axis=range.indexOf(Math.max(...range));
    box.sort((a,b)=>a.rgb[axis]!-b.rgb[axis]!);
    const half=box.reduce((a,e)=>a+e.count,0)/2;
    let sum=0,cut=0; do {sum+=box[cut++]!.count;} while(sum<half && cut<box.length-1);
    boxes.push(box.slice(0,cut),box.slice(cut));
  }
  const palette=boxes.map(box=>{
    const total=box.reduce((a,e)=>a+e.count,0);
    const center=[0,1,2].map(c=>box.reduce((a,e)=>a+e.rgb[c]!*e.count,0)/total);
    return box.reduce((a,b)=>distance(a.rgb,center)<distance(b.rgb,center)?a:b).rgb;
  });
  for(let i=0;i<out.data.length;i+=4) if(out.data[i+3]) {
    const rgb=[r.data[i]!,r.data[i+1]!,r.data[i+2]!];
    const color=palette.reduce((a,b)=>distance(a,rgb)<distance(b,rgb)?a:b);
    out.data.set(color,i);
  }
  return out;
}
const distance=(a:readonly number[],b:readonly number[])=>[.299,.587,.114].reduce((v,w,c)=>v+w*(a[c]!-b[c]!)**2,0);

/** Inward 1px contour. Repeating it cannot grow the alpha or thicken the edge. */
export function outlineItem(r: Raster,color: readonly number[]): Raster {
  const out=copyRaster(r);
  for(let y=0;y<r.height;y++) for(let x=0;x<r.width;x++) {
    const p=(y*r.width+x)*4;
    if(!r.data[p+3]) continue;
    if(x===0||y===0||x===r.width-1||y===r.height-1||
      [[x-1,y],[x+1,y],[x,y-1],[x,y+1]].some(([a,b])=>!r.data[(b!*r.width+a!)*4+3])) out.data.set(color.slice(0,3),p);
  }
  return out;
}

export function transformItem(r:Raster,kind:'left'|'right'|'flipX'|'flipY'):Raster {
  const turn=kind==='left'||kind==='right';
  const out:Raster={width:turn?r.height:r.width,height:turn?r.width:r.height,data:new Uint8ClampedArray(r.data.length)};
  for(let y=0;y<r.height;y++) for(let x=0;x<r.width;x++) {
    const nx=kind==='right'?r.height-1-y:kind==='left'?y:kind==='flipX'?r.width-1-x:x;
    const ny=kind==='right'?x:kind==='left'?r.width-1-x:kind==='flipY'?r.height-1-y:y;
    out.data.set(r.data.subarray((y*r.width+x)*4,(y*r.width+x)*4+4),(ny*out.width+nx)*4);
  }
  return out;
}
