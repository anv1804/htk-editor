/** Reorganize existing controls without duplicating their state or listeners. */
export function setupStudio() {
  document.body.classList.add('studio');
  document.title = 'HKT · Outfit Studio';
  const byId = (id: string) => document.getElementById(id)!;
  const header = document.querySelector('header')!;
  for (const [label, className] of [['Ảnh & thiết lập', 'source-open'], ['Mask & xem thử', 'review-open']]) {
    const toggle = document.createElement('button');
    toggle.className = 'panel-toggle';
    toggle.textContent = label;
    toggle.addEventListener('click', () => {
      const open = !document.body.classList.contains(className);
      document.body.classList.remove('source-open', 'review-open');
      if (open) document.body.classList.add(className);
    });
    header.append(toggle);
  }
  const section = (title: string, nodes: Element[], open = false) => {
    const box = document.createElement('details');
    box.className = 'studio-section';
    box.open = open;
    const heading = document.createElement('summary');
    heading.textContent = title;
    box.append(heading, ...nodes);
    return box;
  };
  const left = byId('baseDrop').parentElement!.parentElement!.parentElement!;
  left.classList.add('source-panel');
  const sources = byId('baseDrop').parentElement!.parentElement!;
  const palette = byId('paletteSwatches').parentElement!;
  const grid = byId('cols').closest('div.border')!;
  const processing = byId('composition').closest('div.border')!;
  left.prepend(section('01 / Ảnh nguồn', [sources], true));
  left.insertBefore(section('Thiết lập sheet', [grid], true), palette);
  left.insertBefore(section('Cắt da & hoàn thiện', [processing], true), palette);
  left.insertBefore(section('Bảng màu tô sửa', [palette]), byId('status'));

  const workflow = document.createElement('p');
  workflow.className = 'workflow-note';
  workflow.textContent = 'Outfit ở trên · Base ở dưới. Cắt da để lộ base; giữ vải ở vùng nhận nhầm, rồi tô sửa chi tiết.';
  processing.prepend(workflow);
  const compose = byId('composition') as HTMLSelectElement;
  compose.add(new Option('Outfit trên base · cắt da thận trọng', 'cutout'), 0);
  compose.value = 'cutout';
  (byId('outline') as HTMLInputElement).checked = true;
  (byId('cleanup') as HTMLInputElement).value = '0';
  (byId('paint') as HTMLSelectElement).options[3].text = 'Giữ sắc độ gốc';
  (byId('paint') as HTMLSelectElement).options[4].text = 'Phác màu sắc nét';
  (byId('paint') as HTMLSelectElement).options[0].text = 'Chỉ giới hạn màu';
  byId('outline').closest('div.flex')!.querySelector('span')!.textContent = 'Rõ viền & đường may';

  const tools: Record<string,string> = { inspect:'Xem', color:'Tô màu', sample:'Hút màu', erase:'Xóa hết', base:'Lộ base', outfit:'Giữ vải', headwear:'Giữ tóc', auto:'Tự động', unpaint:'Bỏ màu' };
  document.querySelectorAll<HTMLButtonElement>('[data-brush-val]').forEach(button => {
    const name = tools[button.dataset.brushVal!];
    if (name) { button.textContent = name; button.setAttribute('aria-label', button.title); }
  });
  byId('tabBtnInspector').textContent = '02 / So sánh & sửa';
  byId('tabBtnSheet').textContent = 'Toàn bộ sheet';
  byId('btnZoomFit').textContent = 'Vừa khung';
  byId('btnToggleGrid').textContent = 'Lưới';
  byId('btnToggleSymmetry').textContent = 'Đối xứng';
  byId('btnToggleOnion').textContent = 'Bóng frame';
  byId('btnToggleBg').textContent = 'Nền';
  byId('prev').textContent = '← Trước';
  byId('next').textContent = 'Sau →';
  byId('btnResetFrameAll').textContent = 'Đặt lại frame';
  byId('clearFrame').textContent = 'Bỏ nét sửa';
  byId('bottomPanel').firstElementChild!.firstChild!.textContent = 'Khung hình';
  const exports = section('03 / Xuất ảnh', ['download', 'downloadOutfit', 'split', 'downloadHeadwear', 'downloadReport'].map(byId));
  exports.classList.add('export-menu');
  byId('repair').parentElement!.append(exports);

  const profile = byId('profileStatus').parentElement!;
  const parent = profile.parentElement!;
  parent.append(section('Nâng cao · vùng base cố định', [profile]));
  byId('animPreviewCanvas').parentElement!.classList.add('animation-stage');
  const reset = document.createElement('button');
  reset.textContent = 'Đặt lại bố cục';
  reset.className = 'reset-layout';
  reset.addEventListener('click', () => {
    ['leftPanel','rightPanel','bottomPanel'].forEach(id => byId(id).removeAttribute('style'));
    byId('btnZoomFit').click();
  });
  parent.append(reset);
}
