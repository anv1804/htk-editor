import type { LayoutState } from './types';
import { currentZoom, currentActiveTool, profileTarget, setActiveTool, applyZoom, showTab } from './editor';
import { $ } from './utils';

export const LAYOUT_KEY = "hkt-pf-layout-v2";
let saveTimeout: number | null = null;

export function initSplitter(splitterId: string, panelId: string, direction: "h" | "v", side: "before" | "after") {
  const splitter = $(splitterId);
  const panel = $(panelId);
  if (!splitter || !panel) return;

  let isDragging = false, startPos = 0, startSize = 0;

  splitter.addEventListener("mousedown", (e: MouseEvent) => {
    e.preventDefault();
    isDragging = true;
    startPos = direction === "h" ? e.clientY : e.clientX;
    startSize = direction === "h" ? panel.offsetHeight : panel.offsetWidth;
    splitter.classList.add("dragging");
    document.body.classList.add("resizing-panels", direction === "h" ? "resizing-h" : "resizing-v");
  });

  window.addEventListener("mousemove", (e: MouseEvent) => {
    if (!isDragging) return;
    e.preventDefault();
    const delta = (direction === "h" ? e.clientY : e.clientX) - startPos;
    const sign = (side === "before") ? 1 : -1;
    const newSize = Math.max(
      parseInt(getComputedStyle(panel).minWidth || getComputedStyle(panel).minHeight || "80"),
      Math.min(
        parseInt(getComputedStyle(panel).maxWidth || getComputedStyle(panel).maxHeight || "600"),
        startSize + delta * sign
      )
    );
    if (direction === "h") panel.style.height = newSize + "px";
    else panel.style.width = newSize + "px";
  });

  window.addEventListener("mouseup", () => {
    if (!isDragging) return;
    isDragging = false;
    splitter.classList.remove("dragging");
    document.body.classList.remove("resizing-panels", "resizing-v", "resizing-h");
    saveLayout();
  });
}

export function saveLayout() {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = window.setTimeout(() => {
    try {
      const tabSheet = $("sheetTab");
      const data: LayoutState = {
        leftW: $("leftPanel")?.style.width,
        rightW: $("rightPanel")?.style.width,
        bottomH: $("bottomPanel")?.style.height,
        zoom: currentZoom,
        tab: tabSheet?.classList.contains("hidden") ? "inspector" : "sheet",
        tool: currentActiveTool,
        profileTarget: profileTarget,
        brushSize: ($("brushSize") as HTMLInputElement)?.value,
        showMask: ($("showMask") as HTMLInputElement)?.checked,
        maskOpacity: ($("maskOpacity") as HTMLInputElement)?.value,
        showProfile: ($("showProfile") as HTMLInputElement)?.checked,
        fps: ($("animFpsSelect") as HTMLSelectElement)?.value,
        paintColor: ($("paintColor") as HTMLInputElement)?.value,
      };
      localStorage.setItem(LAYOUT_KEY, JSON.stringify(data));
    } catch(_) {}
  }, 150);
}

export function restoreLayout() {
  try {
    const json = localStorage.getItem(LAYOUT_KEY);
    if (!json) return;
    const data = JSON.parse(json) as LayoutState;
    
    const lp = $("leftPanel");
    const rp = $("rightPanel");
    const bp = $("bottomPanel");
    if (data.leftW && lp) lp.style.width = data.leftW;
    if (data.rightW && rp) rp.style.width = data.rightW;
    if (data.bottomH && bp) bp.style.height = data.bottomH;
    
    if (data.tool) setActiveTool(data.tool);
    if (data.profileTarget) { 
       // Note: profileTarget setting should happen via API if needed, 
       // handled here indirectly or manually in main.ts
    }
    if (data.brushSize) ($("brushSize") as HTMLInputElement).value = data.brushSize;
    if (data.showMask !== undefined) ($("showMask") as HTMLInputElement).checked = data.showMask;
    if (data.maskOpacity) ($("maskOpacity") as HTMLInputElement).value = data.maskOpacity;
    if (data.showProfile !== undefined) ($("showProfile") as HTMLInputElement).checked = data.showProfile;
    if (data.fps) ($("animFpsSelect") as HTMLSelectElement).value = data.fps;
    
    const paintColorInput = $("paintColor") as HTMLInputElement;
    const swatchPreview = $("colorSwatchPreview");
    if (data.paintColor && paintColorInput && swatchPreview) {
      paintColorInput.value = data.paintColor;
      swatchPreview.style.backgroundColor = data.paintColor;
    }

    if (data.tab === "sheet") showTab("sheet");
    if (data.zoom != null) applyZoom(data.zoom, data.tab);
  } catch(_) {}
}
