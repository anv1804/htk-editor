import './map-studio.css';
import { loadImage, readFile } from './utils';
import { setupMapAssets } from './map-assets';
import { setupMapPixel } from './map-pixel-workbench';
import { createLayer, newScene, placeAsset, readScene, snapshot, snapPixel, uid } from './map-scene-model';
import type { MapScene, SceneAsset, SceneItem, CollisionRect } from './map-scene-model';
import { downloadBlob, imageSource, openDemo, openFolder, openZip, restoreScene, saveScene } from './map-scene-io';
import { drawLayer, renderScene } from './map-scene-render';
import type { SceneImages } from './map-scene-render';

type Tool = 'select' | 'stamp' | 'crop' | 'collision' | 'pan';
type Selection = { kind: 'item'; layer: string; id: string } | { kind: 'collision'; id: string } | null;
type Point = { x: number; y: number };

export function setupMapStudio() {
  if (document.getElementById('mapStudio')) return;
  const nav = document.createElement('button');
  nav.id = 'openMapStudio'; nav.className = 'map-launch'; nav.textContent = '▧ Xưởng map'; nav.title = 'Map Studio · Alt+M';
  document.querySelector('.project-actions')?.before(nav);
  const root = document.createElement('dialog'); root.id = 'mapStudio'; root.className = 'ms'; root.setAttribute('aria-labelledby', 'msTitle');
  root.innerHTML = `
    <div class="ms-header">
      <div class="ms-brand"><div class="ms-mark">▧</div><div><strong id="msTitle">MAP STUDIO</strong><small>LAYER + MODULE · NATIVE PIXEL</small></div></div>
      <button id="msDemo">Map mẫu 8 lớp</button><button id="msNew">Map mới</button><button id="msPixel">Xử lý nét pixel</button>
      <label class="ms-file">Nhập folder<input id="msFolder" type="file" webkitdirectory multiple hidden></label>
      <label class="ms-file">Mở ZIP / JSON<input id="msOpen" type="file" accept=".zip,.json" hidden></label>
      <button id="msExportJson">Lưu Project</button><button id="msExportPng" class="ms-primary">Xuất PNG</button>
      <button id="msClose" class="ms-close" aria-label="Đóng map studio">×</button>
    </div>
    <div class="ms-body">
      <aside class="ms-sidebar">
        <label class="ms-field ms-full">Tên map<input id="msName" maxlength="200"></label>
        <div class="ms-section"><span>Các lớp · trên → dưới</span><button id="msAddLayer" aria-label="Thêm lớp">+</button></div>
        <div id="msLayers"></div>
        <div class="ms-layer-tools"><button id="msLayerUp" aria-label="Đưa lớp lên">↑</button><button id="msLayerDown" aria-label="Đưa lớp xuống">↓</button><button id="msDeleteLayer">Xóa lớp</button></div>
        <hr><label class="ms-field">Rộng<input id="msWidth" type="number" min="1" max="8192"></label>
        <label class="ms-field">Cao<input id="msHeight" type="number" min="1" max="8192"></label>
        <label class="ms-field"><span>Lưới đặt vật thể</span><select id="msSnap"><option value="1">1 px</option><option value="8">8 px</option><option value="16">16 px</option><option value="32">32 px</option><option value="64">64 px</option></select></label>
        <label class="ms-field"><span>Hiện lưới</span><input id="msGrid" type="checkbox"></label>
        <label class="ms-field"><span>Hiện va chạm</span><input id="msCollisions" type="checkbox" checked></label>
        <p class="ms-note">Ảnh nguồn giữ kích thước gốc. Lưới chỉ giúp đặt vị trí. Layer nhập sẵn được khóa để tránh kéo nhầm.</p>
      </aside>
      <main class="ms-center">
        <div class="ms-toolbar" role="toolbar" aria-label="Công cụ map">
          <button data-tool="select" aria-pressed="true">Chọn · V</button><button data-tool="stamp" aria-pressed="false">Đặt · B</button>
          <button data-tool="crop" aria-pressed="false">Cắt module</button><button data-tool="collision" aria-pressed="false">Va chạm</button><button data-tool="pan" aria-pressed="false">Kéo xem</button>
          <span class="ms-spacer"></span><button id="msUndo" aria-label="Hoàn tác" title="Ctrl+Z">↶</button><button id="msRedo" aria-label="Làm lại" title="Ctrl+Shift+Z">↷</button>
          <select id="msZoom" aria-label="Độ phóng đại"><option value="fit">Vừa khung</option><option value="1">100%</option><option value="2">200%</option><option value="4">400%</option></select>
        </div>
        <div class="ms-viewport" id="msViewport" data-tool="select"><div class="ms-stage"><canvas id="mapCanvas" class="ms-canvas" aria-label="Map; chọn và kéo vật thể, hoặc đặt module từ thư viện"></canvas></div></div>
        <div class="ms-camera"><label for="msCamera">Xem parallax</label><input id="msCamera" type="range" min="-600" max="600" value="0" step="1"><output id="msCameraValue">0 px</output><button id="msCameraReset">Về gốc</button></div>
        <div class="ms-library"><div class="ms-library-bar"><span id="msLibraryCount">Thư viện module</span><label class="ms-file">+ PNG<input id="msPngs" type="file" accept="image/png" multiple hidden></label><button id="msCleanup">Sửa alpha / màu</button></div><div id="msLibrary" class="ms-library-items"></div></div>
      </main>
      <aside class="ms-inspector"><section id="msLayerDetails" class="ms-details"></section><hr><section id="msObjectDetails" class="ms-details"></section><hr><p class="ms-note" id="msHint">Chọn layer để chỉnh. Kéo module từ thư viện lên map.</p></aside>
    </div>
    <div class="ms-footer"><span id="msStatus" role="status">Sẵn sàng</span><span id="msSaved"></span><span id="msSize"></span></div>`;
  document.body.append(root);
  const el = <T extends HTMLElement = HTMLElement>(id: string) => root.querySelector<T>(`#${id}`)!;
  const input = (id: string) => el<HTMLInputElement>(id);
  const canvas = el<HTMLCanvasElement>('mapCanvas'), viewport = el('msViewport');
  let scene = newScene(), images: SceneImages = new Map(), activeLayer = scene.layers[1]!.id;
  let selection: Selection = null, activeAsset = '', tool: Tool = 'select', zoom = 1, busy = false, initialized = false, space = false;
  let camera = 0, dirty = true, saveTimer = 0, saveVersion = 0;
  const composed = document.createElement('canvas'), sample = document.createElement('canvas'); sample.width = sample.height = 1;
  const undo: MapScene[] = [], redo: MapScene[] = [];
  let gesture: { kind: 'pan' | 'move' | 'rect'; start: Point; scrollX?: number; scrollY?: number; x?: number; y?: number; changed: boolean; before?: MapScene } | null = null;
  let rectangle: { x: number; y: number; w: number; h: number } | null = null;
  const layer = () => scene.layers.find(l => l.id === activeLayer)!;
  const selectedItem = (): SceneItem | undefined => { const s = selection; return s?.kind === 'item' ? scene.layers.find(l => l.id === s.layer)?.items.find(i => i.id === s.id) : undefined; };
  const selectedCollision = (): CollisionRect | undefined => { const s = selection; return s?.kind === 'collision' ? scene.collisions.find(c => c.id === s.id) : undefined; };
  const selectedAsset = () => scene.assets.find(a => a.id === (selectedItem()?.assetId || activeAsset));
  const step = () => Number(input('msSnap').value);
  const notice = (message: string, error = false) => { el('msStatus').textContent = message; el('msStatus').dataset.error = String(error); };
  const slug = () => scene.name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9_-]+/g, '-').slice(0, 80) || 'map';

  function checkpoint() { undo.push(snapshot(scene)); if (undo.length > 40) undo.shift(); redo.length = 0; }
  function historyButtons() { el<HTMLButtonElement>('msUndo').disabled = !undo.length; el<HTMLButtonElement>('msRedo').disabled = !redo.length; }
  function persist() {
    clearTimeout(saveTimer); const version = ++saveVersion;
    el('msSaved').textContent = 'Đang lưu…'; el('msSaved').className = '';
    saveTimer = window.setTimeout(() => {
      void saveScene(snapshot(scene)).then(() => { if (version === saveVersion) el('msSaved').textContent = 'Đã lưu trên máy'; }).catch(() => {
        if (version === saveVersion) { el('msSaved').textContent = 'Chưa lưu — hãy tải Project'; el('msSaved').className = 'ms-save-warning'; }
      });
    }, 300);
  }
  function changed(message?: string) { dirty = true; sync(); persist(); if (message) notice(message); }
  function mutate(action: () => void, message?: string) { if (busy) return; checkpoint(); action(); changed(message); }
  async function run(action: () => Promise<void>) {
    if (busy) return; busy = true; root.setAttribute('aria-busy', 'true');
    try { await action(); } catch (e) { notice(e instanceof Error ? e.message : String(e), true); }
    finally { busy = false; root.setAttribute('aria-busy', 'false'); historyButtons(); }
  }
  async function prepare(next: MapScene) {
    const validated = readScene(next), loaded: SceneImages = new Map();
    for (const asset of validated.assets) {
      const existing = scene.assets.find(a => a.id === asset.id && a.src === asset.src);
      const img = existing && images.get(asset.id) || await loadImage(asset.src);
      if (img.width !== asset.w || img.height !== asset.h) throw new Error(`Kích thước PNG không khớp: ${asset.name}`);
      loaded.set(asset.id, img);
    }
    return { validated, loaded };
  }
  async function replace(next: MapScene, remember = true) {
    const ready = await prepare(next); if (remember) checkpoint();
    scene = ready.validated; images = ready.loaded; activeLayer = scene.layers.at(-1)!.id; activeAsset = scene.assets.find(a => a.category !== 'layer')?.id || '';
    selection = null; camera = 0; input('msCamera').value = '0'; el('msCameraValue').textContent = '0 px'; input('msZoom').value = 'fit'; dirty = true; sync(); persist();
    notice(`${scene.layers.length} lớp · ${scene.assets.filter(a => a.category !== 'layer').length} module. Vật thể trong layer gốc đã được ghép sẵn.`);
  }
  async function history(isRedo: boolean) {
    const from = isRedo ? redo : undo, to = isRedo ? undo : redo, next = from.at(-1); if (!next) return;
    const ready = await prepare(next); from.pop(); to.push(snapshot(scene)); scene = ready.validated; images = ready.loaded;
    if (!scene.layers.some(l => l.id === activeLayer)) activeLayer = scene.layers.at(-1)!.id;
    selection = null; changed(isRedo ? 'Đã làm lại.' : 'Đã hoàn tác.');
  }
  function setTool(next: Tool) {
    tool = next; viewport.dataset.tool = tool;
    root.querySelectorAll<HTMLButtonElement>('[data-tool]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tool === tool)));
    const hints: Record<Tool, string> = { select: 'Kéo vật thể trên lớp đã mở khóa. Delete: xóa · Ctrl+D: nhân bản · phím mũi tên: dịch pixel.', stamp: 'Bấm hoặc thả module lên lớp đang chọn. Điểm chân bám lưới; ảnh giữ nguyên kích thước.', crop: 'Kéo khung trên layer đang chọn để tạo module. Nguồn gốc được giữ nguyên; module mới nằm trong thư viện.', collision: 'Kéo khung tạo vùng va chạm. Bật “Sàn một chiều” trong thuộc tính khi cần.', pan: 'Kéo để xem map. Có thể giữ Space hoặc chuột giữa ở mọi công cụ.' }; el('msHint').textContent = hints[tool];
  }
  function renderLayers() {
    const host = el('msLayers'); host.replaceChildren();
    for (const l of [...scene.layers].reverse()) {
      const row = document.createElement('div'); row.className = `ms-layer ${l.id === activeLayer ? 'ms-selected' : ''}`;
      const visible = document.createElement('input'); visible.type = 'checkbox'; visible.checked = l.visible; visible.setAttribute('aria-label', `Hiện ${l.name}`); visible.onchange = () => mutate(() => { l.visible = visible.checked; });
      const name = document.createElement('button'); name.className = 'ms-layer-name'; name.textContent = l.name;
      const detail = document.createElement('small'); detail.textContent = `${l.items.length} ảnh · ${Math.round(l.opacity * 100)}%`; name.append(detail); name.onclick = () => { activeLayer = l.id; selection = null; sync(); };
      const lock = document.createElement('button'); lock.textContent = l.locked ? '🔒' : '○'; lock.setAttribute('aria-label', `${l.locked ? 'Mở khóa' : 'Khóa'} ${l.name}`); lock.onclick = () => mutate(() => { l.locked = !l.locked; }); row.append(visible, name, lock); host.append(row);
    }
    const i = scene.layers.findIndex(l => l.id === activeLayer);
    el<HTMLButtonElement>('msLayerUp').disabled = i === scene.layers.length - 1; el<HTMLButtonElement>('msLayerDown').disabled = i === 0; el<HTMLButtonElement>('msDeleteLayer').disabled = scene.layers.length === 1 || layer().locked;
  }
  function renderLibrary() {
    const host = el('msLibrary'); host.replaceChildren(); const assets = scene.assets.filter(a => a.category !== 'layer'); el('msLibraryCount').textContent = `MODULE · ${assets.length} ảnh · kích thước gốc`;
    if (!assets.length) { const p = document.createElement('p'); p.className = 'ms-note'; p.textContent = 'Nhập PNG hoặc dùng Cắt module trên một layer để bắt đầu.'; host.append(p); }
    for (const a of assets) {
      const b = document.createElement('button'); b.className = 'ms-asset'; b.setAttribute('aria-pressed', String(a.id === activeAsset)); b.draggable = true;
      const im = new Image(); im.src = a.src; im.alt = ''; const name = document.createElement('span'); name.textContent = a.name; const size = document.createElement('small'); size.textContent = `${a.w} × ${a.h}`; b.append(im, name, size);
      b.onclick = () => { activeAsset = a.id; selection = null; setTool('stamp'); renderLibrary(); renderInspector(); draw(); };
      b.ondragstart = e => { e.dataTransfer?.setData('application/x-hkt-map-asset', a.id); if (e.dataTransfer) e.dataTransfer.effectAllowed = 'copy'; }; host.append(b);
    }
  }
  function field(host: HTMLElement, label: string, value: string | number, type: 'text' | 'number', action: (value: string) => void, min?: number, max?: number) {
    const line = document.createElement('label'); line.className = `ms-field ${type === 'text' ? 'ms-full' : ''}`; const span = document.createElement('span'); span.textContent = label;
    const control = document.createElement('input'); control.type = type; control.value = String(value); control.setAttribute('aria-label', label);
    if (min !== undefined) control.min = String(min); if (max !== undefined) control.max = String(max);
    control.onchange = () => { if (!control.checkValidity() || (type === 'number' && control.value === '')) { control.value = String(value); return; } action(control.value); };
    line.append(span, control); host.append(line); return control;
  }
  function check(host: HTMLElement, label: string, value: boolean, action: (value: boolean) => void) {
    const line = document.createElement('label'); line.className = 'ms-field'; const span = document.createElement('span'); span.textContent = label;
    const control = document.createElement('input'); control.type = 'checkbox'; control.checked = value; control.onchange = () => action(control.checked); line.append(span, control); host.append(line);
  }
  function button(host: HTMLElement, title: string, action: () => void) { const b = document.createElement('button'); b.textContent = title; b.onclick = action; host.append(b); return b; }
  function heading(host: HTMLElement, title: string) { const h = document.createElement('h3'); h.textContent = title; host.append(h); }
  function renderInspector() {
    const lh = el('msLayerDetails'), oh = el('msObjectDetails'); lh.replaceChildren(); oh.replaceChildren(); const l = layer(); heading(lh, 'Thuộc tính lớp');
    field(lh, 'Tên lớp', l.name, 'text', v => mutate(() => { l.name = v.trim().slice(0, 200) || l.name; }));
    field(lh, 'Độ đậm %', Math.round(l.opacity * 100), 'number', v => mutate(() => { l.opacity = Math.max(0, Math.min(100, Number(v))) / 100; }), 0, 100);
    const parallax = field(lh, 'Parallax', l.parallax, 'number', v => mutate(() => { l.parallax = Math.max(0, Math.min(2, Number(v))); }), 0, 2); parallax.step = '0.05'; check(lh, 'Khóa lớp', l.locked, v => mutate(() => { l.locked = v; }));
    const c = selectedCollision();
    if (c) {
      heading(oh, 'Vùng va chạm');
      for (const [key, label] of [['x', 'X'], ['y', 'Y'], ['w', 'Rộng'], ['h', 'Cao']] as const) field(oh, label, c[key], 'number', v => mutate(() => { c[key] = Math.round(Number(v)); }), key === 'x' || key === 'y' ? -65536 : 1, key === 'x' || key === 'y' ? 65536 : 8192);
      check(oh, 'Sàn một chiều', c.oneWay, v => mutate(() => { c.oneWay = v; })); button(oh, 'Xóa vùng', removeSelection); return;
    }
    const a = selectedAsset(), item = selectedItem();
    if (!a) { heading(oh, 'Vật thể / module'); const p = document.createElement('p'); p.className = 'ms-note'; p.textContent = 'Chọn module trong thư viện hoặc chọn ảnh trên canvas.'; oh.append(p); return; }
    heading(oh, a.name); const im = new Image(); im.src = a.src; im.alt = a.name; im.className = 'ms-asset-preview'; oh.append(im); const dims = document.createElement('p'); dims.className = 'ms-note'; dims.textContent = `${a.w} × ${a.h} px · giữ nguyên ảnh nguồn`; oh.append(dims);
    if (item) {
      for (const axis of ['x', 'y'] as const) { const f = field(oh, axis.toUpperCase(), item[axis], 'number', v => { if (!l.locked) mutate(() => { item[axis] = Math.round(Number(v)); }); }, -65536, 65536); f.disabled = l.locked; }
      button(oh, 'Lật ngang', () => { if (!l.locked) mutate(() => { item.flipX = !item.flipX; }); }).disabled = l.locked; button(oh, 'Lật dọc', () => { if (!l.locked) mutate(() => { item.flipY = !item.flipY; }); }).disabled = l.locked;
      button(oh, 'Nhân bản', duplicate).disabled = l.locked; button(oh, 'Xóa vật thể', removeSelection).disabled = l.locked;
      const line = document.createElement('label'); line.className = 'ms-field'; line.append('Chuyển lớp'); const select = document.createElement('select'); select.setAttribute('aria-label', 'Chuyển vật thể sang lớp');
      for (const target of scene.layers) { const o = document.createElement('option'); o.value = target.id; o.textContent = target.name; o.disabled = target.locked; o.selected = target.id === l.id; select.append(o); }
      select.disabled = l.locked; select.onchange = () => mutate(() => { l.items = l.items.filter(i => i.id !== item.id); const target = scene.layers.find(t => t.id === select.value)!; target.items.push(item); activeLayer = target.id; selection = { kind: 'item', id: item.id, layer: target.id }; }); line.append(select); oh.append(line);
    } else {
      field(oh, 'Tên module', a.name, 'text', v => mutate(() => { a.name = v.trim().slice(0, 200) || a.name; }));
      for (const [key, label, max] of [['pivotX', 'Điểm chân X', a.w], ['pivotY', 'Điểm chân Y', a.h]] as const) field(oh, label, a[key], 'number', v => mutate(() => { a[key] = Math.round(Number(v)); }), 0, max);
      button(oh, 'Đặt module', () => setTool('stamp'));
    }
  }
  function sync() {
    if (!scene.layers.some(l => l.id === activeLayer)) activeLayer = scene.layers.at(-1)!.id;
    input('msName').value = scene.name; input('msWidth').value = String(scene.width); input('msHeight').value = String(scene.height); renderLayers(); renderLibrary(); renderInspector(); historyButtons(); draw();
  }
  function draw() {
    if (!root.open) return;
    if (dirty) { renderScene(composed, scene, images, camera); dirty = false; }
    zoom = input('msZoom').value === 'fit' ? Math.max(.05, Math.min(1, (viewport.clientWidth - 48) / scene.width, (viewport.clientHeight - 48) / scene.height)) : Number(input('msZoom').value);
    if (canvas.width !== scene.width) canvas.width = scene.width; if (canvas.height !== scene.height) canvas.height = scene.height;
    canvas.style.width = `${scene.width * zoom}px`; canvas.style.height = `${scene.height * zoom}px`;
    const ctx = canvas.getContext('2d')!; ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.imageSmoothingEnabled = false; ctx.drawImage(composed, 0, 0);
    if (input('msGrid').checked && camera === 0) {
      const grid = Math.max(step(), zoom >= 4 ? 1 : 8); ctx.strokeStyle = '#b5cad13b'; ctx.lineWidth = 1 / zoom; ctx.beginPath();
      if (grid * zoom >= 4) { for (let x = 0; x <= scene.width; x += grid) { ctx.moveTo(x, 0); ctx.lineTo(x, scene.height); } for (let y = 0; y <= scene.height; y += grid) { ctx.moveTo(0, y); ctx.lineTo(scene.width, y); } ctx.stroke(); }
    }
    if (input('msCollisions').checked && camera === 0) for (const c of scene.collisions) {
      ctx.fillStyle = c.oneWay ? '#f6c75a25' : '#63e9c026'; ctx.strokeStyle = c.oneWay ? '#f6c75a' : '#63e9c0'; ctx.lineWidth = 1 / zoom; ctx.fillRect(c.x, c.y, c.w, c.h); ctx.strokeRect(c.x, c.y, c.w, c.h);
      if (c.oneWay) { ctx.lineWidth = 3 / zoom; ctx.beginPath(); ctx.moveTo(c.x, c.y); ctx.lineTo(c.x + c.w, c.y); ctx.stroke(); }
    }
    const item = selectedItem(), a = selectedAsset(), collision = selectedCollision(); const bounds = collision || (item && a ? { x: item.x, y: item.y, w: a.w, h: a.h } : null);
    if (bounds && camera === 0) { ctx.strokeStyle = '#e7f8b0'; ctx.lineWidth = 2 / zoom; ctx.setLineDash([6 / zoom, 3 / zoom]); ctx.strokeRect(bounds.x, bounds.y, bounds.w, bounds.h); ctx.setLineDash([]); }
    if (rectangle) { ctx.fillStyle = '#b4d8ff25'; ctx.strokeStyle = '#b4d8ff'; ctx.lineWidth = 2 / zoom; ctx.fillRect(rectangle.x, rectangle.y, rectangle.w, rectangle.h); ctx.strokeRect(rectangle.x, rectangle.y, rectangle.w, rectangle.h); }
    el('msSize').textContent = `${scene.width} × ${scene.height} px · ${Math.round(zoom * 100)}%${input('msZoom').value === 'fit' ? ' · xem bố cục' : ' · xem pixel'}`;
  }
  function point(e: MouseEvent): Point { const r = canvas.getBoundingClientRect(); return { x: Math.floor((e.clientX - r.left) * scene.width / r.width), y: Math.floor((e.clientY - r.top) * scene.height / r.height) }; }
  const inMap = (p: Point) => p.x >= 0 && p.y >= 0 && p.x < scene.width && p.y < scene.height;
  function hit(p: Point): Selection {
    if (input('msCollisions').checked && tool === 'collision') { const c = [...scene.collisions].reverse().find(c => p.x >= c.x && p.y >= c.y && p.x < c.x + c.w && p.y < c.y + c.h); if (c) return { kind: 'collision', id: c.id }; }
    const ctx = sample.getContext('2d', { willReadFrequently: true })!;
    for (const l of [...scene.layers].reverse()) {
      if (!l.visible || l.locked || l.opacity === 0) continue;
      for (const i of [...l.items].reverse()) {
        const a = scene.assets.find(a => a.id === i.assetId)!, img = images.get(a.id); let x = p.x - i.x, y = p.y - i.y;
        if (x < 0 || y < 0 || x >= a.w || y >= a.h || !img) continue; if (i.flipX) x = a.w - 1 - x; if (i.flipY) y = a.h - 1 - y;
        ctx.clearRect(0, 0, 1, 1); ctx.drawImage(img, x, y, 1, 1, 0, 0, 1, 1); if (ctx.getImageData(0, 0, 1, 1).data[3]! > 8) return { kind: 'item', layer: l.id, id: i.id };
      }
    }
    return null;
  }
  function stamp(assetId: string, p: Point) {
    if (camera !== 0) { notice('Đưa camera về gốc trước khi chỉnh map.', true); return; }
    const l = layer(), a = scene.assets.find(a => a.id === assetId); if (!a || !inMap(p)) return;
    if (l.locked || !l.visible) { notice('Chọn lớp đang hiện và mở khóa, hoặc tạo lớp mới.', true); return; }
    if (scene.layers.reduce((n, l) => n + l.items.length, 0) >= 10000) { notice('Map tối đa 10.000 vật thể.', true); return; }
    mutate(() => { const i = placeAsset(a, p.x, p.y, step()); l.items.push(i); selection = { kind: 'item', layer: l.id, id: i.id }; activeAsset = a.id; }, `Đã đặt ${a.name} · ${a.w} × ${a.h} px.`);
  }
  function removeSelection() {
    const c = selectedCollision(), i = selectedItem();
    if (c) mutate(() => { scene.collisions = scene.collisions.filter(v => v.id !== c.id); selection = null; });
    else if (i && !layer().locked) mutate(() => { layer().items = layer().items.filter(v => v.id !== i.id); selection = null; });
  }
  function duplicate() { const i = selectedItem(); if (!i || layer().locked) return; mutate(() => { const copy = { ...i, id: uid(), x: i.x + step(), y: i.y + step() }; layer().items.push(copy); selection = { kind: 'item', id: copy.id, layer: activeLayer }; }); }
  async function addAsset(a: SceneAsset) {
    const next = snapshot(scene); next.assets.push(a); readScene(next); const img = await loadImage(a.src); checkpoint(); scene = next; images.set(a.id, img); activeAsset = a.id; selection = null; setTool('stamp'); changed(`Đã thêm module ${a.name}.`);
  }
  async function cropModule(r: { x: number; y: number; w: number; h: number }) {
    const source = document.createElement('canvas'); source.width = scene.width; source.height = scene.height; drawLayer(source.getContext('2d')!, scene, layer(), images);
    const out = document.createElement('canvas'); out.width = r.w; out.height = r.h; const ctx = out.getContext('2d')!; ctx.imageSmoothingEnabled = false; ctx.drawImage(source, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h);
    const pixels = ctx.getImageData(0, 0, r.w, r.h).data; let visible = false; for (let i = 3; i < pixels.length; i += 4) if (pixels[i]! > 0) { visible = true; break; }
    if (!visible) throw new Error('Vùng cắt trên lớp đang chọn không có pixel nhìn thấy.');
    await addAsset({ id: uid(), name: `${layer().name} · vùng ${r.x},${r.y}`, src: out.toDataURL('image/png'), w: r.w, h: r.h, pivotX: Math.floor(r.w / 2), pivotY: r.h, category: 'module' });
  }
  canvas.addEventListener('pointerdown', e => {
    if (busy || e.button === 2) return; e.preventDefault();
    if (space || tool === 'pan' || e.button === 1) { gesture = { kind: 'pan', start: { x: e.clientX, y: e.clientY }, scrollX: viewport.scrollLeft, scrollY: viewport.scrollTop, changed: false }; canvas.setPointerCapture(e.pointerId); return; }
    if (camera !== 0) { notice('Đưa camera về gốc trước khi chỉnh map.', true); return; }
    const p = point(e); if (!inMap(p)) return; if (tool === 'stamp') { stamp(activeAsset, p); return; }
    if (tool === 'crop' || tool === 'collision') {
      const found = tool === 'collision' ? hit(p) : null;
      if (found?.kind === 'collision') { selection = found; const c = selectedCollision()!; gesture = { kind: 'move', start: p, x: c.x, y: c.y, changed: false, before: snapshot(scene) }; }
      else { selection = null; gesture = { kind: 'rect', start: p, changed: false }; }
    } else {
      selection = hit(p);
      if (selection?.kind === 'item') { activeLayer = selection.layer; const i = selectedItem()!; activeAsset = i.assetId; gesture = { kind: 'move', start: p, x: i.x, y: i.y, changed: false, before: snapshot(scene) }; }
    }
    canvas.setPointerCapture(e.pointerId); sync();
  });
  canvas.addEventListener('pointermove', e => {
    if (!gesture) return; const p = point(e);
    if (gesture.kind === 'pan') { viewport.scrollLeft = gesture.scrollX! - (e.clientX - gesture.start.x); viewport.scrollTop = gesture.scrollY! - (e.clientY - gesture.start.y); return; }
    if (gesture.kind === 'move') {
      const item = selectedItem() || selectedCollision(); if (!item) return;
      const x = Math.max(-65536, Math.min(65536, gesture.x! + snapPixel(p.x - gesture.start.x, step()))), y = Math.max(-65536, Math.min(65536, gesture.y! + snapPixel(p.y - gesture.start.y, step())));
      if (item.x !== x || item.y !== y) { item.x = x; item.y = y; gesture.changed = true; dirty = true; }
    } else {
      const a = gesture.start, x = Math.max(0, Math.min(a.x, p.x)), y = Math.max(0, Math.min(a.y, p.y)); rectangle = { x, y, w: Math.min(scene.width, Math.max(a.x, p.x) + 1) - x, h: Math.min(scene.height, Math.max(a.y, p.y) + 1) - y };
    }
    draw();
  });
  function endGesture(cancel = false) {
    const g = gesture, r = rectangle; gesture = null; rectangle = null; if (!g) return;
    if (g.kind === 'move' && g.changed) {
      if (cancel) { scene = g.before!; dirty = true; sync(); return; }
      undo.push(g.before!); if (undo.length > 40) undo.shift(); redo.length = 0; changed();
    } else if (g.kind === 'rect' && r && r.w > 0 && r.h > 0 && !cancel) {
      if (tool === 'crop') void run(() => cropModule(r)); else if (scene.collisions.length < 5000) mutate(() => { const c = { id: uid(), ...r, oneWay: false }; scene.collisions.push(c); selection = { kind: 'collision', id: c.id }; });
    }
    draw();
  }
  canvas.addEventListener('pointerup', () => endGesture()); canvas.addEventListener('pointercancel', () => endGesture(true)); canvas.addEventListener('lostpointercapture', () => endGesture(true)); canvas.addEventListener('contextmenu', e => e.preventDefault());
  canvas.addEventListener('dragover', e => { if (e.dataTransfer?.types.includes('application/x-hkt-map-asset')) e.preventDefault(); });
  canvas.addEventListener('drop', e => { e.preventDefault(); if (!busy) stamp(e.dataTransfer?.getData('application/x-hkt-map-asset') || '', point(e)); });

  const pixelWorkbench = setupMapPixel(() => scene.assets, async (result, sources, uploaded) => {
    if (uploaded) {
      const r = result.items[0]!, original = sources[0]!, assetId = uid();
      const sourceLayer = createLayer('Ảnh gốc'), processedLayer = createLayer('Map đã xử lý');
      sourceLayer.visible = false; sourceLayer.locked = processedLayer.locked = true;
      sourceLayer.items = [{ id: uid(), assetId: original.id, x: 0, y: 0, flipX: false, flipY: false }];
      processedLayer.items = [{ id: uid(), assetId, x: 0, y: 0, flipX: false, flipY: false }];
      const base = { name: original.name, w: r.width, h: r.height, pivotX: 0, pivotY: 0, category: 'layer' };
      await replace({ version: 3, name: original.name, width: r.width, height: r.height, assets: [{ ...base, id: original.id, src: original.image }, { ...base, id: assetId, src: r.image, originalSrc: original.image }], layers: [sourceLayer, processedLayer, createLayer('Module mới')], collisions: [] });
    } else {
      const next = snapshot(scene), byId = new Map(result.items.map(i => [i.id, i]));
      for (const a of next.assets) { const r = byId.get(a.id); if (r) { a.originalSrc ||= a.src; a.src = r.image; } }
      const ready = await prepare(next); checkpoint(); scene = ready.validated; images = ready.loaded; changed();
    }
    notice(`Đã áp dụng xử lý cho ${result.items.length} ảnh. Ảnh gốc được lưu trong Project.`);
  });
  el('msPixel').onclick = () => void pixelWorkbench.open();
  const cleanup = setupMapAssets(async incoming => {
    const next = snapshot(scene); const additions = incoming.map(a => ({ ...a, id: uid(), category: 'module' })); next.assets.push(...additions);
    const ready = await prepare(next); checkpoint(); scene = ready.validated; images = ready.loaded; activeAsset = additions[0]?.id || ''; selection = null; setTool('stamp'); changed('Đã thêm bản xử lý vào thư viện; ảnh nguồn được giữ riêng.');
  });
  el('msCleanup').onclick = () => { const a = selectedAsset(); if (a && a.w * a.h > 1048576) { notice('Cắt một module nhỏ hơn 1 triệu pixel trước khi sửa alpha / màu.', true); return; } void cleanup.open(a ? { name: a.name, src: a.src } : undefined); };
  root.querySelectorAll<HTMLButtonElement>('[data-tool]').forEach(b => b.onclick = () => setTool(b.dataset.tool as Tool));
  el('msUndo').onclick = () => void run(() => history(false)); el('msRedo').onclick = () => void run(() => history(true));
  el('msAddLayer').onclick = () => { if (scene.layers.length >= 64) { notice('Tối đa 64 lớp.', true); return; } mutate(() => { const l = createLayer(`Lớp ${scene.layers.length + 1}`); scene.layers.push(l); activeLayer = l.id; selection = null; }); };
  el('msDeleteLayer').onclick = () => { if (scene.layers.length > 1 && !layer().locked) mutate(() => { scene.layers = scene.layers.filter(l => l.id !== activeLayer); selection = null; }); };
  for (const [id, direction] of [['msLayerUp', 1], ['msLayerDown', -1]] as const) el(id).onclick = () => { const i = scene.layers.findIndex(l => l.id === activeLayer), j = i + direction; if (j >= 0 && j < scene.layers.length) mutate(() => { [scene.layers[i], scene.layers[j]] = [scene.layers[j]!, scene.layers[i]!]; }); };
  input('msName').onchange = () => mutate(() => { scene.name = input('msName').value.trim().slice(0, 200) || 'Map'; });
  for (const id of ['msWidth', 'msHeight']) input(id).onchange = () => {
    const w = Number(input('msWidth').value), h = Number(input('msHeight').value);
    if (!Number.isInteger(w) || !Number.isInteger(h) || w < 1 || h < 1 || w > 8192 || h > 8192 || w * h > 16777216) { notice('Map tối đa 16 triệu pixel; mỗi chiều 1–8192.', true); sync(); return; }
    mutate(() => { scene.width = w; scene.height = h; }, 'Đã đổi canvas. Vật thể giữ tọa độ gốc; phần ngoài canvas được giữ trong project.');
  };
  for (const id of ['msGrid', 'msSnap', 'msZoom', 'msCollisions']) input(id).onchange = draw;
  input('msCamera').oninput = () => { camera = Number(input('msCamera').value); el('msCameraValue').textContent = `${camera} px`; dirty = true; draw(); };
  el('msCameraReset').onclick = () => { camera = 0; input('msCamera').value = '0'; el('msCameraValue').textContent = '0 px'; dirty = true; draw(); };
  el('msDemo').onclick = () => void run(async () => { notice('Đang mở 8 lớp và 20 module…'); await replace(await openDemo()); }); el('msNew').onclick = () => void run(() => replace(newScene()));
  input('msFolder').onchange = () => { const files = Array.from(input('msFolder').files || []); input('msFolder').value = ''; if (files.length) void run(async () => { notice('Đang đọc bộ layer…'); await replace(await openFolder(files)); }); };
  input('msOpen').onchange = () => { const file = input('msOpen').files?.[0]; input('msOpen').value = ''; if (!file) return; void run(async () => { if (file.size > 128 * 1024 * 1024) throw new Error('Project quá lớn.'); notice('Đang đọc project…'); await replace(file.name.toLowerCase().endsWith('.zip') ? await openZip(file) : readScene(JSON.parse(await file.text()))); }); };
  input('msPngs').onchange = () => {
    const files = Array.from(input('msPngs').files || []); input('msPngs').value = ''; if (!files.length) return;
    void run(async () => {
      const next = snapshot(scene), ids: string[] = [];
      for (const file of files) { if (file.size > 24 * 1024 * 1024) throw new Error('PNG tối đa 24 MB.'); const source = await imageSource(await readFile(file)); const id = uid(); ids.push(id); next.assets.push({ ...source, id, name: file.name.slice(0, 200), pivotX: Math.floor(source.w / 2), pivotY: source.h, category: 'module' }); }
      const ready = await prepare(next); checkpoint(); scene = ready.validated; images = ready.loaded; activeAsset = ids[0]!; selection = null; setTool('stamp'); changed(`Đã thêm ${files.length} module nguyên bản.`);
    });
  };
  el('msExportJson').onclick = () => { try { readScene(scene); downloadBlob(new Blob([JSON.stringify(scene)], { type: 'application/json' }), `${slug()}.map.json`); notice('Đã xuất Project gồm ảnh nguồn, layer, module và collision.'); } catch (e) { notice(String(e), true); } };
  el('msExportPng').onclick = () => void run(async () => {
    const out = document.createElement('canvas'); renderScene(out, scene, images);
    const blob = await new Promise<Blob>((resolve, reject) => out.toBlob(b => b ? resolve(b) : reject(new Error('Không tạo được PNG.')), 'image/png')); downloadBlob(blob, `${slug()}.png`); notice('Đã xuất PNG 1:1 ở camera gốc, theo các lớp đang hiện.');
  });
  el('msClose').onclick = () => root.close(); root.addEventListener('close', () => { space = false; endGesture(true); });
  root.addEventListener('keydown', e => {
    e.stopPropagation(); if (busy || cleanup.isOpen()) return; if ((e.target as HTMLElement).matches('input,select,textarea,[contenteditable]')) return;
    if (e.code === 'Space') { e.preventDefault(); space = true; return; } const key = e.key.toLowerCase();
    if ((e.ctrlKey || e.metaKey) && key === 'z') { e.preventDefault(); void run(() => history(e.shiftKey)); }
    else if ((e.ctrlKey || e.metaKey) && key === 'y') { e.preventDefault(); void run(() => history(true)); }
    else if ((e.ctrlKey || e.metaKey) && key === 's') { e.preventDefault(); el('msExportJson').click(); }
    else if ((e.ctrlKey || e.metaKey) && key === 'd') { e.preventDefault(); if (!camera) duplicate(); }
    else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); if (!camera) removeSelection(); }
    else if (key === 'v') setTool('select'); else if (key === 'b') setTool('stamp');
    else if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key) && camera === 0) {
      const item = selectedItem() || selectedCollision(); if (!item || (selectedItem() && layer().locked)) return; e.preventDefault();
      mutate(() => { const amount = e.shiftKey ? step() * 10 : step(); item.x = Math.max(-65536, Math.min(65536, item.x + (e.key === 'ArrowRight' ? amount : e.key === 'ArrowLeft' ? -amount : 0))); item.y = Math.max(-65536, Math.min(65536, item.y + (e.key === 'ArrowDown' ? amount : e.key === 'ArrowUp' ? -amount : 0))); });
    }
  });
  root.addEventListener('keyup', e => { e.stopPropagation(); if (e.code === 'Space') space = false; }); window.addEventListener('blur', () => { space = false; endGesture(true); });
  nav.onclick = () => {
    if (!root.open) root.showModal();
    if (!initialized) { initialized = true; void run(async () => { notice('Đang mở Map Studio…'); let saved: MapScene | null = null; try { saved = await restoreScene(); } catch { notice('Không đọc được bản lưu. Có thể mở Project JSON.', true); } await replace(saved || await openDemo(), false); }); } else draw();
  };
  window.addEventListener('keydown', e => { if (e.altKey && e.key.toLowerCase() === 'm' && !document.querySelector('dialog:modal')) { e.preventDefault(); nav.click(); } });
  new ResizeObserver(() => draw()).observe(viewport); sync();
}
