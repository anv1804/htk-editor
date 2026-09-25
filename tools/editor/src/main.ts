import './style.css';
import { state, corrections, correctionContext, baseMap, baseMapContext, paintLayer, paintContext, profileState, storageKey, setProfileState } from './state';
import { $, status, readFile, loadImage, download } from './utils';
import { doRepair, ensureProfile } from './api';
import { settings, grid, render, checkpoint, remember, invalidate, clearResult, point, dab, stroke, setStroke, getEffectiveBrush, setActiveTool, toggleProfileTarget, currentActiveTool, profileTarget, applyZoom, showTab, currentZoom, doUndo, doRedo, panState, updateContentTransform, toggleSymmetry, togglePixelGrid, toggleOnionSkin, toggleCanvasBackground, fitViewToScreen } from './editor';
import { renderAnimationTimeline, updateFrameThumbnails, togglePlayPause, isPlaying, stopPlaybackLoop, startPlaybackLoop } from './timeline';
import { initSplitter, saveLayout, restoreLayout } from './layout';

// Setup render hook for thumbnails
(window as any).__onRender = () => { updateFrameThumbnails(); };

async function setSource(kind: "base" | "outfit", url: string) {
  if (!url.startsWith("data:")) {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Không tải được ảnh.");
    url = await readFile(await response.blob() as File);
  }
  const img = await loadImage(url);
  if (img.width * img.height > 4194304) throw new Error("Ảnh vượt quá 4 triệu pixel.");
  
  if (kind === "base") { state.base = img; } else { state.outfit = img; }
  
  ($(`${kind}Preview`) as HTMLImageElement).src = url;
  $(`${kind}Drop`).classList.add("loaded");
  $(`${kind}Meta`).textContent = `${img.width} × ${img.height}`;
  
  const reference = state.base || img;
  corrections.width = reference.width;
  corrections.height = reference.height;
  paintLayer.width = reference.width; 
  paintLayer.height = reference.height;
  
  if (kind === "base") {
    baseMap.width = reference.width; 
    baseMap.height = reference.height;
    setProfileState(null, null, null);
  }
  
  state.undo = [];
  state.redo = [];
  clearResult();
  render();
}

let brushHudTimeout: number | null = null;
export function showBrushSizeHUD(size: number) {
  const hud = $("brushSizeHUD");
  if (!hud) return;
  const tool = currentActiveTool;
  const icon = tool === "erase" ? "🧹" : tool === "base" ? "👤" : tool === "outfit" ? "👕" : tool === "headwear" ? "👑" : "🖌️";
  hud.textContent = `${icon} Cỡ cọ: ${size}px`;
  hud.classList.add("visible");
  if (brushHudTimeout) clearTimeout(brushHudTimeout);
  brushHudTimeout = window.setTimeout(() => {
    hud.classList.remove("visible");
  }, 1000);
}

export function updatePixelCursorBox(e: MouseEvent | PointerEvent) {
  const box = $("pixelCursorBox");
  if (!box) return;
  const targetCanvas = (e.target as HTMLElement).closest("canvas") as HTMLCanvasElement;
  if (!targetCanvas || currentActiveTool === "inspect" || isPanning) {
    box.style.display = "none";
    document.body.classList.remove("tool-brush-active");
    return;
  }
  document.body.classList.add("tool-brush-active");
  const g = grid();
  if (!g) return;
  const rect = targetCanvas.getBoundingClientRect();
  const p = point(e as PointerEvent, targetCanvas);
  const size = Number(($("brushSize") as HTMLInputElement)?.value) || 1;
  const half = Math.floor(size / 2);
  const x = Math.max(0, p.x - half);
  const y = Math.max(0, p.y - half);
  const w = Math.min(g.w, p.x + half + 1) - x;
  const h = Math.min(g.h, p.y + half + 1) - y;

  const scaleX = rect.width / g.w;
  const scaleY = rect.height / g.h;
  const boxX = rect.left + x * scaleX;
  const boxY = rect.top + y * scaleY;
  const boxW = w * scaleX;
  const boxH = h * scaleY;

  box.style.display = "block";
  box.style.left = `${boxX}px`;
  box.style.top = `${boxY}px`;
  box.style.width = `${boxW}px`;
  box.style.height = `${boxH}px`;

  // Tint matching tool
  if (currentActiveTool === "color") {
    const color = ($("paintColor") as HTMLInputElement)?.value || "#90b9bb";
    box.style.backgroundColor = `${color}44`;
    box.style.borderColor = color;
  } else if (currentActiveTool === "erase") {
    box.style.backgroundColor = "rgba(255, 60, 60, 0.25)";
    box.style.borderColor = "#ff4444";
  } else if (currentActiveTool === "base") {
    box.style.backgroundColor = "rgba(255, 0, 0, 0.25)";
    box.style.borderColor = "#ff0000";
  } else if (currentActiveTool === "outfit") {
    box.style.backgroundColor = "rgba(0, 100, 255, 0.25)";
    box.style.borderColor = "#0088ff";
  } else if (currentActiveTool === "headwear") {
    box.style.backgroundColor = "rgba(255, 200, 0, 0.25)";
    box.style.borderColor = "#ffcc00";
  } else {
    box.style.backgroundColor = "rgba(67, 209, 123, 0.2)";
    box.style.borderColor = "#43d17b";
  }

  // Update live coordinates & color HUD
  const coordBadge = $("coordBadge");
  const coordHexBadge = $("coordHexBadge");
  if (coordBadge) coordBadge.textContent = `X: ${p.x}, Y: ${p.y}`;
  if (coordHexBadge) {
    try {
      const ctx = targetCanvas.getContext("2d");
      if (ctx) {
        const pixel = ctx.getImageData(p.x, p.y, 1, 1).data;
        if (pixel[3] > 0) {
          const hex = '#' + [...pixel.slice(0, 3)].map(c => c.toString(16).padStart(2, '0')).join('');
          coordHexBadge.textContent = hex;
          coordHexBadge.style.color = hex;
        } else {
          coordHexBadge.textContent = "trong suốt";
          coordHexBadge.style.color = "#9da5ae";
        }
      }
    } catch(_) {}
  }
}

// Pan and Interaction State
let isSpacePressed = false;
let isPanning = false;
let panStartMouseX = 0, panStartMouseY = 0;
let panStartPanX = 0, panStartPanY = 0;
let activePanTab: "inspector" | "sheet" = "inspector";
let didPanMove = false;

function startPan(e: MouseEvent | PointerEvent, tabName?: "inspector" | "sheet") {
  const isSheet = tabName === "sheet" || !$("sheetTab")?.classList.contains("hidden");
  activePanTab = isSheet ? "sheet" : "inspector";
  isPanning = true;
  didPanMove = false;
  panStartMouseX = e.clientX;
  panStartMouseY = e.clientY;
  panStartPanX = panState[activePanTab].x;
  panStartPanY = panState[activePanTab].y;

  const container = $(activePanTab === "sheet" ? "sheetTab" : "inspectorTab");
  if (container) container.classList.add("panning");
  document.body.classList.add("is-panning");
}

// Drawing events
for (const canvasId of ["baseCanvas", "outfitCanvas", "editCanvas"]) {
  const canvas = $(canvasId) as HTMLCanvasElement;
  if (!canvas) continue;
  
  canvas.addEventListener("dragstart", (e) => e.preventDefault());
  canvas.addEventListener("contextmenu", (e) => e.preventDefault());

  canvas.addEventListener("pointerdown", (event) => {
    // Nếu bấm chuột giữa (1), chuột phải (2), giữ Space hoặc đang ở công cụ Inspect: Bắt đầu Pan
    if (event.button === 1 || event.button === 2 || (event.button === 0 && isSpacePressed) || currentActiveTool === "inspect") {
      event.preventDefault();
      startPan(event, "inspector");
      return;
    }
    if (event.button !== 0) return;
    const nativeBrushSelect = $("brush") as HTMLSelectElement;
    if (nativeBrushSelect) {
      const isBase = canvas.id === "baseCanvas";
      if (isBase && profileTarget) {
        nativeBrushSelect.value = getEffectiveBrush(currentActiveTool, event.shiftKey);
      } else {
        nativeBrushSelect.value = currentActiveTool;
      }
    }
  }, true);

  canvas.addEventListener("pointerdown", event => {
    const g = grid();
    const mode = ($("brush") as HTMLSelectElement).value;
    const isProfile = mode.startsWith("profile");
    if (isPanning || !g || !state.base || state.busy || mode === "inspect" || event.button !== 0 || isSpacePressed) return;
    if (isProfile && canvas.id !== "baseCanvas") return status("Tô trên khung base để sửa đầu/tay.");
    if (!isProfile && canvas.id === "baseCanvas") return status("Tô trên khung outfit hoặc kết quả để chỉnh lớp ghép.");
    if (isProfile && !profileState.key) return status("Bấm Nhận diện lại base trước khi sửa bản đồ.");
    if (!isProfile && !state.outfit) return;
    
    const p = point(event, canvas);
    if (mode === "sample") {
      const sample = document.createElement("canvas"); sample.width = g.w; sample.height = g.h;
      const ctx = sample.getContext("2d")!;
      if (canvas.id === "baseCanvas" && state.base) {
        ctx.drawImage(state.base, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
      } else if (canvas.id === "outfitCanvas" && state.outfit) {
        ctx.drawImage(state.outfit, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
      } else {
        ctx.drawImage(state.result || state.outfit!, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
        ctx.drawImage(paintLayer, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
      }
      const rgb = ctx.getImageData(p.x, p.y, 1, 1).data;
      const hex = '#' + [...rgb].slice(0, 3).map(n => n.toString(16).padStart(2, '0')).join('');
      ($("paintColor") as HTMLInputElement).value = hex;
      const swatch = $("colorSwatchPreview");
      if (swatch) swatch.style.backgroundColor = hex;
      const paletteCode = $("paletteColorCode");
      if (paletteCode) paletteCode.textContent = hex;
      ($("brush") as HTMLSelectElement).value = "color"; 
      setActiveTool("color");
      render(); return;
    }
    
    const layer = isProfile ? baseMap : ["color", "unpaint"].includes(mode) ? paintLayer : corrections;
    const extraLayers = isProfile ? [] : [corrections, paintLayer].filter(l => l !== layer);
    checkpoint(layer, g, extraLayers);
    setStroke({ point: p, grid: g, canvas, mode });
    canvas.setPointerCapture(event.pointerId);
    dab(stroke!.point, g, mode);
    invalidate("Vùng chỉnh đã đổi. Bấm Xử lý sprite để áp dụng.");
    render();
  });
  
  canvas.addEventListener("pointermove", event => {
    if (isPanning) return;
    updatePixelCursorBox(event);
    if (!stroke || stroke.canvas !== canvas) return;
    const next = point(event, canvas), previous = stroke.point;
    const steps = Math.max(Math.abs(next.x - previous.x), Math.abs(next.y - previous.y), 1);
    for (let i = 1; i <= steps; i++) {
      dab({ 
        x: Math.round(previous.x + (next.x - previous.x) * i / steps),
        y: Math.round(previous.y + (next.y - previous.y) * i / steps) 
      }, stroke.grid, stroke.mode);
    }
    stroke.point = next;
    render();
  });

  canvas.addEventListener("pointerenter", (event) => {
    if (!isPanning) updatePixelCursorBox(event);
  });

  canvas.addEventListener("pointerleave", () => {
    const box = $("pixelCursorBox");
    if (box) box.style.display = "none";
    document.body.classList.remove("tool-brush-active");
    const coordBadge = $("coordBadge");
    if (coordBadge) coordBadge.textContent = "X: --, Y: --";
    const coordHexBadge = $("coordHexBadge");
    if (coordHexBadge) { coordHexBadge.textContent = "#------"; coordHexBadge.style.color = "#9da5ae"; }
  });
  
  for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) {
    canvas.addEventListener(name, () => {
      if (stroke) { setStroke(null); remember(); }
    });
  }
}

// File drop setups
for (const kind of ["base", "outfit"]) {
  const accept = async (file: File) => {
    if (!file || state.busy) return;
    try { await setSource(kind as "base" | "outfit", await readFile(file)); remember(); }
    catch (error: any) { status(error.message, true); }
  };
  const fileInput = $(`${kind}File`) as HTMLInputElement;
  if (fileInput) fileInput.addEventListener("change", (event: any) => accept(event.target.files[0]));
  const drop = $(`${kind}Drop`);
  if (drop) {
    drop.addEventListener("dragover", event => { event.preventDefault(); drop.classList.add("drag"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
    drop.addEventListener("drop", (event: DragEvent) => { event.preventDefault(); drop.classList.remove("drag"); accept(event.dataTransfer!.files[0]); });
    drop.addEventListener("keydown", event => { if (event.key === "Enter") fileInput.click(); });
  }
}

for (const id of settings) {
  const el = $(id);
  if (el) el.addEventListener("change", () => { invalidate(); render(); remember(); });
}
for (const id of ["frame", "zoom", "sheetZoom", "showMask", "brush", "showProfile", "maskOpacity"]) {
  const el = $(id);
  if (el) el.addEventListener("change", render);
}
const maskOpacityEl = $("maskOpacity");
if (maskOpacityEl) maskOpacityEl.addEventListener("input", render);

const frameEl = $("frame") as HTMLInputElement;
if (frameEl) {
  frameEl.addEventListener("input", () => {
    const value = Number(frameEl.value);
    if (Number.isInteger(value) && value >= 1 && value <= (grid()?.count || 1)) render();
  });
  frameEl.addEventListener("input", renderAnimationTimeline);
  frameEl.addEventListener("change", renderAnimationTimeline);
}

const prevEl = $("prev");
if (prevEl) {
  prevEl.onclick = () => { 
    frameEl.value = Math.max(1, Number(frameEl.value) - 1).toString(); 
    render(); 
    setTimeout(renderAnimationTimeline, 20);
  };
}
const nextEl = $("next");
if (nextEl) {
  nextEl.onclick = () => { 
    frameEl.value = Math.min(grid()?.count || 1, Number(frameEl.value) + 1).toString(); 
    render(); 
    setTimeout(renderAnimationTimeline, 20);
  };
}

const undoEl = $("undo");
if (undoEl) undoEl.onclick = () => doUndo();

const redoEl = $("redo");
if (redoEl) redoEl.onclick = () => doRedo();

const clearFrameEl = $("clearFrame");
if (clearFrameEl) clearFrameEl.onclick = () => {
  const g = grid();
  if (!g || state.busy) return;
  checkpoint(corrections, g, [paintLayer]); 
  correctionContext.clearRect(g.x, g.y, g.w, g.h); 
  paintContext.clearRect(g.x, g.y, g.w, g.h);
  invalidate("Đã xóa toàn bộ vùng sửa của frame này."); render(); remember();
};

const saveMaskEl = $("saveMask");
if (saveMaskEl) saveMaskEl.onclick = () => { if (state.base) download(corrections.toDataURL(), "outfit-corrections.png"); };

const loadMaskEl = $("loadMask") as HTMLInputElement;
if (loadMaskEl) loadMaskEl.onchange = async (event: any) => {
  const file = event.target.files[0];
  if (!file || !state.base || state.busy) return;
  try {
    const img = await loadImage(await readFile(file));
    if (img.width !== corrections.width || img.height !== corrections.height) throw new Error("Vùng chỉnh phải có cùng kích thước với base.");
    checkpoint(); correctionContext.clearRect(0, 0, corrections.width, corrections.height);
    correctionContext.drawImage(img, 0, 0); invalidate(); render(); remember();
  } catch (error: any) { status(error.message, true); }
  event.target.value = "";
};

const analyzeBaseEl = $("analyzeBase");
if (analyzeBaseEl) analyzeBaseEl.onclick = async () => {
  if (state.busy) return;
  state.busy = true;
  try { 
    await ensureProfile(true); 
    ($("showProfile") as HTMLInputElement).checked = true; 
    invalidate("Đã nhận diện đầu/tay từ base. Có thể tô sửa trên khung base."); 
    remember(); 
  }
  catch (error: any) { status(error.message, true); }
  finally { state.busy = false; render(); }
};

const saveProfileEl = $("saveProfile");
if (saveProfileEl) saveProfileEl.onclick = async () => {
  try {
    await ensureProfile();
    const g = grid();
    if (!g) return;
    const documentData = { version: 1, baseId: profileState.key, rows: g.rows, cols: g.cols, mask: baseMap.toDataURL() };
    const url = URL.createObjectURL(new Blob([JSON.stringify(documentData)], { type: "application/json" }));
    download(url, "base-anatomy.json"); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error: any) { status(error.message, true); }
};

const loadProfileEl = $("loadProfile") as HTMLInputElement;
if (loadProfileEl) loadProfileEl.onchange = async (event: any) => {
  const file = event.target.files[0];
  if (!file || state.busy) return;
  try {
    await ensureProfile();
    const data = JSON.parse(await file.text());
    if (data.version !== 1 || data.baseId !== profileState.key) throw new Error("Bản đồ không thuộc base và grid đang chọn.");
    const img = await loadImage(data.mask);
    if (img.width !== baseMap.width || img.height !== baseMap.height) throw new Error("Bản đồ sai kích thước.");
    checkpoint(baseMap); baseMapContext.clearRect(0, 0, baseMap.width, baseMap.height);
    baseMapContext.drawImage(img, 0, 0); ($("showProfile") as HTMLInputElement).checked = true;
    invalidate(); render(); remember();
  } catch (error: any) { status(error.message, true); }
  event.target.value = "";
};

const savePaintEl = $("savePaint");
if (savePaintEl) savePaintEl.onclick = () => { if (state.base) download(paintLayer.toDataURL(), "outfit-retouch.png"); };

const loadPaintEl = $("loadPaint") as HTMLInputElement;
if (loadPaintEl) loadPaintEl.onchange = async (event: any) => {
  const file = event.target.files[0];
  if (!file || !state.base || state.busy) return;
  try {
    const img = await loadImage(await readFile(file));
    if (img.width !== paintLayer.width || img.height !== paintLayer.height) throw new Error("Lớp màu phải cùng kích thước base.");
    checkpoint(paintLayer); paintContext.clearRect(0, 0, paintLayer.width, paintLayer.height);
    paintContext.drawImage(img, 0, 0); invalidate(); render(); remember();
  } catch (error: any) { status(error.message, true); }
  event.target.value = "";
};

const repairEl = $("repair") as HTMLButtonElement;
if (repairEl) repairEl.onclick = async () => {
  if (state.busy) return;
  if (!state.base || !state.outfit) return status("Chọn đủ ảnh base và outfit.", true);
  if (state.base.width !== state.outfit.width || state.base.height !== state.outfit.height) return status("Hai ảnh phải cùng kích thước.", true);
  const g = grid();
  if (!g) return status("Kích thước ảnh phải chia hết cho số hàng và cột (1–64).", true);
  const revision = state.revision;
  state.busy = true;
  repairEl.disabled = true;
  ($("split") as HTMLButtonElement).disabled = ($("downloadOutfit") as HTMLButtonElement).disabled = ($("downloadHeadwear") as HTMLButtonElement).disabled = true;
  ($("download") as HTMLButtonElement).disabled = ($("downloadReport") as HTMLButtonElement).disabled = true;
  status("Đang tách vùng, tô màu và hoàn thiện viền…");
  try {
    if (($("composition") as HTMLSelectElement).value === 'pinned') await ensureProfile();
    const response = await doRepair();
    if (!response) throw new Error("No response");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Không xử lý được ảnh.");
    if (!result.report?.composition) throw new Error("Server chưa cập nhật chế độ ghép lớp. Khởi động lại server.");
    if ((result.report?.version || 0) < 6) throw new Error("Server chưa cập nhật v3. Khởi động lại tools/repair_outfit_ui.py.");
    const [image, mask] = await Promise.all([loadImage(result.image), loadImage(result.mask)]);
    if (revision !== state.revision) return status("Thiết lập đã đổi trong khi xử lý. Bấm Xử lý sprite để cập nhật.");
    state.result = image; state.mask = mask; state.report = result.report;
    state.outfitLayer = result.outfitLayer;
    state.headwearLayer = result.headwearLayer;
    ($("split") as HTMLButtonElement).disabled = !result.headwearLayer;
    ($("downloadHeadwear") as HTMLButtonElement).disabled = true;
    $("splitPreview").hidden = true;
    ($("downloadOutfit") as HTMLButtonElement).disabled = false;
    ($("resultPreview") as HTMLImageElement).src = result.image;
    $("resultStage").classList.add("loaded");
    $("resultMeta").textContent = `${result.width} × ${result.height} · ${result.frameCount} frame · ${result.paletteColors} màu`;
    ($("download") as HTMLButtonElement).disabled = ($("downloadReport") as HTMLButtonElement).disabled = false;
    status(`Hoàn tất: ${result.paletteColors} màu. ${result.report!.composition === 'layers' ? 'Outfit ở trên base; vùng da đã cắt để lộ base bên dưới.' : 'Đang dùng profile đầu/tay cố định.'}`);
    remember();
  } catch (error: any) {
    status(error instanceof TypeError ? "Không kết nối được server. Chạy tools/repair_outfit_ui.py rồi mở http://127.0.0.1:8765/." : error.message, true);
  } finally {
    state.busy = false; repairEl.disabled = location.protocol === "file:"; render();
  }
};

const downloadEl = $("download");
if (downloadEl) downloadEl.onclick = () => { if (state.result) download(state.result.src, "outfit-repaired.png"); };
const downloadOutfitEl = $("downloadOutfit");
if (downloadOutfitEl) downloadOutfitEl.onclick = () => { if (state.outfitLayer) download(state.outfitLayer, "outfit-layer.png"); };

const splitEl = $("split");
if (splitEl) splitEl.onclick = () => {
  if (state.busy || !state.headwearLayer) return;
  ($("clothingPreview") as HTMLImageElement).src = state.outfitLayer!;
  ($("headwearPreview") as HTMLImageElement).src = state.headwearLayer;
  $("splitPreview").hidden = false;
  ($("downloadHeadwear") as HTMLButtonElement).disabled = false;
  status("Đã tách trang phục và tóc + phụ kiện đầu, giữ nguyên kích thước và tọa độ.");
};
const downloadHeadwearEl = $("downloadHeadwear");
if (downloadHeadwearEl) downloadHeadwearEl.onclick = () => {
  if (state.headwearLayer) download(state.headwearLayer, "hair-headwear-layer.png");
};
const downloadReportEl = $("downloadReport");
if (downloadReportEl) downloadReportEl.onclick = () => {
  if (!state.report) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(state.report, null, 2)], { type: "application/json" }));
  download(url, "outfit-report.json"); setTimeout(() => URL.revokeObjectURL(url), 1000);
};

// Toolbar bindings
const toolButtons = document.querySelectorAll(".aseprite-vertical-toolbox .tool-btn:not(.profile-target-btn)") as NodeListOf<HTMLElement>;
toolButtons.forEach(btn => {
  if (btn.dataset.brushVal) {
    btn.addEventListener("click", () => setActiveTool(btn.dataset.brushVal!));
  }
});

const profileTargetBtns = document.querySelectorAll(".profile-target-btn") as NodeListOf<HTMLElement>;
profileTargetBtns.forEach(btn => btn.addEventListener("click", () => toggleProfileTarget(btn.dataset.profileTarget!)));

// Feature toggles
$("btnToggleSymmetry")?.addEventListener("click", () => toggleSymmetry());
$("btnToolSymmetry")?.addEventListener("click", () => toggleSymmetry());
$("btnToggleGrid")?.addEventListener("click", () => togglePixelGrid());
$("btnToolGrid")?.addEventListener("click", () => togglePixelGrid());
$("btnToggleOnion")?.addEventListener("click", () => toggleOnionSkin());

// Mask Opacity slider live value update
const maskOpacityInput = $("maskOpacity") as HTMLInputElement;
const maskOpacityVal = $("maskOpacityVal");
if (maskOpacityInput) {
  maskOpacityInput.addEventListener("input", (e: any) => {
    if (maskOpacityVal) maskOpacityVal.textContent = `${e.target.value}%`;
    render();
    saveLayout();
  });
}

// Xianxia Palette swatches
document.querySelectorAll(".palette-swatch").forEach(swatch => {
  swatch.addEventListener("click", () => {
    const color = (swatch as HTMLElement).dataset.color;
    if (!color) return;
    const paintColorInput = $("paintColor") as HTMLInputElement;
    const swatchPreview = $("colorSwatchPreview");
    const paletteColorCode = $("paletteColorCode");
    if (paintColorInput) paintColorInput.value = color;
    if (swatchPreview) swatchPreview.style.backgroundColor = color;
    if (paletteColorCode) paletteColorCode.textContent = color;
    document.querySelectorAll(".palette-swatch").forEach(s => s.classList.remove("active"));
    swatch.classList.add("active");
    setActiveTool("color");
    saveLayout();
  });
});

const paintColorInput = $("paintColor") as HTMLInputElement;
const swatchPreview = $("colorSwatchPreview");
if (paintColorInput && swatchPreview) {
  paintColorInput.addEventListener("input", (e: any) => {
    swatchPreview.style.backgroundColor = e.target.value;
    const paletteColorCode = $("paletteColorCode");
    if (paletteColorCode) paletteColorCode.textContent = e.target.value;
    saveLayout();
  });
}

const brushSizeSelect = $("brushSize") as HTMLSelectElement;
if (brushSizeSelect) {
  brushSizeSelect.addEventListener("change", () => {
    showBrushSizeHUD(Number(brushSizeSelect.value) || 1);
  });
}


window.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes((e.target as HTMLElement).tagName)) return;

  // Spacebar hold for pan
  if (e.code === "Space" && !e.repeat && !isSpacePressed) {
    isSpacePressed = true;
    document.body.classList.add("space-pan-active");
    return;
  }

  // Undo / Redo
  if ((e.ctrlKey || e.metaKey) && e.key.toUpperCase() === "Z") {
    e.preventDefault();
    if (e.shiftKey) doRedo();
    else doUndo();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toUpperCase() === "Y") {
    e.preventDefault();
    doRedo();
    return;
  }

  // Zoom shortcuts: Ctrl + = / Ctrl + - / Ctrl + 0
  if ((e.ctrlKey || e.metaKey) && (e.key === "=" || e.key === "+")) {
    e.preventDefault();
    applyZoom(currentZoom + (currentZoom < 4 ? 0.5 : 1.0));
    return;
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === "-" || e.key === "_")) {
    e.preventDefault();
    applyZoom(currentZoom - (currentZoom <= 4 ? 0.5 : 1.0));
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "0") {
    e.preventDefault();
    const isSheet = !$("sheetTab")?.classList.contains("hidden");
    const activeTab = isSheet ? "sheet" : "inspector";
    panState[activeTab].x = 0;
    panState[activeTab].y = 0;
    updateContentTransform(activeTab);
    applyZoom(isSheet ? 2.0 : 4.0);
    return;
  }

  // Toggle Grid: Ctrl + '
  if ((e.ctrlKey || e.metaKey) && (e.key === "'" || e.key === '"')) {
    e.preventDefault();
    togglePixelGrid();
    return;
  }

  // Toggle Symmetry: M
  if (e.key.toUpperCase() === "M") {
    e.preventDefault();
    toggleSymmetry();
    return;
  }

  // Toggle Onion Skin: O
  if (e.key.toUpperCase() === "O") {
    e.preventDefault();
    toggleOnionSkin();
    return;
  }

  // Frame navigation (< / , and > / .)
  if (e.key === "," || e.key === "<") {
    e.preventDefault();
    $("prev")?.click();
    return;
  }
  if (e.key === "." || e.key === ">") {
    e.preventDefault();
    $("next")?.click();
    return;
  }

  // Animation Playback (Enter or P)
  if (e.key === "Enter" || e.key.toUpperCase() === "P") {
    e.preventDefault();
    togglePlayPause();
    return;
  }

  // Tab switch (Tab key)
  if (e.key === "Tab") {
    e.preventDefault();
    const isSheet = !$("sheetTab")?.classList.contains("hidden");
    showTab(isSheet ? "inspector" : "sheet");
    return;
  }

  // Brush size: [ and ]
  const bSizeSelect = $("brushSize") as HTMLSelectElement;
  if (e.key === "[") {
    e.preventDefault();
    if (bSizeSelect) {
      const sizes = [1, 2, 3, 4, 5, 6, 8];
      const cur = Number(bSizeSelect.value) || 1;
      const prev = [...sizes].reverse().find(s => s < cur) || 1;
      bSizeSelect.value = prev.toString();
      bSizeSelect.dispatchEvent(new Event("change"));
    }
    return;
  }
  if (e.key === "]") {
    e.preventDefault();
    if (bSizeSelect) {
      const sizes = [1, 2, 3, 4, 5, 6, 8];
      const cur = Number(bSizeSelect.value) || 1;
      const next = sizes.find(s => s > cur) || 8;
      bSizeSelect.value = next.toString();
      bSizeSelect.dispatchEvent(new Event("change"));
    }
    return;
  }

  // Direct number keys 1, 2, 3, 4, 5, 6, 8 for brush size
  if (["1", "2", "3", "4", "5", "6", "8"].includes(e.key)) {
    if (bSizeSelect) {
      bSizeSelect.value = e.key;
      bSizeSelect.dispatchEvent(new Event("change"));
    }
    return;
  }

  // Tool hotkeys:
  const key = e.key.toUpperCase();
  if (key === "B") setActiveTool("color");          // Brush (Tô màu)
  else if (key === "E") {
    if (e.shiftKey) setActiveTool("unpaint");       // Unpaint (chỉ xóa màu vẽ tay)
    else setActiveTool("erase");                    // Eraser (tẩy pixel thành trong suốt)
  }
  else if (key === "I") setActiveTool("sample");   // Eyedropper (hút màu)
  else if (key === "V" || key === "H") setActiveTool("inspect"); // Move / Hand (pan)
  else if (key === "R") setActiveTool("base");      // Lộ Base
  else if (key === "U") setActiveTool("outfit");    // Giữ outfit
  else if (key === "W") setActiveTool("headwear");  // Giữ headwear
  else if (key === "A") setActiveTool("auto");      // Auto (khôi phục pixel gốc)
  else if (key === "X") {
    // Toggle landmark target
    if (!profileTarget) toggleProfileTarget("head");
    else if (profileTarget === "head") toggleProfileTarget("hand");
    else toggleProfileTarget("hand");
  }
});

window.addEventListener("keyup", (e) => {
  if (e.code === "Space") {
    isSpacePressed = false;
    document.body.classList.remove("space-pan-active");
    if (isPanning) {
      isPanning = false;
      document.querySelectorAll("[data-zoom-container]").forEach(el => el.classList.remove("panning"));
      document.body.classList.remove("is-panning");
    }
  }
});

const btnResetFrame = $("btnResetFrameAll");
if (btnResetFrame) {
  btnResetFrame.addEventListener("click", () => {
    const g = grid();
    if (!g) return;
    if (confirm(`Reset Frame ${g.frame + 1} về nguyên gốc?`)) {
      checkpoint(corrections, g, [paintLayer, baseMap]);
      correctionContext.clearRect(g.x, g.y, g.w, g.h);
      paintContext.clearRect(g.x, g.y, g.w, g.h);
      baseMapContext.clearRect(g.x, g.y, g.w, g.h);
      invalidate("Đã reset frame về gốc.");
      render();
      remember();
    }
  });
}

$("btnZoomIn")?.addEventListener("click", () => applyZoom(currentZoom + (currentZoom < 4 ? 0.5 : 1.0)));
$("btnZoomOut")?.addEventListener("click", () => applyZoom(currentZoom - (currentZoom <= 4 ? 0.5 : 1.0)));
$("btnZoomReset")?.addEventListener("click", () => {
  const isSheet = !$("sheetTab")?.classList.contains("hidden");
  const activeTab = isSheet ? "sheet" : "inspector";
  panState[activeTab].x = 0;
  panState[activeTab].y = 0;
  updateContentTransform(activeTab);
  applyZoom(isSheet ? 2.0 : 4.0);
});
$("btnZoomFit")?.addEventListener("click", () => fitViewToScreen());
$("btnToggleBg")?.addEventListener("click", () => toggleCanvasBackground());

const zoomContainers = new Set<HTMLElement>();
document.querySelectorAll("[data-zoom-container]").forEach(el => zoomContainers.add(el as HTMLElement));
const inspectorTabEl = $("inspectorTab");
if (inspectorTabEl) zoomContainers.add(inspectorTabEl);
const sheetTabEl = $("sheetTab");
if (sheetTabEl) zoomContainers.add(sheetTabEl);

zoomContainers.forEach(container => {
  container.addEventListener("contextmenu", (e) => e.preventDefault());

  // 1. Wheel Event: Lăn chuột phóng to / thu nhỏ, Ctrl + lăn chuột đổi cỡ cọ, Shift + lăn chuột di chuyển ngang
  container.addEventListener("wheel", (e: WheelEvent) => {
    const isSheet = container.id === "sheetTab";
    const activeTab = isSheet ? "sheet" : "inspector";

    // 0. Thay đổi kích thước cọ khi giữ Ctrl / Cmd + lăn chuột
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const bSelect = $("brushSize") as HTMLSelectElement;
      if (bSelect) {
        const sizes = [1, 2, 3, 4, 5, 6, 8];
        const curSize = Number(bSelect.value) || 1;
        let idx = sizes.indexOf(curSize);
        if (idx === -1) idx = 0;
        if (e.deltaY < 0) {
          if (idx < sizes.length - 1) idx++;
        } else {
          if (idx > 0) idx--;
        }
        const nextSize = sizes[idx];
        bSelect.value = nextSize.toString();
        bSelect.dispatchEvent(new Event("change"));
        showBrushSizeHUD(nextSize);
        updatePixelCursorBox(e);
      }
      return;
    }

    // Di chuyển 2 bên khi giữ Shift
    if (e.shiftKey) {
      e.preventDefault();
      const delta = (e.deltaY !== 0 ? e.deltaY : e.deltaX);
      panState[activeTab].x += (delta < 0 ? 40 : -40);
      updateContentTransform(activeTab);
      return;
    }

    if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      e.preventDefault();
      panState[activeTab].x += (e.deltaX < 0 ? 40 : -40);
      updateContentTransform(activeTab);
      return;
    }

    // Lăn con lăn chuột (mặc định HOẶC giữ Ctrl/Alt/Meta): Phóng to / thu nhỏ mượt mà
    e.preventDefault();
    const minZoom = isSheet ? 0.25 : 0.5;
    const maxZoom = isSheet ? 16.0 : 32.0;
    const step = currentZoom < 2 ? 0.25 : currentZoom < 8 ? 0.5 : 1.0;
    const delta = e.deltaY < 0 ? step : -step;
    const nextZoom = Math.min(maxZoom, Math.max(minZoom, Math.round((currentZoom + delta) * 100) / 100));

    if (nextZoom !== currentZoom) {
      const rect = container.getBoundingClientRect();
      const mx = e.clientX - (rect.left + rect.width / 2);
      const my = e.clientY - (rect.top + rect.height / 2);
      const ratio = nextZoom / currentZoom;

      panState[activeTab].x = Math.round(panState[activeTab].x * ratio + mx * (1 - ratio));
      panState[activeTab].y = Math.round(panState[activeTab].y * ratio + my * (1 - ratio));

      applyZoom(nextZoom);
      updateContentTransform(activeTab);
    }
  }, { passive: false });

  // 2. Bắt đầu di chuyển (Pan): Ấn con lăn (button 1), hoặc chuột phải (button 2), hoặc Space + click trái, hoặc Hand tool (inspect)
  const handlePanStart = (e: MouseEvent | PointerEvent) => {
    const isMiddle = e.button === 1;
    const isRight = e.button === 2;
    const isInspect = currentActiveTool === "inspect" && e.button === 0;
    const isSpacePan = isSpacePressed && e.button === 0;

    if (isMiddle || isRight || isSpacePan || isInspect) {
      e.preventDefault();
      startPan(e, container.id === "sheetTab" ? "sheet" : "inspector");
    }
  };

  container.addEventListener("pointerdown", handlePanStart);
  container.addEventListener("mousedown", handlePanStart);
  container.addEventListener("auxclick", (e: MouseEvent) => {
    if (e.button === 1 || e.button === 2) e.preventDefault();
  });
});

const handlePanMove = (e: MouseEvent | PointerEvent) => {
  if (!isPanning || !activePanTab) return;
  e.preventDefault();
  const dx = e.clientX - panStartMouseX;
  const dy = e.clientY - panStartMouseY;
  if (Math.hypot(dx, dy) > 3) didPanMove = true;
  panState[activePanTab].x = panStartPanX + dx;
  panState[activePanTab].y = panStartPanY + dy;
  updateContentTransform(activePanTab);
};

window.addEventListener("pointermove", handlePanMove);
window.addEventListener("mousemove", handlePanMove);

const handlePanEnd = () => {
  if (isPanning) {
    isPanning = false;
    document.querySelectorAll("[data-zoom-container]").forEach(el => el.classList.remove("panning"));
    $("inspectorTab")?.classList.remove("panning");
    $("sheetTab")?.classList.remove("panning");
    document.body.classList.remove("is-panning");
    setTimeout(() => { didPanMove = false; }, 50);
  }
};

window.addEventListener("pointerup", handlePanEnd);
window.addEventListener("mouseup", handlePanEnd);
window.addEventListener("pointercancel", handlePanEnd);
window.addEventListener("auxclick", (e: MouseEvent) => {
  if (e.button === 1 || e.button === 2) e.preventDefault();
});

const resultPreviewImg = $("resultPreview");
if (resultPreviewImg) {
  resultPreviewImg.addEventListener("click", (e) => {
    if (didPanMove) return;
    const cols = Number(($("cols") as HTMLInputElement)?.value) || 4;
    const rows = Number(($("rows") as HTMLInputElement)?.value) || 7;
    const rect = resultPreviewImg.getBoundingClientRect();
    const col = Math.floor(((e.clientX - rect.left) / rect.width) * cols);
    const row = Math.floor(((e.clientY - rect.top) / rect.height) * rows);
    const targetFrame = row * cols + col + 1;
    if (targetFrame >= 1 && targetFrame <= cols * rows) {
      if (frameEl) {
        frameEl.value = targetFrame.toString();
        frameEl.dispatchEvent(new Event("change"));
      }
      showTab("inspector");
    }
  });
}

$("tabBtnInspector")?.addEventListener("click", () => showTab("inspector"));
$("tabBtnSheet")?.addEventListener("click", () => showTab("sheet"));

// Retain initial tab after repair completes: update thumbnails without switching tabs
const observer = new MutationObserver(() => {
  const stage = $("resultStage");
  if (stage && stage.classList.contains("loaded")) {
    updateFrameThumbnails();
  }
});
const resultStage = $("resultStage");
if (resultStage) observer.observe(resultStage, { attributes: true, attributeFilter: ["class"] });

$("animFpsSelect")?.addEventListener("change", () => {
  if (isPlaying) { stopPlaybackLoop(); startPlaybackLoop(); }
  saveLayout();
});
$("btnPlayPause")?.addEventListener("click", togglePlayPause);

initSplitter("leftSplitter", "leftPanel", "v", "before");
initSplitter("rightSplitter", "rightPanel", "v", "after");
initSplitter("bottomSplitter", "bottomPanel", "h", "after");

$("brushSize")?.addEventListener("change", saveLayout);
$("showMask")?.addEventListener("change", saveLayout);
$("maskOpacity")?.addEventListener("input", saveLayout);
$("showProfile")?.addEventListener("change", saveLayout);

(async () => {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
    if (saved) {
      for (const id of settings) if (saved.values?.[id] !== undefined) {
        const el = $(id) as any;
        if (id === "outline") el.checked = saved.values[id]; else el.value = saved.values[id];
      }
      if (saved.version !== 4) ($("paint") as HTMLInputElement).value = "3";
      if (saved.base) await setSource("base", saved.base);
      if (saved.outfit) await setSource("outfit", saved.outfit);
      if (saved.corrections && state.base) {
        const img = await loadImage(saved.corrections);
        if (img.width === corrections.width && img.height === corrections.height) correctionContext.drawImage(img, 0, 0);
      }
      const savedPaint = sessionStorage.getItem(`${storageKey}:paint`);
      if (savedPaint && state.base) {
        const img = await loadImage(savedPaint);
        if (img.width === paintLayer.width && img.height === paintLayer.height) paintContext.drawImage(img, 0, 0);
      }
    }
  } catch (_) { status("Chọn lại ảnh để bắt đầu."); }
  if (!state.base && location.protocol !== "file:") {
    try { await setSource("base", "/assets/default-base.png"); }
    catch (_) { status("Không nạp được base mặc định. Bạn có thể chọn base thủ công.", true); }
  }
  if (location.protocol === "file:") {
    const fileNotice = $("fileNotice");
    if (fileNotice) fileNotice.hidden = false; 
    if (repairEl) repairEl.disabled = true;
    status("Trang đang mở dạng file. Chạy server local và mở http://127.0.0.1:8765/ để xử lý.", true);
  }
  
  restoreLayout();
  renderAnimationTimeline();
  setTimeout(renderAnimationTimeline, 250);
  render();
})();
