import './map-assets.css';
import { readFile, loadImage } from './utils';
import { pixelLine } from './item-pixels';
import type { MapLibraryAsset } from './map-asset-model';

type Result = { id:string; image:string; original:string; mask:string; width:number; height:number;
  report:{ colors:number; visiblePixels:number; partialAlphaPixels:number } };
type Item = { id:string; name:string; image:string; width:number; height:number; pivotX:number; pivotY:number;
  result?:Result; edits:HTMLCanvasElement; undo:ImageData[]; stale:boolean; revision:number };
type Settings = { colors:number; alphaMode:string; alphaLow:number; alphaHigh:number; smooth:number; chroma:number; contrast:number };
const canvas = () => document.createElement('canvas');

async function request(path:string, body:unknown, binary=false) {
  const json = JSON.stringify(body);
  if (new Blob([json]).size > 32*1024*1024) throw new Error('Lượt xử lý vượt 32 MB; hãy chia nhỏ danh sách.');
  const response = await fetch(`/api/map-assets/${path}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:json});
  if (!response.ok) {
    const data = await response.json().catch(()=>({}));
    throw new Error(data.error || (response.status === 404 ? 'Khởi động lại server Python để bật công cụ asset map.' : `Không xử lý được yêu cầu (${response.status}).`));
  }
  return binary ? response.blob() : response.json();
}

function downloadBlob(blob:Blob, name:string) {
  const a = document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=name; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000);
}

/** A Map sub-workbench. Sources stay immutable; edits only affect the mask. */
export function setupMapAssets(onAdd:(assets:MapLibraryAsset[])=>Promise<void>) {
  const dialog = document.createElement('dialog');
  dialog.className='map-assets-studio'; dialog.id='mapAssetsStudio'; dialog.setAttribute('aria-labelledby','maTitle');
  dialog.innerHTML=`
    <header class="ma-header"><div><h2 id="maTitle">Tách & làm sạch asset map</h2><p>Giữ kích thước gốc · duyệt khuôn · đặt vật thể lên map</p></div><button id="maClose" aria-label="Đóng bàn asset">✕</button></header>
    <div class="ma-layout">
      <aside class="ma-sidebar">
        <label class="ma-file">+ PNG / sprite sheet<input id="maImages" type="file" accept="image/png,image/webp,image/jpeg" multiple></label>
        <label class="ma-file">+ ZIP item<input id="maZip" type="file" accept=".zip,application/zip"></label>
        <label class="ma-check"><input id="maUseSheet" type="checkbox">Lấy màu gốc từ sheet đang mở và tọa độ trong ZIP</label>
        <button id="maDemo">Mở 3 mẫu nghiên cứu</button>
        <div class="ma-inline"><button id="maCropToggle">Cắt từ sheet</button><button id="maDelete">Bỏ item</button></div>
        <button id="maRemoveEmpty">Bỏ item rỗng sau xử lý</button>
        <div class="ma-muted" id="maCount">Chưa có item</div>
        <div class="ma-items" id="maItems" aria-label="Danh sách item"></div>
      </aside>
      <main class="ma-main">
        <div class="ma-bar">
          <label>Phóng <select id="maZoom"><option value="1">100%</option><option value="2" selected>200%</option><option value="4">400%</option><option value="8">800%</option></select></label>
          <label>Nền <select id="maBackground"><option value="checker">Caro</option><option value="white">Trắng</option><option value="dark">Xanh đen</option></select></label>
          <label><input id="maShowMask" type="checkbox">Xem khuôn</label>
          <span class="ma-muted" id="maDimensions">Chọn ảnh để bắt đầu</span>
        </div>
        <section class="ma-crop" id="maCropPanel" hidden>
          <p class="ma-muted">Kéo trên sheet để khoanh một item. Khung cắt giữ nguyên pixel nguồn.</p>
          <div class="ma-sheet-scroll"><canvas id="maSheet" aria-label="Sheet nguồn; kéo để chọn vùng cắt"></canvas></div>
          <div class="ma-crop-fields">
            <label>X<input id="maCropX" type="number" min="0" value="0"></label><label>Y<input id="maCropY" type="number" min="0" value="0"></label>
            <label>Rộng<input id="maCropW" type="number" min="1" value="1"></label><label>Cao<input id="maCropH" type="number" min="1" value="1"></label>
            <button id="maCropAdd">Thêm vùng thành item</button>
          </div>
        </section>
        <div class="ma-previews">
          <figure><figcaption>Ảnh nguồn</figcaption><div class="ma-viewport"><canvas id="maOriginal" aria-label="Ảnh nguồn của item"></canvas></div></figure>
          <figure><figcaption id="maResultLabel">Kết quả / sửa khuôn</figcaption><div class="ma-viewport" id="maEditViewport"><canvas id="maResult" aria-label="Kết quả; có thể tẩy hoặc giữ khuôn"></canvas></div></figure>
        </div>
        <div class="ma-result-info" id="maReport">Mở PNG hoặc ZIP để xem từng item. Với sheet, khoanh đúng vật thể trước khi xử lý.</div>
      </main>
      <aside class="ma-controls">
        <div><div class="ma-label">01 · Khuôn vật thể</div>
          <label>Alpha<select id="maAlpha"><option value="hard">Nét đặc 0 / 255</option><option value="preserve" selected>Giữ alpha gốc</option></select></label>
          <label>Ngưỡng viền<input id="maLow" type="number" min="1" max="255" value="110"></label>
          <label>Ngưỡng lõi<input id="maHigh" type="number" min="1" max="255" value="200"></label>
          <div class="ma-inline"><button id="maInspect" class="active">Xem</button><button id="maErase">Tẩy</button><button id="maRestore">Giữ</button></div>
          <label>Cỡ cọ<input id="maBrush" type="number" min="1" max="24" value="3"></label>
          <div class="ma-inline"><button id="maUndoMask">Hoàn tác</button><button id="maResetMask">Bỏ sửa khuôn</button></div>
          <p class="ma-muted">Đỏ: bỏ vùng thừa. Xanh: giữ chi tiết. Xử lý lại để áp dụng.</p>
        </div>
        <div><hr><div class="ma-label">02 · Màu sắc</div>
          <label>Bảng màu<select id="maColors"><option value="0">Giữ nhiều chi tiết</option><option value="128">128 màu</option><option value="64">64 màu</option><option value="48">48 màu</option></select></label>
          <label>Gom nhiễu nhẹ<input id="maSmooth" type="number" min="0" max="32" value="0"></label>
          <label>Độ đậm màu<input id="maChroma" type="number" min="0.5" max="1.5" step="0.02" value="1"></label>
          <label>Tương phản<input id="maContrast" type="number" min="0.5" max="1.5" step="0.02" value="1"></label>
          <button class="primary ma-wide" id="maProcess">Làm sạch item đang chọn</button>
          <button class="ma-wide" id="maProcessAll">Làm sạch cả danh sách</button>
          <p class="ma-muted">Xử lý cả danh sách để dùng chung bảng màu. Ảnh thiếu chi tiết vẫn cần vẽ lại.</p>
        </div>
        <div><hr><div class="ma-label">03 · Đặt lên map & xuất</div>
          <label>Tên<input id="maName" maxlength="160" placeholder="Tên item"></label>
          <label>Điểm chân X<input id="maPivotX" type="number" min="0" value="0"></label>
          <label>Điểm chân Y<input id="maPivotY" type="number" min="0" value="0"></label>
          <button class="primary ma-wide" id="maAdd">Đưa item vào thư viện Map</button>
          <button class="ma-wide" id="maAddAll">Đưa cả danh sách vào Map</button>
          <div class="ma-inline"><button id="maPng">PNG item</button><button id="maExport">ZIP danh sách</button></div>
          <p class="ma-muted">Vật thể giữ kích thước riêng. Các cạnh terrain cần được thiết kế để nối khớp.</p>
        </div>
      </aside>
    </div><div class="ma-footer" id="maStatus" role="status">Sẵn sàng. File gốc được giữ riêng khi làm sạch.</div>`;
  document.body.append(dialog);
  const el = <T extends HTMLElement>(id:string) => dialog.querySelector<T>(`#${id}`)!;
  const input = (id:string) => el<HTMLInputElement>(id);
  const value = (id:string) => Number(input(id).value);
  let items:Item[]=[], selected='', busy=false, tool:'view'|'erase'|'restore'='view';
  let sheet:{image:HTMLImageElement;url:string;name:string}|null=null;
  let renderToken=0, stroke:{item:Item;last:{x:number;y:number}}|null=null;
  const current=()=>items.find(i=>i.id===selected);
  const status=(message:string,error=false)=>{el('maStatus').textContent=message; el('maStatus').dataset.error=String(error);};
  const settings=():Settings=>({colors:value('maColors'),alphaMode:input('maAlpha').value,alphaLow:value('maLow'),alphaHigh:value('maHigh'),smooth:value('maSmooth'),chroma:value('maChroma'),contrast:value('maContrast')});
  const ready=(item:Item)=>!!item.result && !item.stale && item.result.report.visiblePixels>0;

  function buttons() {
    const item=current(), allReady=items.length>0&&items.every(ready);
    for (const id of ['maProcess','maProcessAll','maDelete','maUndoMask','maResetMask']) el<HTMLButtonElement>(id).disabled=busy||!item;
    for (const id of ['maAdd','maPng']) el<HTMLButtonElement>(id).disabled=busy||!item||!ready(item);
    for (const id of ['maAddAll','maExport']) el<HTMLButtonElement>(id).disabled=busy||!allReady;
    el<HTMLButtonElement>('maCropAdd').disabled=busy||!sheet;
    el<HTMLButtonElement>('maCropToggle').disabled=!sheet||busy;
    el<HTMLButtonElement>('maRemoveEmpty').disabled=busy||!items.some(i=>i.result&&!i.stale&&i.result.report.visiblePixels===0);
    for (const id of ['maImages','maZip','maDemo']) (el(id) as HTMLInputElement|HTMLButtonElement).disabled=busy;
  }
  function list() {
    const host=el('maItems'); host.replaceChildren();
    for(const item of items) {
      const b=document.createElement('button'); b.className=`ma-item ${item.id===selected?'active':''}`;
      b.type='button'; b.setAttribute('aria-pressed',String(item.id===selected));
      const img=new Image(); img.src=item.result?.image||item.image; img.alt='';
      const label=document.createElement('span'); label.textContent=item.name;
      const sub=document.createElement('small'); sub.textContent=`${item.width} × ${item.height} · ${ready(item)?'Đã xử lý':item.stale&&item.result?'Cần xử lý lại':'Nguồn'}`;
      label.append(sub); b.append(img,label); b.onclick=()=>{if(!busy){selected=item.id;list();void render();}};
      host.append(b);
    }
    el('maCount').textContent=`${items.length} item · ${items.filter(ready).length} đã xử lý`;
    buttons();
  }

  async function render() {
    const token=++renderToken, item=current();
    const left=el<HTMLCanvasElement>('maOriginal'), right=el<HTMLCanvasElement>('maResult');
    dialog.querySelectorAll<HTMLElement>('.ma-viewport').forEach(v=>v.dataset.bg=input('maBackground').value);
    el('maEditViewport').dataset.edit=String(tool!=='view');
    if(!item){left.width=right.width=1;left.height=right.height=1;el('maReport').textContent='Chưa chọn item.';buttons();return;}
    const [original,result]=await Promise.all([loadImage(item.image),loadImage(input('maShowMask').checked&&item.result?item.result.mask:item.result?.image||item.image)]);
    if(token!==renderToken)return;
    const zoom=value('maZoom');
    for(const [c,im] of [[left,original],[right,result]] as const){c.width=item.width;c.height=item.height;c.style.width=`${item.width*zoom}px`;c.style.height=`${item.height*zoom}px`;c.getContext('2d')!.drawImage(im,0,0);}
    if(tool!=='view') {const ctx=right.getContext('2d')!;ctx.globalAlpha=.65;ctx.drawImage(item.edits,0,0);ctx.globalAlpha=1;}
    el('maDimensions').textContent=`${item.width} × ${item.height} px · không resize`;
    input('maName').value=item.name;input('maPivotX').value=String(item.pivotX);input('maPivotY').value=String(item.pivotY);
    input('maPivotX').max=String(item.width);input('maPivotY').max=String(item.height);
    const r=item.result?.report;
    el('maReport').textContent=r?`${r.colors.toLocaleString()} màu · ${r.visiblePixels.toLocaleString()} pixel hiện · ${r.partialAlphaPixels.toLocaleString()} pixel bán trong suốt${item.stale?' · Đã đổi khuôn/thông số: cần xử lý lại.':''}`:'Nguồn giữ nguyên. Chọn Làm sạch để tạo kết quả.';
    buttons();
  }

  async function addSources(sources:{image:string;name:string;pivot?:number[]}[]) {
    if(items.length+sources.length>512)throw new Error('Tối đa 512 item.');
    const incoming:Item[]=[];
    let total=items.reduce((n,i)=>n+i.width*i.height,0);
    for(const src of sources){
      const im=await loadImage(src.image);total+=im.width*im.height;
      if(im.width*im.height>1048576||total>4194304)throw new Error('Item tối đa 1 triệu pixel; danh sách tối đa 4 triệu pixel.');
      const edits=canvas();edits.width=im.width;edits.height=im.height;
      incoming.push({id:crypto.randomUUID(),name:src.name.slice(0,160),image:src.image,width:im.width,height:im.height,
        pivotX:Math.max(0,Math.min(im.width,src.pivot?.[0]??Math.floor(im.width/2))),pivotY:Math.max(0,Math.min(im.height,src.pivot?.[1]??im.height)),edits,undo:[],stale:false,revision:0});
    }
    items.push(...incoming); selected=incoming[0]?.id||selected;list();await render();
  }
  async function run(action:()=>Promise<void>) {
    if(busy)return;
    busy=true;buttons();
    try{await action();}catch(e){status(e instanceof Error?e.message:String(e),true);}finally{busy=false;buttons();}
  }
  function markStale(item:Item){item.stale=true;item.revision++;buttons();}
  function cropRect(){return {x:value('maCropX'),y:value('maCropY'),w:value('maCropW'),h:value('maCropH')};}
  function drawSheet(){
    if(!sheet)return;
    const c=el<HTMLCanvasElement>('maSheet'),ctx=c.getContext('2d')!;
    c.width=sheet.image.width;c.height=sheet.image.height;
    const scale=Math.min(1,600/c.width);c.style.width=`${c.width*scale}px`;c.style.height=`${c.height*scale}px`;
    ctx.drawImage(sheet.image,0,0);const r=cropRect();ctx.strokeStyle='#ffce64';ctx.lineWidth=2/scale;ctx.strokeRect(r.x,r.y,r.w,r.h);
  }
  function point(e:PointerEvent,c:HTMLCanvasElement){const r=c.getBoundingClientRect();return {x:Math.max(0,Math.min(c.width-1,Math.floor((e.clientX-r.left)*c.width/r.width))),y:Math.max(0,Math.min(c.height-1,Math.floor((e.clientY-r.top)*c.height/r.height)))};}

  input('maImages').onchange=()=>void run(async()=>{
    const files=Array.from(input('maImages').files||[]);input('maImages').value='';
    if(!files.length)return;
    if(files.length===1){
      const url=await readFile(files[0]!);const im=await loadImage(url);
      if(im.width*im.height>4194304)throw new Error('Sheet vượt quá 4 triệu pixel.');
      sheet={image:im,url,name:files[0]!.name};input('maCropX').value=input('maCropY').value='0';input('maCropW').value=String(im.width);input('maCropH').value=String(im.height);drawSheet();
      el('maCropPanel').hidden=im.width<=512&&im.height<=512;
      if(im.width<=512&&im.height<=512)await addSources([{image:url,name:files[0]!.name}]);
      status('Đã mở ảnh. Khoanh từng item trên sheet hoặc nhập ZIP kèm tọa độ nguồn.');
    }else{const sources=await Promise.all(files.map(async f=>({image:await readFile(f),name:f.name})));await addSources(sources);status(`Đã nhập ${sources.length} PNG.`);}
  });
  input('maZip').onchange=()=>void run(async()=>{
    const file=input('maZip').files?.[0];input('maZip').value='';if(!file)return;
    if(input('maUseSheet').checked&&!sheet)throw new Error('Mở sheet nguồn trước khi dùng tọa độ trong ZIP.');
    status('Đang đọc ZIP…');
    const data=await request('import',{archive:await readFile(file),sheet:input('maUseSheet').checked?sheet!.url:undefined});
    await addSources(data.items);status(`Đã nhập ${data.items.length} item${input('maUseSheet').checked?' từ màu gốc của sheet':''}. Duyệt khuôn trước khi dùng.`);
  });
  el('maDemo').onclick=()=>void run(async()=>{
    const sources=await Promise.all([['platform','Bục đá'],['gate','Cổng'],['bamboo','Cụm tre']].map(async([slug,name])=>{
      const response=await fetch(`/assets/map-cleanup-demo/${slug}.png`);if(!response.ok)throw new Error('Không tải được bộ mẫu.');
      return {image:await readFile(await response.blob() as File),name:name!};
    }));await addSources(sources);status('Đã mở 3 mẫu gốc. Mẫu cổng cần tẩy các mảnh thừa ở mép phải và chân.');
  });
  el('maCropToggle').onclick=()=>{el('maCropPanel').hidden=!el('maCropPanel').hidden;drawSheet();};
  for(const id of ['maCropX','maCropY','maCropW','maCropH'])input(id).onchange=drawSheet;
  let start:{x:number;y:number}|null=null;
  const sheetCanvas=el<HTMLCanvasElement>('maSheet');
  sheetCanvas.onpointerdown=e=>{if(busy||!sheet)return;start=point(e,sheetCanvas);sheetCanvas.setPointerCapture(e.pointerId);};
  sheetCanvas.onpointermove=e=>{if(!start)return;const p=point(e,sheetCanvas);input('maCropX').value=String(Math.min(p.x,start.x));input('maCropY').value=String(Math.min(p.y,start.y));input('maCropW').value=String(Math.abs(p.x-start.x)+1);input('maCropH').value=String(Math.abs(p.y-start.y)+1);drawSheet();};
  sheetCanvas.onpointerup=sheetCanvas.onpointercancel=()=>{start=null;};
  el('maCropAdd').onclick=()=>void run(async()=>{if(!sheet)return;status('Đang lấy pixel gốc…');const data=await request('crop',{image:sheet.url,crop:cropRect()});await addSources([{image:data.image,name:`${sheet.name.replace(/\.[^.]+$/,'')}-${items.length+1}`}]);status('Đã thêm item. Có thể cắt thêm vùng hoặc làm sạch.');});
  el('maDelete').onclick=()=>{if(busy)return;items=items.filter(i=>i.id!==selected);selected=items[0]?.id||'';list();void render();};
  el('maRemoveEmpty').onclick=()=>{if(busy)return;const before=items.length;items=items.filter(i=>!i.result||i.stale||i.result.report.visiblePixels>0);if(!current())selected=items[0]?.id||'';list();void render();status(`Đã bỏ ${before-items.length} item rỗng khỏi danh sách làm việc.`);};

  async function processItems(targets:Item[]) {
    if(!targets.length)return;
    status(`Đang xử lý ${targets.length} item bằng Python…`);
    const opt=settings();const versions=new Map(targets.map(i=>[i.id,i.revision]));
    const data=await request('process',{settings:opt,items:targets.map(i=>({id:i.id,name:i.name,image:i.image,overrides:i.edits.toDataURL()}))});
    for(const result of data.items as Result[]){const item=items.find(i=>i.id===result.id);if(item){item.result=result;item.stale=item.revision!==versions.get(item.id)||JSON.stringify(settings())!==JSON.stringify(opt);}}
    list();await render();status(`Đã xử lý ${targets.length} item. Kiểm tra trên nền trắng/tối trước khi đưa vào Map.`);
  }
  el('maProcess').onclick=()=>void run(()=>processItems(current()?[current()!]:[]));
  el('maProcessAll').onclick=()=>void run(()=>processItems(items));
  for(const id of ['maAlpha','maLow','maHigh','maColors','maSmooth','maChroma','maContrast'])input(id).oninput=()=>{items.forEach(markStale);list();void render();};
  for(const id of ['maZoom','maBackground','maShowMask'])input(id).onchange=()=>void render();
  for(const [id,mode] of [['maInspect','view'],['maErase','erase'],['maRestore','restore']] as const){el(id).onclick=()=>{tool=mode;for(const other of ['maInspect','maErase','maRestore'])el(other).classList.toggle('active',other===id);void render();};}
  const resultCanvas=el<HTMLCanvasElement>('maResult');
  function dab(e:PointerEvent){
    if(!stroke)return;const p=point(e,resultCanvas),ctx=stroke.item.edits.getContext('2d')!;
    const size=Math.max(1,Math.min(24,Math.round(value('maBrush')||1))),half=Math.floor(size/2);
    ctx.fillStyle=tool==='erase'?'#ff0000':'#00ff00';
    for(const q of pixelLine(stroke.last,p))ctx.fillRect(q.x-half,q.y-half,size,size);
    stroke.last=p;markStale(stroke.item);void render();
  }
  resultCanvas.onpointerdown=e=>{const item=current();if(busy||tool==='view'||!item)return;e.preventDefault();item.undo.push(item.edits.getContext('2d')!.getImageData(0,0,item.width,item.height));if(item.undo.length>20)item.undo.shift();stroke={item,last:point(e,resultCanvas)};resultCanvas.setPointerCapture(e.pointerId);dab(e);};
  resultCanvas.onpointermove=e=>{if(stroke)dab(e);};
  resultCanvas.onpointerup=resultCanvas.onpointercancel=()=>{stroke=null;list();};
  el('maUndoMask').onclick=()=>{const item=current(),prior=item?.undo.pop();if(!item||!prior)return;item.edits.getContext('2d')!.putImageData(prior,0,0);markStale(item);list();void render();};
  el('maResetMask').onclick=()=>{const item=current();if(!item)return;item.undo.push(item.edits.getContext('2d')!.getImageData(0,0,item.width,item.height));if(item.undo.length>20)item.undo.shift();item.edits.getContext('2d')!.clearRect(0,0,item.width,item.height);markStale(item);list();void render();};
  input('maName').onchange=()=>{const item=current();if(item){item.name=input('maName').value.trim()||'item';list();}};
  for(const id of ['maPivotX','maPivotY'])input(id).onchange=()=>{const item=current();if(!item)return;const isX=id==='maPivotX';const v=Math.max(0,Math.min(isX?item.width:item.height,Math.round(value(id)||0)));item[isX?'pivotX':'pivotY']=v;input(id).value=String(v);};

  async function addToMap(targets:Item[]) {
    if(!targets.length||!targets.every(ready))throw new Error('Làm sạch lại các item đã thay đổi trước khi đưa vào Map.');
    await onAdd(targets.map(i=>({id:`custom-${crypto.randomUUID()}`,name:i.name,src:i.result!.image,w:i.width,h:i.height,pivotX:i.pivotX,pivotY:i.pivotY})));
    dialog.close();
  }
  el('maAdd').onclick=()=>void run(()=>addToMap(current()?[current()!]:[]));
  el('maAddAll').onclick=()=>void run(()=>addToMap(items));
  el('maPng').onclick=()=>void run(async()=>{const i=current();if(!i||!ready(i))return;downloadBlob(await (await fetch(i.result!.image)).blob(),`${i.name.replace(/\.[^.]+$/,'')}-clean.png`);status('Đã xuất PNG giữ nguyên kích thước.');});
  el('maExport').onclick=()=>void run(async()=>{
    if(!items.length||!items.every(ready))throw new Error('Làm sạch cả danh sách trước khi xuất.');
    const blob=await request('export',{items:items.map(i=>({name:i.name,image:i.result!.image,pivot:[i.pivotX,i.pivotY]}))},true);
    downloadBlob(blob,'map-assets-clean.zip');status('Đã xuất PNG riêng và manifest điểm đặt chân.');
  });
  el('maClose').onclick=()=>dialog.close();
  dialog.addEventListener('keydown',e=>{e.stopPropagation();if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'&&!(e.target instanceof HTMLInputElement)){e.preventDefault();if(!busy)el('maUndoMask').click();}});
  buttons();
  return {
    isOpen:()=>dialog.open,
    open:async(source?:{name:string;src:string})=>{
      if(!dialog.open)dialog.showModal();
      if(source)await run(async()=>{const response=await fetch(source.src);if(!response.ok)throw new Error('Không tải được vật thể.');await addSources([{name:source.name,image:await readFile(await response.blob() as File)}]);});
      else await render();
    }
  };
}
