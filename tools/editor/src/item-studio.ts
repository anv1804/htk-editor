import './item-studio.css';
import { state, paintLayer, paintContext } from './state';
import { grid, checkpoint, invalidate, render, remember } from './editor';
import { download, loadImage } from './utils';
import { isPlaying, togglePlayPause } from './timeline';
import { connectedRegion } from './region';
import { pixelBounds, pixelLine, removeBorderBackground, reduceItemPalette, outlineItem, transformItem } from './item-pixels';
import type { Raster, PixelPoint } from './item-pixels';

type Snapshot={ raster:Raster; anchor:PixelPoint; name:string };
type Tool='brush'|'erase'|'fill'|'pick'|'wand'|'line'|'rect'|'move'|'anchor'|'place';
const DRAFT='hkt-item-workbench-v1';
const icon=(path:string)=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${path}"/></svg>`;
const tools: [Tool,string,string,string][]=[
  ['brush','B','Cọ pixel','m15 3 6 6-12 12H3v-6L15 3ZM5 13l6 6'],
  ['erase','E','Tẩy','m14 3 7 7-10 10H5l-4-4L14 3ZM6 11l7 7'],
  ['fill','G','Tô vùng','m10 3 9 9-8 8-9-9 8-8ZM3 12h15'],
  ['pick','I','Hút màu','m14 3 7 7M18 6 5 19l-3 1 1-3L16 4'],
  ['wand','W','Xóa vùng cùng màu','m4 20 13-13M15 3l1-2m5 8 2-1M7 4v4M5 6h4'],
  ['line','L','Đường thẳng','M4 20 20 4'],
  ['rect','R','Khung chữ nhật','M4 4h16v16H4z'],
  ['move','V','Di chuyển item','M12 2v20M2 12h20M9 5l3-3 3 3M9 19l3 3 3-3M5 9l-3 3 3 3m14-6 3 3-3 3'],
  ['anchor','A','Điểm neo tay cầm','M12 2v6m0 8v6M2 12h6m8 0h6M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8'],
  ['place','T','Đặt điểm neo lên bàn tay','M4 3v17l5-5 4 7 3-2-4-7h7L4 3Z']
];

export function setupItemStudio() {
  const launch=document.createElement('button'); launch.id='openItemStudio'; launch.className='item-launch';
  launch.innerHTML=`${icon('M4 4h16v16H4zM4 10h16M10 4v16')}<span>Xưởng item</span><small>MỚI</small>`;
  launch.title='Bảng vẽ phụ kiện & vũ khí (Alt+J)';
  document.querySelector('.project-actions')!.before(launch);
  const dialog=document.createElement('dialog'); dialog.id='itemStudio'; dialog.className='item-studio';
  dialog.setAttribute('aria-labelledby','itemStudioTitle');
  dialog.innerHTML=`
    <div class="item-heading"><div class="item-brand">${icon('m12 3 9 9-9 9-9-9 9-9ZM12 7v10M7 12h10')}<div><span class="item-eyebrow">PIXEL WORKBENCH</span><h2 id="itemStudioTitle">Xưởng item</h2></div><span class="item-tag">Phụ kiện & vũ khí</span></div>
      <div class="item-actions"><button id="itemOpen">Mở bản vẽ</button><button id="itemSave">Lưu bản vẽ</button><button id="itemExport" class="item-secondary">Xuất PNG ↗</button><button id="itemClose" aria-label="Đóng xưởng item" title="Đóng (Esc)">✕</button></div></div>
    <div class="item-layout">
      <aside class="item-source">
        <div class="item-section-title"><span>01</span><h3>Ảnh → item</h3></div>
        <button class="item-upload" id="itemImport">${icon('M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6')}<strong>Chọn ảnh tham chiếu</strong><small>PNG, JPG, WebP · hoặc kéo ảnh vào</small></button>
        <div class="item-reference" hidden><canvas id="itemReference" width="384" height="256" aria-label="Kéo để chọn vùng vật phẩm trong ảnh"></canvas><button id="itemFullCrop">Chọn toàn ảnh</button></div>
        <p id="itemSourceInfo" class="item-hint">Ảnh vật phẩm trên nền đơn giản cho kết quả tốt nhất.</p>
        <div class="item-fields"><label>Cạnh dài item<input id="itemImportSize" type="number" min="4" max="128" value="32"></label><label>Bảng màu<select id="itemPaletteSize"><option value="0">Giữ gốc</option><option value="8">8 màu</option><option value="16" selected>16 màu</option><option value="32">32 màu</option></select></label></div>
        <label class="item-label">Ảnh nguồn<select id="itemSampling"><option value="pixel">Pixel art · giữ từng pixel</option><option value="photo">Tranh / ảnh chụp · thu nhỏ mượt</option></select></label>
        <label class="item-check"><input id="itemRemoveBg" type="checkbox" checked>Bỏ nền nối với mép ảnh</label>
        <div class="item-fields"><label>Màu nền<input id="itemBgColor" type="color" value="#ffffff"></label><label>Độ lệch màu<input id="itemTolerance" type="number" min="0" max="100" value="28"></label></div>
        <button id="itemPrepare" class="item-primary" disabled>Đưa lên bảng vẽ</button>
        <div class="item-template-heading">HOẶC BẮT ĐẦU TỪ MẪU</div>
        <div class="item-templates"><button data-template="sword">⚔<span>Kiếm</span></button><button data-template="staff">✦<span>Trượng</span></button><button data-template="shield">♢<span>Khiên</span></button></div>
        <button id="itemBlank" class="item-quiet">＋ Bảng vẽ trống</button>
      </aside>
      <main class="item-main">
        <div class="item-board-toolbar"><div><span class="item-dot"></span><input id="itemName" value="item-moi" maxlength="80" aria-label="Tên item"></div><label>Lưới<select id="itemSize"><option>32</option><option selected>64</option><option>128</option></select></label><button id="itemUndo" title="Hoàn tác (Ctrl+Z)" aria-label="Hoàn tác item">↶</button><button id="itemRedo" title="Làm lại (Ctrl+Shift+Z)" aria-label="Làm lại item">↷</button></div>
        <div class="item-drawing-tools">${tools.map(([key,hotkey,label,path])=>`<button data-item-tool="${key}" title="${label} (${hotkey})" aria-label="${label}" aria-pressed="${key==='brush'}">${icon(path)}</button>`).join('')}<span></span><button id="itemGrid" aria-pressed="true" title="Hiện lưới pixel">#</button><button id="itemSymmetry" aria-pressed="false" title="Vẽ đối xứng qua trục giữa">↔</button></div>
        <div class="item-board-stage" id="itemStage"><canvas id="itemBoard" width="640" height="640" aria-label="Bảng vẽ pixel item" tabindex="0"></canvas><div id="itemEmpty" class="item-empty"><span>Ý tưởng bắt đầu từ một pixel.</span><small>Vẽ trực tiếp, chọn mẫu hoặc đưa ảnh lên bảng.</small></div></div>
        <div class="item-board-footer"><span id="itemCoordinate">64 × 64 · nền trong suốt</span><div><button id="itemZoomOut" aria-label="Thu nhỏ bảng vẽ">−</button><output id="itemZoomLabel">100%</output><button id="itemZoomIn" aria-label="Phóng to bảng vẽ">＋</button><button id="itemFit">Vừa khung</button></div></div>
        <div class="item-note" id="itemNotice" role="status" aria-live="polite">Bản vẽ riêng. Outfit chỉ thay đổi khi bạn gắn item vào frame.</div>
      </main>
      <aside class="item-inspector">
        <div class="item-section-title"><span>02</span><h3>Thử trên nhân vật</h3><b id="itemFrameLabel">—</b></div>
        <div class="item-preview"><canvas id="itemPreview" width="192" height="192" aria-label="Xem thử item trên nhân vật"></canvas><span id="itemNoBase">Chọn base trong editor để thử item</span></div>
        <label class="item-check"><input id="itemShowGuide" type="checkbox" checked>Hiện nhân vật trên bảng vẽ</label>
        <div class="item-property-tabs"><button data-item-page="paint" aria-pressed="true">Vẽ & màu</button><button data-item-page="attach" aria-pressed="false">Căn tay cầm</button></div>
        <div id="itemPaintPage" class="item-property-page">
        <div class="item-fields"><label>Màu cọ<input id="itemColor" type="color" value="#b9e4ef"></label><label>Cỡ cọ<select id="itemBrushSize"><option>1</option><option>2</option><option>3</option><option>5</option><option>8</option></select></label></div>
        <div id="itemSwatches" class="item-swatches" aria-label="Màu của item"></div>
        <div class="item-transform"><button id="itemFlipX" title="Lật ngang">↔ Lật</button><button id="itemRotate" title="Xoay 90 độ">↻ Xoay</button><button id="itemOutline" title="Viền phía trong 1 pixel, không làm phình hình">Viền 1px</button><button id="itemReduce">Gom màu</button></div>
        <p class="item-hint">B: cọ · E: tẩy · G: tô vùng · I: hút màu<br>Ctrl+Z / Ctrl+Y: hoàn tác / làm lại</p></div>
        <div id="itemAttachPage" class="item-property-page" hidden>
        <div class="item-anchor"><strong>Điểm neo tay cầm <code id="itemAnchorLabel">32, 32</code></strong><p>A: chấm vào cán để đặt neo.<br>T: chấm vào tay để đưa neo đến đó.<br>V: kéo item; mũi tên: căn từng pixel.</p></div>
        <p class="item-hint">Shift + mũi tên: dịch 5px. Điểm neo được lưu trong bản vẽ JSON, không hiện trong PNG.</p>
        <p class="item-hint">Ảnh được xử lý trên máy. Công cụ không tự dựng góc nhìn hoặc animation còn thiếu.</p></div>
        <button id="itemApply" class="item-primary">Gắn vào frame</button><p class="item-hint">Gắn vào lớp tô tay của frame hiện tại. Ctrl+Z trong editor để hoàn tác.</p>
      </aside>
    </div><input id="itemFile" type="file" accept="image/png,image/jpeg,image/webp" hidden><input id="itemProjectFile" type="file" accept=".json" hidden>`;
  document.body.append(dialog);
  const el=<T extends HTMLElement>(id:string)=>dialog.querySelector<T>(`#${id}`)!;
  const input=(id:string)=>el<HTMLInputElement>(id);
  const number=(id:string,min:number,max:number)=>Math.max(min,Math.min(max,Number(input(id).value)||min));
  const button=(id:string,handler:()=>void)=>el(id).addEventListener('click',handler);
  const layer=document.createElement('canvas'); layer.width=layer.height=64;
  const ctx=layer.getContext('2d',{willReadFrequently:true})!;
  const board=el<HTMLCanvasElement>('itemBoard'), preview=el<HTMLCanvasElement>('itemPreview');
  const ref=el<HTMLCanvasElement>('itemReference');
  const guide=document.createElement('canvas'); guide.width=guide.height=64;
  let anchor:PixelPoint={x:32,y:32},tool:Tool='brush',zoom=1,showGrid=true,symmetry=false;
  let source:HTMLImageElement|null=null, crop={x:0,y:0,w:1,h:1},cropStart:PixelPoint|null=null;
  let undo:Snapshot[]=[],redo:Snapshot[]=[],stroke:Snapshot|null=null,start:PixelPoint|null=null,last:PixelPoint|null=null;
  let frame=grid(),hasGuide=false,busy=false,saveTimer=0,resumePlayback=false;
  let referenceFit={x:0,y:0,w:384,h:256};
  const rgba=(hex:string)=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
  const read=():Raster=>({width:layer.width,height:layer.height,data:ctx.getImageData(0,0,layer.width,layer.height).data});
  const snapshot=():Snapshot=>({raster:read(),anchor:{...anchor},name:input('itemName').value});
  const write=(r:Raster)=>{layer.width=r.width;layer.height=r.height;ctx.putImageData(new ImageData(new Uint8ClampedArray(r.data),r.width,r.height),0,0);};
  const note=(s:string,error=false)=>{el('itemNotice').textContent=s;el('itemNotice').classList.toggle('is-error',error);};
  const setTool=(t:Tool)=>{tool=t;dialog.querySelectorAll<HTMLButtonElement>('[data-item-tool]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.itemTool===t)));board.style.cursor=t==='move'?'move':'crosshair';};
  const capture=()=>{undo.push(snapshot());if(undo.length>40)undo.shift();redo=[];};
  function restore(s:Snapshot) {write(s.raster);anchor={...s.anchor};input('itemName').value=s.name;input('itemSize').value=String(layer.width);draw();}
  function changeHistory(back:boolean) {const from=back?undo:redo,to=back?redo:undo;if(!from.length||busy)return;to.push(snapshot());restore(from.pop()!);finish();}
  function persist() {
    try {localStorage.setItem(DRAFT,JSON.stringify(project()));} catch {note('Bộ nhớ bản nháp đã đầy. Dùng Lưu bản vẽ để giữ item.',true);}
  }
  function project() {return {format:'hkt-pixel-item',version:1,name:input('itemName').value,width:layer.width,height:layer.height,png:layer.toDataURL(),anchor:{...anchor}};}
  function finish(message?:string) {draw();updateSwatches();clearTimeout(saveTimer);saveTimer=window.setTimeout(persist,350);if(message)note(message);}
  function mutate(fn:()=>void,message?:string) {if(busy)return;capture();fn();finish(message);}
  function syncGuide() {
    frame=grid();hasGuide=!!(state.base&&frame);guide.width=frame?.w||64;guide.height=frame?.h||64;
    if(frame&&state.base) {
      const g=guide.getContext('2d')!;g.imageSmoothingEnabled=false;
      g.drawImage(state.result||state.base,frame.x,frame.y,frame.w,frame.h,0,0,frame.w,frame.h);
      g.drawImage(paintLayer,frame.x,frame.y,frame.w,frame.h,0,0,frame.w,frame.h);
    }
    el('itemFrameLabel').textContent=frame?`F${frame.frame+1}`:'—';
    el('itemNoBase').hidden=hasGuide;
    el<HTMLButtonElement>('itemApply').disabled=!hasGuide||state.busy;
    el('itemApply').textContent=frame?`Gắn vào frame ${frame.frame+1}`:'Gắn vào frame';
  }
  function fitDraw(c:CanvasRenderingContext2D,img:HTMLCanvasElement,w:number,h:number) {
    const scale=Math.min(w/img.width,h/img.height);c.drawImage(img,Math.round((w-img.width*scale)/2),Math.round((h-img.height*scale)/2),Math.round(img.width*scale),Math.round(img.height*scale));
  }
  function checker(c:CanvasRenderingContext2D,w:number,h:number,step:number) {
    c.fillStyle='#242a35';c.fillRect(0,0,w,h);c.fillStyle='#2b3240';
    for(let y=0;y<h;y+=step)for(let x=0;x<w;x+=step)if((x/step+y/step)%2===0)c.fillRect(x,y,step,step);
  }
  function draw() {
    const size=640,scale=size/layer.width,c=board.getContext('2d')!;c.imageSmoothingEnabled=false;
    checker(c,size,size,Math.max(scale,20));
    if(hasGuide&&input('itemShowGuide').checked){c.globalAlpha=.35;fitDraw(c,guide,size,size);c.globalAlpha=1;}
    c.drawImage(layer,0,0,size,size);
    if(showGrid&&layer.width<=128){c.strokeStyle='#080c1733';c.lineWidth=1;c.beginPath();for(let i=1;i<layer.width;i++){c.moveTo(i*scale+.5,0);c.lineTo(i*scale+.5,size);c.moveTo(0,i*scale+.5);c.lineTo(size,i*scale+.5);}c.stroke();}
    const ax=(anchor.x+.5)*scale,ay=(anchor.y+.5)*scale;
    c.strokeStyle='#69e6c5';c.lineWidth=1.5;c.beginPath();c.arc(ax,ay,6,0,Math.PI*2);c.moveTo(ax-11,ay);c.lineTo(ax+11,ay);c.moveTo(ax,ay-11);c.lineTo(ax,ay+11);c.stroke();
    const p=preview.getContext('2d')!;p.imageSmoothingEnabled=false;checker(p,192,192,12);
    if(hasGuide)fitDraw(p,guide,192,192);p.drawImage(layer,0,0,192,192);
    el('itemAnchorLabel').textContent=`${anchor.x}, ${anchor.y}`;
    el<HTMLButtonElement>('itemUndo').disabled=!undo.length||busy;el<HTMLButtonElement>('itemRedo').disabled=!redo.length||busy;
    const bounds=pixelBounds(read());el('itemEmpty').hidden=!!bounds;
    el<HTMLButtonElement>('itemExport').disabled=!bounds;
    el<HTMLButtonElement>('itemApply').disabled=!bounds||!hasGuide||state.busy;
  }
  function fitBoard() {
    if(!dialog.open)return;
    const stage=el('itemStage');const edge=Math.max(128,Math.min(stage.clientWidth-48,stage.clientHeight-48))*zoom;
    board.style.width=board.style.height=`${Math.round(edge)}px`;
    el('itemZoomLabel').textContent=`${Math.round(zoom*100)}%`;
  }
  function updateSwatches() {
    const data=read().data,counts=new Map<string,number>();
    for(let i=0;i<data.length;i+=4)if(data[i+3]){const color='#'+Array.from(data.subarray(i,i+3)).map(v=>v.toString(16).padStart(2,'0')).join('');counts.set(color,(counts.get(color)||0)+1);}
    const colors=[...counts].sort((a,b)=>b[1]-a[1]).slice(0,16).map(([c])=>c);
    if(!colors.length)colors.push('#252333','#f3efcf','#b9e4ef','#5f9fb6','#c19a58','#805640','#b6a0f7','#71c8aa');
    el('itemSwatches').replaceChildren(...colors.map(color=>{const b=document.createElement('button');b.style.background=color;b.title=color;b.setAttribute('aria-label',`Màu ${color}`);b.onclick=()=>{input('itemColor').value=color;};return b;}));
  }
  const pos=(e:PointerEvent):PixelPoint=>{const r=board.getBoundingClientRect();return{x:Math.max(0,Math.min(layer.width-1,Math.floor((e.clientX-r.left)/r.width*layer.width))),y:Math.max(0,Math.min(layer.height-1,Math.floor((e.clientY-r.top)/r.height*layer.height)))};};
  function dab(p:PixelPoint,erase=false) {
    const size=number('itemBrushSize',1,8),offset=Math.floor(size/2);
    ctx.fillStyle=input('itemColor').value;
    const apply=(x:number)=>erase?ctx.clearRect(x-offset,p.y-offset,size,size):ctx.fillRect(x-offset,p.y-offset,size,size);
    apply(p.x);if(symmetry)apply(layer.width-1-p.x);
  }
  function translate(s:Snapshot,dx:number,dy:number) {
    write(s.raster);const temp=document.createElement('canvas');temp.width=layer.width;temp.height=layer.height;temp.getContext('2d')!.drawImage(layer,0,0);
    ctx.clearRect(0,0,layer.width,layer.height);ctx.drawImage(temp,dx,dy);anchor={x:s.anchor.x+dx,y:s.anchor.y+dy};
  }
  board.addEventListener('pointerdown',e=>{
    if(e.button!==0||busy)return;e.preventDefault();board.focus();board.setPointerCapture(e.pointerId);
    start=last=pos(e);
    if(tool==='pick') {const p=ctx.getImageData(start.x,start.y,1,1).data;if(p[3])input('itemColor').value='#'+Array.from(p.slice(0,3)).map(n=>n.toString(16).padStart(2,'0')).join('');start=last=null;return;}
    capture();stroke=snapshot();
    if(tool==='anchor'){anchor={...start};finish('Đã đặt điểm neo. Điểm xanh không xuất vào ảnh.');stroke=null;start=last=null;return;}
    if(tool==='place'){translate(stroke,start.x-anchor.x,start.y-anchor.y);stroke=null;start=last=null;finish('Đã đưa điểm neo đến vị trí bàn tay. Có thể căn thêm bằng phím mũi tên.');return;}
    if(tool==='fill'||tool==='wand') {
      const data=read(),seeds=[start];if(symmetry)seeds.push({x:layer.width-1-start.x,y:start.y});
      const color=tool==='wand'?[0,0,0,0]:[...rgba(input('itemColor').value),255];
      const indices=new Set(seeds.flatMap(p=>connectedRegion(data.data,data.width,data.height,p.x,p.y,number('itemTolerance',0,100))));
      indices.forEach(i=>data.data.set(color,i*4));write(data);stroke=null;start=last=null;finish(`Đã ${tool==='wand'?'xóa':'tô'} ${indices.size} pixel.`);return;
    }
    if(['brush','erase','line','rect'].includes(tool))dab(start,tool==='erase');draw();
  });
  board.addEventListener('pointermove',e=>{
    const p=pos(e);el('itemCoordinate').textContent=`X ${p.x} · Y ${p.y}  /  ${layer.width} × ${layer.height}`;
    if(!stroke||!start||!last)return;
    if(tool==='move')translate(stroke,p.x-start.x,p.y-start.y);
    else if(tool==='line'||tool==='rect') {
      write(stroke.raster);
      const points=tool==='line'?pixelLine(start,p):[...pixelLine(start,{x:p.x,y:start.y}),...pixelLine({x:p.x,y:start.y},p),...pixelLine(p,{x:start.x,y:p.y}),...pixelLine({x:start.x,y:p.y},start)];
      points.forEach(q=>dab(q));
    } else pixelLine(last,p).forEach(q=>dab(q,tool==='erase'));
    last=p;draw();
  });
  const endStroke=()=>{if(!stroke)return;stroke=null;start=last=null;finish();};
  board.addEventListener('pointerup',endStroke);board.addEventListener('lostpointercapture',endStroke);
  board.addEventListener('pointercancel',()=>{if(stroke){const before=stroke;stroke=null;start=last=null;undo.pop();restore(before);finish();}});
  dialog.querySelectorAll<HTMLButtonElement>('[data-item-tool]').forEach(b=>b.onclick=()=>setTool(b.dataset.itemTool as Tool));
  dialog.querySelectorAll<HTMLButtonElement>('[data-item-page]').forEach(b=>b.onclick=()=>{
    const paint=b.dataset.itemPage==='paint';el('itemPaintPage').hidden=!paint;el('itemAttachPage').hidden=paint;
    dialog.querySelectorAll('[data-item-page]').forEach(t=>t.setAttribute('aria-pressed',String(t===b)));
  });
  function drawReference() {
    if(!source)return;const c=ref.getContext('2d')!;c.clearRect(0,0,384,256);
    const scale=Math.min(384/source.width,256/source.height);
    referenceFit={x:(384-source.width*scale)/2,y:(256-source.height*scale)/2,w:source.width*scale,h:source.height*scale};
    c.imageSmoothingEnabled=false;c.drawImage(source,referenceFit.x,referenceFit.y,referenceFit.w,referenceFit.h);
    c.fillStyle='#0c0f1599';c.fillRect(0,0,384,256);
    c.drawImage(source,crop.x,crop.y,crop.w,crop.h,referenceFit.x+crop.x*scale,referenceFit.y+crop.y*scale,crop.w*scale,crop.h*scale);
    c.strokeStyle='#bdb0ff';c.lineWidth=2;c.strokeRect(referenceFit.x+crop.x*scale,referenceFit.y+crop.y*scale,crop.w*scale,crop.h*scale);
    el('itemSourceInfo').textContent=`Vùng chọn ${crop.w} × ${crop.h}px. Kéo trên ảnh để chọn lại vật phẩm.`;
  }
  const refPos=(e:PointerEvent)=>{const b=ref.getBoundingClientRect();return{x:Math.max(0,Math.min(source!.width-1,Math.floor(((e.clientX-b.left)/b.width*384-referenceFit.x)/referenceFit.w*source!.width))),y:Math.max(0,Math.min(source!.height-1,Math.floor(((e.clientY-b.top)/b.height*256-referenceFit.y)/referenceFit.h*source!.height)))};};
  ref.onpointerdown=e=>{if(!source)return;ref.setPointerCapture(e.pointerId);cropStart=refPos(e);};
  ref.onpointermove=e=>{if(!cropStart||!source)return;const p=refPos(e);crop={x:Math.min(p.x,cropStart.x),y:Math.min(p.y,cropStart.y),w:Math.abs(p.x-cropStart.x)+1,h:Math.abs(p.y-cropStart.y)+1};drawReference();};
  ref.onpointerup=()=>{cropStart=null;};ref.onpointercancel=()=>{cropStart=null;};
  async function importFile(file:File) {
    if(busy)return;busy=true;
    const url=URL.createObjectURL(file);
    try {
      if(!['image/png','image/jpeg','image/webp'].includes(file.type)||file.size>20*1024*1024)throw new Error('Chọn PNG, JPG hoặc WebP không quá 20 MB.');
      const image=await loadImage(url);if(image.width*image.height>4194304)throw new Error('Ảnh vượt 4 triệu pixel. Hãy cắt phần vật phẩm trước.');
      source=image;crop={x:0,y:0,w:image.width,h:image.height};
      el('itemReference').parentElement!.hidden=false;el<HTMLButtonElement>('itemPrepare').disabled=false;drawReference();
      note('Đã nhận ảnh. Chọn vùng vật phẩm rồi bấm Đưa lên bảng vẽ.');
    }catch(e){note(e instanceof Error?e.message:'Không mở được ảnh.',true);}finally{busy=false;URL.revokeObjectURL(url);}
  }
  button('itemImport',()=>input('itemFile').click());
  input('itemFile').onchange=()=>{const f=input('itemFile').files?.[0];if(f)void importFile(f);input('itemFile').value='';};
  dialog.addEventListener('dragover',e=>{e.preventDefault();});dialog.addEventListener('drop',e=>{e.preventDefault();const f=e.dataTransfer?.files[0];if(f)void importFile(f);});
  button('itemFullCrop',()=>{if(source){crop={x:0,y:0,w:source.width,h:source.height};drawReference();}});
  button('itemPrepare',()=>{
    if(!source||busy)return;
    const temp=document.createElement('canvas');temp.width=crop.w;temp.height=crop.h;const c=temp.getContext('2d')!;
    c.drawImage(source,crop.x,crop.y,crop.w,crop.h,0,0,crop.w,crop.h);
    let data:Raster={width:crop.w,height:crop.h,data:c.getImageData(0,0,crop.w,crop.h).data};
    if(input('itemRemoveBg').checked)data=removeBorderBackground(data,rgba(input('itemBgColor').value),number('itemTolerance',0,100));
    const b=pixelBounds(data);if(!b)return note('Vùng chọn trống sau khi bỏ nền. Giảm độ lệch màu hoặc bỏ chọn tách nền.',true);
    c.putImageData(new ImageData(new Uint8ClampedArray(data.data),crop.w,crop.h),0,0);
    mutate(()=>{
      ctx.clearRect(0,0,layer.width,layer.height);ctx.imageSmoothingEnabled=el<HTMLSelectElement>('itemSampling').value==='photo';ctx.imageSmoothingQuality='high';
      const size=Math.min(layer.width-2,number('itemImportSize',4,128)),scale=size/Math.max(b.w,b.h),w=Math.max(1,Math.round(b.w*scale)),h=Math.max(1,Math.round(b.h*scale));
      ctx.drawImage(temp,b.x,b.y,b.w,b.h,Math.floor((layer.width-w)/2),Math.floor((layer.height-h)/2),w,h);
      let raster=read();for(let i=0;i<raster.data.length;i+=4){if(raster.data[i+3]!<128)raster.data.fill(0,i,i+4);else raster.data[i+3]=255;}
      const count=Number(input('itemPaletteSize').value);if(count)raster=reduceItemPalette(raster,count);write(raster);
      anchor={x:Math.floor(layer.width/2),y:Math.floor(layer.height/2)};setTool('move');
    },'Đã tạo item pixel. Dùng V để căn vị trí; A đặt điểm neo trên cán.');
  });
  function template(kind:string) {
    mutate(()=>{
      ctx.clearRect(0,0,layer.width,layer.height);const ox=Math.floor(layer.width/2),oy=Math.floor(layer.height/2)-14;
      const rect=(color:string,x:number,y:number,w:number,h:number)=>{ctx.fillStyle=color;ctx.fillRect(ox+x,oy+y,w,h);};
      if(kind==='sword') {
        rect('#29273d',-2,1,5,22);rect('#91bacf',-1,2,3,20);rect('#e3f5f5',-1,2,1,20);rect('#29273d',-6,21,13,3);rect('#ddb876',-5,21,11,1);rect('#29273d',-2,24,5,7);rect('#9b7152',-1,24,3,6);rect('#ddb876',-2,30,5,2);anchor={x:ox,y:oy+27};
      } else if(kind==='staff') {
        rect('#33293f',-2,8,5,24);rect('#a77450',-1,8,3,24);rect('#e3b96a',0,10,1,21);rect('#33293f',-5,0,11,10);rect('#b6a0f7',-3,1,7,7);rect('#e8dbff',-2,2,3,3);rect('#ddb876',-4,9,9,2);anchor={x:ox,y:oy+25};
      } else {
        rect('#29273d',-9,5,19,18);rect('#29273d',-6,23,13,3);rect('#29273d',-3,26,7,2);rect('#ccaf77',-8,6,17,16);rect('#719eb5',-6,8,13,14);rect('#719eb5',-4,21,9,4);rect('#bddde2',-5,9,2,11);rect('#e9d599',-1,10,3,12);rect('#e9d599',-4,14,9,3);anchor={x:ox,y:oy+16};
      }
      input('itemName').value={sword:'kiem',staff:'truong',shield:'khien'}[kind]||'item';setTool('move');
    },'Mẫu đã sẵn sàng. Kéo item đến bàn tay, rồi chỉnh màu hoặc vẽ thêm.');
  }
  dialog.querySelectorAll<HTMLButtonElement>('[data-template]').forEach(b=>b.onclick=()=>template(b.dataset.template!));
  button('itemBlank',()=>mutate(()=>{ctx.clearRect(0,0,layer.width,layer.height);anchor={x:layer.width/2,y:layer.height/2};input('itemName').value='item-moi';setTool('brush');},'Bảng vẽ trống đã sẵn sàng. Có thể hoàn tác để lấy lại item trước.'));
  button('itemUndo',()=>changeHistory(true));button('itemRedo',()=>changeHistory(false));
  button('itemGrid',()=>{showGrid=!showGrid;el('itemGrid').setAttribute('aria-pressed',String(showGrid));draw();});
  button('itemSymmetry',()=>{symmetry=!symmetry;el('itemSymmetry').setAttribute('aria-pressed',String(symmetry));});
  input('itemShowGuide').onchange=draw;
  button('itemZoomIn',()=>{zoom=Math.min(4,zoom+.25);fitBoard();});button('itemZoomOut',()=>{zoom=Math.max(.5,zoom-.25);fitBoard();});button('itemFit',()=>{zoom=1;fitBoard();});
  input('itemSize').onchange=()=>{const size=number('itemSize',32,128);mutate(()=>{const old=snapshot(),shift=Math.floor((size-old.raster.width)/2);layer.width=layer.height=size;const temp=document.createElement('canvas');temp.width=old.raster.width;temp.height=old.raster.height;temp.getContext('2d')!.putImageData(new ImageData(new Uint8ClampedArray(old.raster.data),old.raster.width,old.raster.height),0,0);ctx.drawImage(temp,shift,shift);anchor={x:anchor.x+shift,y:anchor.y+shift};},'Đã đổi lưới, giữ kích thước pixel. Pixel ngoài lưới bị cắt; Ctrl+Z để trở lại.');};
  button('itemFlipX',()=>mutate(()=>{write(transformItem(read(),'flipX'));anchor.x=layer.width-1-anchor.x;}));
  button('itemRotate',()=>mutate(()=>{const {x,y}=anchor;write(transformItem(read(),'right'));anchor={x:layer.width-1-y,y:x};}));
  button('itemOutline',()=>mutate(()=>write(outlineItem(read(),[37,35,51])),'Đã tạo viền trong 1px, giữ nguyên kích thước item.'));
  button('itemReduce',()=>{const count=Number(input('itemPaletteSize').value);if(!count)return note('Chọn 8, 16 hoặc 32 màu trong bảng bên trái.');mutate(()=>write(reduceItemPalette(read(),count)),`Đã gom về tối đa ${count} màu, không dithering.`);});
  input('itemName').onchange=()=>finish();
  const filename=()=>input('itemName').value.replace(/[^\p{L}\p{N}_-]+/gu,'-').slice(0,80)||'item';
  button('itemExport',()=>{download(layer.toDataURL(),`${filename()}.png`);note('Đã xuất PNG trong suốt. Nhân vật, lưới và điểm neo không nằm trong ảnh.');});
  button('itemSave',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(project())],{type:'application/json'}));download(url,`${filename()}.item.json`);setTimeout(()=>URL.revokeObjectURL(url),1000);note('Đã lưu bản vẽ và điểm neo tay cầm.');});
  async function openProject(p:unknown,history=true) {
    if(!p||typeof p!=='object')throw new Error('Bản vẽ không hợp lệ.');
    const data=p as Record<string,unknown>,a=data.anchor as PixelPoint|undefined;
    if(data.format!=='hkt-pixel-item'||data.version!==1||![32,64,128].includes(Number(data.width))||data.height!==data.width||typeof data.png!=='string'||!data.png.startsWith('data:image/png;base64,')||data.png.length>2_000_000||!a||!Number.isInteger(a.x)||!Number.isInteger(a.y)||Math.abs(a.x)>1024||Math.abs(a.y)>1024)throw new Error('Sai định dạng bản vẽ item.');
    const image=await loadImage(data.png);if(image.width!==data.width||image.height!==data.height)throw new Error('Ảnh item không khớp lưới.');
    if(history)capture();layer.width=image.width;layer.height=image.height;ctx.drawImage(image,0,0);anchor={x:a.x,y:a.y};input('itemName').value=String(data.name||'item').slice(0,80);input('itemSize').value=String(image.width);finish('Đã mở bản vẽ item.');
  }
  button('itemOpen',()=>input('itemProjectFile').click());
  input('itemProjectFile').onchange=async()=>{const f=input('itemProjectFile').files?.[0];if(!f||busy)return;busy=true;try{if(f.size>2_000_000)throw new Error('Bản vẽ vượt 2 MB.');await openProject(JSON.parse(await f.text()));}catch(e){note(e instanceof Error?e.message:'Không mở được bản vẽ.',true);}finally{busy=false;input('itemProjectFile').value='';draw();}};
  button('itemApply',()=>{
    const current=grid();if(busy||state.busy||!current||!state.base||!pixelBounds(read()))return;
    if(!frame||current.frame!==frame.frame||current.w!==frame.w||current.h!==frame.h){syncGuide();draw();return note('Frame đã thay đổi. Kiểm tra vị trí rồi gắn lại.');}
    checkpoint(paintLayer,current);paintContext.save();paintContext.imageSmoothingEnabled=false;
    // Invert the guide's contain transform. Clip to the active frame so a
    // non-square frame can never spill item pixels into adjacent animations.
    const scale=Math.max(current.w/layer.width,current.h/layer.height),w=Math.round(layer.width*scale),h=Math.round(layer.height*scale);
    paintContext.beginPath();paintContext.rect(current.x,current.y,current.w,current.h);paintContext.clip();
    paintContext.drawImage(layer,current.x+Math.floor((current.w-w)/2),current.y+Math.floor((current.h-h)/2),w,h);paintContext.restore();
    invalidate(`Đã gắn item vào frame ${current.frame+1}. Bấm Xử lý sprite để cập nhật bản xuất.`);render();remember();
    dialog.close();
  });
  button('itemClose',()=>dialog.close());dialog.addEventListener('close',()=>{endStroke();persist();if(resumePlayback&&!isPlaying)togglePlayPause();resumePlayback=false;});
  let restored=false;
  launch.onclick=async()=>{resumePlayback=isPlaying;if(resumePlayback)togglePlayPause();dialog.showModal();syncGuide();draw();fitBoard();updateSwatches();
    if(!restored){restored=true;try{const saved=localStorage.getItem(DRAFT);if(saved){busy=true;await openProject(JSON.parse(saved),false);}}catch{note('Không đọc được bản nháp. Bạn có thể mở file bản vẽ đã lưu.',true);}finally{busy=false;draw();}}
  };
  window.addEventListener('keydown',e=>{
    if(!dialog.open){if(e.altKey&&e.key.toLowerCase()==='j'){e.preventDefault();launch.click();}return;}
    // Capture before the existing editor shortcuts. Keep native form editing,
    // Tab focus navigation and Escape dialog closing available.
    e.stopImmediatePropagation();
    if(e.key==='Escape')return;
    if((e.target as HTMLElement).matches('input,select,textarea'))return;
    const key=e.key.toLowerCase();
    if((e.ctrlKey||e.metaKey)&&(key==='z'||key==='y')){e.preventDefault();changeHistory(key==='z'&&!e.shiftKey);return;}
    if(busy)return;
    const selected=tools.find(t=>t[1].toLowerCase()===key);if(selected&&!e.ctrlKey&&!e.metaKey){e.preventDefault();setTool(selected[0]);}
    const arrows:Record<string,[number,number]>={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
    if(arrows[e.key]){e.preventDefault();const [x,y]=arrows[e.key]!,step=e.shiftKey?5:1;mutate(()=>translate(snapshot(),x*step,y*step));}
  },true);
  window.addEventListener('keyup',e=>{if(dialog.open)e.stopImmediatePropagation();},true);
  new MutationObserver(()=>{if(dialog.open&&!state.busy){syncGuide();draw();}}).observe(document.getElementById('status')!,{childList:true});
  window.addEventListener('pagehide',()=>{if(restored)persist();});
  new ResizeObserver(fitBoard).observe(el('itemStage'));
}
