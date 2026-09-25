"use strict";

const $ = id => document.getElementById(id);
const settings = ["rows", "cols", "colors", "threshold", "outline", "paint", "cleanup"];
const state = { base: null, outfit: null, result: null, mask: null, report: null, undo: [], busy: false, revision: 0 };
const corrections = document.createElement("canvas");
const correctionContext = corrections.getContext("2d", { willReadFrequently: true });
const baseMap = document.createElement("canvas");
const baseMapContext = baseMap.getContext("2d", { willReadFrequently: true });
const paintLayer = document.createElement("canvas");
const paintContext = paintLayer.getContext("2d", { willReadFrequently: true });
const storageKey = "outfit-repair-v2";
let stroke = null;
let profileKey = null;
let profileSource = null;
let profileGrid = null;

async function ensureProfile(force = false) {
  if (!state.base) throw new Error("Chọn ảnh base trước.");
  const g = grid();
  if (!g) throw new Error("Kiểm tra số hàng/cột của base.");
  const identity = `${g.cols}:${g.rows}`;
  if (!force && profileSource === state.base.src && profileGrid === identity) return;
  const source = state.base.src;
  const response = await fetch("/api/base-profile", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base: source, rows: g.rows, cols: g.cols, backgroundThreshold: Number($("threshold").value) }) });
  if (!response.ok) throw new Error("Không nhận diện được base. Kiểm tra grid và khởi động lại server bản mới.");
  const data = await response.json();
  let url = data.profile;
  if (!force) { try { url = localStorage.getItem(`sprite-base:${data.baseId}`) || url; } catch (_) {} }
  const img = await loadImage(url);
  if (state.base.src !== source || `${grid()?.cols}:${grid()?.rows}` !== identity) throw new Error("Base đã thay đổi trong lúc nhận diện; thử lại.");
  if (img.width !== state.base.width || img.height !== state.base.height) throw new Error("Bản đồ base lưu trước đó sai kích thước.");
  if (force && profileKey) checkpoint(baseMap);
  baseMap.width = img.width; baseMap.height = img.height;
  baseMapContext.drawImage(img, 0, 0);
  profileKey = data.baseId; profileSource = source; profileGrid = identity;
  $("profileStatus").textContent = "Đã cố định vị trí đầu/tay từ base. Sửa trên khung base; bản đồ được lưu riêng và dùng lại khi đổi outfit.";
  render();
}

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
    sessionStorage.setItem(storageKey, JSON.stringify({ version: 4, values, base: state.base?.src, outfit: state.outfit?.src,
      corrections: state.base ? corrections.toDataURL() : null }));
  } catch (_) { /* Large uploads may exceed the browser's session storage quota. */ }
  try {
    if (profileKey) localStorage.setItem(`sprite-base:${profileKey}`, baseMap.toDataURL());
    sessionStorage.setItem(`${storageKey}:paint`, paintLayer.toDataURL());
  } catch (_) { $("profileStatus").textContent = "Bộ nhớ trình duyệt đã đầy. Dùng Lưu bản đồ base / Lưu lớp màu tô để giữ các chỉnh sửa."; }
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
  paintLayer.width = reference.width; paintLayer.height = reference.height;
  if (kind === "base") {
    baseMap.width = reference.width; baseMap.height = reference.height;
    profileKey = profileSource = profileGrid = null;
  }
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
  const baseContext = drawCrop($("baseCanvas"), state.base, g);
  if (g && profileKey && ($("showProfile").checked || $("brush").value.startsWith("profile"))) {
    baseContext.globalAlpha = 0.4;
    baseContext.drawImage(baseMap, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    baseContext.globalAlpha = 1;
  }
  drawCrop($("outfitCanvas"), state.outfit, g);
  const ctx = drawCrop($("editCanvas"), state.result || state.outfit, g);
  if (g) {
    ctx.drawImage(paintLayer, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    if ($("showMask").checked && state.mask) {
      ctx.globalAlpha = Number($("maskOpacity").value) / 100;
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
function checkpoint(canvas = corrections, rect = null, extra = []) {
  const box = rect || { x: 0, y: 0, w: canvas.width, h: canvas.height };
  const data = canvas.getContext("2d").getImageData(box.x, box.y, box.w, box.h);
  const other = extra.map(layer => ({ canvas: layer, data: layer.getContext("2d").getImageData(box.x, box.y, box.w, box.h) }));
  state.undo.push({ canvas, data, x: box.x, y: box.y, other });
  if (state.undo.length > 12) state.undo.shift();
  while (state.undo.length > 1 && state.undo.reduce((n, item) => n + item.data.data.length + item.other.reduce((m, layer) => m + layer.data.data.length, 0), 0) > 48000000) state.undo.shift();
}
function point(event, canvas = event.currentTarget) {
  const rect = canvas.getBoundingClientRect();
  return { x: Math.floor((event.clientX - rect.left) * canvas.width / rect.width),
    y: Math.floor((event.clientY - rect.top) * canvas.height / rect.height) };
}
function dab(p, g, mode) {
  const size = Number($("brushSize").value), half = Math.floor(size / 2);
  const x = Math.max(0, p.x - half), y = Math.max(0, p.y - half);
  const w = Math.min(g.w, p.x + half + 1) - x, h = Math.min(g.h, p.y + half + 1) - y;
  if (w <= 0 || h <= 0) return;
  const context = mode.startsWith("profile") ? baseMapContext : ["color", "unpaint"].includes(mode) ? paintContext : correctionContext;
  if (context === correctionContext) paintContext.clearRect(g.x + x, g.y + y, w, h);
  if (["auto", "profileErase", "unpaint"].includes(mode)) context.clearRect(g.x + x, g.y + y, w, h);
  else {
    context.fillStyle = { base: "#ff0000", outfit: "#0000ff", erase: "#00ff00", profileHead: "#ff0000", profileHand: "#ff8000", color: $("paintColor").value }[mode];
    context.fillRect(g.x + x, g.y + y, w, h);
  }
}
for (const canvas of [$("baseCanvas"), $("editCanvas")]) canvas.addEventListener("pointerdown", event => {
  const g = grid();
  const mode = $("brush").value, isProfile = mode.startsWith("profile");
  if (!g || !state.base || state.busy || mode === "inspect" || event.button !== 0) return;
  if (isProfile !== (canvas.id === "baseCanvas")) return status(isProfile ? "Tô trên khung base để sửa đầu/tay." : "Tô trên khung kết quả.");
  if (isProfile && !profileKey) return status("Bấm Nhận diện lại base trước khi sửa bản đồ.");
  if (!isProfile && !state.outfit) return;
  const p = point(event);
  if (mode === "sample") {
    const sample = document.createElement("canvas"); sample.width = g.w; sample.height = g.h;
    const ctx = sample.getContext("2d");
    ctx.drawImage(state.result || state.outfit, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    ctx.drawImage(paintLayer, g.x, g.y, g.w, g.h, 0, 0, g.w, g.h);
    const rgb = ctx.getImageData(p.x, p.y, 1, 1).data;
    $("paintColor").value = '#' + [...rgb].slice(0, 3).map(n => n.toString(16).padStart(2, '0')).join('');
    $("brush").value = "color"; render(); return;
  }
  const layer = isProfile ? baseMap : ["color", "unpaint"].includes(mode) ? paintLayer : corrections;
  checkpoint(layer, g, layer === corrections ? [paintLayer] : []);
  stroke = { point: p, grid: g, canvas, mode };
  canvas.setPointerCapture(event.pointerId);
  dab(stroke.point, g, mode);
  invalidate("Vùng chỉnh đã đổi. Bấm Xử lý sprite để áp dụng.");
  render();
});
for (const canvas of [$("baseCanvas"), $("editCanvas")]) canvas.addEventListener("pointermove", event => {
  if (!stroke || stroke.canvas !== canvas) return;
  const next = point(event), previous = stroke.point;
  const steps = Math.max(Math.abs(next.x - previous.x), Math.abs(next.y - previous.y), 1);
  for (let i = 1; i <= steps; i++) dab({ x: Math.round(previous.x + (next.x - previous.x) * i / steps),
    y: Math.round(previous.y + (next.y - previous.y) * i / steps) }, stroke.grid, stroke.mode);
  stroke.point = next;
  render();
});
for (const canvas of [$("baseCanvas"), $("editCanvas")]) for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) canvas.addEventListener(name, () => {
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
for (const id of ["frame", "zoom", "sheetZoom", "showMask", "brush", "showProfile", "maskOpacity"]) $(id).addEventListener("change", render);
$("maskOpacity").addEventListener("input", render);
$("frame").addEventListener("input", () => {
  const value = Number($("frame").value);
  if (Number.isInteger(value) && value >= 1 && value <= (grid()?.count || 1)) render();
});
$("prev").onclick = () => { $("frame").value = Math.max(1, Number($("frame").value) - 1); render(); };
$("next").onclick = () => { $("frame").value = Math.min(grid()?.count || 1, Number($("frame").value) + 1); render(); };
$("undo").onclick = () => {
  const item = state.undo.pop();
  if (item) {
    item.canvas.getContext("2d").putImageData(item.data, item.x, item.y);
    for (const other of item.other) other.canvas.getContext("2d").putImageData(other.data, item.x, item.y);
    invalidate(); render(); remember();
  }
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
$("analyzeBase").onclick = async () => {
  if (state.busy) return;
  state.busy = true;
  try { await ensureProfile(true); $("showProfile").checked = true; invalidate("Đã nhận diện đầu/tay từ base. Có thể tô sửa trên khung base."); remember(); }
  catch (error) { status(error.message, true); }
  finally { state.busy = false; render(); }
};
$("saveProfile").onclick = async () => {
  try {
    await ensureProfile();
    const g = grid();
    const document = { version: 1, baseId: profileKey, rows: g.rows, cols: g.cols, mask: baseMap.toDataURL() };
    const url = URL.createObjectURL(new Blob([JSON.stringify(document)], { type: "application/json" }));
    download(url, "base-anatomy.json"); setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { status(error.message, true); }
};
$("loadProfile").onchange = async event => {
  const file = event.target.files[0];
  if (!file || state.busy) return;
  try {
    await ensureProfile();
    const data = JSON.parse(await file.text());
    if (data.version !== 1 || data.baseId !== profileKey) throw new Error("Bản đồ không thuộc base và grid đang chọn.");
    const img = await loadImage(data.mask);
    if (img.width !== baseMap.width || img.height !== baseMap.height) throw new Error("Bản đồ sai kích thước.");
    checkpoint(baseMap); baseMapContext.clearRect(0, 0, baseMap.width, baseMap.height);
    baseMapContext.drawImage(img, 0, 0); $("showProfile").checked = true;
    invalidate(); render(); remember();
  } catch (error) { status(error.message, true); }
  event.target.value = "";
};
$("savePaint").onclick = () => { if (state.base) download(paintLayer.toDataURL(), "outfit-retouch.png"); };
$("loadPaint").onchange = async event => {
  const file = event.target.files[0];
  if (!file || !state.base || state.busy) return;
  try {
    const img = await loadImage(await readFile(file));
    if (img.width !== paintLayer.width || img.height !== paintLayer.height) throw new Error("Lớp màu phải cùng kích thước base.");
    checkpoint(paintLayer); paintContext.clearRect(0, 0, paintLayer.width, paintLayer.height);
    paintContext.drawImage(img, 0, 0); invalidate(); render(); remember();
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
    await ensureProfile();
    const response = await fetch("/api/repair", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
      base: state.base.src, outfit: state.outfit.src, rows: g.rows, cols: g.cols,
      colors: Number($("colors").value), backgroundThreshold: Number($("threshold").value), skinExpand: 0,
      outline: $("outline").checked, cleanup: Number($("cleanup").value), paint: Number($("paint").value), overrides: corrections.toDataURL(),
      lockBase: true, baseProfile: baseMap.toDataURL(), retouch: paintLayer.toDataURL()
    }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Không xử lý được ảnh.");
    if ((result.report?.version || 0) < 5) throw new Error("Server đang chạy thuật toán cũ. Khởi động lại tools/repair_outfit_ui.py để dùng bản tô màu giữ nếp áo và đai.");
    const [image, mask] = await Promise.all([loadImage(result.image), loadImage(result.mask)]);
    if (revision !== state.revision) return status("Thiết lập đã đổi trong khi xử lý. Bấm Xử lý sprite để cập nhật.");
    state.result = image; state.mask = mask; state.report = result.report;
    $("resultPreview").src = result.image;
    $("resultStage").classList.add("loaded");
    $("resultMeta").textContent = `${result.width} × ${result.height} · ${result.frameCount} frame · ${result.paletteColors} màu`;
    $("download").disabled = $("downloadReport").disabled = false;
    status(`Hoàn tất: ${result.paletteColors} màu. Đầu/tay dùng bản đồ base cố định; ${result.restoredPixels.toLocaleString("vi-VN")} pixel lấy từ base. Có thể sửa bản đồ hoặc tô màu/bóng trực tiếp rồi xử lý lại.`);
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
      if (saved.version !== 4) $("paint").value = "3";
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
  if (location.protocol === "file:") {
    $("fileNotice").hidden = false; $("repair").disabled = true;
    status("Trang đang mở dạng file. Chạy server local và mở http://127.0.0.1:8765/ để xử lý.", true);
  }
  render();
})();
