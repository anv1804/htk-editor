import './ui-studio.css';
import { download, loadImage } from './utils';
import { isPlaying, togglePlayPause } from './timeline';
import { UIPaint, type PaintTool } from './ui-paint';
import { drawAssembly, partNames, type Recipe } from './ui-assembly';

type Settings={surface:string;metal:string;gem:string;width:number;height:number;border:number;detail:number;shadow:number;corner:string;crest:boolean;texture:boolean};
type Asset={id:string;name:string;primary:boolean;recipe?:Recipe|null;family?:string;part?:string;width:number;height:number;kind:string;margins:number[]|null;url:string;image:HTMLImageElement|HTMLCanvasElement};
type Element={id:string;asset:string;x:number;y:number;width?:number;height?:number;label?:string;fill?:string;value?:number;locked?:boolean;visible?:boolean};
const DEFAULT:Settings={surface:'#253f39',metal:'#b7975f',gem:'#8ab397',width:216,height:156,border:5,detail:2,shadow:3,corner:'cloud',crest:true,texture:true};
const THEMES=[{name:'Tử kim',sub:'Thạch anh · vàng cổ',surface:'#39243e',metal:'#c69a54',gem:'#9d639e'},
  {name:'Thanh ngọc',sub:'Ngọc bích · đồng ấm',surface:'#253f39',metal:'#b7975f',gem:'#8ab397'},
  {name:'Huyết nguyệt',sub:'Sơn son · hắc thiết',surface:'#422428',metal:'#b59677',gem:'#c55f65'}];
const KEY='hkt-ui-forge-v3';
const names:Record<string,string>={panel:'Khung bảng',button:'Nút & tab',skill:'Khung chiêu tròn',item:'Ô item / trang bị',inventory:'Bảng túi đồ',background:'Nền riêng',piece:'Mảnh ghép',joystick:'Joystick',scrollbar:'Thanh cuộn',bar:'Thanh HUD',fill:'Màu thanh HUD',ornament:'Trang trí'};

export function setupUIStudio(){
  const launch=document.createElement('button');launch.id='openUIStudio';launch.className='ui-launch';
  launch.innerHTML='<span aria-hidden="true">▣</span> Xưởng UI / HUD';launch.title='Thiết kế bộ giao diện (Alt+U)';
  document.querySelector('.project-actions')!.before(launch);
  const dialog=document.createElement('dialog');dialog.id='uiStudio';dialog.className='ui-studio';dialog.setAttribute('aria-labelledby','uiTitle');
  dialog.innerHTML=`
  <div class="uf-heading"><div class="uf-brand"><b>◈</b><div><small>HKT / INTERFACE ATELIER</small><h2 id="uiTitle">Xưởng UI / HUD</h2></div><span>Bộ giao diện của bạn</span></div>
    <div class="uf-actions"><button id="ufImport">Mở thiết kế</button><button id="ufSave">Lưu thiết kế</button><button id="ufExport" class="uf-primary">Xuất bộ Godot ↗</button><button id="ufClose" aria-label="Đóng xưởng UI">✕</button></div></div>
  <div class="uf-layout">
    <aside class="uf-library"><div class="uf-section"><small>01 / PHONG CÁCH</small><h3>Khung ghép · 16:9</h3><p>Đốt ngang, đốt dọc và lá góc tách riêng. Khung xanh đơn giản, lòng trong suốt.</p></div>
      <details class="uf-theme-details"><summary>Chọn sắc độ</summary><div class="uf-themes">${THEMES.map((t,i)=>`<button data-uf-theme="${i}" aria-pressed="${i===1}"><i style="--surface:${t.surface};--metal:${t.metal};--gem:${t.gem}">◈</i><span><strong>${t.name}</strong><small>${t.sub}</small></span></button>`).join('')}</div></details>
      <button id="ufGenerate" class="uf-primary">✦ Tạo bộ UI / HUD</button>
      <div class="uf-section uf-component-heading"><small>02 / THÀNH PHẦN</small><h3>Thư viện <span id="ufCount">—</span></h3></div>
      <select id="ufFilter" aria-label="Lọc thành phần"><option value="all">Tất cả thành phần</option>${Object.entries(names).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select>
      <input id="ufSearch" type="search" placeholder="Tìm khung, nền, thanh cuộn…" aria-label="Tìm thành phần">
      <label class="uf-check"><input id="ufSecondary" type="checkbox">Hiện thêm mẫu cũ</label>
      <div id="ufList" class="uf-list"></div>
      <p class="uf-tip">Chọn thành phần để xem. Bấm ＋ để đặt lên HUD.</p>
    </aside>
    <section class="uf-workspace"><div class="uf-toolbar"><div class="uf-tabs"><button data-uf-view="hud" aria-pressed="false">HUD mẫu</button><button data-uf-view="kit" aria-pressed="true">Bộ thành phần</button><button data-uf-view="assembly" aria-pressed="false">Ghép khung</button><button data-uf-view="asset" aria-pressed="false">Vẽ pixel</button></div>
      <label>Thu phóng <select id="ufZoom"><option value="fit">Vừa khung</option><option value="1">1×</option><option value="2">2×</option><option value="3">3×</option><option value="4">4×</option><option value="8">8×</option></select></label></div>
      <div class="uf-device-toolbar"><label>Màn hình <select id="ufDevice"><option value="640">Ngang 16:9 · 640 × 360</option><option value="780">Ngang 19.5:9 · 780 × 360</option><option value="800">Ngang 20:9 · 800 × 360</option></select></label><label class="uf-check"><input id="ufSafe" type="checkbox" checked>Vùng an toàn</label><span>Pixel gốc · góc giữ nguyên, cạnh nối thêm đốt</span></div>
      <div id="ufPaintTools" class="uf-paint-tools" hidden>
        <div class="uf-tabs">${[['brush','Bút · B'],['eraser','Tẩy · E'],['picker','Hút màu · I'],['fill','Đổ màu · G']].map(([k,label])=>`<button data-uf-tool="${k}" aria-pressed="${k==='brush'}">${label}</button>`).join('')}</div>
        <label>Màu <input id="ufPaintColor" type="color" value="#e3e9c4"></label><label>Cỡ <select id="ufPaintSize"><option>1</option><option>2</option><option>3</option><option>5</option></select></label>
        <label class="uf-check"><input id="ufGrid" type="checkbox">Lưới</label><button id="ufUndo" title="Ctrl+Z">↶</button><button id="ufRedo" title="Ctrl+Shift+Z">↷</button><button id="ufRestorePixels">Về mẫu sinh</button><span id="ufPaintState"></span>
      </div>
      <div class="uf-canvas-caption"><span id="ufCanvasTitle">HUYẾT KIẾM TÔNG / GIAO DIỆN</span><span id="ufDimensions">640 × 360</span></div>
      <div id="ufStage" class="uf-stage"><canvas id="ufCanvas" width="640" height="360" tabindex="0" aria-label="HUD mẫu: kéo để di chuyển, phím mũi tên để căn chỉnh"></canvas><div id="ufGallery" class="uf-gallery" hidden></div></div>
      <div class="uf-stage-footer"><span id="ufHint">Chọn một mẫu để vẽ pixel.</span><div><button id="ufLayoutUndo" title="Hoàn tác bố cục">↶</button><button id="ufLayoutRedo" title="Làm lại bố cục">↷</button><button id="ufTryStick" aria-pressed="false">Thử joystick</button><select id="ufPreset" aria-label="Bố cục mẫu"><option value="combat">HUD chiến đấu</option><option value="inventory">Túi đồ + trang bị</option><option value="chat">Chat + hội thoại</option></select><button id="ufTemplate">Áp dụng mẫu</button><button id="ufPNG">PNG thành phần ↓</button></div></div>
      <div class="uf-status" id="ufStatus" role="status" aria-live="polite">Chọn phong cách, bấm tạo để bắt đầu.</div>
    </section>
    <aside class="uf-inspector"><section id="ufAssembly" hidden><div class="uf-section"><small>LẮP GHÉP / MẢNH RỜI</small><h3 id="ufAssemblyTitle">Cấu tạo khung</h3></div><p id="ufRecipeHint" class="uf-tip"></p><div id="ufPieces" class="uf-pieces"></div><label class="uf-check"><input id="ufExplode" type="checkbox">Tách các mảnh để xem</label><button id="ufSplit">Tách khung thành mảnh</button><button id="ufAssemblyBack">Xem khung ghép</button><p class="uf-tip">Chọn mảnh để vẽ. Nét sửa áp dụng cho mọi khung dùng mảnh đó.</p></section><div class="uf-section"><small>03 / TÙY CHỈNH</small><h3>Màu & chất liệu</h3></div>
      <div class="uf-colors">${[['surface','Nền'],['metal','Kim loại'],['gem','Ngọc']].map(([k,label])=>`<label>${label}<input type="color" id="uf-${k}" data-setting="${k}" value="${DEFAULT[k as keyof Settings]}"></label>`).join('')}</div>
      <details class="uf-legacy-settings"><summary>Tùy chỉnh mẫu cũ</summary><div class="uf-fields"><label>Rộng bảng cũ<input id="uf-width" data-setting="width" type="number" min="96" max="400" value="216"></label><label>Cao bảng cũ<input id="uf-height" data-setting="height" type="number" min="80" max="280" value="156"></label></div>
      <p id="ufSizeNote" class="uf-tip" hidden>Panel đã vẽ tay. Về mẫu sinh của panel trước khi đổi kích thước.</p>
      <label class="uf-field">Kiểu góc<select id="uf-corner" data-setting="corner"><option value="cloud">Mây cuộn chạm nổi</option><option value="fret">Hồi văn cổ</option><option value="cut">Vát góc tinh giản</option></select></label>
      ${[['border','Độ dày khung',3,8,5],['detail','Độ cầu kỳ',0,3,2],['shadow','Độ lệch bóng',0,5,3]].map(([k,label,min,max,v])=>`<label class="uf-range">${label}<output id="uf-${k}-value">${v}</output><input id="uf-${k}" data-setting="${k}" type="range" min="${min}" max="${max}" value="${v}"></label>`).join('')}
      <label class="uf-check"><input id="uf-crest" data-setting="crest" type="checkbox" checked>Phù điêu đỉnh khung</label>
      </details><label class="uf-check"><input id="uf-texture" data-setting="texture" type="checkbox" checked>Vân nền và vân tre</label>
      <p class="uf-tip">Màu kim loại, ngọc và bóng áp dụng theo chất liệu từng mẫu. Độ dày, kiểu góc và phù điêu dành cho bộ khung phụ. Ảnh đã vẽ tay giữ nguyên khi đổi phong cách.</p>
      <div class="uf-selection"><div class="uf-section"><small>04 / BỐ CỤC HUD</small><h3 id="ufSelectionTitle">Chọn một thành phần</h3></div>
      <div id="ufNodeFields" hidden><label class="uf-field">Nhãn hiển thị<input id="ufLabel" maxlength="64" placeholder="Không có nhãn"></label>
      <div class="uf-fields"><label>X<input id="ufX" type="number" min="0" max="639"></label><label>Y<input id="ufY" type="number" min="0" max="359"></label></div>
      <div id="ufNodeSize" class="uf-fields" hidden><label>Rộng khung<input id="ufNodeW" type="number" min="32" max="800"></label><label>Cao khung<input id="ufNodeH" type="number" min="32" max="360"></label></div><p id="ufSizeHint" class="uf-tip" hidden>Cạnh lặp theo đốt. Lá góc là lớp phủ riêng, lòng khung trong suốt.</p>
      <label id="ufValueField" class="uf-range" hidden>Giá trị thanh <output id="ufValueText">75</output><input id="ufValue" type="range" min="0" max="100"></label>
      <div class="uf-node-actions"><button id="ufFront">Lên trước</button><button id="ufBack">Ra sau</button><button id="ufDuplicate">Nhân đôi</button><button id="ufDelete">Xóa</button></div></div>
      <section class="uf-layer-section"><h3>Các lớp HUD <span id="ufLayerCount">0</span></h3><div id="ufLayers" class="uf-layers"></div></section>
      <p class="uf-tip">640 × 360 px gốc. Khung ảnh có outline 1 px; phóng theo bội số nguyên để giữ nét.</p></div>
      <button id="ufReset" class="uf-quiet">Khôi phục phong cách gốc</button>
    </aside>
  </div><input id="ufFile" type="file" accept=".json,application/json" hidden>`;
  document.body.append(dialog);
  const el=<T extends HTMLElement>(id:string)=>dialog.querySelector<T>(`#${id}`)!;
  const input=(id:string)=>el<HTMLInputElement>(id);
  const canvas=el<HTMLCanvasElement>('ufCanvas'),ctx=canvas.getContext('2d')!;
  let s={...DEFAULT}, assets:Asset[]=[], nodes:Element[]=[], selected='inventory-board', active:string|null=null;
  let screen:[number,number]=[640,360],assemblyFamily='bamboo';
  let view='hud', busy=false, dirty=true, timer=0, serial=0, controller:AbortController|null=null, resumed=false;
  let edits:Record<string,string>={};const painters=new Map<string,UIPaint>();
  let painting:{id:string;pointer:number}|null=null,paintTool:PaintTool='brush';
  let tryStick=false,stick:{id:string;pointer:number;x:number;y:number}|null=null;
  let pendingLayout:Element[]|undefined;
  const assetMap=new Map<string,Asset>();
  const layoutUndo:Element[][]=[],layoutRedo:Element[][]=[];
  function checkpoint(){layoutUndo.push(structuredClone(nodes));if(layoutUndo.length>50)layoutUndo.shift();layoutRedo.length=0;}
  function undoLayout(redo=false){const source=redo?layoutRedo:layoutUndo,target=redo?layoutUndo:layoutRedo;const previous=source.pop();if(!previous)return;target.push(structuredClone(nodes));nodes=previous;active=null;inspector();persist();render();}
  function note(message:string,error=false){el('ufStatus').textContent=message;el('ufStatus').classList.toggle('error',error);}
  function design(){return {version:3,settings:s,layout:nodes,edits,canvas:screen};}
  function persist(){try{localStorage.setItem(KEY,JSON.stringify(design()));}catch{note('Không lưu được bản nháp. Dùng Lưu thiết kế để giữ bản vẽ.',true);}}
  function saveBlob(blob:Blob,name:string){const url=URL.createObjectURL(blob);download(url,name);setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function byId(id:string){return assetMap.get(id);}
  function current(){return nodes.find(n=>n.id===active);}
  function displaySize(a:Asset|undefined){const n=current();return {w:n?.asset===a?.id?n?.width??a?.width??224:a?.width??224,h:n?.asset===a?.id?n?.height??a?.height??176:a?.height??176};}
  function refreshAssemblies(){
    for(const a of assets){if(!a.recipe)continue;const image=document.createElement('canvas');image.width=a.width;image.height=a.height;drawAssembly(image.getContext('2d')!,a.recipe,a.width,a.height,byId);a.image=image;a.url=image.toDataURL('image/png');}
  }
  function assemblyInspector(){
    const a=byId(selected),family=a?.recipe?.family??a?.family;
    el('ufAssembly').hidden=!family;if(!family)return;assemblyFamily=family;
    const recipe=a?.recipe??assets.find(v=>v.recipe?.family===family)?.recipe;if(!recipe)return;
    const canSplit=Object.keys(recipe.pieces).length>0;
    el('ufSplit').hidden=!canSplit;el('ufAssemblyBack').hidden=!canSplit;input('ufExplode').closest('label')!.hidden=!canSplit;
    el('ufAssembly').querySelector<HTMLElement>('p:last-child')!.hidden=!canSplit;
    if(!canSplit)input('ufExplode').checked=false;
    el('ufRecipeHint').textContent=recipe.mode==='circle'?'Vòng một nét 1 px. Thay đường kính trong HUD; vòng được vẽ lại tại kích thước mới.':recipe.mode==='outline'?'Thanh cuộn một nét 1 px, không có nền. Rãnh và con trượt là hai lớp riêng.':recipe.mode==='tile'?'Nền riêng 32 × 32, lặp khi tăng kích thước. Đặt dưới lớp khung.':'Cạnh nối thêm đốt; góc giữ nguyên. Nền được thêm bằng một lớp riêng.';
    el('ufAssemblyTitle').textContent=a?.recipe?a.name:'Chỉnh mảnh dùng chung';
    const parts=el('ufPieces');parts.replaceChildren();
    for(const [part,id] of Object.entries(recipe.pieces)){
      const image=byId(id);if(!image)continue;const b=document.createElement('button');b.title=`Vẽ ${image.name}`;b.classList.toggle('selected',selected===id);
      const img=document.createElement('img');img.src=image.url;img.alt='';const text=document.createElement('span');text.textContent=partNames[part]??part;b.append(img,text);
      b.onclick=()=>{endDrag();selected=id;setView('asset');inspector();library();};parts.append(b);
    }
  }
  function syncSettings(){
    for(const [k,v] of Object.entries(s)){const control=input(`uf-${k}`);if(!control)continue;if(typeof v==='boolean')control.checked=v;else control.value=String(v);}
    for(const k of ['border','detail','shadow'] as const)el(`uf-${k}-value`).textContent=String(s[k]);
    dialog.querySelectorAll<HTMLElement>('[data-uf-theme]').forEach(b=>{const t=THEMES[Number(b.dataset.ufTheme)]!;b.setAttribute('aria-pressed',String(t.surface===s.surface&&t.metal===s.metal&&t.gem===s.gem));});
  }
  function lock(){
    for(const id of ['ufExport','ufPNG','ufSave'])(el(id) as HTMLButtonElement).disabled=busy||dirty||!assets.length;
    (el('ufGenerate') as HTMLButtonElement).disabled=busy;
    el('ufGenerate').textContent=busy?'Đang tạo bộ UI…':'✦ Tạo bộ UI / HUD';
    const paintedPanel=!!(edits.panel||edits['bamboo-panel']);
    input('uf-width').disabled=paintedPanel;input('uf-height').disabled=paintedPanel;el('ufSizeNote').hidden=!paintedPanel;
    paintControls();
  }
  async function generate(){
    clearTimeout(timer);controller?.abort();controller=new AbortController();const token=++serial;busy=true;dirty=true;lock();note('Đang vẽ khung, nút và hoa văn…');
    try{
      const layout=pendingLayout??(assets.length?nodes:undefined);
      const res=await fetch('/api/ui-forge/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({settings:s,edits,canvas:screen,...(layout?{layout}:{})}),signal:controller.signal});
      const data=await res.json();if(!res.ok)throw new Error(data.error||'Không tạo được bộ UI.');
      const loaded=await Promise.all((data.assets as Asset[]).map(async a=>({...a,image:await loadImage(a.url)})));
      if(token!==serial)return false;
      pendingLayout=undefined;
      for(const id of painters.keys())if(!edits[id])painters.delete(id);
      if(data.schema!==4)throw new Error('Server UI đang chạy bản cũ. Khởi động lại editor để tải bộ khung mới.');
      s=data.settings;screen=data.canvas??[640,360];el<HTMLSelectElement>('ufDevice').value=String(screen[0]);nodes=data.layout;assets=loaded;assetMap.clear();for(const a of assets)assetMap.set(a.id,a);if(!byId(selected))selected='frame-panel';dirty=false;syncSettings();persist();library();inspector();setView(view);
      note(`Khung ghép từ mảnh rời · Bấm ＋ để đặt lên HUD · Chọn khung trên HUD để đổi rộng/cao.`);
      return true;
    }catch(e){if(token===serial&&(e as Error).name!=='AbortError')note(`Không tạo được UI: ${(e as Error).message}`,true);return false;}
    finally{if(token===serial){busy=false;lock();}}
  }
  function schedule(){
    dirty=true;controller?.abort();serial++;busy=false;lock();syncSettings();
    note('Đã thay đổi cấu hình · đang cập nhật…');clearTimeout(timer);timer=window.setTimeout(()=>void generate(),300);
  }
  function add(asset:string){
    if(busy||dirty)return;
    if(nodes.length>=100){note('HUD tối đa 100 thành phần.',true);return;}
    const a=byId(asset);if(!a)return;
    checkpoint();
    const n:Element={id:crypto.randomUUID(),asset,x:Math.floor((screen[0]-a.width)/2),y:Math.floor((screen[1]-a.height)/2),width:a.width,height:a.height};
    if(a.kind==='background'){n.width=224;n.height=176;n.x=208;n.y=92;}
    if(a.kind==='button')n.label='Nút mới';if(a.kind==='inventory')n.label='Túi đồ';
    if(asset==='bar-track'){n.fill='bar-health-fill';n.value=75;}
    nodes.push(n);active=n.id;selected=asset;setView('hud');inspector();persist();render();
  }
  function library(){
    const category=el<HTMLSelectElement>('ufFilter').value;
    const query=input('ufSearch').value.toLocaleLowerCase('vi');
    const visible=assets.filter(a=>(input('ufSecondary').checked||a.primary||category==='piece'||category==='ornament'||category==='fill')&&(category==='all'||a.kind===category)&&`${a.name} ${a.id}`.toLocaleLowerCase('vi').includes(query));
    el('ufCount').textContent=String(visible.length);
    const list=el('ufList');list.replaceChildren();const gallery=el('ufGallery');gallery.replaceChildren();
    for(const a of visible){
      const row=document.createElement('div');row.className='uf-asset-row';row.classList.toggle('selected',a.id===selected);
      const choose=document.createElement('button');choose.className='uf-asset-select';choose.title=`Vẽ ${a.name}`;
      const img=document.createElement('img');img.src=a.url;img.alt='';
      const label=document.createElement('span');const title=document.createElement('strong');title.textContent=a.name;
      const dims=document.createElement('small');dims.textContent=`${a.width} × ${a.height}`;label.append(title,dims);choose.append(img,label);
      choose.onclick=()=>{selected=a.id;active=null;setView(a.recipe?'assembly':'asset');library();inspector();render();};
      const plus=document.createElement('button');plus.textContent='＋';plus.title=`Thêm ${a.id} lên HUD`;plus.onclick=()=>add(a.id);row.append(choose,plus);list.append(row);
      const tile=document.createElement('button');tile.className='uf-tile';tile.title=`Xem ${a.id}`;
      const preview=document.createElement('div');preview.className='uf-tile-preview';const image=img.cloneNode() as HTMLImageElement;preview.append(image);
      const caption=document.createElement('span');caption.textContent=a.name;tile.append(preview,caption);tile.onclick=choose.onclick;gallery.append(tile);
    }
  }
  function inspector(){
    layers();
    const n=current();el('ufNodeFields').hidden=!n;input('ufLabel').closest('label')!.hidden=n?.asset==='frame-skill';
    el('ufNodeFields').querySelectorAll<HTMLInputElement|HTMLButtonElement>('input,button').forEach(control=>control.disabled=!!n?.locked);
    assemblyInspector();el('ufSelectionTitle').textContent=byId(n?.asset??selected)?.name??'Chọn một thành phần';
    if(!n)return;
    const a=byId(n.asset)!;const resizable=!!a.recipe||n.asset==='joystick-base';el('ufNodeSize').hidden=!resizable;el('ufSizeHint').hidden=!resizable;input('ufNodeW').value=String(n.width??a.width);input('ufNodeH').value=String(n.height??a.height);input('ufNodeW').min=n.asset==='inventory-board'?'184':'32';input('ufNodeH').min=n.asset==='inventory-board'?'156':'32';input('ufNodeW').max=String(screen[0]);input('ufNodeH').max=String(screen[1]);
    input('ufLabel').value=n.label??'';input('ufX').value=String(n.x);input('ufY').value=String(n.y);
    el('ufValueField').hidden=!n.fill;input('ufValue').value=String(n.value??75);el('ufValueText').textContent=String(n.value??75);
  }
  function layers(){
    el('ufLayerCount').textContent=String(nodes.length);el('ufLayers').replaceChildren();
    for(const n of [...nodes].reverse()){
      const row=document.createElement('div');row.className='uf-layer';row.classList.toggle('selected',n.id===active);
      const choose=document.createElement('button');choose.textContent=byId(n.asset)?.name??n.asset;choose.title=choose.textContent;
      choose.onclick=()=>{active=n.id;selected=n.asset;setView('hud');inspector();render();};
      const visible=document.createElement('button');visible.textContent=n.visible===false?'○':'●';visible.title=n.visible===false?'Hiện lớp':'Ẩn lớp';visible.onclick=()=>{checkpoint();n.visible=n.visible===false;persist();inspector();render();};
      const locked=document.createElement('button');locked.textContent=n.locked?'◆':'◇';locked.title=n.locked?'Mở khóa lớp':'Khóa lớp';locked.onclick=()=>{checkpoint();n.locked=!n.locked;persist();inspector();};row.append(choose,visible,locked);el('ufLayers').append(row);
    }
    (el('ufLayoutUndo') as HTMLButtonElement).disabled=!layoutUndo.length;(el('ufLayoutRedo') as HTMLButtonElement).disabled=!layoutRedo.length;
  }
  function fit(){
    if(view==='kit')return;
    const stage=el('ufStage'),zoom=el<HTMLSelectElement>('ufZoom').value;
    const available=Math.min((stage.clientWidth-48)/canvas.width,(stage.clientHeight-48)/canvas.height);
    const z=zoom==='fit'?Math.max(.25,available>=1?Math.floor(available):available):Number(zoom);
    canvas.style.width=`${canvas.width*z}px`;canvas.style.height=`${canvas.height*z}px`;
    // A reduced preview needs filtering or individual 1px rails disappear.
    // Native artwork and PNG/Godot exports always retain hard integer pixels.
    canvas.style.imageRendering=z<1?'auto':'pixelated';
    canvas.title=z<1?'Bản xem thu nhỏ. Chọn 1× để xem chính xác nét 1 pixel.':'Pixel gốc, thu phóng theo số nguyên.';
  }
  function render(){
    if(view==='kit')return;
    const a=byId(selected);
    const sz=displaySize(a);const exploded=view==='assembly'&&input('ufExplode').checked;const splitParts=a?.recipe?Object.values(a.recipe.pieces).map(byId).filter((p):p is Asset=>!!p):[];const splitCols=Math.min(3,splitParts.length);const splitW=40+Math.max(0,splitCols-1)*48+Math.max(16,...splitParts.map(p=>p.width));const splitH=40+Math.max(0,Math.ceil(splitParts.length/3)-1)*48+Math.max(16,...splitParts.map(p=>p.height));
    canvas.width=view==='hud'?screen[0]:exploded?splitW:sz.w+40;canvas.height=view==='hud'?screen[1]:exploded?splitH:sz.h+40;
    ctx.imageSmoothingEnabled=false;
    if(view==='hud'){
      ctx.fillStyle='#111b22';ctx.fillRect(0,0,screen[0],screen[1]);ctx.save();ctx.scale(screen[0]/640,screen[1]/360);
      for(const [points,color] of [[[[0,195],[76,118],[142,184],[255,67],[345,187],[441,122],[553,197],[640,134],[640,360],[0,360]],'#192a32'],[[[0,268],[110,195],[204,248],[326,169],[468,258],[578,200],[640,244],[640,360],[0,360]],'#1b3138']] as [number[][],string][]){ctx.fillStyle=color;ctx.beginPath();points.forEach(([x,y],i)=>i?ctx.lineTo(x!,y!):ctx.moveTo(x!,y!));ctx.closePath();ctx.fill();}
      ctx.restore();
      if(input('ufSafe').checked){ctx.strokeStyle='#92b79c55';ctx.setLineDash([4,4]);ctx.strokeRect(16.5,16.5,screen[0]-33,screen[1]-33);ctx.setLineDash([]);}
      ctx.fillStyle='#476065';ctx.font='10px "Segoe UI"';ctx.fillText('HUYẾT KIẾM TÔNG  /  HUD',22,108);
      for(const n of nodes){const asset=byId(n.asset);if(!asset||n.visible===false)continue;const w=n.width??asset.width,h=n.height??asset.height;ctx.save();ctx.translate(n.x,n.y);if(asset.recipe)drawAssembly(ctx,asset.recipe,w,h,byId);else ctx.drawImage(asset.image,0,0,w,h);ctx.restore();
        if(n.asset==='joystick-base'){const thumb=byId('joystick-thumb');if(thumb){const z=w/116;ctx.drawImage(thumb.image,n.x+(35+(stick?.id===n.id?stick.x:0))*z,n.y+(35+(stick?.id===n.id?stick.y:0))*z,thumb.width*z,thumb.height*z);}}
        if(n.fill){const fill=byId(n.fill);if(fill){const width=Math.round(fill.width*(n.value??75)/100);if(width>0)ctx.drawImage(fill.image,0,0,width,fill.height,n.x,n.y,width,fill.height);}}
        if(n.label&&n.asset!=='frame-skill'){ctx.save();ctx.beginPath();ctx.rect(n.x+6,n.y+4,w-12,h-8);ctx.clip();ctx.fillStyle='#dbe6c9';ctx.font='10px "Segoe UI"';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(n.label,n.x+w/2,n.y+(asset.recipe?.inventory?19:h/2));ctx.restore();}
        if(n.id===active){ctx.strokeStyle='#c6b9fa';ctx.lineWidth=1;ctx.setLineDash([3,2]);ctx.strokeRect(n.x+.5,n.y+.5,w-1,h-1);ctx.setLineDash([]);}
      }
    }else{
      for(let y=0;y<canvas.height;y+=8)for(let x=0;x<canvas.width;x+=8){ctx.fillStyle=(x/8+y/8)%2?'#252932':'#20232b';ctx.fillRect(x,y,8,8);}
      if(a){ctx.save();ctx.translate(20,20);if(exploded&&a.recipe){Object.values(a.recipe.pieces).forEach((id,i)=>{const part=byId(id);if(part)ctx.drawImage(part.image,(i%3)*48,Math.floor(i/3)*48);});}else if(a.recipe)drawAssembly(ctx,a.recipe,sz.w,sz.h,byId);else ctx.drawImage(a.image,0,0);ctx.restore();}
      if(view==='asset'&&a&&input('ufGrid').checked){ctx.strokeStyle='#b8cfca38';ctx.lineWidth=.15;ctx.beginPath();for(let x=0;x<=a.width;x++){ctx.moveTo(x+20,20);ctx.lineTo(x+20,a.height+20);}for(let y=0;y<=a.height;y++){ctx.moveTo(20,y+20);ctx.lineTo(a.width+20,y+20);}ctx.stroke();}
    }
    el('ufDimensions').textContent=`${canvas.width} × ${canvas.height}`;
    el('ufCanvasTitle').textContent=view==='hud'?'HUYẾT KIẾM TÔNG / GIAO DIỆN':`${a?.name??selected} / ${view==='assembly'?'GHÉP TỪ MẢNH RỜI':'VẼ PIXEL'}`;
    fit();
  }
  function setView(value:string){endDrag();if(value==='asset'&&byId(selected)?.recipe)value='assembly';if(value==='assembly'&&!byId(selected)?.recipe){selected=assets.find(a=>a.recipe?.family===(byId(selected)?.family??assemblyFamily))?.id??'frame-panel';}view=value;stick=null;el('ufGallery').hidden=view!=='kit';canvas.hidden=view==='kit';el('ufPaintTools').hidden=view!=='asset';el('ufTryStick').hidden=view!=='hud';
    el('ufLayers').closest<HTMLElement>('section')!.hidden=view!=='hud';
    dialog.querySelectorAll<HTMLElement>('[data-uf-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ufView===view)));
    el('ufHint').textContent=view==='hud'?(tryStick?'Kéo joystick để thử hướng di chuyển.':'Kéo để bố trí · Nhấp đúp để vẽ · Delete: xóa'):view==='kit'?'Chọn khung để xem cấu tạo; bấm ＋ để thêm lên HUD.':view==='assembly'?'Chọn một góc hoặc đốt bên phải để vẽ. Đổi kích thước sau khi đặt lên HUD.':'B: bút · E: tẩy · I: hút màu · G: đổ màu · Ctrl+Z: hoàn tác';
    if(view==='assembly'&&['circle','outline'].includes(byId(selected)?.recipe?.mode??''))el('ufHint').textContent='Nét 1 px được vẽ theo kích thước. Bấm ＋ để thêm vào HUD và đổi rộng/cao.';
    if(view==='kit'){el('ufCanvasTitle').textContent='TIÊN MÔN / BỘ THÀNH PHẦN';el('ufDimensions').textContent='KHUNG / NÚT / CHIÊU / ITEM';}assemblyInspector();paintControls();render();}
  function painter(){
    const a=byId(selected);if(!a||a.recipe)return;
    let p=painters.get(a.id);if(!p){p=new UIPaint(a.image,a.width,a.height);painters.set(a.id,p);}
    p.tool=paintTool;p.color=input('ufPaintColor').value;p.size=Number(el<HTMLSelectElement>('ufPaintSize').value);return p;
  }
  function paintControls(){
    const p=painters.get(selected);
    (el('ufUndo') as HTMLButtonElement).disabled=busy||dirty||!p?.undoStack.length;
    (el('ufRedo') as HTMLButtonElement).disabled=busy||dirty||!p?.redoStack.length;
    (el('ufRestorePixels') as HTMLButtonElement).disabled=busy||dirty||!edits[selected];
    el('ufPaintState').textContent=edits[selected]?'Đã vẽ tay · giữ màu riêng':'Mẫu sinh bằng Python';
    dialog.querySelectorAll<HTMLElement>('[data-uf-tool]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ufTool===paintTool)));
  }
  function commitPixels(id:string){
    const a=byId(id),p=painters.get(id);if(!a||!p)return;
    a.image=p.canvas;a.url=p.canvas.toDataURL('image/png');edits[id]=a.url;refreshAssemblies();persist();library();assemblyInspector();lock();render();
  }
  function history(redo=false){if(busy||dirty)return;const p=painter();if(p?.history(redo))commitPixels(selected);}
  function move(n:Element,x:number,y:number){const a=byId(n.asset);if(!a)return;n.x=Math.max(0,Math.min(screen[0]-(n.width??a.width),Math.round(x)));n.y=Math.max(0,Math.min(screen[1]-(n.height??a.height),Math.round(y)));}
  let drag:{id:string;dx:number;dy:number;pointer:number}|null=null;
  function point(e:PointerEvent){const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left-canvas.clientLeft)*canvas.width/canvas.clientWidth,y:(e.clientY-r.top-canvas.clientTop)*canvas.height/canvas.clientHeight};}
  canvas.onpointerdown=e=>{if(busy||dirty||e.button!==0)return;const p=point(e);
    if(view==='asset'){
      const pen=painter();if(!pen)return;
      if(pen.begin({x:Math.floor(p.x)-20,y:Math.floor(p.y)-20})){painting={id:selected,pointer:e.pointerId};byId(selected)!.image=pen.canvas;canvas.setPointerCapture(e.pointerId);}
      input('ufPaintColor').value=pen.color;canvas.focus();render();return;
    }
    if(view!=='hud')return;
    const n=[...nodes].reverse().find(n=>{const a=byId(n.asset);return a&&n.visible!==false&&!n.locked&&p.x>=n.x&&p.y>=n.y&&p.x<n.x+(n.width??a.width)&&p.y<n.y+(n.height??a.height);});
    if(tryStick){if(n?.asset==='joystick-base'){stick={id:n.id,pointer:e.pointerId,x:0,y:0};canvas.setPointerCapture(e.pointerId);updateStick(p);}return;}
    active=n?.id??null;if(n){checkpoint();selected=n.asset;drag={id:n.id,dx:p.x-n.x,dy:p.y-n.y,pointer:e.pointerId};canvas.setPointerCapture(e.pointerId);}canvas.focus();inspector();render();};
  function updateStick(p:{x:number;y:number}){if(!stick)return;const n=nodes.find(n=>n.id===stick!.id);if(!n)return;const z=(n.width??116)/116;let x=(p.x-n.x)/z-54,y=(p.y-n.y)/z-54;const length=Math.hypot(x,y);if(length>30){x*=30/length;y*=30/length;}stick.x=Math.round(x);stick.y=Math.round(y);el('ufHint').textContent=`Hướng: (${(x/30).toFixed(2)}, ${(y/30).toFixed(2)}) · Thả để về tâm`;render();}
  canvas.onpointermove=e=>{const p=point(e);
    if(painting?.pointer===e.pointerId){painters.get(painting.id)?.move({x:Math.floor(p.x)-20,y:Math.floor(p.y)-20});render();return;}
    if(stick?.pointer===e.pointerId){updateStick(p);return;}
    if(!drag||drag.pointer!==e.pointerId)return;const n=nodes.find(n=>n.id===drag!.id);if(!n)return;move(n,p.x-drag.dx,p.y-drag.dy);input('ufX').value=String(n.x);input('ufY').value=String(n.y);render();};
  function endDrag(){if(painting){const id=painting.id;painting=null;if(painters.get(id)?.end())commitPixels(id);}if(drag)persist();drag=null;if(stick){stick=null;el('ufHint').textContent='Hướng: (0.00, 0.00) · Kéo joystick để thử';render();}}
  canvas.onpointerup=endDrag;canvas.onpointercancel=endDrag;canvas.onlostpointercapture=endDrag;
  canvas.ondblclick=()=>{if(view==='hud'&&current()&&!tryStick)setView('asset');};
  const click=(id:string,fn:()=>void)=>el(id).addEventListener('click',fn);
  dialog.querySelectorAll<HTMLButtonElement>('[data-uf-view]').forEach(b=>b.onclick=()=>setView(b.dataset.ufView!));
  dialog.querySelectorAll<HTMLButtonElement>('[data-uf-tool]').forEach(b=>b.onclick=()=>{endDrag();paintTool=b.dataset.ufTool as PaintTool;paintControls();});
  dialog.querySelectorAll<HTMLButtonElement>('[data-uf-theme]').forEach(b=>b.onclick=()=>{const t=THEMES[Number(b.dataset.ufTheme)]!;s={...s,surface:t.surface,metal:t.metal,gem:t.gem};schedule();});
  dialog.querySelectorAll<HTMLInputElement|HTMLSelectElement>('[data-setting]').forEach(control=>control.addEventListener('input',()=>{
    const key=control.dataset.setting as keyof Settings;let value:unknown=control.value;
    if(typeof DEFAULT[key]==='boolean')value=(control as HTMLInputElement).checked;
    else if(typeof DEFAULT[key]==='number'){if(!control.value||!(control as HTMLInputElement).checkValidity())return;value=Number(control.value);}
    s={...s,[key]:value};schedule();
  }));
  el('ufZoom').onchange=fit;el('ufFilter').onchange=library;el('ufSearch').oninput=library;el('ufSecondary').onchange=library;el('ufGrid').onchange=render;el('ufSafe').onchange=render;el('ufExplode').onchange=()=>setView('assembly');
  el('ufDevice').onchange=()=>{const previous=screen[0];screen=[Number(el<HTMLSelectElement>('ufDevice').value),360];for(const n of nodes){const a=byId(n.asset);if(!a)continue;if(n.width&&n.width>screen[0])n.width=screen[0];const center=n.x+(n.width??a.width)/2;if(Math.abs(center-previous/2)<16)n.x+=(screen[0]-previous)/2;else if(center>previous*.65)n.x+=screen[0]-previous;move(n,n.x,n.y);}persist();render();};
  click('ufSplit',()=>{input('ufExplode').checked=true;setView('assembly');note('Chọn một mảnh bên phải để vẽ hoặc tải PNG riêng.');});
  click('ufAssemblyBack',()=>{input('ufExplode').checked=false;setView('assembly');});
  click('ufUndo',()=>history());click('ufRedo',()=>history(true));
  click('ufRestorePixels',()=>{if(busy||dirty)return;delete edits[selected];painters.delete(selected);void generate();});
  click('ufTryStick',()=>{tryStick=!tryStick;el('ufTryStick').setAttribute('aria-pressed',String(tryStick));setView('hud');});
  click('ufGenerate',()=>void generate());click('ufClose',()=>dialog.close());
  click('ufReset',()=>{s={...DEFAULT,width:s.width,height:s.height};schedule();});
  click('ufLayoutUndo',()=>undoLayout());click('ufLayoutRedo',()=>undoLayout(true));
  click('ufTemplate',()=>{
    if(busy||dirty)return;checkpoint();const preset=el<HTMLSelectElement>('ufPreset').value;
    const make=(asset:string,x:number,y:number,width?:number,height?:number,label?:string):Element=>({id:crypto.randomUUID(),asset,x,y,width:width??byId(asset)!.width,height:height??byId(asset)!.height,...(label?{label}:{})});
    if(preset==='inventory')nodes=[make('background-jade',26,24,588,308),make('inventory-board',28,26,284,288,'Túi đồ'),make('equipment-preview',328,26,144,240),make('equipment-details',486,26,128,240),make('scroll-track-v',286,70,32,188),make('scroll-grabber-v',286,86,32,40),make('frame-button',332,278,136,40,'Trang bị'),make('frame-button',480,278,130,40,'Tháo đồ')];
    else if(preset==='chat')nodes=[make('background-jade',24,24,360,204),make('chat-frame',24,24,360,164),make('chat-input',24,194,284,36),make('frame-button',312,194,72,36,'Gửi'),make('scroll-track-v',356,34,32,144),make('scroll-grabber-v',356,42,32,40),make('background-paper',28,248,584,84),make('dialog-frame',24,244,592,92)];
    else nodes=[make('joystick-base',24,248,88,88),make('bar-track',24,20),make('bar-track',24,44),make('frame-skill',552,272,64,64),make('frame-skill',490,286,48,48),make('frame-skill',514,222,48,48),make('frame-skill',572,206,44,44),make('frame-item',150,296,40,40),make('frame-item',194,296,40,40),make('frame-button',504,20,112,40,'Túi đồ')];
    active=null;selected='frame-skill';setView('hud');persist();inspector();render();note('Đã áp dụng bố cục mẫu. Bấm ↶ để trở lại bố cục trước.');
  });
  function editNode(event?:Event){const n=current();if(!n||n.locked||busy||dirty)return;checkpoint();move(n,Number(input('ufX').value)||0,Number(input('ufY').value)||0);n.label=input('ufLabel').value;
    const a=byId(n.asset)!;if(a.recipe||n.asset==='joystick-base'){n.width=Math.max(n.asset==='inventory-board'?184:32,Math.min(screen[0],Math.round(Number(input('ufNodeW').value))||a.width));n.height=Math.max(n.asset==='inventory-board'?156:32,Math.min(screen[1],Math.round(Number(input('ufNodeH').value))||a.height));if(n.asset==='frame-skill'){const diameter=(event?.target as HTMLElement)?.id==='ufNodeH'?n.height:n.width;n.width=Math.min(screen[1],diameter);n.height=n.width;delete n.label;}if(n.asset==='joystick-base'){n.width=Math.max(64,Math.min(116,n.width));n.height=n.width;}move(n,n.x,n.y);}
    if(n.fill)n.value=Number(input('ufValue').value);inspector();persist();render();}
  for(const id of ['ufLabel','ufValue'])el(id).addEventListener('input',editNode);
  for(const id of ['ufX','ufY','ufNodeW','ufNodeH'])el(id).addEventListener('change',editNode);
  click('ufFront',()=>{const n=current();if(!n||n.locked||busy||dirty)return;checkpoint();nodes=nodes.filter(item=>item!==n);nodes.push(n);persist();inspector();render();});
  click('ufBack',()=>{const n=current();if(!n||n.locked||busy||dirty)return;checkpoint();nodes=nodes.filter(item=>item!==n);nodes.unshift(n);persist();inspector();render();});
  function remove(){if(!active||current()?.locked||busy||dirty)return;checkpoint();nodes=nodes.filter(n=>n.id!==active);active=null;inspector();persist();render();}
  click('ufDelete',remove);click('ufDuplicate',()=>{const n=current();if(!n||busy||dirty||nodes.length>=100)return;checkpoint();const copy={...n,id:crypto.randomUUID(),locked:false};move(copy,n.x+8,n.y+8);nodes.push(copy);active=copy.id;inspector();persist();render();});
  click('ufSave',()=>saveBlob(new Blob([JSON.stringify(design(),null,2)],{type:'application/json'}),'hkt-ui-design.json'));
  click('ufPNG',()=>{const a=byId(selected);if(!a)return;if(a.recipe){const sz=displaySize(a),out=document.createElement('canvas');out.width=sz.w;out.height=sz.h;drawAssembly(out.getContext('2d')!,a.recipe,sz.w,sz.h,byId);download(out.toDataURL(),`${a.id}-${sz.w}x${sz.h}.png`);}else download(a.url,`${a.id}.png`);});
  click('ufImport',()=>input('ufFile').click());
  input('ufFile').onchange=async()=>{const f=input('ufFile').files?.[0];if(!f)return;
    try{if(f.size>8_000_000)throw new Error('File thiết kế tối đa 8 MB.');const data=JSON.parse(await f.text());if(![1,2,3].includes(data.version)||!data.settings||!Array.isArray(data.layout))throw new Error('Định dạng thiết kế không hợp lệ.');
      const previous={s,edits,pendingLayout,dirty,screen};screen=data.canvas??[640,360];s=data.settings;pendingLayout=data.layout;edits=data.edits??{};
      if(await generate()){painters.clear();paintControls();}else{s=previous.s;screen=previous.screen;edits=previous.edits;pendingLayout=previous.pendingLayout;dirty=previous.dirty;syncSettings();lock();}
    }
    catch(e){note((e as Error).message,true);}finally{input('ufFile').value='';}};
  click('ufExport',()=>{void(async()=>{if(busy||dirty)return;const exported=structuredClone(design());note('Đang đóng gói PNG, Theme, joystick và scene Godot…');
    (el('ufExport') as HTMLButtonElement).disabled=true;
    try{const response=await fetch('/api/ui-forge/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(exported)});
      if(!response.ok)throw new Error((await response.json()).error);saveBlob(await response.blob(),'hkt-ui-godot.zip');note('Đã tải gói Godot. Chép thư mục ui_forge vào project, mở HUD.tscn.');}
    catch(e){note(`Xuất thất bại: ${(e as Error).message}`,true);}finally{lock();}})();});
  let opened=false;
  launch.onclick=()=>{resumed=isPlaying;if(resumed)togglePlayPause();dialog.showModal();
    if(!opened){opened=true;try{const saved=JSON.parse(localStorage.getItem(KEY)||'null');if(saved?.version===3){s=saved.settings;screen=saved.canvas??[640,360];pendingLayout=saved.layout;edits=saved.edits??{};}}catch{note('Bản nháp cũ không đọc được.',true);}void generate();}else{render();fit();}
  };
  dialog.addEventListener('close',()=>{endDrag();if(!dirty)persist();if(resumed&&!isPlaying)togglePlayPause();resumed=false;});
  window.addEventListener('keydown',e=>{
    if(!dialog.open){if(e.altKey&&e.key.toLowerCase()==='u'&&!document.querySelector('dialog[open]')){e.preventDefault();launch.click();}return;}
    e.stopImmediatePropagation();if(e.key==='Escape')return;if((e.target as HTMLElement).matches('input,select,textarea'))return;
    if(busy||dirty)return;
    if(view==='hud'&&(e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();endDrag();undoLayout(e.shiftKey);return;}
    if(view==='asset'){
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();endDrag();history(e.shiftKey);return;}
      const shortcuts:Record<string,PaintTool>={b:'brush',e:'eraser',i:'picker',g:'fill'};
      if(shortcuts[e.key.toLowerCase()]){e.preventDefault();paintTool=shortcuts[e.key.toLowerCase()]!;paintControls();}
    }
    if(e.key==='Delete'&&view==='hud'){e.preventDefault();remove();}
    const steps:Record<string,[number,number]>={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
    const n=current();if(n&&!n.locked&&steps[e.key]&&view==='hud'){e.preventDefault();checkpoint();const [x,y]=steps[e.key]!;move(n,n.x+x*(e.shiftKey?8:1),n.y+y*(e.shiftKey?8:1));inspector();persist();render();}
  },true);
  window.addEventListener('keyup',e=>{if(dialog.open)e.stopImmediatePropagation();},true);
  new ResizeObserver(fit).observe(el('ufStage'));syncSettings();lock();
}
