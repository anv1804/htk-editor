import { loadImage, readFile } from './utils';
import type { SceneAsset } from './map-scene-model';

type PixelInput = { id: string; name: string; image: string };
export type PixelResult = { id: string; name: string; image: string; width: number; height: number; colors: number; partialAlphaPixels: number };
type Result = { items: PixelResult[]; elapsedSeconds: number; settings: { grid: number; colors: number }; note: string };
type Job = { id: string; state: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'; progress: number; message: string; elapsedSeconds: number };

export function setupMapPixel(getAssets: () => SceneAsset[], onApply: (result: Result, inputs: PixelInput[], uploaded: boolean) => Promise<void>) {
  const dialog = document.createElement('dialog'); dialog.className = 'mpw'; dialog.setAttribute('aria-labelledby', 'mpwTitle');
  dialog.innerHTML = `<div class="mpw-head"><div><h2 id="mpwTitle">Xử lý nét pixel · toàn map</h2><p>Gom mảng màu, giảm chấm vụn, giữ biên và chi tiết tương phản cao.</p></div><button id="mpwClose" aria-label="Đóng bàn xử lý pixel">×</button></div>
    <div class="mpw-body"><aside>
      <label>Nguồn xử lý<select id="mpwScope"><option value="map">Toàn bộ layer + module hiện tại</option><option value="upload">Một ảnh map gốc</option></select></label>
      <label class="mpw-file" id="mpwUploadLabel">Chọn ảnh map<input id="mpwUpload" type="file" accept="image/png,image/jpeg,image/webp"></label>
      <p id="mpwSource" class="mpw-muted"></p><hr>
      <label>Lưới pixel<select id="mpwGrid"><option value="1">1 px · giữ mật độ chi tiết</option><option value="2">2 px · cụm lớn hơn</option><option value="3">3 px</option><option value="4">4 px</option></select></label>
      <label>Bảng màu chung<select id="mpwColors"><option value="64">64 màu</option><option value="96">96 màu</option><option value="128" selected>128 màu</option><option value="192">192 màu</option><option value="256">256 màu</option></select></label>
      <label>Mức gom cụm<select id="mpwStrength"><option value="1">Nhẹ</option><option value="2" selected>Cân bằng</option><option value="3">Mạnh</option></select></label>
      <label>Lượt tinh chỉnh<select id="mpwPasses"><option value="2">2 lượt</option><option value="3" selected>3 lượt</option><option value="5">5 lượt</option></select></label>
      <label>Alpha<select id="mpwAlpha"><option value="preserve">Giữ gốc · phù hợp nước/sương</option><option value="hard">Cứng 0/255 · prop/terrain</option></select></label>
      <div class="mpw-reference"><img src="/assets/map-layer-reference/objects/gate_main.png" alt="Cổng mẫu từ 06_props"><span>Mẫu 06_props<br><small>Tham chiếu tương phản chi tiết</small></span></div>
      <button id="mpwStart" class="mpw-primary">Phân tích & xử lý</button><button id="mpwCancel" disabled>Hủy lượt xử lý</button><button id="mpwResume" hidden>Tiếp tục theo dõi</button>
      <p class="mpw-muted">Tối đa 5 phút tính toán/lượt, 16 triệu pixel và 32 MB tải lên. Hoàn tất sớm nếu đủ bước.</p>
    </aside><main>
      <div class="mpw-bar"><label>Ảnh<select id="mpwItem"></select></label><label>Xem<select id="mpwZoom"><option value="fit">Vừa khung</option><option value="1">100%</option><option value="2">200%</option><option value="4">400%</option></select></label></div>
      <div class="mpw-previews"><figure><figcaption>Nguồn gốc</figcaption><div><canvas id="mpwBefore" aria-label="Ảnh nguồn trước xử lý"></canvas></div></figure><figure><figcaption id="mpwAfterLabel">Kết quả chờ duyệt</figcaption><div><canvas id="mpwAfter" aria-label="Ảnh sau xử lý"></canvas></div></figure></div>
      <div class="mpw-progress"><progress id="mpwProgress" max="100" value="0"></progress><output id="mpwTime">0 giây</output></div><p id="mpwStatus" role="status">Sẵn sàng.</p>
      <p class="mpw-muted">Xử lý này không tự tách lớp theo nội dung, không vẽ bù phần bị che. Kết quả cần được xem ở 100% và 400% trước khi dùng.</p>
      <div class="mpw-actions"><button id="mpwApply" class="mpw-primary" disabled>Áp dụng bản đã xử lý</button></div>
    </main></div>`;
  document.body.append(dialog);
  const el = <T extends HTMLElement = HTMLElement>(id: string) => dialog.querySelector<T>(`#${id}`)!;
  const input = (id: string) => el<HTMLInputElement>(id);
  let inputs: PixelInput[] = [], upload: PixelInput | null = null, result: Result | null = null, job: Job | null = null;
  let tracking = false, loading = false, uploaded = false, selected = 0, drawToken = 0, reference: string | undefined;
  const running = () => loading || tracking || !!job && ['queued', 'running'].includes(job.state);
  const message = (s: string, error = false) => { el('mpwStatus').textContent = s; el('mpwStatus').dataset.error = String(error); };
  function controls() {
    const active = running();
    for (const id of ['mpwScope', 'mpwUpload', 'mpwGrid', 'mpwColors', 'mpwStrength', 'mpwPasses', 'mpwAlpha', 'mpwStart']) (el(id) as HTMLInputElement).disabled = active;
    el<HTMLButtonElement>('mpwCancel').disabled = !job || !['queued', 'running'].includes(job.state);
    el<HTMLButtonElement>('mpwApply').disabled = !result || active;
    el('mpwUploadLabel').hidden = input('mpwScope').value !== 'upload';
  }
  async function request<T>(url: string, body?: unknown): Promise<T> {
    const init: RequestInit = { signal: AbortSignal.timeout(body === undefined ? 60000 : 120000) };
    if (body !== undefined) { init.method = 'POST'; init.headers = { 'Content-Type': 'application/json' }; init.body = JSON.stringify(body); }
    const response = await fetch(url, init); const data = await response.json().catch(() => ({ error: 'Không đọc được phản hồi server. Khởi động lại server Python nếu vừa cập nhật.' }));
    if (!response.ok) throw new Error(data.error || `Yêu cầu thất bại (${response.status}).`); return data as T;
  }
  function list() {
    const select = el<HTMLSelectElement>('mpwItem'); select.replaceChildren();
    inputs.forEach((i, n) => { const option = document.createElement('option'); option.value = String(n); option.textContent = i.name; select.append(option); });
    selected = Math.min(selected, Math.max(0, inputs.length - 1)); select.value = String(selected);
    el('mpwSource').textContent = `${inputs.length} ảnh · ${input('mpwScope').value === 'upload' ? 'map phẳng' : 'xử lý đồng bộ từng ảnh, giữ cấu trúc lớp'}`;
  }
  async function draw() {
    const token = ++drawToken, item = inputs[selected]; if (!item) { for (const id of ['mpwBefore', 'mpwAfter']) { const c = el<HTMLCanvasElement>(id); c.width = c.height = 1; } return; }
    const after = result?.items.find(r => r.id === item.id);
    const [beforeImage, afterImage] = await Promise.all([loadImage(item.image), loadImage(after?.image || item.image)]);
    if (token !== drawToken) return;
    for (const [id, image] of [['mpwBefore', beforeImage], ['mpwAfter', afterImage]] as const) {
      const c = el<HTMLCanvasElement>(id); c.width = image.width; c.height = image.height; const ctx = c.getContext('2d')!; ctx.imageSmoothingEnabled = false; ctx.drawImage(image, 0, 0);
      const z = input('mpwZoom').value === 'fit' ? Math.min(1, Math.max(100, c.parentElement!.clientWidth - 20) / c.width, 410 / c.height) : Number(input('mpwZoom').value);
      c.style.width = `${c.width * z}px`; c.style.height = `${c.height * z}px`;
    }
    el('mpwAfterLabel').textContent = after ? `Kết quả · ${after.colors} màu · ${after.width} × ${after.height}` : 'Chưa xử lý';
  }
  async function sources() {
    if (running()) return;
    result = null; job = null; uploaded = input('mpwScope').value === 'upload';
    inputs = uploaded ? (upload ? [upload] : []) : getAssets().map(a => ({ id: a.id, name: a.name, image: a.originalSrc || a.src }));
    selected = 0; list(); controls(); await draw();
  }
  async function track() {
    if (!job || tracking) return; tracking = true; el('mpwResume').hidden = true; controls();
    let failures = 0;
    try {
      while (job && ['queued', 'running'].includes(job.state)) {
        try { job = await request<Job>(`/api/map-pixel/jobs/${job.id}`); failures = 0; }
        catch (e) { if (++failures >= 3) throw e; message('Tạm mất kết nối. Đang thử lại cùng lượt xử lý…', true); await new Promise(r => setTimeout(r, 1800)); continue; }
        el<HTMLProgressElement>('mpwProgress').value = job.progress; el('mpwTime').textContent = `${Math.round(job.elapsedSeconds)} giây`; message(job.message);
        if (['queued', 'running'].includes(job.state)) await new Promise(r => setTimeout(r, 800));
      }
      if (job?.state === 'done') { result = await request<Result>(`/api/map-pixel/jobs/${job.id}/result`); await draw(); message(`Xong trong ${result.elapsedSeconds} giây. So sánh trước/sau; chọn Áp dụng khi phù hợp.`); }
      else if (job?.state === 'failed') message(job.message, true);
    } catch (e) { message(`${e instanceof Error ? e.message : String(e)} Bấm Tiếp tục theo dõi để lấy lại kết quả.`, true); el('mpwResume').hidden = false; }
    finally { tracking = false; controls(); }
  }
  el('mpwStart').onclick = async () => {
    if (running() || !inputs.length) { if (!inputs.length) message('Chọn ảnh hoặc mở map có layer trước.', true); return; }
    loading = true; result = null; job = null; controls();
    try {
      if (!reference) { const r = await fetch('/assets/map-layer-reference/objects/gate_main.png'); if (!r.ok) throw new Error('Không đọc được mẫu 06_props.'); reference = await readFile(await r.blob() as File); }
      const body = { items: inputs, reference, settings: { colors: Number(input('mpwColors').value), grid: Number(input('mpwGrid').value), strength: Number(input('mpwStrength').value), passes: Number(input('mpwPasses').value), alpha: input('mpwAlpha').value } };
      if (new Blob([JSON.stringify(body)]).size > 32 * 1024 * 1024) throw new Error('Lượt xử lý vượt 32 MB. Chia nhỏ bộ ảnh.');
      message('Đang tải ảnh lên server xử lý…'); el<HTMLProgressElement>('mpwProgress').value = 0;
      job = await request<Job>('/api/map-pixel/jobs', body);
      loading = false; await track();
    } catch (e) { message(e instanceof Error ? e.message : String(e), true); }
    finally { loading = false; controls(); }
  };
  el('mpwCancel').onclick = async () => { if (!job) return; try { job = await request<Job>(`/api/map-pixel/jobs/${job.id}/cancel`, {}); message(job.message); if (!tracking) await track(); } catch (e) { message(String(e), true); } };
  el('mpwResume').onclick = () => void track();
  el('mpwApply').onclick = async () => {
    if (!result || running()) return; loading = true; controls();
    try { await onApply(result, inputs, uploaded); dialog.close(); } catch (e) { message(e instanceof Error ? e.message : String(e), true); } finally { loading = false; controls(); }
  };
  input('mpwScope').onchange = () => void sources();
  input('mpwUpload').onchange = async () => {
    const file = input('mpwUpload').files?.[0]; input('mpwUpload').value = ''; if (!file || running()) return;
    loading = true; controls();
    try {
      if (file.size > 23 * 1024 * 1024) throw new Error('Ảnh tải lên tối đa 23 MB.');
      const src = await readFile(file), image = await loadImage(src);
      if (image.width * image.height > 16777216 || Math.max(image.width, image.height) > 8192) throw new Error('Ảnh tối đa 16 triệu pixel, mỗi chiều tối đa 8192.');
      upload = { id: crypto.randomUUID(), name: file.name.slice(0, 200), image: src }; loading = false; await sources();
    } catch (e) { message(String(e), true); } finally { loading = false; controls(); }
  };
  for (const id of ['mpwGrid', 'mpwColors', 'mpwStrength', 'mpwPasses', 'mpwAlpha']) input(id).onchange = () => { result = null; controls(); void draw(); message('Thông số đã đổi. Xử lý lại trước khi áp dụng.'); };
  input('mpwItem').onchange = () => { selected = Number(input('mpwItem').value); void draw(); }; input('mpwZoom').onchange = () => void draw();
  const close = () => { if (running()) message('Hủy lượt xử lý trước khi đóng bàn này.', true); else dialog.close(); };
  el('mpwClose').onclick = close; dialog.addEventListener('cancel', e => { e.preventDefault(); close(); }); dialog.addEventListener('keydown', e => e.stopPropagation()); dialog.addEventListener('keyup', e => e.stopPropagation());
  return { isOpen: () => dialog.open, open: async () => { if (!dialog.open) dialog.showModal(); await sources(); } };
}
