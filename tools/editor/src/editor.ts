import { state, corrections, correctionContext, baseMap, baseMapContext, paintLayer, paintContext, profileState, storageKey } from './state';
import type { GridInfo, StrokeState } from './types';
import { $, status } from './utils';
import { saveLayout } from './layout';

export const settings = ["rows", "cols", "colors", "threshold", "outline", "paint", "cleanup", "composition"];
export let currentZoom = 4.0;
export let stroke: StrokeState | null = null;
export let currentActiveTool = "inspect";
export let profileTarget: string | null = null;
export let isSymmetryEnabled = false;
export let isPixelGridEnabled = false;
export let isOnionSkinEnabled = false;

export function toggleSymmetry(): boolean {
  isSymmetryEnabled = !isSymmetryEnabled;
  const inspectorTab = $("inspectorTab");
  if (inspectorTab) {
    if (isSymmetryEnabled) inspectorTab.classList.add("show-symmetry");
    else inspectorTab.classList.remove("show-symmetry");
  }
  const btns = [ $("btnToggleSymmetry"), $("btnToolSymmetry") ];
  btns.forEach(b => {
    if (b) {
      if (isSymmetryEnabled) b.classList.add("active", "border-teal-400", "text-teal-300");
      else b.classList.remove("active", "border-teal-400", "text-teal-300");
    }
  });
  return isSymmetryEnabled;
}

export function togglePixelGrid(): boolean {
  isPixelGridEnabled = !isPixelGridEnabled;
  const inspectorTab = $("inspectorTab");
  if (inspectorTab) {
    if (isPixelGridEnabled) inspectorTab.classList.add("show-pixel-grid");
    else inspectorTab.classList.remove("show-pixel-grid");
  }
  const btns = [ $("btnToggleGrid"), $("btnToolGrid") ];
  btns.forEach(b => {
    if (b) {
      if (isPixelGridEnabled) b.classList.add("active", "border-teal-400", "text-teal-300");
      else b.classList.remove("active", "border-teal-400", "text-teal-300");
    }
  });
  return isPixelGridEnabled;
}

export function toggleOnionSkin(): boolean {
  isOnionSkinEnabled = !isOnionSkinEnabled;
  const btn = $("btnToggleOnion");
  if (btn) {
    if (isOnionSkinEnabled) btn.classList.add("active", "bg-amber-900/60", "border-amber-400");
    else btn.classList.remove("active", "bg-amber-900/60", "border-amber-400");
  }
  render();
  return isOnionSkinEnabled;
}

export type CanvasBgTheme = "neutral" | "dark" | "light" | "green";
export let currentCanvasBg: CanvasBgTheme = "neutral";

export function setCanvasBackground(theme: CanvasBgTheme) {
  currentCanvasBg = theme;
  const targets = document.querySelectorAll(".canvas-container, .canvas-container canvas, #animPreviewCanvas");
  targets.forEach(c => {
    c.classList.remove("canvas-bg-neutral", "canvas-bg-dark", "canvas-bg-light", "canvas-bg-green");
    c.classList.add(`canvas-bg-${theme}`);
  });
  const btn = $("btnToggleBg");
  if (btn) {
    const labels: Record<CanvasBgTheme, string> = {
      neutral: "🏁 Nền Xám (1:1)",
      dark: "🌑 Nền Tối (1:1)",
      light: "💡 Nền Sáng (1:1)",
      green: "🟩 Phông Xanh"
    };
    btn.textContent = labels[theme] || "🏁 Đổi nền";
  }
}

export function toggleCanvasBackground(): CanvasBgTheme {
  const modes: CanvasBgTheme[] = ["neutral", "dark", "light", "green"];
  const nextIdx = (modes.indexOf(currentCanvasBg) + 1) % modes.length;
  setCanvasBackground(modes[nextIdx]);
  return currentCanvasBg;
}

export function fitViewToScreen() {
  const isSheet = !$("sheetTab")?.classList.contains("hidden");
  const activeTab = isSheet ? "sheet" : "inspector";
  panState[activeTab].x = 0;
  panState[activeTab].y = 0;
  updateContentTransform(activeTab);

  if (isSheet) {
    applyZoom(2.0, "sheet");
  } else {
    const tabEl = $("inspectorTab");
    if (tabEl) {
      const availW = tabEl.clientWidth - 80;
      const availH = tabEl.clientHeight - 100;
      // 3 viewports: each has (64 * zoom + padding/borders ~ 16px) + gap 24px
      // at 1x zoom: 3 * (64 + 16) + 48 = 288px width, 64 + 40 = 104px height
      const zoomW = Math.floor((availW / 288) * 2) / 2;
      const zoomH = Math.floor((availH / 104) * 2) / 2;
      const bestZoom = Math.min(5.0, Math.max(2.0, Math.min(zoomW, zoomH)));
      applyZoom(bestZoom, "inspector");
    } else {
      applyZoom(4.0, "inspector");
    }
  }
}

export function grid(): GridInfo | null {
  const colsStr = ($("cols") as HTMLInputElement).value;
  const rowsStr = ($("rows") as HTMLInputElement).value;
  const cols = Number(colsStr), rows = Number(rowsStr);
  const img = state.base || state.outfit;
  if (!img || !Number.isInteger(cols) || !Number.isInteger(rows) || cols < 1 || rows < 1 || cols > 64 || rows > 64) return null;
  if (img.width % cols || img.height % rows) return null;
  const count = rows * cols;
  const frameInput = Math.trunc(Number(($("frame") as HTMLInputElement).value)) || 1;
  const frame = Math.min(count, Math.max(1, frameInput)) - 1;
  return { cols, rows, count, frame, w: img.width / cols, h: img.height / rows,
    x: (frame % cols) * img.width / cols, y: Math.floor(frame / cols) * img.height / rows };
}

export function drawCrop(canvas: HTMLCanvasElement, image: HTMLImageElement | null, g: GridInfo | null) {
  const w = g?.w || 64;
  const h = g?.h || 64;
  canvas.width = w;
  canvas.height = h;
  const zoom = Number(($("zoom") as HTMLSelectElement).value);
  canvas.style.width = `${w * zoom}px`;
  canvas.style.height = `${h * zoom}px`;
  canvas.style.setProperty("--grid-w", `${w}`);
  canvas.style.setProperty("--grid-h", `${h}`);
  const container = canvas.closest(".canvas-container") as HTMLElement;
  if (container) {
    container.style.setProperty("--grid-w", `${w}`);
    container.style.setProperty("--grid-h", `${h}`);
  }
  const card = canvas.closest(".viewport-card") as HTMLElement;
  if (card) {
    card.style.width = `${w * zoom + 16}px`;
  }
  const context = canvas.getContext("2d")!;
  context.imageSmoothingEnabled = false;
  if (image && g) context.drawImage(image, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
  return context;
}

export function render() {
  const g = grid();
  const frameEl = $("frame") as HTMLInputElement;
  if (g && frameEl) { frameEl.max = g.count.toString(); frameEl.value = (g.frame + 1).toString(); }
  const zoomEl = $("zoom") as HTMLSelectElement;
  const frameWidth = (g?.w || 64) * Number(zoomEl?.value || 4) + 2;
  const gridContainer = document.querySelector(".frame-grid") as HTMLElement;
  if (gridContainer) gridContainer.style.gridTemplateColumns = `repeat(auto-fit, minmax(min(100%, ${frameWidth}px), 1fr))`;
  
  const baseContext = drawCrop($("baseCanvas") as HTMLCanvasElement, state.base, g);
  if (g && profileState.key && (($("showProfile") as HTMLInputElement).checked || ($("brush") as HTMLSelectElement).value.startsWith("profile"))) {
    baseContext.globalAlpha = 0.4;
    baseContext.drawImage(baseMap, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    baseContext.globalAlpha = 1;
  }
  
  const outfitCanvas = $("outfitCanvas") as HTMLCanvasElement;
  const outfitContext = drawCrop(outfitCanvas, state.outfit, g);
  const ctx = drawCrop($("editCanvas") as HTMLCanvasElement, state.result || state.outfit, g);
  if (!state.result && state.outfit && g) {
    const imgData = ctx.getImageData(0, 0, g.w, g.h);
    const thresh = Number(($("threshold") as HTMLInputElement)?.value) || 30;
    const cutoff = Math.max(180, 255 - thresh);
    const d = imgData.data;
    for (let i = 0; i < d.length; i += 4) {
      if (d[i] >= cutoff && d[i+1] >= cutoff && d[i+2] >= cutoff) {
        d[i+3] = 0;
      }
    }
    ctx.putImageData(imgData, 0, 0);
  }
  
  if (g) {
    const labels = correctionContext.getImageData(g.x, g.y, g.w, g.h).data;
    const source = document.createElement('canvas'); source.width = g.w; source.height = g.h;
    const sourceCtx = source.getContext('2d')!;
    if (state.base) sourceCtx.drawImage(state.base, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    const basePixels = sourceCtx.getImageData(0, 0, g.w, g.h).data;

    const outfitSource = document.createElement('canvas'); outfitSource.width = g.w; outfitSource.height = g.h;
    const outfitSourceCtx = outfitSource.getContext('2d')!;
    if (state.outfit) outfitSourceCtx.drawImage(state.outfit, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    const outfitPixels = outfitSourceCtx.getImageData(0, 0, g.w, g.h).data;

    const preview = ctx.getImageData(0, 0, g.w, g.h);
    for (let i = 0; i < labels.length; i += 4) {
      if (labels[i+3] >= 128) {
        // Red: Base reveal (cắt da để lộ base)
        if (labels[i] > 200 && labels[i+1] < 100 && labels[i+2] < 100) {
          preview.data.set(basePixels.slice(i, i+4), i);
        }
        // Green: Erase (xóa thành trong suốt)
        else if (labels[i+1] > 200 && labels[i] < 100 && labels[i+2] < 100) {
          preview.data.fill(0, i, i+4);
        }
        // Blue: Keep outfit (giữ nguyên outfit/dải lụa, không cắt da)
        else if (labels[i+2] > 200 && labels[i] < 100 && labels[i+1] < 100) {
          preview.data.set(outfitPixels.slice(i, i+4), i);
        }
        // Yellow: Keep headwear (giữ tóc & phụ kiện đầu)
        else if (labels[i] > 200 && labels[i+1] > 150 && labels[i+2] < 100) {
          preview.data.set(outfitPixels.slice(i, i+4), i);
        }
      }
    }
    ctx.putImageData(preview, 0, 0);
    ctx.drawImage(paintLayer, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);

    if (isOnionSkinEnabled && g && (state.result || state.outfit)) {
      const srcImg = state.result || state.outfit;
      if (g.frame > 0 && srcImg) {
        const prevX = ((g.frame - 1) % g.cols) * g.w;
        const prevY = Math.floor((g.frame - 1) / g.cols) * g.h;
        ctx.save();
        ctx.globalAlpha = 0.25;
        ctx.drawImage(srcImg, prevX, prevY, g.w, g.h, 0, 0, g.w, g.h);
        ctx.restore();
      }
    }
    
    const showMaskChecked = ($("showMask") as HTMLInputElement).checked;
    if (showMaskChecked) {
      const maskOpacity = Number(($("maskOpacity") as HTMLInputElement).value) / 100;
      if (state.mask) {
        ctx.globalAlpha = maskOpacity;
        ctx.drawImage(state.mask, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
        outfitContext.globalAlpha = maskOpacity;
        outfitContext.drawImage(state.mask, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
      }
      ctx.globalAlpha = 0.65;
      ctx.drawImage(corrections, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
      outfitContext.globalAlpha = 0.65;
      outfitContext.drawImage(corrections, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
      ctx.globalAlpha = 1;
      outfitContext.globalAlpha = 1;
    } else {
      // Lightly show corrections on outfitCanvas while using correction brush tools
      const curBrush = ($("brush") as HTMLSelectElement)?.value || "";
      if (["base", "outfit", "headwear", "erase"].includes(curBrush)) {
        outfitContext.globalAlpha = 0.35;
        outfitContext.drawImage(corrections, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
        outfitContext.globalAlpha = 1;
      }
    }
  }
  
  updateUndoRedoButtons();
  
  const editCvs = $("editCanvas") as HTMLCanvasElement;
  if (editCvs) editCvs.style.cursor = ($("brush") as HTMLSelectElement).value === "inspect" ? "default" : "crosshair";
  if (outfitCanvas) outfitCanvas.style.cursor = ($("brush") as HTMLSelectElement).value === "inspect" ? "default" : "crosshair";
  
  if (state.result) {
    const sheetZoom = Number(($("sheetZoom") as HTMLSelectElement).value);
    const resultPreview = $("resultPreview") as HTMLImageElement;
    if (resultPreview) {
      resultPreview.style.width = `${state.result.width * sheetZoom}px`;
      resultPreview.style.height = `${state.result.height * sheetZoom}px`;
    }
  }
  
  // Call global render hook if needed
  if ((window as any).__onRender) (window as any).__onRender();
}

export function updateUndoRedoButtons() {
  const undoBtn = $("undo") as HTMLButtonElement;
  if (undoBtn) undoBtn.disabled = !state.undo.length || state.busy;
  const redoBtn = $("redo") as HTMLButtonElement;
  if (redoBtn) redoBtn.disabled = !state.redo || !state.redo.length || state.busy;
}

export function checkpoint(canvas = corrections, rect: {x:number, y:number, w:number, h:number} | null = null, extra: HTMLCanvasElement[] = []) {
  const box = rect || { x: 0, y: 0, w: canvas.width, h: canvas.height };
  const data = canvas.getContext("2d")!.getImageData(box.x, box.y, box.w, box.h);
  const other = extra.map(layer => ({ canvas: layer, data: layer.getContext("2d")!.getImageData(box.x, box.y, box.w, box.h) }));
  state.undo.push({ canvas, data, x: box.x, y: box.y, other });
  if (state.redo) state.redo = [];
  if (state.undo.length > 20) state.undo.shift();
  updateUndoRedoButtons();
}

export function doUndo() {
  if (!state.undo.length || state.busy) return;
  const item = state.undo.pop();
  if (item) {
    if (!state.redo) state.redo = [];
    const curData = item.canvas.getContext("2d")!.getImageData(item.x, item.y, item.data.width, item.data.height);
    const curOther = item.other.map(o => ({ canvas: o.canvas, data: o.canvas.getContext("2d")!.getImageData(item.x, item.y, o.data.width, o.data.height) }));
    state.redo.push({ canvas: item.canvas, data: curData, x: item.x, y: item.y, other: curOther });

    item.canvas.getContext("2d")!.putImageData(item.data, item.x, item.y);
    for (const other of item.other) other.canvas.getContext("2d")!.putImageData(other.data, item.x, item.y);
    invalidate(); render(); remember();
    updateUndoRedoButtons();
  }
}

export function doRedo() {
  if (!state.redo || !state.redo.length || state.busy) return;
  const item = state.redo.pop();
  if (item) {
    const curData = item.canvas.getContext("2d")!.getImageData(item.x, item.y, item.data.width, item.data.height);
    const curOther = item.other.map(o => ({ canvas: o.canvas, data: o.canvas.getContext("2d")!.getImageData(item.x, item.y, o.data.width, o.data.height) }));
    state.undo.push({ canvas: item.canvas, data: curData, x: item.x, y: item.y, other: curOther });

    item.canvas.getContext("2d")!.putImageData(item.data, item.x, item.y);
    for (const other of item.other) other.canvas.getContext("2d")!.putImageData(other.data, item.x, item.y);
    invalidate(); render(); remember();
    updateUndoRedoButtons();
  }
}

export function remember() {
  try {
    const values = Object.fromEntries(settings.map(id => [id, id === "outline" ? ($<HTMLInputElement>(id)).checked : ($<HTMLInputElement>(id)).value]));
    sessionStorage.setItem(storageKey, JSON.stringify({ version: 4, values, base: state.base?.src, outfit: state.outfit?.src,
      corrections: state.base ? corrections.toDataURL() : null }));
  } catch (_) { }
  try {
    if (profileState.key) localStorage.setItem(`sprite-base:${profileState.key}`, baseMap.toDataURL());
    sessionStorage.setItem(`${storageKey}:paint`, paintLayer.toDataURL());
  } catch (_) { $("profileStatus").textContent = "Bộ nhớ trình duyệt đã đầy."; }
}

export function invalidate(message = "Thiết lập đã đổi. Bấm Xử lý sprite để cập nhật.") {
  state.revision++;
  ($("download") as HTMLButtonElement).disabled = true;
  ($("downloadReport") as HTMLButtonElement).disabled = true;
  ($("downloadOutfit") as HTMLButtonElement).disabled = true;
  ($("split") as HTMLButtonElement).disabled = true;
  ($("downloadHeadwear") as HTMLButtonElement).disabled = true;
  $("splitPreview").hidden = true;
  if (state.base && state.outfit) status(message);
}

export function clearResult() {
  state.result = state.mask = state.report = null;
  $("resultStage").classList.remove("loaded");
  $("resultPreview").removeAttribute("src");
  $("resultMeta").textContent = "";
  invalidate();
}

export function point(event: PointerEvent, canvas: HTMLCanvasElement = event.currentTarget as HTMLCanvasElement) {
  const rect = canvas.getBoundingClientRect();
  return { x: Math.floor((event.clientX - rect.left) * canvas.width / rect.width),
    y: Math.floor((event.clientY - rect.top) * canvas.height / rect.height) };
}

function singleDab(p: {x:number, y:number}, g: GridInfo, mode: string) {
  const size = Number(($("brushSize") as HTMLInputElement).value) || 1, half = Math.floor(size / 2);
  const x = Math.max(0, p.x - half), y = Math.max(0, p.y - half);
  const w = Math.min(g.w, p.x + half + 1) - x, h = Math.min(g.h, p.y + half + 1) - y;
  if (w <= 0 || h <= 0) return;

  if (mode.startsWith("profile")) {
    if (mode === "profileErase") {
      baseMapContext.clearRect(g.x + x, g.y + y, w, h);
    } else {
      const colors: Record<string, string> = { profileHead: "#ff0000", profileHand: "#ff8000" };
      baseMapContext.fillStyle = colors[mode] || "#ff0000";
      baseMapContext.fillRect(g.x + x, g.y + y, w, h);
    }
    return;
  }

  // Edit / Result canvas operations
  if (mode === "color") {
    // Painting color: write to paintLayer and clear any previous erase/override mark
    correctionContext.clearRect(g.x + x, g.y + y, w, h);
    paintContext.fillStyle = ($("paintColor") as HTMLInputElement).value;
    paintContext.fillRect(g.x + x, g.y + y, w, h);
  } else if (mode === "erase") {
    // Erase: clear manual paint AND write #00ff00 to corrections (removes underlying sprite pixel)
    paintContext.clearRect(g.x + x, g.y + y, w, h);
    correctionContext.fillStyle = "#00ff00";
    correctionContext.fillRect(g.x + x, g.y + y, w, h);
  } else if (mode === "unpaint") {
    // Only erase manual paint layer without removing outfit pixel
    paintContext.clearRect(g.x + x, g.y + y, w, h);
  } else if (mode === "auto") {
    // Restore original: clear both corrections and paintLayer
    paintContext.clearRect(g.x + x, g.y + y, w, h);
    correctionContext.clearRect(g.x + x, g.y + y, w, h);
  } else {
    // base (#ff0000), outfit (#0000ff), headwear (#ffc800)
    paintContext.clearRect(g.x + x, g.y + y, w, h);
    const colors: Record<string, string> = { base: "#ff0000", outfit: "#0000ff", headwear: "#ffc800" };
    correctionContext.fillStyle = colors[mode] || "#ff0000";
    correctionContext.fillRect(g.x + x, g.y + y, w, h);
  }
}

export function dab(p: {x:number, y:number}, g: GridInfo, mode: string) {
  singleDab(p, g, mode);
  if (isSymmetryEnabled) {
    const mirrorX = g.w - 1 - p.x;
    if (mirrorX !== p.x) {
      singleDab({ x: mirrorX, y: p.y }, g, mode);
    }
  }
}

export function getEffectiveBrush(tool: string, shiftKey: boolean) {
  if (!profileTarget) return tool;
  if (tool === "color" || tool === "inspect") {
    if (shiftKey) return profileTarget === "head" ? "profileBoxHead" : "profileBoxHand";
    return profileTarget === "head" ? "profileHead" : "profileHand";
  }
  if (tool === "unpaint" || tool === "erase") {
    return shiftKey ? "profileBoxErase" : "profileErase";
  }
  return tool;
}

export function updateProfileTargetUI() {
  const profileTargetBtns = document.querySelectorAll(".profile-target-btn") as NodeListOf<HTMLElement>;
  profileTargetBtns.forEach(btn => {
    if (btn.dataset.profileTarget === profileTarget) btn.classList.add("target-active");
    else btn.classList.remove("target-active");
  });
  const profileBadge = $("profileTargetBadge");
  if (profileBadge) {
    if (profileTarget) {
      profileBadge.textContent = profileTarget === "head" ? "🧑 ĐẦU" : "🤚 TAY";
      profileBadge.classList.remove("hidden");
    } else {
      profileBadge.classList.add("hidden");
    }
  }
  saveLayout();
}

export function setActiveTool(toolMode: string) {
  currentActiveTool = toolMode;
  if (toolMode === "inspect") {
    document.body.classList.add("tool-inspect");
  } else {
    document.body.classList.remove("tool-inspect");
  }
  const nativeBrushSelect = $("brush") as HTMLSelectElement;
  if (nativeBrushSelect) {
    nativeBrushSelect.value = toolMode;
    nativeBrushSelect.dispatchEvent(new Event("change"));
  }
  const toolButtons = document.querySelectorAll(".aseprite-vertical-toolbox .tool-btn:not(.profile-target-btn)") as NodeListOf<HTMLElement>;
  toolButtons.forEach(btn => {
    if (btn.dataset.brushVal === toolMode) btn.classList.add("active");
    else btn.classList.remove("active");
  });
  saveLayout();
}

export function toggleProfileTarget(target: string) {
  if (profileTarget === target) {
    profileTarget = null;
  } else {
    profileTarget = target;
    if (currentActiveTool === "inspect") setActiveTool("color");
  }
  updateProfileTargetUI();
}

export const panState = {
  inspector: { x: 0, y: 0 },
  sheet: { x: 0, y: 0 }
};

export function updateContentTransform(tabMode?: "inspector" | "sheet") {
  const currentTab = tabMode || (!($("sheetTab")?.classList.contains("hidden")) ? "sheet" : "inspector");
  const el = $(currentTab === "inspector" ? "inspectorContent" : "sheetContent");
  if (el) {
    const pan = panState[currentTab];
    el.style.transform = `translate(${pan.x}px, ${pan.y}px)`;
  }
}

export function applyZoom(newZoom: number, tabMode: string | null = null) {
  const isSheet = tabMode === "sheet" || !$("sheetTab")?.classList.contains("hidden");
  const minZoom = isSheet ? 0.25 : 0.5;
  const maxZoom = isSheet ? 16.0 : 32.0;
  currentZoom = Math.min(maxZoom, Math.max(minZoom, Math.round(newZoom * 10) / 10));
  const zoomPercentEl = $("zoomPercent");
  if (zoomPercentEl) zoomPercentEl.textContent = `${Math.round(currentZoom * 100)}%`;

  if (isSheet) {
    const sheetZoomSelect = $("sheetZoom") as HTMLSelectElement;
    if (sheetZoomSelect) {
      let opt = sheetZoomSelect.querySelector(`option[value="${currentZoom}"]`) as HTMLOptionElement;
      if (!opt) {
        opt = document.createElement("option");
        opt.value = currentZoom.toString();
        sheetZoomSelect.appendChild(opt);
      }
      sheetZoomSelect.value = currentZoom.toString();
    }
  } else {
    const zoomSelect = $("zoom") as HTMLSelectElement;
    if (zoomSelect) {
      let opt = zoomSelect.querySelector(`option[value="${currentZoom}"]`) as HTMLOptionElement;
      if (!opt) {
        opt = document.createElement("option");
        opt.value = currentZoom.toString();
        zoomSelect.appendChild(opt);
      }
      zoomSelect.value = currentZoom.toString();
    }
  }
  render();
  updateContentTransform(isSheet ? "sheet" : "inspector");
  saveLayout();
}

export function showTab(tabName: string) {
  const btnInspector = $("tabBtnInspector");
  const btnSheet = $("tabBtnSheet");
  const tabInspector = $("inspectorTab");
  const tabSheet = $("sheetTab");

  if (tabName === "inspector") {
    btnInspector?.classList.add("active", "border-teal-400", "text-teal-300", "bg-as-subpanel");
    btnInspector?.classList.remove("border-transparent", "text-slate-400");
    btnSheet?.classList.remove("active", "border-teal-400", "text-teal-300", "bg-as-subpanel");
    btnSheet?.classList.add("border-transparent", "text-slate-400");
    tabInspector?.classList.remove("hidden");
    tabSheet?.classList.add("hidden");
    applyZoom(Number(($("zoom") as HTMLSelectElement)?.value) || 4.0, "inspector");
    updateContentTransform("inspector");
  } else {
    btnSheet?.classList.add("active", "border-teal-400", "text-teal-300", "bg-as-subpanel");
    btnSheet?.classList.remove("border-transparent", "text-slate-400");
    btnInspector?.classList.remove("active", "border-teal-400", "text-teal-300", "bg-as-subpanel");
    btnInspector?.classList.add("border-transparent", "text-slate-400");
    tabSheet?.classList.remove("hidden");
    tabInspector?.classList.add("hidden");
    applyZoom(Number(($("sheetZoom") as HTMLSelectElement)?.value) || 2.0, "sheet");
    updateContentTransform("sheet");
  }
  saveLayout();
}

export function setStroke(s: StrokeState | null) { stroke = s; }
