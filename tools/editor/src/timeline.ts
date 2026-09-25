import type { AnimationDef } from './types';
import { state } from './state';
import { $ } from './utils';

export const ANIMATION_DEFS: AnimationDef[] = [
  { id: "preview", name: "Nhìn thẳng (Preview)", row: 1, cols: [1, 2], frames: [1, 2], color: "#38bdf8" },
  { id: "idle",    name: "Thở đứng (Idle)",        row: 1, cols: [3, 4], frames: [3, 4], color: "#2dd4bf" },
  { id: "archery", name: "Bắn cung",              row: 2, cols: [1, 2, 3, 4], frames: [5, 6, 7, 8], color: "#fbbf24" },
  { id: "spear",   name: "Đâm thương",            row: 3, cols: [1, 2, 3, 4], frames: [9, 10, 11, 12], color: "#f87171" },
  { id: "jump",    name: "Nhảy (Jump)",           row: 4, cols: [1, 2, 3, 4], frames: [13, 14, 15, 16], color: "#a855f7" },
  { id: "slash",   name: "Vung kiếm (Slash)",     row: 5, cols: [1, 2, 3, 4], frames: [17, 18, 19, 20], color: "#ec4899" },
  { id: "walk",    name: "Đi bộ (Walk)",          row: 6, cols: [1, 2, 3, 4], frames: [21, 22, 23, 24], color: "#3b82f6" },
  { id: "run",     name: "Chạy (Run)",            row: 7, cols: [1, 2, 3, 4], frames: [25, 26, 27, 28], color: "#10b981" }
];

export let isPlaying = false;
let playTimer: number | null = null;
let animPlayFrameIdx = 0;

export function renderAnimationTimeline() {
  const matrixScrollEl = $("timelineMatrixScroll");
  const frameInput = $("frame") as HTMLInputElement;
  if (!matrixScrollEl || !frameInput) return;
  const currentFrame = parseInt(frameInput.value, 10) || 1;
  let activeAnim = ANIMATION_DEFS.find(a => a.frames.includes(currentFrame)) || ANIMATION_DEFS[0];

  const currentAnimBadge = $("currentAnimBadge");
  if (currentAnimBadge) currentAnimBadge.textContent = `${activeAnim.name} (F${currentFrame})`;
  if ($("playerAnimName")) $("playerAnimName").textContent = activeAnim.name.toUpperCase();
  if ($("playerFrameBadge")) $("playerFrameBadge").textContent = `F${currentFrame}`;

  if (matrixScrollEl.childElementCount === 0) {
    matrixScrollEl.innerHTML = "";
    ANIMATION_DEFS.forEach(anim => {
      const row = document.createElement("div");
      row.className = "anim-row" + (anim.id === activeAnim.id ? " current-row" : "");
      row.dataset.animId = anim.id;

      let framesHtml = "";
      anim.frames.forEach((f, idx) => {
        framesHtml += `
          <div class="frame-card ${f === currentFrame ? 'active' : ''}" data-frame="${f}" title="${anim.name} · C${anim.cols[idx]}">
            <div class="frame-card-idx">F${f}</div>
            <div class="frame-card-canvas-box"><canvas width="32" height="32" id="thumbCanvas_${f}"></canvas></div>
          </div>`;
      });

      row.innerHTML = `
        <div class="anim-row-title-box" title="${anim.name}">
          <span class="anim-row-dot" style="background:${anim.color}"></span>
          <span class="anim-row-label">${anim.name}</span>
        </div>
        <div class="anim-frames-strip">${framesHtml}</div>`;

      row.querySelector(".anim-row-title-box")!.addEventListener("click", () => {
        frameInput.value = anim.frames[0].toString();
        frameInput.dispatchEvent(new Event("change"));
      });
      row.querySelectorAll(".frame-card").forEach(card => {
        card.addEventListener("click", (e) => {
          e.stopPropagation();
          frameInput.value = (card as HTMLElement).dataset.frame!;
          frameInput.dispatchEvent(new Event("change"));
        });
      });
      matrixScrollEl.appendChild(row);
    });
  } else {
    matrixScrollEl.querySelectorAll(".anim-row").forEach(row => {
      row.classList.toggle("current-row", (row as HTMLElement).dataset.animId === activeAnim.id);
    });
    matrixScrollEl.querySelectorAll(".frame-card").forEach(card => {
      card.classList.toggle("active", parseInt((card as HTMLElement).dataset.frame!, 10) === currentFrame);
    });
  }
  updateFrameThumbnails();
  renderLivePlayerFrame(currentFrame);
}

export function updateFrameThumbnails() {
  const srcImg = state.result || state.outfit || state.base;
  if (!srcImg) return;
  const cols = Number(($("cols") as HTMLInputElement)?.value) || 4;
  const rows = Number(($("rows") as HTMLInputElement)?.value) || 7;
  const fw = srcImg.width / cols, fh = srcImg.height / rows;
  const frameInput = $("frame") as HTMLInputElement;
  const currentFrame = parseInt(frameInput?.value, 10) || 1;
  const editCanvas = $("editCanvas") as HTMLCanvasElement;

  for (let f = 1; f <= cols * rows; f++) {
    const cvs = $(`thumbCanvas_${f}`) as HTMLCanvasElement;
    if (!cvs) continue;
    const ctx = cvs.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, cvs.width, cvs.height);
    if (f === currentFrame && editCanvas && editCanvas.width > 0) {
      ctx.drawImage(editCanvas, 0, 0, editCanvas.width, editCanvas.height, 0, 0, cvs.width, cvs.height);
    } else {
      const colIdx = (f - 1) % cols, rowIdx = Math.floor((f - 1) / cols);
      ctx.drawImage(srcImg, colIdx * fw, rowIdx * fh, fw, fh, 0, 0, cvs.width, cvs.height);
    }
  }
}

export function renderLivePlayerFrame(frameNumber: number) {
  const animPreviewCanvas = $("animPreviewCanvas") as HTMLCanvasElement;
  if (!animPreviewCanvas) return;
  const srcImg = state.result || state.outfit || state.base;
  if (!srcImg) return;
  const cols = Number(($("cols") as HTMLInputElement)?.value) || 4;
  const rows = Number(($("rows") as HTMLInputElement)?.value) || 7;
  const fw = srcImg.width / cols, fh = srcImg.height / rows;
  animPreviewCanvas.width = fw;
  animPreviewCanvas.height = fh;
  animPreviewCanvas.style.setProperty("--grid-w", `${fw}`);
  animPreviewCanvas.style.setProperty("--grid-h", `${fh}`);
  const ctx = animPreviewCanvas.getContext("2d")!;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, fw, fh);

  const frameInput = $("frame") as HTMLInputElement;
  const currentFrame = parseInt(frameInput?.value, 10) || 1;
  const editCanvas = $("editCanvas") as HTMLCanvasElement;

  if (frameNumber === currentFrame && editCanvas && editCanvas.width > 0) {
    ctx.drawImage(editCanvas, 0, 0, editCanvas.width, editCanvas.height, 0, 0, fw, fh);
  } else {
    const colIdx = (frameNumber - 1) % cols, rowIdx = Math.floor((frameNumber - 1) / cols);
    ctx.drawImage(srcImg, colIdx * fw, rowIdx * fh, fw, fh, 0, 0, fw, fh);
  }
  if ($("playerFrameBadge")) $("playerFrameBadge").textContent = `F${frameNumber}`;
}

export function togglePlayPause() {
  isPlaying = !isPlaying;
  const btnPlayPause = $("btnPlayPause");
  if (isPlaying) {
    if (btnPlayPause) {
      btnPlayPause.textContent = "❚❚ STOP";
      btnPlayPause.style.background = "#f43f5e";
      btnPlayPause.style.color = "#fff";
    }
    startPlaybackLoop();
  } else {
    if (btnPlayPause) {
      btnPlayPause.textContent = "▶ PLAY";
      btnPlayPause.style.background = "";
      btnPlayPause.style.color = "";
    }
    stopPlaybackLoop();
  }
}

export function startPlaybackLoop() {
  const animFpsSelect = $("animFpsSelect") as HTMLSelectElement;
  const frameInput = $("frame") as HTMLInputElement;
  const fps = parseInt(animFpsSelect?.value, 10) || 8;
  playTimer = window.setInterval(() => {
    const currentFrame = parseInt(frameInput?.value, 10) || 1;
    let activeAnim = ANIMATION_DEFS.find(a => a.frames.includes(currentFrame)) || ANIMATION_DEFS[0];
    animPlayFrameIdx = (animPlayFrameIdx + 1) % activeAnim.frames.length;
    renderLivePlayerFrame(activeAnim.frames[animPlayFrameIdx]);
  }, 1000 / fps);
}

export function stopPlaybackLoop() {
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
}
