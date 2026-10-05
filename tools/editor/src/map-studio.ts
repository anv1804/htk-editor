import { $ } from './utils';
import { setupMapAssets } from './map-assets';
import { assetPlacement, parseMapAssets } from './map-asset-model';
import type { MapLibraryAsset } from './map-asset-model';

export type BrushMode = 'autofit' | 'manual' | 'prop' | 'eraser';

export interface PlacedProp {
  id: string;
  propKey: string;
  x: number; // grid coordinate or pixel coordinate
  y: number;
  width: number;
  height: number;
}

export interface MapProject {
  version: 2;
  name: string;
  cols: number;
  rows: number;
  tileSize: number;
  loopX: boolean;
  themeId: string;
  showParallax: boolean;
  showGrid: boolean;
  // tiles: -1 for air, otherwise tile index 0..55 in the 8x7 atlas
  tiles: number[];
  props: PlacedProp[];
  assets?: MapLibraryAsset[];
}

export const TILES_COLS = 8;
export const TILES_ROWS = 7;
export const DEFAULT_TILE_SIZE = 64;

export const ATLAS_URL = '/assets/extracted_sheet/tileset_atlas_64x64.png';
export const PARALLAX_SKY = '/assets/extracted_sheet/parallax/layer_01_sky_clouds.png';
export const PARALLAX_FOREST = '/assets/extracted_sheet/parallax/layer_02_forest_waterfall.png';

export const PROPS_LIST = [
  { id: 'temple_gate', name: '⛩ Cổng Miếu', src: '/assets/extracted_sheet/props/prop_temple_gate.png', w: 110, h: 115 },
  { id: 'cherry_tree', name: '🌸 Cây Hoa Đào', src: '/assets/extracted_sheet/props/prop_cherry_tree.png', w: 145, h: 115 },
  { id: 'bamboo', name: '🎋 Rặng Trúc Xanh', src: '/assets/extracted_sheet/props/prop_bamboo.png', w: 180, h: 140 },
  { id: 'bridge', name: '🪵 Cầu Treo Gỗ', src: '/assets/extracted_sheet/props/prop_bridge.png', w: 120, h: 95 },
  { id: 'pagoda', name: '🏯 Đình Đài Tiên Cảnh', src: '/assets/extracted_sheet/props/prop_pagoda.png', w: 150, h: 115 },
  { id: 'stairs', name: '🪜 Bậc Thang Đá', src: '/assets/extracted_sheet/props/prop_stairs.png', w: 90, h: 80 },
  { id: 'waterwheel', name: '⚙ Bánh Xe Nước', src: '/assets/extracted_sheet/props/prop_waterwheel.png', w: 75, h: 85 },
  { id: 'stone_lanterns', name: '🪨 Đèn Đá & Bia Mộ', src: '/assets/extracted_sheet/props/prop_stone_lanterns.png', w: 140, h: 80 },
  { id: 'red_lanterns', name: '🏮 Đèn Lồng Đỏ', src: '/assets/extracted_sheet/props/prop_red_lanterns.png', w: 65, h: 145 },
];

// Autotile Index Lookup in 8x7 atlas
// Row 0: Top grass surface (0: meadow, 5: top-left, 6: top-center, 7: top-right)
// Row 1: Mid wall (5: left edge, 6: vertical wall center, 7: right edge)
// Row 2: Deep rock (2: inner bedrock, 6: deep wall)
// Row 3: Isolated ledge / bottom overhang (5: ledge-L, 6: bottom, 7: ledge-R)
// Row 6: Water (1: river stream, 2: lotus pond)
export const AUTOTILE = {
  TOP_LEFT: 5,     // row 0, col 5
  TOP_MID: 6,      // row 0, col 6
  TOP_RIGHT: 7,    // row 0, col 7
  TOP_SINGLE: 0,   // row 0, col 0
  MID_LEFT: 13,    // row 1, col 5
  MID_WALL: 14,    // row 1, col 6 (vách dựng đứng đập thẳng màn hình)
  MID_RIGHT: 15,   // row 1, col 7
  DEEP_WALL: 22,   // row 2, col 6
  INNER_ROCK: 18,  // row 2, col 2
  BOTTOM_MID: 30,  // row 3, col 6
  BOTTOM_LEFT: 29, // row 3, col 5
  BOTTOM_RIGHT: 31,// row 3, col 7
  WATER: 49,       // row 6, col 1
  WATER_LOTUS: 50, // row 6, col 2
};

let project: MapProject;
let atlasImage: HTMLImageElement | null = null;
let skyImage: HTMLImageElement | null = null;
let forestImage: HTMLImageElement | null = null;
const propImages: Map<string, HTMLImageElement> = new Map();

let brushMode: BrushMode = 'autofit';
let selectedTileIndex = AUTOTILE.TOP_MID;
let selectedPropKey = 'temple_gate';
let brushSize = 1;
let zoom = 0.85;
let drawing = false;

const undoStack: MapProject[] = [];
const redoStack: MapProject[] = [];
const PROJECT_KEY = 'hkt-celestial-map-project-v2';

function allProps() { return [...PROPS_LIST, ...(project?.assets || [])]; }

function syncProjectControls() {
  for (const [id,value] of [['mapName',project.name],['mapCols',String(project.cols)],['mapRows',String(project.rows)]] as const) {
    const input = $(id) as HTMLInputElement | null;
    if (input) input.value = value;
  }
  for (const [id,value] of [['mapLoop',project.loopX],['mapShowGrid',project.showGrid],['mapShowParallax',project.showParallax]] as const) {
    const input = $(id) as HTMLInputElement | null;
    if (input) input.checked = !!value;
  }
}

function renderPropLibrary() {
  const host = $('propsGrid');
  if (!host) return;
  host.replaceChildren();
  for (const prop of allProps()) {
    const card = document.createElement('button');
    card.className = `celestial-prop-card ${prop.id === selectedPropKey ? 'selected' : ''}`;
    card.dataset.prop = prop.id;
    const img = new Image(); img.src = prop.src; img.alt = prop.name;
    const title = document.createElement('span'); title.textContent = prop.name;
    card.append(img, title); host.append(card);
  }
}

function syncCustomAssets() {
  const defs = project.assets || [];
  for (const key of propImages.keys()) {
    if (key.startsWith('custom-') && !defs.some(a => a.id === key)) propImages.delete(key);
  }
  for (const def of defs) {
    if (propImages.get(def.id)?.src === def.src) continue;
    const img = new Image();
    img.onload = draw;
    img.onerror = () => { const notice = $('mapLibraryNotice'); if (notice) notice.textContent = `Không đọc được asset: ${def.name}`; };
    img.src = def.src;
    propImages.set(def.id, img);
  }
  if (!allProps().some(a => a.id === selectedPropKey)) selectedPropKey = 'temple_gate';
  renderPropLibrary();
}

function readMapProject(raw: unknown): MapProject {
  const p = raw as MapProject;
  if (!p || p.version !== 2 || !Number.isInteger(p.cols) || !Number.isInteger(p.rows) ||
      p.cols < 8 || p.cols > 64 || p.rows < 8 || p.rows > 32 || p.tileSize !== DEFAULT_TILE_SIZE ||
      !Array.isArray(p.tiles) || p.tiles.length !== p.cols*p.rows ||
      p.tiles.some(t => !Number.isInteger(t) || t < -1 || t >= 56) ||
      !Array.isArray(p.props) || p.props.length > 10000 || typeof p.name !== 'string') {
    throw new Error('Project map không hợp lệ.');
  }
  const assets = parseMapAssets(p.assets);
  const known = new Set([...PROPS_LIST, ...assets].map(a => a.id));
  if (p.props.some(a => !a || !known.has(a.propKey) || typeof a.id !== 'string' ||
      ![a.x,a.y,a.width,a.height].every(Number.isFinite) || a.width <= 0 || a.height <= 0 || a.width*a.height > 4194304)) {
    throw new Error('Project có vật thể hoặc tọa độ không hợp lệ.');
  }
  return { ...blankProject(p.cols,p.rows,false), ...p, assets };
}

function blankProject(cols = 28, rows = 14, demo = true): MapProject {
  const tiles = Array.from({ length: cols * rows }, () => -1);
  const props: PlacedProp[] = [];

  if (demo) {
    // Stage with left island, center gorge waterfall & bridge, right high mountain
    const floorY = rows - 4;
    // Ground foundation
    for (let x = 0; x < cols; x++) {
      if (x >= 9 && x <= 14) continue; // Gorge / chasm in the middle
      for (let y = floorY; y < rows; y++) {
        tiles[y * cols + x] = 1; // Mark as solid ground
      }
    }
    // High mountain on the right
    for (let x = 16; x < cols - 1; x++) {
      for (let y = floorY - 3; y < floorY; y++) {
        tiles[y * cols + x] = 1;
      }
    }
    // Floating ledge in the sky
    for (let x = 3; x <= 7; x++) {
      tiles[(floorY - 4) * cols + x] = 1;
      tiles[(floorY - 3) * cols + x] = 1;
    }
    // Waterfall river at bottom of gorge
    for (let x = 9; x <= 14; x++) {
      tiles[(rows - 2) * cols + x] = AUTOTILE.WATER;
      tiles[(rows - 1) * cols + x] = x % 2 === 0 ? AUTOTILE.WATER_LOTUS : AUTOTILE.WATER;
    }

    // Place iconic props
    props.push({ id: 'p1', propKey: 'temple_gate', x: 4, y: floorY - 6.8, width: 110, height: 115 });
    props.push({ id: 'p2', propKey: 'bridge', x: 9.2, y: floorY - 1.2, width: 120, height: 95 });
    props.push({ id: 'p3', propKey: 'cherry_tree', x: 18, y: floorY - 5.8, width: 145, height: 115 });
    props.push({ id: 'p4', propKey: 'bamboo', x: 23, y: floorY - 6.2, width: 180, height: 140 });
    props.push({ id: 'p5', propKey: 'stone_lanterns', x: 1, y: floorY - 2.2, width: 140, height: 80 });
  }

  const p: MapProject = {
    version: 2,
    name: 'Rừng Trúc Tiên Cảnh · Sơn Thạch 64×64',
    cols,
    rows,
    tileSize: DEFAULT_TILE_SIZE,
    loopX: true,
    themeId: 'celestial_forest',
    showParallax: true,
    showGrid: false,
    tiles,
    props
  };

  if (demo) {
    recalculateAllAutotiles(p);
  }
  return p;
}

function recalculateAllAutotiles(proj: MapProject) {
  const isSolid = (x: number, y: number) => {
    if (y < 0 || y >= proj.rows) return false;
    if (proj.loopX) x = (x % proj.cols + proj.cols) % proj.cols;
    else if (x < 0 || x >= proj.cols) return false;
    const t = proj.tiles[y * proj.cols + x];
    return t !== -1 && t !== AUTOTILE.WATER && t !== AUTOTILE.WATER_LOTUS;
  };

  for (let y = 0; y < proj.rows; y++) {
    for (let x = 0; x < proj.cols; x++) {
      const current = proj.tiles[y * proj.cols + x];
      if (current === -1 || current === AUTOTILE.WATER || current === AUTOTILE.WATER_LOTUS) continue;

      const top = isSolid(x, y - 1);
      const bottom = isSolid(x, y + 1);
      const left = isSolid(x - 1, y);
      const right = isSolid(x + 1, y);

      let tile = AUTOTILE.MID_WALL;

      if (!top) {
        // Hàng Đỉnh (Surface Top)
        if (!left && !right) tile = AUTOTILE.TOP_SINGLE;
        else if (!left) tile = AUTOTILE.TOP_LEFT;
        else if (!right) tile = AUTOTILE.TOP_RIGHT;
        else tile = AUTOTILE.TOP_MID;
      } else {
        // Hàng Thân / Vách đứng (Mid / Body)
        if (!bottom) {
          // Chân thềm
          if (!left) tile = AUTOTILE.BOTTOM_LEFT;
          else if (!right) tile = AUTOTILE.BOTTOM_RIGHT;
          else tile = AUTOTILE.BOTTOM_MID;
        } else {
          // Thân vách giữa
          if (!left) tile = AUTOTILE.MID_LEFT;
          else if (!right) tile = AUTOTILE.MID_RIGHT;
          else {
            // Sâu trong ruột
            tile = y % 2 === 0 ? AUTOTILE.MID_WALL : AUTOTILE.INNER_ROCK;
          }
        }
      }
      proj.tiles[y * proj.cols + x] = tile;
    }
  }
}

function loadAssets(onReady: () => void) {
  let loaded = 0;
  const total = 3 + PROPS_LIST.length;
  const check = () => {
    loaded++;
    if (loaded >= total) onReady();
  };

  atlasImage = new Image();
  atlasImage.onload = check;
  atlasImage.onerror = check;
  atlasImage.src = ATLAS_URL;

  skyImage = new Image();
  skyImage.onload = check;
  skyImage.onerror = check;
  skyImage.src = PARALLAX_SKY;

  forestImage = new Image();
  forestImage.onload = check;
  forestImage.onerror = check;
  forestImage.src = PARALLAX_FOREST;

  for (const p of PROPS_LIST) {
    const img = new Image();
    img.onload = check;
    img.onerror = check;
    img.src = p.src;
    propImages.set(p.id, img);
  }
}

function drawTileCell(ctx: CanvasRenderingContext2D, tileIndex: number, dx: number, dy: number, size: number) {
  if (tileIndex < 0 || !atlasImage?.complete || atlasImage.naturalWidth <= 0) return;
  const c = tileIndex % TILES_COLS;
  const r = Math.floor(tileIndex / TILES_COLS);
  const sx = c * 64;
  const sy = r * 64;
  ctx.drawImage(atlasImage, sx, sy, 64, 64, dx, dy, size, size);
}

function draw() {
  const canvas = $('mapCanvas') as HTMLCanvasElement | null;
  if (!canvas || !project || !canvas.closest('dialog')?.open) return;


  const cell = Math.max(16, Math.floor(project.tileSize * zoom));
  const pad = 40;
  const width = project.cols * cell + pad * 2;
  const height = project.rows * cell + pad * 2;

  canvas.width = width;
  canvas.height = height;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;

  const ctx = canvas.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  // 1. Draw Parallax Background
  if (project.showParallax && skyImage?.complete && skyImage.naturalWidth > 0 && forestImage?.complete && forestImage.naturalWidth > 0) {
    // Sky gradient base
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, '#3a5f82');
    grad.addColorStop(0.55, '#75a6c4');
    grad.addColorStop(1, '#a6cde2');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, width, height);

    // Far Sky & Clouds Layer
    ctx.drawImage(skyImage, 0, 0, skyImage.naturalWidth, skyImage.naturalHeight, 0, pad, width, height * 0.75);

    // Midground Mountain & Waterfall
    ctx.globalAlpha = 0.88;
    ctx.drawImage(forestImage, 0, 0, forestImage.naturalWidth, forestImage.naturalHeight, 0, pad + height * 0.15, width, height * 0.85);
    ctx.globalAlpha = 1.0;
  } else {
    ctx.fillStyle = '#181e26';
    ctx.fillRect(0, 0, width, height);
  }

  const originX = pad;
  const originY = pad;

  // 2. Draw Tiles
  for (let y = 0; y < project.rows; y++) {
    for (let x = 0; x < project.cols; x++) {
      const tileIndex = project.tiles[y * project.cols + x];
      if (tileIndex >= 0) {
        drawTileCell(ctx, tileIndex, originX + x * cell, originY + y * cell, cell);
      }
    }
  }

  // 3. Draw Placed Props
  for (const p of project.props) {
    const img = propImages.get(p.propKey);
    if (img && img.complete && img.naturalWidth > 0) {
      const px = originX + p.x * cell;
      const py = originY + p.y * cell;
      const pw = (p.width / DEFAULT_TILE_SIZE) * cell;
      const ph = (p.height / DEFAULT_TILE_SIZE) * cell;
      ctx.drawImage(img, px, py, pw, ph);
    }
  }

  // 4. Draw Grid Lines (if enabled)
  if (project.showGrid) {
    ctx.strokeStyle = '#ffffff24';
    ctx.lineWidth = 1;
    for (let x = 0; x <= project.cols; x++) {
      ctx.beginPath();
      ctx.moveTo(originX + x * cell + 0.5, originY);
      ctx.lineTo(originX + x * cell + 0.5, originY + project.rows * cell);
      ctx.stroke();
    }
    for (let y = 0; y <= project.rows; y++) {
      ctx.beginPath();
      ctx.moveTo(originX, originY + y * cell + 0.5);
      ctx.lineTo(originX + project.cols * cell, originY + y * cell + 0.5);
      ctx.stroke();
    }
  }

  // 5. Border Frame of Active Map Area
  ctx.strokeStyle = '#4e7596';
  ctx.lineWidth = 2;
  ctx.strokeRect(originX, originY, project.cols * cell, project.rows * cell);

  canvas.dataset.cell = String(cell);
  canvas.dataset.originX = String(originX);
  canvas.dataset.originY = String(originY);

  const sizeLabel = $('mapSizeLabel');
  if (sizeLabel) {
    sizeLabel.textContent = `${project.cols} × ${project.rows} ô · ${project.cols * 64} × ${project.rows * 64} px chuẩn`;
  }
}

function checkpoint() {
  undoStack.push({
    ...project,
    tiles: [...project.tiles],
    props: project.props.map(p => ({ ...p })),
    assets: project.assets?.map(a => ({ ...a }))
  });
  if (undoStack.length > 60) undoStack.shift();
  redoStack.length = 0;
  updateHistoryButtons();
}

function updateHistoryButtons() {
  const undo = $('mapUndo') as HTMLButtonElement | null;
  const redo = $('mapRedo') as HTMLButtonElement | null;
  if (undo) undo.disabled = !undoStack.length;
  if (redo) redo.disabled = !redoStack.length;
}

function history(redo = false) {
  const from = redo ? redoStack : undoStack;
  const to = redo ? undoStack : redoStack;
  const prior = from.pop();
  if (!prior) return;
  to.push({
    ...project,
    tiles: [...project.tiles],
    props: project.props.map(p => ({ ...p })),
    assets: project.assets?.map(a => ({ ...a }))
  });
  project = prior;
  syncCustomAssets();
  syncProjectControls();
  persist();
  draw();
  updateHistoryButtons();
}

function persist() {
  try {
    localStorage.setItem(PROJECT_KEY, JSON.stringify(project));
    const notice = $('mapLibraryNotice');
    if (notice) notice.textContent = '';
  } catch {
    const notice = $('mapLibraryNotice');
    if (notice) notice.textContent = 'Bộ nhớ trình duyệt đầy. Xuất Project JSON để lưu cả asset.';
  }
}

function fileSlug(value: string) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'celestial-map';
}

function download(name: string, blob: Blob) {
  const a = document.createElement('a');
  const url = URL.createObjectURL(blob);
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function paintAt(event: PointerEvent) {
  const canvas = $('mapCanvas') as HTMLCanvasElement;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const originX = Number(canvas.dataset.originX);
  const originY = Number(canvas.dataset.originY);
  const cell = Number(canvas.dataset.cell);

  const gridX = Math.floor(((event.clientX - rect.left) * scaleX - originX) / cell);
  const gridY = Math.floor(((event.clientY - rect.top) * scaleY - originY) / cell);

  if (gridY < 0 || gridY >= project.rows || gridX < 0 || gridX >= project.cols) return;

  const isEraser = brushMode === 'eraser' || event.button === 2;

  if (brushMode === 'prop' && !isEraser) {
    if (event.type === 'pointerdown') {
      const def = allProps().find(p => p.id === selectedPropKey);
      if (def) {
        const custom = project.assets?.find(a => a.id === def.id);
        const placement = custom ? assetPlacement(custom, gridX, gridY, project.tileSize) : {
          x: gridX, y: gridY - (def.h / DEFAULT_TILE_SIZE) + 1, width: def.w, height: def.h
        };
        project.props.push({
          id: `p_${Date.now()}`,
          propKey: def.id,
          ...placement
        });
        draw();
      }
    }
    return;
  }

  // Brush on tile layer
  const start = -Math.floor((brushSize - 1) / 2);
  for (let dy = start; dy < start + brushSize; dy++) {
    for (let dx = start; dx < start + brushSize; dx++) {
      const yy = gridY + dy;
      let xx = gridX + dx;
      if (yy < 0 || yy >= project.rows) continue;
      if (project.loopX) xx = (xx % project.cols + project.cols) % project.cols;
      if (xx < 0 || xx >= project.cols) continue;

      if (isEraser) {
        project.tiles[yy * project.cols + xx] = -1;
      } else if (brushMode === 'autofit') {
        project.tiles[yy * project.cols + xx] = AUTOTILE.TOP_MID; // Temporary mark
      } else {
        project.tiles[yy * project.cols + xx] = selectedTileIndex;
      }
    }
  }

  if (brushMode === 'autofit' && !isEraser) {
    recalculateAllAutotiles(project);
  }
  draw();
}

function exportMapPng() {
  if (project.props.some(p => { const im = propImages.get(p.propKey); return !im?.complete || im.naturalWidth === 0; })) {
    $('mapLibraryNotice').textContent = 'Có vật thể chưa tải được ảnh. Đợi tải xong trước khi xuất PNG.';
    return;
  }
  const size = project.tileSize;
  const out = document.createElement('canvas');
  out.width = project.cols * size;
  out.height = project.rows * size;
  const ctx = out.getContext('2d')!;
  ctx.imageSmoothingEnabled = false;

  // Background
  if (project.showParallax && skyImage?.complete && skyImage.naturalWidth > 0 && forestImage?.complete && forestImage.naturalWidth > 0) {
    ctx.drawImage(skyImage, 0, 0, skyImage.naturalWidth, skyImage.naturalHeight, 0, 0, out.width, out.height * 0.75);
    ctx.drawImage(forestImage, 0, 0, forestImage.naturalWidth, forestImage.naturalHeight, 0, out.height * 0.2, out.width, out.height * 0.8);
  }

  // Tiles
  for (let y = 0; y < project.rows; y++) {
    for (let x = 0; x < project.cols; x++) {
      const t = project.tiles[y * project.cols + x];
      if (t >= 0) drawTileCell(ctx, t, x * size, y * size, size);
    }
  }

  // Props
  for (const p of project.props) {
    const img = propImages.get(p.propKey);
    if (img && img.complete && img.naturalWidth > 0) {
      ctx.drawImage(img, p.x * size, p.y * size, (p.width / DEFAULT_TILE_SIZE) * size, (p.height / DEFAULT_TILE_SIZE) * size);
    }
  }

  out.toBlob(blob => blob && download(`${fileSlug(project.name)}.png`, blob), 'image/png');
}

const mapStudioCss = `
.celestial-map-studio {
  position: fixed; inset: 0; margin: auto;
  width: calc(100vw - 28px); height: calc(100dvh - 28px); max-width: 1750px;
  background: #0f131a; color: #e4eaf5;
  border: 1px solid #2d3848; border-radius: 12px;
  box-shadow: 0 25px 90px #000c; overflow: hidden;
  font: 13px Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  display: flex; flex-direction: column;
}
.celestial-map-studio::backdrop { background: #06090ebd; backdrop-filter: blur(8px); }
.celestial-map-studio:not([open]) { display: none; }
.celestial-heading {
  height: 58px; display: flex; align-items: center; justify-content: space-between;
  padding: 0 18px; background: #161c26; border-bottom: 1px solid #283344; flex-shrink: 0;
}
.celestial-brand { display: flex; align-items: center; gap: 12px; }
.celestial-logo {
  width: 36px; height: 36px; border-radius: 8px;
  background: linear-gradient(135deg, #497d5a, #2f5647);
  display: grid; place-items: center; font-size: 20px; color: #d7f5db;
  box-shadow: 0 4px 14px #264a3955;
}
.celestial-title h2 { font-size: 15px; font-weight: 700; margin: 0; color: #f1f5fa; }
.celestial-title small { font-size: 9px; letter-spacing: 1.5px; color: #8ba1b8; }
.celestial-top-actions { display: flex; gap: 8px; align-items: center; }
.celestial-btn {
  border: 1px solid #2d3849; background: #202836; color: #cdd7e5;
  padding: 7px 12px; border-radius: 6px; font-size: 11px; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px; transition: all .15s ease;
}
.celestial-btn:hover { background: #2b3648; border-color: #4b5f7d; color: #ffffff; }
.celestial-btn.primary { background: #47926b; border-color: #55ac7e; color: #fff; font-weight: 600; }
.celestial-btn.primary:hover { background: #52a67a; }
.celestial-close {
  background: transparent; border: none; color: #8ba1b8; font-size: 18px;
  width: 32px; height: 32px; border-radius: 6px; cursor: pointer; display: grid; place-items: center;
}
.celestial-close:hover { background: #242d3c; color: #fff; }

.celestial-body { display: flex; flex: 1; min-height: 0; }
.celestial-sidebar {
  width: 310px; flex: none; background: #131922; border-right: 1px solid #263140;
  display: flex; flex-direction: column; overflow: hidden;
}
.celestial-tabs { display: flex; border-bottom: 1px solid #263140; background: #10141c; }
.celestial-tab-btn {
  flex: 1; padding: 11px 8px; border: none; background: transparent;
  color: #8da1b5; font-size: 11px; font-weight: 600; cursor: pointer;
  border-bottom: 2px solid transparent;
}
.celestial-tab-btn.active { color: #5bc48f; border-bottom-color: #5bc48f; background: #151b24; }
.celestial-tab-content { flex: 1; overflow-y: auto; padding: 14px; }

.celestial-section-title {
  font-size: 10px; font-weight: 700; color: #8298b0; letter-spacing: 1.2px;
  text-transform: uppercase; margin: 14px 0 8px;
}
.celestial-mode-selector { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 12px; }
.celestial-mode-btn {
  border: 1px solid #2d3849; background: #1a222e; color: #bccadb;
  padding: 8px; border-radius: 6px; font-size: 11px; cursor: pointer;
  text-align: center; font-weight: 500;
}
.celestial-mode-btn.active { background: #2a4738; border-color: #55ac7e; color: #e9fbf2; font-weight: 700; }

.celestial-atlas-grid {
  display: grid; grid-template-columns: repeat(8, 1fr); gap: 2px;
  background: #090c10; padding: 5px; border-radius: 6px; border: 1px solid #222b38;
}
.celestial-tile-cell {
  aspect-ratio: 1; cursor: pointer; border: 1px solid transparent; border-radius: 3px;
  background-size: 800% 700%; image-rendering: pixelated;
}
.celestial-tile-cell:hover { border-color: #6edba4; transform: scale(1.1); z-index: 2; }
.celestial-tile-cell.selected { border-color: #58ea9c; box-shadow: 0 0 0 2px #58ea9c88; z-index: 3; }

.celestial-props-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.celestial-prop-card {
  border: 1px solid #273344; background: #1a222f; border-radius: 6px; padding: 8px;
  cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 6px;
  text-align: center;
}
.celestial-prop-card:hover { border-color: #517196; background: #202b3b; }
.celestial-prop-card.selected { border-color: #5bc48f; background: #223c31; }
.celestial-prop-card img { max-width: 100%; max-height: 52px; object-fit: contain; image-rendering: pixelated; }
.celestial-prop-card span { font-size: 10px; color: #d2dcee; font-weight: 500; }

.celestial-controls-group label {
  display: flex; justify-content: space-between; align-items: center;
  color: #9ab0c7; font-size: 11px; margin: 10px 0;
}
.celestial-controls-group input, .celestial-controls-group select {
  width: 90px; background: #0e1218; border: 1px solid #2b3648;
  border-radius: 5px; padding: 4px 8px; color: #e4eaf5; font: inherit;
}
.celestial-check { display: flex !important; justify-content: flex-start !important; gap: 8px; cursor: pointer; }
.celestial-check input { width: auto; accent-color: #5bc48f; }

.celestial-center { flex: 1; display: flex; flex-direction: column; min-width: 0; background: #0c0f14; }
.celestial-topbar {
  min-height: 44px; display: flex; align-items: center; gap: 8px;
  padding: 6px 14px; background: #141a24; border-bottom: 1px solid #252f3e;
}
.celestial-map-name {
  width: min(300px, 35%); height: 30px; background: #0c1016; color: #e6edf7;
  border: 1px solid #293444; border-radius: 6px; padding: 4px 9px; font-weight: 600;
}
.celestial-spacer { flex: 1; }
.celestial-canvas-wrap {
  flex: 1; min-height: 0; overflow: auto; display: flex; align-items: center; justify-content: center;
  padding: 30px; background: radial-gradient(circle at center, #1b2432 0%, #0d1117 80%);
}
#mapCanvas {
  image-rendering: pixelated; box-shadow: 0 16px 48px #000c;
  cursor: crosshair; touch-action: none;
}
.celestial-statusbar {
  min-height: 32px; display: flex; align-items: center; gap: 16px;
  padding: 0 16px; background: #121720; border-top: 1px solid #252f3e;
  color: #7d93ab; font-size: 11px;
}
.celestial-statusbar strong { color: #8de3b5; font-weight: 600; }
`;

export function setupMapStudio() {
  const header = document.querySelector('header');
  if (!header) return;

  const style = document.createElement('style');
  style.textContent = mapStudioCss;
  document.head.append(style);

  // Replace or attach trigger button
  const oldBtn = document.querySelector('#openMapStudio');
  if (oldBtn) oldBtn.remove();

  const nav = document.createElement('button');
  nav.id = 'openMapStudio';
  nav.className = 'map-launch';
  nav.innerHTML = '<span aria-hidden="true">🎋</span> Xưởng map Tiên Cảnh';
  nav.title = 'Mở Xưởng Map Tiên Cảnh 64x64 (Alt+M)';
  document.querySelector('.project-actions')?.before(nav);

  // Remove old dialog if exists
  const oldDialog = document.querySelector('#mapStudio');
  if (oldDialog) oldDialog.remove();

  const root = document.createElement('dialog');
  root.id = 'mapStudio';
  root.className = 'celestial-map-studio';
  root.setAttribute('aria-labelledby', 'celestialMapTitle');

  root.innerHTML = `
    <div class="celestial-heading">
      <div class="celestial-brand">
        <div class="celestial-logo">🎋</div>
        <div class="celestial-title">
          <small>HKT / CELESTIAL ASSET ENGINE</small>
          <h2 id="celestialMapTitle">Xưởng Map Tiên Cảnh 64×64</h2>
        </div>
      </div>
      <div class="celestial-top-actions">
        <button id="mapOpenAssets" class="celestial-btn primary">✦ Tách & làm sạch asset</button>
        <button id="mapExportJson" class="celestial-btn">↓ Project JSON</button>
        <label class="celestial-btn" style="cursor:pointer">↑ Mở JSON<input id="mapImport" type="file" accept="application/json" hidden></label>
        <button id="mapExportPng" class="celestial-btn primary">↓ Xuất ảnh Map PNG</button>
        <button id="mapClose" class="celestial-close" aria-label="Đóng">✕</button>
      </div>
    </div>

    <div class="celestial-body">
      <aside class="celestial-sidebar">
        <div class="celestial-tabs">
          <button class="celestial-tab-btn active" data-tab="terrain">🎨 Địa hình</button>
          <button class="celestial-tab-btn" data-tab="props">⛩ Vật thể</button>
          <button class="celestial-tab-btn" data-tab="settings">⚙ Cài đặt</button>
        </div>

        <!-- Tab 1: Terrain & Autotile -->
        <div id="tabTerrain" class="celestial-tab-content">
          <div class="celestial-section-title">Chế độ cọ vẽ</div>
          <div class="celestial-mode-selector">
            <button id="modeAutofit" class="celestial-mode-btn active">⚡ Tự động ráp</button>
            <button id="modeManual" class="celestial-mode-btn">🖌 Chọn ô tự do</button>
          </div>

          <div id="autofitInfo" style="padding:10px; background:#182330; border-radius:6px; font-size:11px; line-height:1.6; color:#9cbcd8; margin-bottom:12px;">
            <b style="color:#7ee4b2">Chế độ Tự Động Ráp:</b> Quét chuột vẽ đảo hoặc vách, hệ thống sẽ <b>tự động khớp</b> cỏ đỉnh, vách đứng đập vào màn hình, mép trái và mép phải.
          </div>

          <div class="celestial-section-title">Bảng 56 ô Tile chuẩn (64×64)</div>
          <div class="celestial-atlas-grid" id="atlasGrid" title="Bấm vào ô để vẽ chính xác ô đó"></div>

          <div class="celestial-section-title">Công cụ</div>
          <div class="celestial-mode-selector">
            <button id="toolEraser" class="celestial-mode-btn">🧹 Tẩy (Xóa)</button>
            <button id="clearAllProps" class="celestial-mode-btn">❌ Xóa vật thể</button>
          </div>
        </div>

        <!-- Tab 2: Props -->
        <div id="tabProps" class="celestial-tab-content" style="display:none;">
          <div class="celestial-section-title">Thư viện vật thể trong suốt</div>
          <button id="mapCleanSelected" class="celestial-btn" style="width:100%;margin-bottom:10px">Làm sạch vật thể đang chọn</button>
          <p style="font-size:11px; color:#8ea2b8; margin:0 0 10px;">Chọn vật thể rồi bấm chuột lên canvas để đặt vào vị trí mong muốn:</p>
          <div class="celestial-props-grid" id="propsGrid"></div>
        </div>

        <!-- Tab 3: Settings -->
        <div id="tabSettings" class="celestial-tab-content" style="display:none;">
          <div class="celestial-section-title">Thông số bản đồ</div>
          <div class="celestial-controls-group">
            <label>Cỡ cọ vẽ<select id="mapBrush"><option value="1">1 ô</option><option value="2">2 × 2 ô</option><option value="3">3 × 3 ô</option></select></label>
            <label>Số cột<input id="mapCols" type="number" min="8" max="64" value="28"></label>
            <label>Số hàng<input id="mapRows" type="number" min="8" max="32" value="14"></label>
            <label class="celestial-check"><input id="mapLoop" type="checkbox" checked> Lặp ngang liền mạch (Loop X)</label>
            <label class="celestial-check"><input id="mapShowGrid" type="checkbox"> Hiện lưới ô (Grid)</label>
            <label class="celestial-check"><input id="mapShowParallax" type="checkbox" checked> Hiện cảnh nền Parallax</label>
          </div>
          <button id="mapReset" class="celestial-btn" style="width:100%; margin-top:14px; justify-content:center;">Tạo bản đồ mới rỗng</button>
        </div>
      </aside>

      <div class="celestial-center">
        <div class="celestial-topbar">
          <input id="mapName" class="celestial-map-name" aria-label="Tên bản đồ" value="Rừng Trúc Tiên Cảnh · Sơn Thạch 64×64">
          <span class="celestial-spacer"></span>
          <button id="mapUndo" class="celestial-btn" title="Hoàn tác (Ctrl+Z)" disabled>↶ Hoàn tác</button>
          <button id="mapRedo" class="celestial-btn" title="Làm lại (Ctrl+Y)" disabled>↷ Làm lại</button>
          <button id="mapZoomOut" class="celestial-btn">−</button>
          <button id="mapZoomLabel" class="celestial-btn">85%</button>
          <button id="mapZoomIn" class="celestial-btn">+</button>
        </div>

        <div class="celestial-canvas-wrap">
          <canvas id="mapCanvas" aria-label="Bản đồ 64x64 pixel"></canvas>
        </div>

        <div class="celestial-statusbar">
          <strong id="mapSizeLabel">28 × 14 ô · 1792 × 896 px</strong>
          <span id="mapLibraryNotice" role="status" style="color:#ffd79b"></span>
          <span>Chuẩn ô 64×64 px nguyên bản</span>
          <span>Khử phông trong suốt (RGBA)</span>
          <span class="celestial-spacer"></span>
          <span>Chuột trái: Vẽ · Chuột phải: Tẩy</span>
        </div>
      </div>
    </div>
  `;

  document.body.append(root);

  project = blankProject();

  const assetWorkbench = setupMapAssets(async assets => {
    const next = parseMapAssets([...(project.assets || []), ...assets]);
    const loaded = await Promise.all(assets.map(a => new Promise<HTMLImageElement>((resolve,reject) => {
      const img = new Image();
      img.onload = () => img.width === a.w && img.height === a.h ? resolve(img) : reject(new Error('Kích thước asset không khớp PNG.'));
      img.onerror = () => reject(new Error('Không đọc được asset đã xử lý.'));
      img.src = a.src;
    })));
    checkpoint();
    project.assets = next;
    assets.forEach((a,i) => propImages.set(a.id,loaded[i]!));
    selectedPropKey = assets[0]!.id;
    brushMode = 'prop';
    renderPropLibrary(); updateModeButtons(); persist();
    root.querySelector<HTMLButtonElement>('[data-tab="props"]')?.click();
    draw();
  });
  $('mapOpenAssets').addEventListener('click', () => void assetWorkbench.open());
  $('mapCleanSelected').addEventListener('click', () => {
    const prop = allProps().find(a => a.id === selectedPropKey);
    if (prop) void assetWorkbench.open({name:prop.name,src:prop.src});
  });

  // Populate 56 tiles in sidebar
  const atlasGrid = $('atlasGrid');
  if (atlasGrid) {
    atlasGrid.innerHTML = Array.from({ length: 56 }, (_, i) => {
      const c = i % TILES_COLS;
      const r = Math.floor(i / TILES_COLS);
      const px = (c / (TILES_COLS - 1)) * 100;
      const py = (r / (TILES_ROWS - 1)) * 100;
      return `<div class="celestial-tile-cell ${i === selectedTileIndex ? 'selected' : ''}" data-tile="${i}" style="background-image:url('${ATLAS_URL}'); background-position:${px}% ${py}%;"></div>`;
    }).join('');

    atlasGrid.addEventListener('click', e => {
      const cell = (e.target as HTMLElement).closest<HTMLElement>('[data-tile]');
      if (!cell) return;
      selectedTileIndex = Number(cell.dataset.tile);
      brushMode = 'manual';
      updateModeButtons();
      atlasGrid.querySelectorAll('.celestial-tile-cell').forEach(el => el.classList.toggle('selected', el === cell));
    });
  }

  // Populate Props
  const propsGrid = $('propsGrid');
  if (propsGrid) {
    renderPropLibrary();

    propsGrid.addEventListener('click', e => {
      const card = (e.target as HTMLElement).closest<HTMLElement>('[data-prop]');
      if (!card) return;
      selectedPropKey = card.dataset.prop!;
      brushMode = 'prop';
      propsGrid.querySelectorAll('.celestial-prop-card').forEach(el => el.classList.toggle('selected', el === card));
      updateModeButtons();
    });
  }

  function updateModeButtons() {
    $('modeAutofit')?.classList.toggle('active', brushMode === 'autofit');
    $('modeManual')?.classList.toggle('active', brushMode === 'manual');
    $('toolEraser')?.classList.toggle('active', brushMode === 'eraser');
    const info = $('autofitInfo');
    if (info) info.style.display = brushMode === 'autofit' ? 'block' : 'none';
  }

  // Tabs
  root.querySelectorAll('.celestial-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      root.querySelectorAll('.celestial-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = (btn as HTMLElement).dataset.tab;
      $('tabTerrain')!.style.display = tab === 'terrain' ? 'block' : 'none';
      $('tabProps')!.style.display = tab === 'props' ? 'block' : 'none';
      $('tabSettings')!.style.display = tab === 'settings' ? 'block' : 'none';
    });
  });

  $('modeAutofit')?.addEventListener('click', () => {
    brushMode = 'autofit';
    updateModeButtons();
  });

  $('modeManual')?.addEventListener('click', () => {
    brushMode = 'manual';
    updateModeButtons();
  });

  $('toolEraser')?.addEventListener('click', () => {
    brushMode = brushMode === 'eraser' ? 'autofit' : 'eraser';
    updateModeButtons();
  });

  $('clearAllProps')?.addEventListener('click', () => {
    checkpoint();
    project.props = [];
    persist();
    draw();
  });

  // Controls
  $('mapBrush')?.addEventListener('change', e => {
    brushSize = Number((e.target as HTMLSelectElement).value) || 1;
  });

  for (const id of ['mapCols', 'mapRows']) {
    $(id)?.addEventListener('change', () => {
      const cols = Math.max(8, Math.min(64, Number(($('mapCols') as HTMLInputElement).value) || project.cols));
      const rows = Math.max(8, Math.min(32, Number(($('mapRows') as HTMLInputElement).value) || project.rows));
      const old = project;
      const nextTiles = Array.from({ length: cols * rows }, (_, i) => {
        const x = i % cols;
        const y = Math.floor(i / cols);
        return (x < old.cols && y < old.rows) ? old.tiles[y * old.cols + x]! : -1;
      });
      checkpoint();
      project = { ...project, cols, rows, tiles: nextTiles };
      persist();
      draw();
    });
  }

  $('mapLoop')?.addEventListener('change', e => {
    project.loopX = (e.target as HTMLInputElement).checked;
    persist();
    draw();
  });

  $('mapShowGrid')?.addEventListener('change', e => {
    project.showGrid = (e.target as HTMLInputElement).checked;
    persist();
    draw();
  });

  $('mapShowParallax')?.addEventListener('change', e => {
    project.showParallax = (e.target as HTMLInputElement).checked;
    persist();
    draw();
  });

  $('mapReset')?.addEventListener('click', () => {
    checkpoint();
    project = {...blankProject(project.cols, project.rows, false), assets: project.assets};
    syncProjectControls();
    persist();
    draw();
  });

  // Canvas pointer events
  const canvas = $('mapCanvas') as HTMLCanvasElement;
  canvas.addEventListener('pointerdown', e => {
    drawing = true;
    checkpoint();
    canvas.setPointerCapture(e.pointerId);
    paintAt(e);
  });

  canvas.addEventListener('pointermove', e => {
    if (drawing) paintAt(e);
  });

  const stopDraw = () => {
    if (drawing) {
      drawing = false;
      persist();
      updateHistoryButtons();
    }
  };
  canvas.addEventListener('pointerup', stopDraw);
  canvas.addEventListener('pointercancel', stopDraw);
  window.addEventListener('pointerup', stopDraw);
  canvas.addEventListener('contextmenu', e => e.preventDefault());

  // Zoom
  $('mapZoomOut')?.addEventListener('click', () => {
    zoom = Math.max(0.4, zoom - 0.1);
    $('mapZoomLabel')!.textContent = `${Math.round(zoom * 100)}%`;
    draw();
  });
  $('mapZoomIn')?.addEventListener('click', () => {
    zoom = Math.min(1.8, zoom + 0.1);
    $('mapZoomLabel')!.textContent = `${Math.round(zoom * 100)}%`;
    draw();
  });

  // Undo / Redo
  $('mapUndo')?.addEventListener('click', () => history(false));
  $('mapRedo')?.addEventListener('click', () => history(true));

  // Export
  $('mapExportPng')?.addEventListener('click', exportMapPng);
  $('mapExportJson')?.addEventListener('click', () => {
    download(`${fileSlug(project.name)}.json`, new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' }));
  });

  $('mapImport')?.addEventListener('change', async e => {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const data = readMapProject(JSON.parse(await file.text()));
      if (data) {
        checkpoint();
        project = data;
        syncCustomAssets();
        syncProjectControls();
        ($('mapName') as HTMLInputElement).value = project.name;
        ($('mapCols') as HTMLInputElement).value = String(project.cols);
        ($('mapRows') as HTMLInputElement).value = String(project.rows);
        persist();
        draw();
      }
    } catch {
      alert('File project JSON không hợp lệ.');
    } finally {
      input.value = '';
    }
  });

  $('mapName')?.addEventListener('input', e => {
    project.name = (e.target as HTMLInputElement).value || 'Bản đồ Tiên Cảnh';
    persist();
  });

  // Dialog open/close
  $('mapClose')?.addEventListener('click', () => root.close());
  root.addEventListener('click', e => {
    if (e.target === root) root.close();
  });

  nav.addEventListener('click', () => {
    if (!root.open) root.showModal();
    persist();
    requestAnimationFrame(draw);
  });

  window.addEventListener('keydown', e => {
    if (!root.open) {
      if (e.altKey && e.key.toLowerCase() === 'm' && !document.querySelector('dialog:modal')) {
        e.preventDefault();
        nav.click();
      }
      return;
    }
    if (assetWorkbench.isOpen()) return;
    if (e.key === 'Escape') return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      history(e.shiftKey);
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
      e.preventDefault();
      history(true);
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      exportMapPng();
    }
  });

  // Load assets and initial draw
  loadAssets(() => {
    try {
      const saved = localStorage.getItem(PROJECT_KEY);
      if (saved) {
        project = readMapProject(JSON.parse(saved));
        syncCustomAssets();
        syncProjectControls();
      }
    } catch { /* use default */ }
    draw();
  });
}
