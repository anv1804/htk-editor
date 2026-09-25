import { state, baseMap, profileState, setProfileState, corrections, paintLayer } from './state';
import { $, loadImage } from './utils';
import { grid, checkpoint, render } from './editor';

export async function ensureProfile(force = false) {
  if (!state.base) throw new Error("Chọn ảnh base trước.");
  const g = grid();
  if (!g) throw new Error("Kiểm tra số hàng/cột của base.");
  
  const identity = `${g.cols}:${g.rows}`;
  if (!force && profileState.source === state.base.src && profileState.grid === identity) return;
  
  const source = state.base.src;
  const threshold = Number(($("threshold") as HTMLInputElement).value);
  
  const response = await fetch("/api/base-profile", { 
    method: "POST", 
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base: source, rows: g.rows, cols: g.cols, backgroundThreshold: threshold }) 
  });
  
  if (!response.ok) throw new Error("Không nhận diện được base. Kiểm tra grid và khởi động lại server bản mới.");
  
  const data = await response.json();
  let url = data.profile;
  if (!force) { 
    try { url = localStorage.getItem(`sprite-base:${data.baseId}`) || url; } catch (_) {} 
  }
  
  const img = await loadImage(url);
  if (state.base.src !== source || `${grid()?.cols}:${grid()?.rows}` !== identity) {
    throw new Error("Base đã thay đổi trong lúc nhận diện; thử lại.");
  }
  if (img.width !== state.base.width || img.height !== state.base.height) {
    throw new Error("Bản đồ base lưu trước đó sai kích thước.");
  }
  
  if (force && profileState.key) checkpoint(baseMap);
  baseMap.width = img.width; 
  baseMap.height = img.height;
  const baseMapContext = baseMap.getContext("2d")!;
  baseMapContext.drawImage(img, 0, 0);
  
  setProfileState(data.baseId, source, identity);
  $("profileStatus").textContent = "Đã cố định vị trí đầu/tay từ base. Sửa trên khung base; bản đồ được lưu riêng và dùng lại khi đổi outfit.";
  render();
}

// Ensure repair is called in main.ts logic or we can export a doRepair function
export async function doRepair() {
    const g = grid();
    if (!g) return;
    const threshold = Number(($("threshold") as HTMLInputElement).value);
    const cleanup = Number(($("cleanup") as HTMLInputElement).value);
    const paint = Number(($("paint") as HTMLInputElement).value);
    const colors = Number(($("colors") as HTMLInputElement).value);
    const outline = ($("outline") as HTMLInputElement).checked;
    const composition = ($("composition") as HTMLSelectElement).value;

    const response = await fetch("/api/repair", { 
      method: "POST", 
      headers: { "Content-Type": "application/json" }, 
      body: JSON.stringify({
        base: state.base!.src, 
        outfit: state.outfit!.src, 
        rows: g.rows, 
        cols: g.cols,
        colors: colors, 
        backgroundThreshold: threshold, 
        skinExpand: 0,
        outline: outline, 
        cleanup: cleanup, 
        paint: paint, 
        overrides: corrections.toDataURL(),
        composition: composition,
        lockBase: true, 
        baseProfile: composition === 'pinned' ? baseMap.toDataURL() : null, 
        retouch: paintLayer.toDataURL()
    }) });
    return response;
}
