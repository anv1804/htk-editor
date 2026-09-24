"use strict";

const $ = id => document.getElementById(id);
const settings = ["rows", "cols", "colors", "threshold", "outline", "paint", "cleanup"];
const state = { base: null, outfit: null, result: null, mask: null, report: null, undo: [], busy: false, revision: 0 };
const corrections = document.createElement("canvas");
const correctionContext = corrections.getContext("2d", { willReadFrequently: true });
const storageKey = "outfit-repair-v2";
let stroke = null;

function status(message, error = false) {
  $("status").textContent = message;
  $("status").className = error ? "status error" : "status";
}
function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Không đọc được ảnh."));
    reader.readAsDataURL(file);
  });
}
function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Ảnh không hợp lệ."));
    img.src = url;
  });
}
function grid() {
  const cols = Number($("cols").value), rows = Number($("rows").value);
  const img = state.base || state.outfit;
  if (!img || !Number.isInteger(cols) || !Number.isInteger(rows) || cols < 1 || rows < 1 || cols > 64 || rows > 64) return null;
  if (img.width % cols || img.height % rows) return null;
  const count = rows * cols;
  const frame = Math.min(count, Math.max(1, Math.trunc(Number($("frame").value)) || 1)) - 1;
  return { cols, rows, count, frame, w: img.width / cols, h: img.height / rows,
    x: (frame % cols) * img.width / cols, y: Math.floor(frame / cols) * img.height / rows };
}
function remember() {
  try {
    const values = Object.fromEntries(settings.map(id => [id, id === "outline" ? $(id).checked : $(id).value]));
    sessionStorage.setItem(storageKey, JSON.stringify({ values, base: state.base?.src, outfit: state.outfit?.src,
      corrections: state.base ? corrections.toDataURL() : null }));
  } catch (_) { /* Large uploads may exceed the browser's session storage quota. */ }
}
function invalidate(message = "Thiết lập đã đổi. Bấm Xử lý sprite để cập nhật.") {
  state.revision++;
  $("download").disabled = true;
  $("downloadReport").disabled = true;
  if (state.base && state.outfit) status(message);
}
function clearResult() {
  state.result = state.mask = state.report = null;
  $("resultStage").classList.remove("loaded");
  $("resultPreview").removeAttribute("src");
  $("resultMeta").textContent = "";
  invalidate();
}
async function setSource(kind, url) {
  const img = await loadImage(url);
  if (img.width * img.height > 4194304) throw new Error("Ảnh vượt quá 4 triệu pixel.");
  state[kind] = img;
  $(kind + "Preview").src = url;
  $(kind + "Drop").classList.add("loaded");
  $(kind + "Meta").textContent = `${img.width} × ${img.height}`;
  const reference = state.base || img;
  corrections.width = reference.width;
  corrections.height = reference.height;
  state.undo = [];
  clearResult();
  render();
}
function drawCrop(canvas, image, g) {
  canvas.width = g?.w || 64;
  canvas.height = g?.h || 64;
  const zoom = Number($("zoom").value);
  canvas.style.width = `${canvas.width * zoom}px`;
  canvas.style.height = `${canvas.height * zoom}px`;
  const context = canvas.getContext("2d");
  context.imageSmoothingEnabled = false;
  if (image && g) context.drawImage(image, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
  return context;
}
function render() {
  const g = grid();
  if (g) { $("frame").max = g.count; $("frame").value = g.frame + 1; }
  const frameWidth = (g?.w || 64) * Number($("zoom").value) + 2;
  document.querySelector(".frame-grid").style.gridTemplateColumns = `repeat(auto-fit, minmax(min(100%, ${frameWidth}px), 1fr))`;
  drawCrop($("baseCanvas"), state.base, g);
  drawCrop($("outfitCanvas"), state.outfit, g);
  const ctx = drawCrop($("editCanvas"), state.result || state.outfit, g);
  if (g) {
    if ($("showMask").checked && state.mask) {
      ctx.globalAlpha = 0.5;
      ctx.drawImage(state.mask, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    }
    ctx.globalAlpha = 0.65;
    ctx.drawImage(corrections, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    ctx.globalAlpha = 1;
  }
  $("undo").disabled = !state.undo.length || state.busy;
  $("editCanvas").style.cursor = $("brush").value === "inspect" ? "default" : "crosshair";
  if (state.result) {
    const zoom = Number($("sheetZoom").value);
    $("resultPreview").style.width = `${state.result.width * zoom}px`;
    $("resultPreview").style.height = `${state.result.height * zoom}px`;
  }
}
function checkpoint() {
  state.undo.push(correctionContext.getImageData(0, 0, corrections.width, corrections.height));
  if (state.undo.length > 12) state.undo.shift();
}
function point(event) {
  const rect = $("editCanvas").getBoundingClientRect();
  return { x: Math.floor((event.clientX - rect.left) * $("editCanvas").width / rect.width),
    y: Math.floor((event.clientY - rect.top) * $("editCanvas").height / rect.height) };
}
function dab(p, g) {
  const size = Number($("brushSize").value), half = Math.floor(size / 2);
  const x = Math.max(0, p.x - half), y = Math.max(0, p.y - half);
  const w = Math.min(g.w, p.x + half + 1) - x, h = Math.min(g.h, p.y + half + 1) - y;
  if (w <= 0 || h <= 0) return;
  if ($("brush").value === "auto") correctionContext.clearRect(g.x + x, g.y + y, w, h);
  else {
    correctionContext.fillStyle = { base: "#ff0000", outfit: "#0000ff", erase: "#00ff00" }[$("brush").value];
    correctionContext.fillRect(g.x + x, g.y + y, w, h);
  }
}
$("editCanvas").addEventListener("pointerdown", event => {
  const g = grid();
  if (!g || !state.base || !state.outfit || state.busy || $("brush").value === "inspect" || event.button !== 0) return;
  checkpoint();
  stroke = { point: point(event), grid: g };
  $("editCanvas").setPointerCapture(event.pointerId);
  dab(stroke.point, g);
  invalidate("Vùng chỉnh đã đổi. Bấm Xử lý sprite để áp dụng.");
  render();
});
$("editCanvas").addEventListener("pointermove", event => {
  if (!stroke) return;
  const next = point(event), previous = stroke.point;
  const steps = Math.max(Math.abs(next.x - previous.x), Math.abs(next.y - previous.y), 1);
  for (let i = 1; i <= steps; i++) dab({ x: Math.round(previous.x + (next.x - previous.x) * i / steps),
    y: Math.round(previous.y + (next.y - previous.y) * i / steps) }, stroke.grid);
  stroke.point = next;
  render();
});
for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) $("editCanvas").addEventListener(name, () => {
  if (stroke) { stroke = null; remember(); }
});
function download(url, filename) {
  const link = document.createElement("a");
  link.href = url; link.download = filename; link.click();
}
for (const kind of ["base", "outfit"]) {
  const accept = async file => {
    if (!file || state.busy) return;
    try { await setSource(kind, await readFile(file)); remember(); }
    catch (error) { status(error.message, true); }
  };
  $(kind + "File").addEventListener("change", event => accept(event.target.files[0]));
  const drop = $(kind + "Drop");
  drop.addEventListener("dragover", event => { event.preventDefault(); drop.classList.add("drag"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
  drop.addEventListener("drop", event => { event.preventDefault(); drop.classList.remove("drag"); accept(event.dataTransfer.files[0]); });
  drop.addEventListener("keydown", event => { if (event.key === "Enter") $(kind + "File").click(); });
}
for (const id of settings) $(id).addEventListener("change", () => { invalidate(); render(); remember(); });
for (const id of ["frame", "zoom", "sheetZoom", "showMask", "brush"]) $(id).addEventListener("change", render);
$("frame").addEventListener("input", () => {
  const value = Number($("frame").value);
  if (Number.isInteger(value) && value >= 1 && value <= (grid()?.count || 1)) render();
});
$("prev").onclick = () => { $("frame").value = Math.max(1, Number($("frame").value) - 1); render(); };
$("next").onclick = () => { $("frame").value = Math.min(grid()?.count || 1, Number($("frame").value) + 1); render(); };
$("undo").onclick = () => {
  const data = state.undo.pop();
  if (data) { correctionContext.putImageData(data, 0, 0); invalidate(); render(); remember(); }
};
$("clearFrame").onclick = () => {
  const g = grid();
  if (!g || state.busy) return;
  checkpoint(); correctionContext.clearRect(g.x, g.y, g.w, g.h); invalidate(); render(); remember();
};
$("saveMask").onclick = () => { if (state.base) download(corrections.toDataURL(), "outfit-corrections.png"); };
$("loadMask").onchange = async event => {
  const file = event.target.files[0];
  if (!file || !state.base || state.busy) return;
  try {
    const img = await loadImage(await readFile(file));
    if (img.width !== corrections.width || img.height !== corrections.height) throw new Error("Vùng chỉnh phải có cùng kích thước với base.");
    checkpoint(); correctionContext.clearRect(0, 0, corrections.width, corrections.height);
    correctionContext.drawImage(img, 0, 0); invalidate(); render(); remember();
  } catch (error) { status(error.message, true); }
  event.target.value = "";
};
$("repair").onclick = async () => {
  if (state.busy) return;
  if (!state.base || !state.outfit) return status("Chọn đủ ảnh base và outfit.", true);
  if (state.base.width !== state.outfit.width || state.base.height !== state.outfit.height) return status("Hai ảnh phải cùng kích thước.", true);
  const g = grid();
  if (!g) return status("Kích thước ảnh phải chia hết cho số hàng và cột (1–64).", true);
  const revision = state.revision;
  state.busy = true;
  $("repair").disabled = true;
  $("download").disabled = $("downloadReport").disabled = true;
  status("Đang tách vùng, tô màu và hoàn thiện viền…");
  try {
    const response = await fetch("/api/repair", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      base: state.base.src, outfit: state.outfit.src, rows: g.rows, cols: g.cols,
      colors: Number($("colors").value), backgroundThreshold: Number($("threshold").value), skinExpand: 0,
      outline: $("outline").checked, cleanup: Number($("cleanup").value), paint: Number($("paint").value), overrides: corrections.toDataURL()
    }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Không xử lý được ảnh.");
    if ((result.report?.version || 0) < 3) throw new Error("Server đang chạy thuật toán cũ. Khởi động lại tools/repair_outfit_ui.py để dùng bản sửa tay áo và cổ.");
    const [image, mask] = await Promise.all([loadImage(result.image), loadImage(result.mask)]);
    if (revision !== state.revision) return status("Thiết lập đã đổi trong khi xử lý. Bấm Xử lý sprite để cập nhật.");
    state.result = image; state.mask = mask; state.report = result.report;
    $("resultPreview").src = result.image;
    $("resultStage").classList.add("loaded");
    $("resultMeta").textContent = `${result.width} × ${result.height} · ${result.frameCount} frame · ${result.paletteColors} màu`;
    $("download").disabled = $("downloadReport").disabled = false;
    status(`Hoàn tất: ${result.paletteColors} màu. Giữ ${result.restoredPixels.toLocaleString("vi-VN")} pixel base trong vùng da lộ ra; vá ${result.reconstructedPixels.toLocaleString("vi-VN")} pixel cổ/tay. Trang phục che phần thân và cánh tay bên dưới.`);
    remember();
  } catch (error) {
    status(error instanceof TypeError ? "Không kết nối được server. Chạy tools/repair_outfit_ui.py rồi mở http://127.0.0.1:8765/." : error.message, true);
  } finally {
    state.busy = false; $("repair").disabled = location.protocol === "file:"; render();
  }
};
$("download").onclick = () => { if (state.result) download(state.result.src, "outfit-repaired.png"); };
$("downloadReport").onclick = () => {
  if (!state.report) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(state.report, null, 2)], { type: "application/json" }));
  download(url, "outfit-report.json"); setTimeout(() => URL.revokeObjectURL(url), 1000);
};
(async () => {
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
    if (saved) {
      for (const id of settings) if (saved.values?.[id] !== undefined) {
        if (id === "outline") $(id).checked = saved.values[id]; else $(id).value = saved.values[id];
      }
      if (saved.base) await setSource("base", saved.base);
      if (saved.outfit) await setSource("outfit", saved.outfit);
      if (saved.corrections && state.base) {
        const img = await loadImage(saved.corrections);
        if (img.width === corrections.width && img.height === corrections.height) correctionContext.drawImage(img, 0, 0);
      }
    }
  } catch (_) { status("Chọn lại ảnh để bắt đầu."); }
  if (location.protocol === "file:") {
    $("fileNotice").hidden = false; $("repair").disabled = true;
    status("Trang đang mở dạng file. Chạy server local và mở http://127.0.0.1:8765/ để xử lý.", true);
  }
  render();
})();
