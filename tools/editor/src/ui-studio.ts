import './ui-studio.css';
import { download, loadImage } from './utils';
import { isPlaying, togglePlayPause } from './timeline';
import { UIPaint, type PaintTool } from './ui-paint';
import { drawAssembly, partNames, type Recipe } from './ui-assembly';

type Settings={surface:string;rail:string;metal:string;outline:string;gem:string;width:number;height:number;border:number;detail:number;shadow:number;corner:string;crest:boolean;texture:boolean;showBg:boolean;enableShadow:boolean;frameStyle:string};
type Asset={id:string;name:string;primary:boolean;recipe?:Recipe|null;family?:string;part?:string;width:number;height:number;kind:string;margins:number[]|null;url:string;image:HTMLImageElement|HTMLCanvasElement};
type Element={id:string;asset:string;x:number;y:number;width?:number;height?:number;label?:string;fill?:string;value?:number;locked?:boolean;visible?:boolean};
const STYLE_PALETTES:Record<string,{rail:string;metal:string;outline:string;gem:string;surface:string}>={
  bamboo:{rail:'#4c6f30',metal:'#d7b96e',outline:'#0a100e',gem:'#46a082',surface:'#14221a'},
  wood:{rail:'#6e4027',metal:'#e6b969',outline:'#140c09',gem:'#d74628',surface:'#1a1310'},
  jade:{rail:'#2e7270',metal:'#dae8ee',outline:'#0a1414',gem:'#50dcd2',surface:'#0f1a1a'}
};
const DEFAULT:Settings={surface:'#14221a',rail:'#4c6f30',metal:'#d7b96e',outline:'#0a100e',gem:'#46a082',width:216,height:156,border:5,detail:2,shadow:3,corner:'leaves',crest:true,texture:true,showBg:true,enableShadow:true,frameStyle:'bamboo'};
const MATERIALS=[{id:'bamboo',name:'Trúc'},{id:'wood',name:'Gỗ chạm mây'},{id:'jade',name:'Ngọc khảm'}];
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
    <aside class="uf-library"><div class="uf-section"><small>01 / CHẤT LIỆU</small><h3>Kiểu khung</h3></div>
      <div class="uf-materials" role="group" aria-label="Kiểu khung">${MATERIALS.map(t=>`<button data-uf-style="${t.id}" aria-pressed="${t.id==='bamboo'}"><img alt="" hidden><span>${t.name}</span></button>`).join('')}</div>
      <button id="ufGenerate" class="uf-primary">✦ Tạo bộ UI / HUD</button>
      <div class="uf-section uf-component-heading"><small>02 / THÀNH PHẦN</small><h3>Thư viện <span id="ufCount">—</span></h3></div>
      <select id="ufFilter" aria-label="Lọc thành phần"><option value="all">Tất cả thành phần</option>${Object.entries(names).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select>
      <input id="ufSearch" type="search" placeholder="Tìm khung, nền, thanh cuộn…" aria-label="Tìm thành phần">
      <label class="uf-check"><input id="ufSecondary" type="checkbox">Hiện thêm mẫu cũ</label>
      <div id="ufList" class="uf-list"></div>
      <p class="uf-tip">Chọn thành phần để xem. Bấm ＋ để đặt lên HUD.</p>
    </aside>
    <section class="uf-workspace"><div class="uf-toolbar"><div class="uf-tabs"><button data-uf-view="hud" aria-pressed="false">HUD mẫu</button><button data-uf-view="kit" aria-pressed="true">Bộ thành phần</button><button data-uf-view="assembly" aria-pressed="false">Ghép khung</button><button data-uf-view="asset" aria-pressed="false">Vẽ pixel</button></div>
      <div style="display:flex;gap:12px;align-items:center"><label id="ufPaddingLabel" title="Khoảng đệm trống xung quanh canvas">Lề canvas <select id="ufPadding"><option value="0" selected>0 px (Khít)</option><option value="8">8 px</option><option value="16">16 px</option><option value="20">20 px</option></select></label><label>Thu phóng <select id="ufZoom"><option value="fit">Vừa khung</option><option value="1">1×</option><option value="2">2×</option><option value="3">3×</option><option value="4">4×</option><option value="8">8×</option></select></label></div></div>
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
    <aside class="uf-inspector"><section id="ufAssembly" hidden><div class="uf-section"><small>LẮP GHÉP / MẢNH RỜI</small><h3 id="ufAssemblyTitle">Cấu tạo khung</h3></div>
      <div class="uf-assembly-mode-bar">
        <button id="ufModeAssembled" type="button" class="uf-mode-btn active" title="Xem khung ghép hoàn chỉnh">Khung hoàn chỉnh</button>
        <button id="ufModeExploded" type="button" class="uf-mode-btn" title="Xem dải mảnh nằm sát ngang nhau cho Godot">Dải mảnh (Godot)</button>
      </div>
      <input id="ufExplode" type="checkbox" hidden>
      <div id="ufPreviewSize" class="uf-fields"><label>Rộng mẫu<input id="ufPreviewW" type="number" min="32" max="800"></label><label>Cao mẫu<input id="ufPreviewH" type="number" min="32" max="360"></label></div>
      <p id="ufRecipeHint" class="uf-tip"></p>
      <div id="ufPieces" class="uf-pieces"></div>
      <div id="ufGodotSlices" class="uf-godot-slices" hidden>
        <div class="uf-slice-heading"><span>DẢI SPRITE GODOT</span><strong id="ufStripDims">0 × 0</strong></div>
        <div id="ufSliceList" class="uf-slice-list"></div>
        <button id="ufDownloadStrip" type="button" class="uf-primary" style="width:100%;margin-top:6px">⤓ Tải dải Sprite (Godot)</button>
      </div>
      <label id="ufAssemblyShowBgLabel" class="uf-check" hidden><input id="ufAssemblyShowBg" type="checkbox" checked>Hiện nền ô (lòng khung)</label>
      <button id="ufSplit" hidden></button><button id="ufAssemblyBack" hidden></button>
      <p class="uf-tip">Bấm vào mảnh để chuyển sang chế độ vẽ tay từng pixel.</p></section><div class="uf-section"><small>03 / TÙY CHỈNH</small><h3>Thanh & góc khung</h3></div>
      <div class="uf-colors">${[['rail','Thân & Ô item'],['metal','Kim loại / Nẹp'],['outline','Viền nét (Outline)'],['gem','Bảo ngọc'],['surface','Nền lòng / Cavity']].map(([k,label])=>`<label>${label}<input type="color" id="uf-${k}" data-setting="${k}" value="${DEFAULT[k as keyof Settings]}"></label>`).join('')}</div>
      <label class="uf-field">Kiểu góc<select id="uf-corner" data-setting="corner"><option value="cloud">Mây cuộn chạm nổi</option><option value="leaves">Cụm lá phủ góc</option><option value="fret">Hồi văn cổ</option><option value="cut">Vát góc tinh giản</option></select></label>
      ${[['border','Độ dày khung',3,8,5],['detail','Độ cầu kỳ',0,3,2],['shadow','Độ lệch bóng',0,5,3]].map(([k,label,min,max,v])=>`<label class="uf-range">${label}<output id="uf-${k}-value">${v}</output><input id="uf-${k}" data-setting="${k}" type="range" min="${min}" max="${max}" value="${v}"></label>`).join('')}
      <label class="uf-check"><input id="uf-crest" data-setting="crest" type="checkbox" checked><span id="ufCrestLabel">Chốt & hoa văn trang trí</span></label>
      <label class="uf-check"><input id="uf-texture" data-setting="texture" type="checkbox" checked>Vân chất liệu</label>
      <label class="uf-check"><input id="uf-showBg" data-setting="showBg" type="checkbox" checked><span id="ufBgLabel">Hiện nền lòng khung (Nền ô)</span></label>
      <label class="uf-check"><input id="uf-enableShadow" data-setting="enableShadow" type="checkbox" checked><span id="ufShadowLabel">Đổ bóng viền & chiều sâu</span></label>
      <div class="uf-selection"><div class="uf-section"><small>04 / BỐ CỤC HUD</small><h3 id="ufSelectionTitle">Chọn một thành phần</h3></div>
      <div id="ufNodeFields" hidden><label class="uf-field">Nhãn hiển thị / Nội dung<textarea id="ufLabel" rows="2" maxlength="512" placeholder="Không có nhãn" style="resize:vertical;"></textarea></label>
      <div class="uf-fields"><label>X<input id="ufX" type="number" min="0" max="639"></label><label>Y<input id="ufY" type="number" min="0" max="359"></label></div>
      <div id="ufNodeSize" class="uf-fields" hidden><label>Rộng khung<input id="ufNodeW" type="number" min="32" max="800"></label><label>Cao khung<input id="ufNodeH" type="number" min="32" max="360"></label></div><p id="ufSizeHint" class="uf-tip" hidden>Cạnh lặp theo đốt. Lá góc là lớp phủ riêng, lòng khung trong suốt.</p>
      <label id="ufValueField" class="uf-range" hidden>Giá trị thanh <output id="ufValueText">75</output><input id="ufValue" type="range" min="0" max="100"></label>
      <div class="uf-node-actions"><button id="ufFront">Lên trước</button><button id="ufBack">Ra sau</button><button id="ufDuplicate">Nhân đôi</button><button id="ufDelete">Xóa</button></div></div>
      <section class="uf-layer-section"><h3>Các lớp HUD <span id="ufLayerCount">0</span></h3><div id="ufLayers" class="uf-layers"></div></section>
      </div>
      <button id="ufReset" class="uf-quiet">Khôi phục phong cách gốc</button>
    </aside>
  </div><input id="ufFile" type="file" accept=".json,application/json" hidden>`;
  document.body.append(dialog);
  const el=<T extends HTMLElement>(id:string)=>dialog.querySelector<T>(`#${id}`)!;
  const input=(id:string)=>el<HTMLInputElement | HTMLTextAreaElement>(id) as HTMLInputElement;
  const canvas=el<HTMLCanvasElement>('ufCanvas'),ctx=canvas.getContext('2d')!;
  let s={...DEFAULT}, assets:Asset[]=[], nodes:Element[]=[], selected='inventory-board', active:string|null=null;
  let screen:[number,number]=[640,360],assemblyFamily='bamboo';
  let view='hud', busy=false, dirty=true, timer=0, serial=0, controller:AbortController|null=null, resumed=false;
  let edits:Record<string,string>={};const painters=new Map<string,UIPaint>();
  let painting:{id:string;pointer:number}|null=null,paintTool:PaintTool='brush';
  let tryStick=false,stick:{id:string;pointer:number;x:number;y:number}|null=null;
  let pendingLayout:Element[]|undefined;
  const assetMap=new Map<string,Asset>();
  const previewSizes=new Map<string,{w:number;h:number}>();
  const layoutUndo:Element[][]=[],layoutRedo:Element[][]=[];
  function checkpoint(){layoutUndo.push(structuredClone(nodes));if(layoutUndo.length>50)layoutUndo.shift();layoutRedo.length=0;}
  function undoLayout(redo=false){const source=redo?layoutRedo:layoutUndo,target=redo?layoutUndo:layoutRedo;const previous=source.pop();if(!previous)return;target.push(structuredClone(nodes));nodes=previous;active=null;inspector();persist();render();}
  function note(message:string,error=false){el('ufStatus').textContent=message;el('ufStatus').classList.toggle('error',error);}
  let restoredView:string|undefined,restoredSelected:string|undefined,restoredActive:string|null|undefined,restoredZoom:string|undefined,restoredExploded:boolean|undefined,restoredFilter:string|undefined,restoredSearch:string|undefined,restoredSecondary:boolean|undefined,restoredSafe:boolean|undefined,restoredGrid:boolean|undefined,restoredDevice:string|undefined,restoredPadding:number|undefined;
  function canvasPadding(){
    if(view==='hud'||(view==='assembly'&&input('ufExplode')?.checked))return 0;
    return Number(el<HTMLSelectElement>('ufPadding')?.value??0);
  }
  function uiState(){
    return {
      modalOpen:dialog.open,view,selected,active,
      zoom:el<HTMLSelectElement>('ufZoom')?.value??'fit',
      exploded:input('ufExplode')?.checked??false,
      padding:canvasPadding(),
      filter:el<HTMLSelectElement>('ufFilter')?.value??'all',
      search:input('ufSearch')?.value??'',
      secondary:input('ufSecondary')?.checked??false,
      safe:input('ufSafe')?.checked??true,
      grid:input('ufGrid')?.checked??false,
      device:el<HTMLSelectElement>('ufDevice')?.value??'640'
    };
  }
  function design(){return {version:3,styleRevision:1,settings:s,layout:nodes,edits,canvas:screen,uiState:uiState()};}
  function persist(){try{localStorage.setItem(KEY,JSON.stringify(design()));}catch{note('Không lưu được bản nháp. Dùng Lưu thiết kế để giữ bản vẽ.',true);}}
  function saveBlob(blob:Blob,name:string){const url=URL.createObjectURL(blob);download(url,name);setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function byId(id:string){return assetMap.get(id);}
  function current(){return nodes.find(n=>n.id===active);}
  function displaySize(a:Asset|undefined){const n=current(),size=a?previewSizes.get(a.id):undefined;return {w:n?.asset===a?.id?n?.width??a?.width??224:size?.w??a?.width??224,h:n?.asset===a?.id?n?.height??a?.height??176:size?.h??a?.height??176};}
  function refreshAssemblies(){
    for(const a of assets){if(!a.recipe)continue;const image=document.createElement('canvas');image.width=a.width;image.height=a.height;drawAssembly(image.getContext('2d')!,a.recipe,a.width,a.height,byId);a.image=image;a.url=image.toDataURL('image/png');}
  }
  function updateGodotSlices(){
    const a=byId(selected),slicesBox=el('ufGodotSlices'),sliceList=el('ufSliceList');
    if(!slicesBox||!sliceList||!a?.recipe)return;
    const pieceEntries=Object.entries(a.recipe.pieces).filter(([_,id])=>!!byId(id));
    const stripW=pieceEntries.reduce((sum,[_,id])=>sum+(byId(id)?.width??0),0);
    const stripH=Math.max(16,...pieceEntries.map(([_,id])=>byId(id)?.height??0));
    el('ufStripDims').textContent=`${stripW} × ${stripH}`;
    sliceList.replaceChildren();
    let curX=0;
    for(const [partKey,id] of pieceEntries){
      const part=byId(id);if(!part)continue;
      const item=document.createElement('div');item.className='uf-slice-item';
      const nameSpan=document.createElement('span');nameSpan.className='uf-slice-name';nameSpan.textContent=partNames[partKey]??partKey;
      const code=document.createElement('code');code.textContent=`Rect2(${curX}, 0, ${part.width}, ${part.height})`;
      code.title=`Bấm để vẽ pixel mảnh này · Tọa độ Godot: Rect2(${curX}, 0, ${part.width}, ${part.height})`;
      item.append(nameSpan,code);
      item.onclick=()=>{endDrag();selected=id;setView('asset');inspector();library();};
      sliceList.append(item);
      curX+=part.width;
    }
  }
  function downloadSpriteStrip(){
    const a=byId(selected);if(!a?.recipe)return;
    const pieceEntries=Object.entries(a.recipe.pieces).filter(([_,id])=>!!byId(id));
    if(!pieceEntries.length)return;
    const stripW=pieceEntries.reduce((sum,[_,id])=>sum+(byId(id)?.width??0),0);
    const stripH=Math.max(16,...pieceEntries.map(([_,id])=>byId(id)?.height??0));
    const out=document.createElement('canvas');out.width=stripW;out.height=stripH;
    const outCtx=out.getContext('2d')!;
    let curX=0;
    for(const [_,id] of pieceEntries){
      const part=byId(id);if(!part)continue;
      outCtx.drawImage(part.image,curX,0);
      curX+=part.width;
    }
    download(out.toDataURL('image/png'),`${a.id}-strip-${stripW}x${stripH}.png`);
    note(`Đã tải dải sprite ${stripW}×${stripH} px (Godot Atlas).`);
  }
  function assemblyInspector(){
    const a=byId(selected),family=a?.recipe?.family??a?.family;
    el('ufAssembly').hidden=!family;if(!family)return;assemblyFamily=family;
    const recipe=a?.recipe??assets.find(v=>v.recipe?.family===family)?.recipe;if(!recipe)return;
    const canSplit=Object.keys(recipe.pieces).length>0;
    el('ufModeAssembled').hidden=!canSplit;el('ufModeExploded').hidden=!canSplit;
    if(!canSplit)input('ufExplode').checked=false;
    const exploded=canSplit&&input('ufExplode').checked;
    el('ufModeAssembled').classList.toggle('active',!exploded);
    el('ufModeExploded').classList.toggle('active',exploded);
    el('ufPreviewSize').hidden=!a?.recipe||exploded;
    const size=displaySize(a);
    input('ufPreviewW').value=String(size.w);input('ufPreviewH').value=String(size.h);
    input('ufPreviewW').min=selected==='inventory-board'?'184':'32';input('ufPreviewH').min=selected==='inventory-board'?'156':'32';
    const slicesBox=el('ufGodotSlices');
    if(slicesBox){
      slicesBox.hidden=!canSplit||!exploded;
      if(canSplit&&exploded)updateGodotSlices();
    }
    const hasBg = !!recipe.pieces.bg;
    const showBgLabel = el('ufAssemblyShowBgLabel');
    if (showBgLabel) {
      showBgLabel.hidden = !hasBg;
      input('ufAssemblyShowBg').checked = recipe.showBg ?? s.showBg ?? true;
    }
    el('ufRecipeHint').textContent='';
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
    const assemBg = input('ufAssemblyShowBg'); if (assemBg) assemBg.checked = s.showBg;
    for(const k of ['border','detail','shadow'] as const)el(`uf-${k}-value`).textContent=String(s[k]);
    el('ufCrestLabel').textContent = s.frameStyle === 'bamboo' ? 'Chốt & cụm lá góc' : s.frameStyle === 'wood' ? 'Chốt & hoa mây góc' : 'Chốt & ngọc khảm góc';
    dialog.querySelectorAll<HTMLElement>('[data-uf-style]').forEach(b=>{b.setAttribute('aria-pressed',String(b.dataset.ufStyle===s.frameStyle));const image=b.querySelector('img')!;const part=byId(b.dataset.ufStyle==='bamboo'?'piece-bamboo-leaves':`piece-${b.dataset.ufStyle}-corner`);if(part){image.src=part.url;image.hidden=false;}});
  }
  function lock(){
    for(const id of ['ufExport','ufPNG','ufSave'])(el(id) as HTMLButtonElement).disabled=busy||dirty||!assets.length;
    (el('ufGenerate') as HTMLButtonElement).disabled=busy;
    el('ufGenerate').textContent=busy?'Đang tạo bộ UI…':'✦ Tạo bộ UI / HUD';
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
      s=data.settings;screen=data.canvas??[640,360];el<HTMLSelectElement>('ufDevice').value=String(screen[0]);nodes=data.layout;assets=loaded;assetMap.clear();for(const a of assets)assetMap.set(a.id,a);
      if(restoredSelected&&assetMap.has(restoredSelected)){selected=restoredSelected;restoredSelected=undefined;}
      else if(!byId(selected))selected='frame-panel';
      if(restoredActive&&nodes.some(n=>n.id===restoredActive)){active=restoredActive;restoredActive=undefined;}
      if(restoredZoom){el<HTMLSelectElement>('ufZoom').value=restoredZoom;restoredZoom=undefined;}
      if(restoredExploded!==undefined){input('ufExplode').checked=!!restoredExploded;restoredExploded=undefined;}
      if(restoredFilter){el<HTMLSelectElement>('ufFilter').value=restoredFilter;restoredFilter=undefined;}
      if(restoredSearch!==undefined){input('ufSearch').value=restoredSearch;restoredSearch=undefined;}
      if(restoredSecondary!==undefined){input('ufSecondary').checked=!!restoredSecondary;restoredSecondary=undefined;}
      if(restoredSafe!==undefined){input('ufSafe').checked=!!restoredSafe;restoredSafe=undefined;}
      if(restoredGrid!==undefined){input('ufGrid').checked=!!restoredGrid;restoredGrid=undefined;}
      if(restoredDevice){el<HTMLSelectElement>('ufDevice').value=restoredDevice;restoredDevice=undefined;}
      if(restoredPadding!==undefined){el<HTMLSelectElement>('ufPadding').value=String(restoredPadding);restoredPadding=undefined;}
      if(restoredView){view=restoredView;restoredView=undefined;}
      dirty=false;syncSettings();persist();library();inspector();setView(view);
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
    const size=displaySize(a);
    const n:Element={id:crypto.randomUUID(),asset,x:Math.floor((screen[0]-size.w)/2),y:Math.floor((screen[1]-size.h)/2),width:size.w,height:size.h};
    if(a.kind==='background'){n.width=224;n.height=176;n.x=208;n.y=92;}
    if(a.kind==='button')n.label='Nút mới';if(a.kind==='inventory')n.label='Túi đồ';
    if(asset==='text-panel')n.label='Tu tiên giả: Đạo tâm như thiết, vạn kiếp bất diệt.\nBấm vào đây để chỉnh sửa văn tự hội thoại...';
    if(asset==='bar-track'){n.label='Khí mạch';n.fill='bar-health-fill';n.value=75;}
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
    const a=byId(n.asset)!;const resizable=!!a.recipe||n.asset==='joystick-base';el('ufNodeSize').hidden=!resizable;el('ufSizeHint').hidden=!resizable;input('ufNodeW').value=String(n.width??a.width);input('ufNodeH').value=String(n.height??a.height);input('ufNodeW').min=n.asset==='inventory-board'?'184':'32';input('ufNodeH').min=n.asset==='inventory-board'?'156':(n.asset==='bar-track'?'16':'32');input('ufNodeW').max=String(screen[0]);input('ufNodeH').max=String(screen[1]);
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
    const z=zoom==='fit'?Math.max(1,available>=1?Math.floor(available):available):Number(zoom);
    canvas.style.width=`${canvas.width*z}px`;canvas.style.height=`${canvas.height*z}px`;
    canvas.style.imageRendering=z<1?'auto':'pixelated';
    canvas.title=z<1?'Bản xem thu nhỏ. Chọn 1× để xem chính xác nét 1 pixel.':'Pixel gốc, thu phóng theo số nguyên.';
  }
  function render(){
    if(view==='kit')return;
    const a=byId(selected);
    const sz=displaySize(a);const exploded=view==='assembly'&&input('ufExplode').checked;
    const pieceEntries=a?.recipe?Object.entries(a.recipe.pieces).filter(([_,id])=>!!byId(id)):[];
    const stripW=pieceEntries.reduce((sum,[_,id])=>sum+(byId(id)?.width??0),0);
    const stripH=Math.max(16,...pieceEntries.map(([_,id])=>byId(id)?.height??0));
    const pad=canvasPadding();
    canvas.width=view==='hud'?screen[0]:exploded?Math.max(32,stripW):sz.w+pad*2;
    canvas.height=view==='hud'?screen[1]:exploded?Math.max(16,stripH):sz.h+pad*2;
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
        if(n.label&&n.asset!=='frame-skill'){
          if(n.asset==='text-panel'){
            ctx.save();ctx.beginPath();ctx.rect(n.x+14,n.y+10,w-28,h-20);ctx.clip();
            ctx.fillStyle='#e8eed9';ctx.font='11px "Segoe UI", sans-serif';ctx.textAlign='left';ctx.textBaseline='top';
            const maxWidth=w-28,lineHeight=16;let curY=n.y+12;
            for(const para of n.label.split('\n')){
              const words=para.split(' ');let line='';
              for(let i=0;i<words.length;i++){
                const test=line?line+' '+words[i]:words[i];
                if(ctx.measureText(test).width>maxWidth&&line){ctx.fillText(line,n.x+14,curY);curY+=lineHeight;line=words[i];}
                else line=test;
              }
              if(line){ctx.fillText(line,n.x+14,curY);curY+=lineHeight;}
            }
            ctx.restore();
          }else{
            ctx.save();ctx.beginPath();ctx.rect(n.x+6,n.y+4,w-12,h-8);ctx.clip();ctx.fillStyle='#dbe6c9';ctx.font='10px "Segoe UI"';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(n.label,n.x+w/2,n.y+(asset.recipe?.inventory?19:h/2));ctx.restore();
          }
        }
        if(n.id===active){ctx.strokeStyle='#c6b9fa';ctx.lineWidth=1;ctx.setLineDash([3,2]);ctx.strokeRect(n.x+.5,n.y+.5,w-1,h-1);ctx.setLineDash([]);}
      }
    }else{
      ctx.clearRect(0,0,canvas.width,canvas.height);
      if(exploded&&a?.recipe){
        let curX=0;
        pieceEntries.forEach(([_,id])=>{
          const part=byId(id);if(!part)return;
          ctx.drawImage(part.image,curX,0);
          curX+=part.width;
        });
        if(input('ufGrid').checked){
          ctx.strokeStyle='#dfc18d88';ctx.lineWidth=1;ctx.setLineDash([2,2]);
          let gx=0;
          pieceEntries.forEach(([_,id])=>{
            const part=byId(id);if(!part)return;
            gx+=part.width;
            ctx.beginPath();ctx.moveTo(gx-.5,0);ctx.lineTo(gx-.5,canvas.height);ctx.stroke();
          });
          ctx.setLineDash([]);
        }
      }else if(a){
        ctx.save();ctx.translate(pad,pad);
        if(a.recipe)drawAssembly(ctx,a.recipe,sz.w,sz.h,byId);
        else ctx.drawImage(a.image,0,0);
        ctx.restore();
      }
      if(view==='asset'&&a&&input('ufGrid').checked){ctx.strokeStyle='#b8cfca38';ctx.lineWidth=.15;ctx.beginPath();for(let x=0;x<=a.width;x++){ctx.moveTo(x+pad,pad);ctx.lineTo(x+pad,a.height+pad);}for(let y=0;y<=a.height;y++){ctx.moveTo(pad,y+pad);ctx.lineTo(a.width+pad,y+pad);}ctx.stroke();}
    }
    el('ufDimensions').textContent=`${canvas.width} × ${canvas.height}`;
    el('ufCanvasTitle').textContent=view==='hud'?'HUYẾT KIẾM TÔNG / GIAO DIỆN':`${a?.name??selected} / ${view==='assembly'?(exploded?'DẢI SPRITE GHÉP (GODOT)':'GHÉP TỪ MẢNH RỜI'):'VẼ PIXEL'}`;
    fit();
  }
  function setView(value:string){endDrag();if(value==='asset'&&byId(selected)?.recipe)value='assembly';if(value==='assembly'&&!byId(selected)?.recipe){selected=assets.find(a=>a.recipe?.family===(byId(selected)?.family??assemblyFamily))?.id??'frame-panel';}view=value;stick=null;el('ufGallery').hidden=view!=='kit';canvas.hidden=view==='kit';el('ufPaintTools').hidden=view!=='asset';el('ufTryStick').hidden=view!=='hud';el('ufPaddingLabel').hidden=view==='hud'||view==='kit';
    el('ufLayers').closest<HTMLElement>('section')!.hidden=view!=='hud';
    dialog.querySelectorAll<HTMLElement>('[data-uf-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ufView===view)));
    el('ufHint').textContent=view==='hud'?(tryStick?'Kéo joystick để thử hướng di chuyển.':'Kéo để bố trí · Nhấp đúp để vẽ · Delete: xóa'):view==='kit'?'Chọn khung để xem cấu tạo; bấm ＋ để thêm lên HUD.':view==='assembly'?(input('ufExplode').checked?'Dải sprite xếp sát nhau cho Godot. Bấm mảnh để vẽ · Lưới: hiện vạch phân mảnh.':'Chọn một góc hoặc đốt bên phải để vẽ. Đổi kích thước sau khi đặt lên HUD.'):'B: bút · E: tẩy · I: hút màu · G: đổ màu · Ctrl+Z: hoàn tác';
    if(view==='assembly'&&['circle','outline'].includes(byId(selected)?.recipe?.mode??''))el('ufHint').textContent='Nét 1 px được vẽ theo kích thước. Bấm ＋ để thêm vào HUD và đổi rộng/cao.';
    if(view==='kit'){el('ufCanvasTitle').textContent='TIÊN MÔN / BỘ THÀNH PHẦN';el('ufDimensions').textContent='KHUNG / NÚT / CHIÊU / ITEM';}assemblyInspector();paintControls();render();persist();}
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
      const pad=canvasPadding();
      if(pen.begin({x:Math.floor(p.x)-pad,y:Math.floor(p.y)-pad})){painting={id:selected,pointer:e.pointerId};byId(selected)!.image=pen.canvas;canvas.setPointerCapture(e.pointerId);}
      input('ufPaintColor').value=pen.color;canvas.focus();render();return;
    }
    if(view==='assembly'&&input('ufExplode').checked){
      const a=byId(selected);
      const pieceEntries=a?.recipe?Object.entries(a.recipe.pieces).filter(([_,id])=>!!byId(id)):[];
      let curX=0;
      for(const [_,id] of pieceEntries){
        const part=byId(id);if(!part)continue;
        if(p.x>=curX&&p.x<curX+part.width&&p.y>=0&&p.y<part.height){
          endDrag();selected=id;setView('asset');inspector();library();return;
        }
        curX+=part.width;
      }
      return;
    }
    if(view!=='hud')return;
    const n=[...nodes].reverse().find(n=>{const a=byId(n.asset);return a&&n.visible!==false&&!n.locked&&p.x>=n.x&&p.y>=n.y&&p.x<n.x+(n.width??a.width)&&p.y<n.y+(n.height??a.height);});
    if(tryStick){if(n?.asset==='joystick-base'){stick={id:n.id,pointer:e.pointerId,x:0,y:0};canvas.setPointerCapture(e.pointerId);updateStick(p);}return;}
    active=n?.id??null;if(n){checkpoint();selected=n.asset;drag={id:n.id,dx:p.x-n.x,dy:p.y-n.y,pointer:e.pointerId};canvas.setPointerCapture(e.pointerId);}canvas.focus();inspector();render();};
  function updateStick(p:{x:number;y:number}){if(!stick)return;const n=nodes.find(n=>n.id===stick!.id);if(!n)return;const z=(n.width??116)/116;let x=(p.x-n.x)/z-54,y=(p.y-n.y)/z-54;const length=Math.hypot(x,y);if(length>30){x*=30/length;y*=30/length;}stick.x=Math.round(x);stick.y=Math.round(y);el('ufHint').textContent=`Hướng: (${(x/30).toFixed(2)}, ${(y/30).toFixed(2)}) · Thả để về tâm`;render();}
  canvas.onpointermove=e=>{const p=point(e);
    if(painting?.pointer===e.pointerId){const pad=canvasPadding();painters.get(painting.id)?.move({x:Math.floor(p.x)-pad,y:Math.floor(p.y)-pad});render();return;}
    if(stick?.pointer===e.pointerId){updateStick(p);return;}
    if(!drag||drag.pointer!==e.pointerId)return;const n=nodes.find(n=>n.id===drag!.id);if(!n)return;move(n,p.x-drag.dx,p.y-drag.dy);input('ufX').value=String(n.x);input('ufY').value=String(n.y);render();};
  function endDrag(){if(painting){const id=painting.id;painting=null;if(painters.get(id)?.end())commitPixels(id);}if(drag)persist();drag=null;if(stick){stick=null;el('ufHint').textContent='Hướng: (0.00, 0.00) · Kéo joystick để thử';render();}}
  canvas.onpointerup=endDrag;canvas.onpointercancel=endDrag;canvas.onlostpointercapture=endDrag;
  canvas.ondblclick=()=>{if(view==='hud'&&current()&&!tryStick)setView('asset');};
  const click=(id:string,fn:()=>void)=>el(id).addEventListener('click',fn);
  dialog.querySelectorAll<HTMLButtonElement>('[data-uf-view]').forEach(b=>b.onclick=()=>setView(b.dataset.ufView!));
  dialog.querySelectorAll<HTMLButtonElement>('[data-uf-tool]').forEach(b=>b.onclick=()=>{endDrag();paintTool=b.dataset.ufTool as PaintTool;paintControls();});
  dialog.querySelectorAll<HTMLButtonElement>('[data-uf-style]').forEach(b=>b.onclick=()=>{
    const style=b.dataset.ufStyle!;
    const palette=STYLE_PALETTES[style]??STYLE_PALETTES.bamboo;
    s={...s,...palette,frameStyle:style,corner:style==='bamboo'?'leaves':style==='wood'?'cloud':'fret'};
    if(edits[selected]){
      delete edits[selected];
      painters.delete(selected);
      paintControls();
    }
    syncSettings();
    schedule();
  });
  for(const id of ['ufPreviewW','ufPreviewH'])el(id).addEventListener('change',()=>{
    const a=byId(selected);if(!a?.recipe||!input(id).checkValidity())return;
    let w=Math.max(Number(input('ufPreviewW').min),Math.min(screen[0],Number(input('ufPreviewW').value))),h=Math.max(Number(input('ufPreviewH').min),Math.min(screen[1],Number(input('ufPreviewH').value)));
    if(a.id==='frame-skill'||a.id==='frame-item'){w=h=Math.min(screen[1],id==='ufPreviewH'?h:w);}
    const n=current();if(n?.asset===a.id){checkpoint();n.width=w;n.height=h;move(n,n.x,n.y);persist();}else previewSizes.set(a.id,{w,h});
    assemblyInspector();render();
  });
  dialog.querySelectorAll<HTMLInputElement|HTMLSelectElement>('[data-setting]').forEach(control=>control.addEventListener('input',()=>{
    const key=control.dataset.setting as keyof Settings;let value:unknown=control.value;
    if(typeof DEFAULT[key]==='boolean')value=(control as HTMLInputElement).checked;
    else if(typeof DEFAULT[key]==='number'){if(!control.value||!(control as HTMLInputElement).checkValidity())return;value=Number(control.value);}
    if(edits[selected]){
      delete edits[selected];
      painters.delete(selected);
      paintControls();
    }
    s={...s,[key]:value};schedule();
  }));
  el('ufZoom').onchange=()=>{fit();persist();};
  el('ufFilter').onchange=()=>{library();persist();};
  el('ufSearch').oninput=()=>{library();persist();};
  el('ufSecondary').onchange=()=>{library();persist();};
  el('ufGrid').onchange=()=>{render();persist();};
  el('ufSafe').onchange=()=>{render();persist();};
  el('ufPadding').onchange=()=>{render();fit();persist();};
  el('ufExplode').onchange=()=>{assemblyInspector();render();persist();};
  const setExplodeMode=(exploded:boolean)=>{
    input('ufExplode').checked=exploded;
    setView('assembly');
    assemblyInspector();
    render();
    persist();
  };
  el('ufModeAssembled')?.addEventListener('click',()=>setExplodeMode(false));
  el('ufModeExploded')?.addEventListener('click',()=>setExplodeMode(true));
  el('ufDownloadStrip')?.addEventListener('click',downloadSpriteStrip);
  el('ufAssemblyShowBg')?.addEventListener('change',()=>{
    if(edits[selected]){
      delete edits[selected];
      painters.delete(selected);
      paintControls();
    }
    s={...s,showBg:input('ufAssemblyShowBg').checked};schedule();
  });
  el('ufDevice').onchange=()=>{const previous=screen[0];screen=[Number(el<HTMLSelectElement>('ufDevice').value),360];for(const n of nodes){const a=byId(n.asset);if(!a)continue;if(n.width&&n.width>screen[0])n.width=screen[0];const center=n.x+(n.width??a.width)/2;if(Math.abs(center-previous/2)<16)n.x+=(screen[0]-previous)/2;else if(center>previous*.65)n.x+=screen[0]-previous;move(n,n.x,n.y);}persist();render();};
  click('ufSplit',()=>setExplodeMode(true));
  click('ufAssemblyBack',()=>setExplodeMode(false));
  click('ufUndo',()=>history());click('ufRedo',()=>history(true));
  click('ufRestorePixels',()=>{if(busy||dirty)return;delete edits[selected];painters.delete(selected);void generate();});
  click('ufTryStick',()=>{tryStick=!tryStick;el('ufTryStick').setAttribute('aria-pressed',String(tryStick));setView('hud');});
  click('ufGenerate',()=>void generate());click('ufClose',()=>dialog.close());
  click('ufReset',()=>{
    if(edits[selected]){
      delete edits[selected];
      painters.delete(selected);
      paintControls();
    }
    s={...DEFAULT,width:s.width,height:s.height};schedule();
  });
  click('ufLayoutUndo',()=>undoLayout());click('ufLayoutRedo',()=>undoLayout(true));
  click('ufTemplate',()=>{
    if(busy||dirty)return;checkpoint();const preset=el<HTMLSelectElement>('ufPreset').value;
    const make=(asset:string,x:number,y:number,width?:number,height?:number,label?:string):Element=>({id:crypto.randomUUID(),asset,x,y,width:width??byId(asset)!.width,height:height??byId(asset)!.height,...(label?{label}:{})});
    if(preset==='inventory')nodes=[make('background-jade',26,24,588,308),make('inventory-board',28,26,284,288,'Túi đồ'),make('equipment-preview',328,26,144,240),make('equipment-details',486,26,128,240),make('scroll-track-v',286,70,32,188),make('scroll-grabber-v',286,86,32,40),make('frame-button',332,278,136,40,'Trang bị'),make('frame-button',480,278,130,40,'Tháo đồ')];
    else if(preset==='chat')nodes=[make('background-jade',24,24,360,204),make('chat-frame',24,24,360,164),make('chat-input',24,194,284,36),make('frame-button',312,194,72,36,'Gửi'),make('scroll-track-v',356,34,32,144),make('scroll-grabber-v',356,42,32,40),make('text-panel',24,244,592,92,'Bạch Y Tiên Tử: Đạo hữu đã chuẩn bị xong đan dược chưa?\nPhía trước là đầm lầy Vạn Yêu, sương độc ngập trời, vô cùng hung hiểm!')];
    else nodes=[make('joystick-base',24,248,88,88),make('bar-track',24,20),make('bar-track',24,44),make('frame-skill',552,272,64,64),make('frame-skill',490,286,48,48),make('frame-skill',514,222,48,48),make('frame-skill',572,206,44,44),make('frame-item',150,296,40,40),make('frame-item',194,296,40,40),make('frame-button',504,20,112,40,'Túi đồ')];
    active=null;selected='frame-skill';setView('hud');persist();inspector();render();note('Đã áp dụng bố cục mẫu. Bấm ↶ để trở lại bố cục trước.');
  });
  function editNode(event?:Event){const n=current();if(!n||n.locked||busy||dirty)return;checkpoint();move(n,Number(input('ufX').value)||0,Number(input('ufY').value)||0);n.label=input('ufLabel').value;
    const a=byId(n.asset)!;if(a.recipe||n.asset==='joystick-base'){n.width=Math.max(n.asset==='inventory-board'?184:32,Math.min(screen[0],Math.round(Number(input('ufNodeW').value))||a.width));n.height=Math.max(n.asset==='inventory-board'?156:(n.asset==='bar-track'?16:32),Math.min(screen[1],Math.round(Number(input('ufNodeH').value))||a.height));if(n.asset==='frame-skill'||n.asset==='frame-item'){const diameter=(event?.target as HTMLElement)?.id==='ufNodeH'?n.height:n.width;n.width=Math.min(screen[1],diameter);n.height=n.width;if(n.asset==='frame-skill')delete n.label;}if(n.asset==='joystick-base'){n.width=Math.max(64,Math.min(116,n.width));n.height=n.width;}move(n,n.x,n.y);}
    if(n.fill)n.value=Number(input('ufValue').value);inspector();persist();render();}
  for(const id of ['ufLabel','ufValue'])el(id).addEventListener('input',editNode);
  for(const id of ['ufX','ufY','ufNodeW','ufNodeH'])el(id).addEventListener('change',editNode);
  click('ufFront',()=>{const n=current();if(!n||n.locked||busy||dirty)return;checkpoint();nodes=nodes.filter(item=>item!==n);nodes.push(n);persist();inspector();render();});
  click('ufBack',()=>{const n=current();if(!n||n.locked||busy||dirty)return;checkpoint();nodes=nodes.filter(item=>item!==n);nodes.unshift(n);persist();inspector();render();});
  function remove(){if(!active||current()?.locked||busy||dirty)return;checkpoint();nodes=nodes.filter(n=>n.id!==active);active=null;inspector();persist();render();}
  click('ufDelete',remove);click('ufDuplicate',()=>{const n=current();if(!n||busy||dirty||nodes.length>=100)return;checkpoint();const copy={...n,id:crypto.randomUUID(),locked:false};move(copy,n.x+8,n.y+8);nodes.push(copy);active=copy.id;inspector();persist();render();});
  click('ufSave',()=>saveBlob(new Blob([JSON.stringify(design(),null,2)],{type:'application/json'}),'hkt-ui-design.json'));
  click('ufPNG',()=>{
    const a=byId(selected);if(!a)return;
    if(view==='assembly'&&input('ufExplode').checked&&a.recipe){downloadSpriteStrip();return;}
    if(a.recipe){const sz=displaySize(a),out=document.createElement('canvas');out.width=sz.w;out.height=sz.h;drawAssembly(out.getContext('2d')!,a.recipe,sz.w,sz.h,byId);download(out.toDataURL('image/png'),`${a.id}-${sz.w}x${sz.h}.png`);}else download(a.url,`${a.id}.png`);
  });
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
    if(!opened){opened=true;try{const saved=JSON.parse(localStorage.getItem(KEY)||'null');if(saved?.version===3){s={...DEFAULT,...saved.settings};if(!saved.styleRevision&&s.frameStyle==='wood'){s.frameStyle='bamboo';s.corner='leaves';}if(!saved.settings?.rail||!saved.settings?.outline){const p=STYLE_PALETTES[s.frameStyle]??STYLE_PALETTES.bamboo;s={...s,...p};}screen=saved.canvas??[640,360];pendingLayout=saved.layout;edits=saved.edits??{};if(saved.uiState){restoredView=saved.uiState.view;restoredSelected=saved.uiState.selected;restoredActive=saved.uiState.active;restoredZoom=saved.uiState.zoom;restoredExploded=saved.uiState.exploded;restoredPadding=saved.uiState.padding;restoredFilter=saved.uiState.filter;restoredSearch=saved.uiState.search;restoredSecondary=saved.uiState.secondary;restoredSafe=saved.uiState.safe;restoredGrid=saved.uiState.grid;restoredDevice=saved.uiState.device;}}}catch{note('Bản nháp cũ không đọc được.',true);}void generate();}else{render();fit();}
  };
  dialog.addEventListener('close',()=>{endDrag();persist();if(resumed&&!isPlaying)togglePlayPause();resumed=false;});
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
  let wasModalOpen=false;
  try{const saved=JSON.parse(localStorage.getItem(KEY)||'null');if(saved?.version===3&&saved?.uiState?.modalOpen)wasModalOpen=true;}catch{}
  if(wasModalOpen)setTimeout(()=>launch.click(),60);
}
