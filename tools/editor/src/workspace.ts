import { $, } from './utils';
import { fitViewToScreen } from './editor';

const paths: Record<string,string> = {
  inspect:'M9 3a6 6 0 1 0 0 12A6 6 0 0 0 9 3Zm5 11 5 5',
  color:'m14 3 5 5-10 10-6 1 1-6L14 3Zm-9 9 5 5',
  fill:'m10 3 8 8-7 7-8-8 7-7Zm-6 8h13m3 3s-2 3-2 4a2 2 0 0 0 4 0c0-1-2-4-2-4Z',
  sample:'m14 3 5 5m-3-3L5 16l-1 4 4-1L19 8',
  erase:'m13 3 7 7-10 10H5l-4-4L13 3Zm-8 9 8 8m-3 0h11',
  base:'M8 8a4 4 0 1 0 8 0 4 4 0 0 0-8 0ZM4 21v-3a8 8 0 0 1 16 0v3',
  outfit:'m8 3-6 4 3 5 3-2v11h8V10l3 2 3-5-6-4c0 4-8 4-8 0Z',
  headwear:'m3 6 4 4 5-7 5 7 4-4-2 13H5L3 6Z',
  auto:'M4 10a8 8 0 1 1 1 8M4 3v7h7',
  unpaint:'m4 4 16 16M9 4h7v7M4 9v7a4 4 0 0 0 4 4h7',
};
function icon(path:string) {
  return `<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${path}"/></svg>`;
}

/** A single workspace shell; existing controls keep their state and handlers. */
export function setupWorkspace() {
  document.body.classList.add('atelier');
  const header=document.querySelector('header')!;
  header.firstElementChild!.innerHTML='<div class="brand-mark">▦</div><div class="brand-copy"><strong>Outfit Studio</strong><span>HKT / PIXEL FORGE</span></div><span class="workspace-tag">Không gian chỉnh sửa</span>';
  const center=$('inspectorTab').parentElement!.parentElement!;
  center.classList.add('workspace-center');
  const left=$('leftPanel');
  const source=left.querySelector('.source-panel')!;
  const library=document.createElement('div'); library.className='panel-heading';
  library.innerHTML='<span class="eyebrow">TÀI NGUYÊN</span><h2>Sprite của bạn</h2><p>Chọn base và trang phục cùng bố cục.</p>';
  source.prepend(library);
  const settings=$('cols').closest('details')!;
  settings.open=false;
  settings.querySelector('summary')!.textContent='Kích thước & bảng màu';
  const sources=$('baseDrop').closest('details')!;
  sources.classList.add('asset-section');
  sources.querySelector('summary')!.textContent='Ảnh nguồn';
  for (const [id,label] of [['baseDrop','01 · Nhân vật gốc'],['outfitDrop','02 · Trang phục'],['greenBaseDrop','03 · Base xanh'],['headBaseDrop','04 · Base đầu'],['bodyBaseDrop','05 · Base thân']]) {
    const holder=$(id!).closest('.flex-col')!;
    holder.classList.add('asset-item');
    holder.querySelector('span')!.textContent=label!;
  }
  const palette=$('paletteSwatches').closest('details')!;
  palette.open=true; palette.querySelector('summary')!.textContent='Màu tô thủ công';

  // Tools belong to the canvas, not to the source-file navigation.
  const tools=document.querySelector<HTMLElement>('.aseprite-vertical-toolbox')!;
  tools.classList.add('canvas-tools');
  const modes=document.querySelector('.view-modes')!;
  modes.before(tools);
  tools.querySelectorAll<HTMLButtonElement>('[data-brush-val]').forEach(b=>{
    b.innerHTML=icon(paths[b.dataset.brushVal!]!);
    b.setAttribute('aria-label',b.title);
  });
  const brush=tools.querySelector('#brushSize')!.parentElement!;
  brush.classList.add('brush-controls');
  const sizeLabel=document.createElement('span');sizeLabel.textContent='Cọ';brush.prepend(sizeLabel);
  const undoGroup=document.createElement('div'); undoGroup.className='history-controls';
  for (const [id,label] of [['undo','↶'],['redo','↷']]) { const b=$(id!);b.textContent=label!;undoGroup.append(b); }
  tools.append(undoGroup);
  // Less frequent profile editing is grouped with its advanced settings.
  const profile=$('profileStatus').parentElement!;
  const targets=document.createElement('div');targets.className='profile-targets';
  tools.querySelectorAll('.profile-target-btn').forEach(b=>targets.append(b));
  profile.prepend(targets);
  tools.querySelectorAll('hr').forEach(el=>el.remove());
  $('btnToolSymmetry').hidden=true; $('btnToolGrid').hidden=true;
  const showBase=document.createElement('button');showBase.id='toggleBaseReference';
  showBase.textContent='Hiện base';showBase.setAttribute('aria-pressed','false');
  showBase.onclick=()=>{
    const shown=document.body.classList.toggle('show-base-reference');
    showBase.setAttribute('aria-pressed',String(shown));showBase.textContent=shown?'Ẩn base':'Hiện base';
    fitViewToScreen();
  };
  modes.append(showBase);
  const maskLegend=document.createElement('div');
  maskLegend.className='mask-legend';
  maskLegend.setAttribute('role','note');
  maskLegend.innerHTML='<span class="mask-legend-title">LỚP PIXEL</span><span class="mask-key"><i class="mask-blue"></i>Outfit</span><span class="mask-key"><i class="mask-red"></i>Base lộ ra</span><span class="mask-key"><i class="mask-yellow"></i>Tóc / phụ kiện</span><span class="mask-key"><i class="mask-gold"></i>Da dựng</span><span class="mask-legend-hint">Đỏ là pixel lấy từ base, không phải da còn sót trong outfit.</span>';
  modes.after(maskLegend);
  const maskToggle=$('showMask') as HTMLInputElement;
  const updateMaskLegend=()=>{maskLegend.hidden=!maskToggle.checked;};
  maskToggle.addEventListener('change',updateMaskLegend);
  updateMaskLegend();
  $('view-compare').textContent='Trước / sau';
  $('tabBtnInspector').textContent='Chỉnh sửa';$('tabBtnSheet').textContent='Sprite sheet';
  document.querySelectorAll('.viewport-header').forEach((el,i)=>{
    el.firstElementChild!.textContent=['BASE · Tham chiếu','OUTFIT · Ảnh nguồn','KẾT QUẢ · Đang chỉnh'][i]!;
  });

  const right=$('rightPanel').firstElementChild!;
  right.classList.add('inspector-scroll');
  const process=$('composition').closest('details')!;process.open=true;
  process.querySelector('summary')!.textContent='Ghép & hoàn thiện';
  const masks=$('showMask').closest('div.border')!;
  masks.classList.add('mask-panel');masks.firstElementChild!.textContent='Mặt nạ chỉnh sửa';
  const help=masks.lastElementChild!;
  const guide=document.createElement('details');guide.className='shortcut-guide';
  guide.innerHTML='<summary>Hướng dẫn phím tắt</summary>';guide.append(help);masks.append(guide);
  const preview=$('animPreviewCanvas').parentElement!.parentElement!;
  preview.classList.add('preview-panel');
  const tabs=document.createElement('div');tabs.className='inspector-tabs';
  const adjustment=document.createElement('div');adjustment.className='inspector-page';
  const retouch=document.createElement('div');retouch.className='inspector-page';retouch.hidden=true;
  adjustment.append(process);
  const layerStack=document.createElement('details');layerStack.className='layer-stack';
  layerStack.innerHTML='<summary>3 LỚP NHÂN VẬT</summary><div><i class="layer-dot paint-dot"></i><span>Tóc · băng cài · mũ<small>Lớp trên cùng</small></span><b>03</b></div><div><i class="layer-dot outfit-dot"></i><span>Outfit<small>Trang phục, không chứa da tay</small></span><b>02</b></div><div><i class="layer-dot base-dot"></i><span>Base<small>Nhân vật gốc và da tay</small></span><b>01</b></div>';
  adjustment.append(layerStack);
  const learning=document.createElement('details');learning.className='learning-panel shortcut-guide';
  learning.innerHTML='<summary>Đối chiếu & ghi nhớ</summary><p>Tự đối chiếu tóc giữa các frame. Chỉ ghi nhớ nét sửa khi bạn xác nhận.</p><label><input id="useLearning" type="checkbox" checked> Dùng chỉnh sửa đã ghi nhớ</label><div class="learning-actions"><button id="learnCorrections">Nhớ nét sửa</button><button id="forgetLearning">Quên bộ này</button></div><p id="learningStatus" role="status">Ghi nhớ riêng cho từng bộ ảnh và bố cục frame, lưu trên trình duyệt này.</p><button id="reviewLearning" hidden>Đến frame cần kiểm tra</button>';
  adjustment.append(learning);
  for (const panel of [process,layerStack,learning]) panel.addEventListener('toggle',()=>{
    if (panel.open) for (const other of [process,layerStack,learning]) if (other!==panel) other.open=false;
  });
  const fill=document.querySelector('.editing-options')!;
  retouch.append(fill,masks,$('profileStatus').closest('details')!);
  for (const [label,page] of [['Điều chỉnh',adjustment],['Tô & mask',retouch]] as const) {
    const b=document.createElement('button');b.textContent=label;b.setAttribute('aria-selected',String(page===adjustment));
    b.onclick=()=>{adjustment.hidden=page!==adjustment;retouch.hidden=page!==retouch;tabs.querySelectorAll('button').forEach(t=>t.setAttribute('aria-selected',String(t===b)));};tabs.append(b);
  }
  $('brush').addEventListener('change',()=>{
    if (($('brush') as HTMLSelectElement).value==='fill') (tabs.lastElementChild as HTMLButtonElement).click();
  });
  const inspector=$('rightPanel');
  right.prepend(tabs,adjustment,retouch);
  inspector.prepend(preview);
  document.querySelector('.reset-layout')!.classList.add('quiet-action');
  $('repair').innerHTML='<span>✦</span> Xử lý sprite';
  header.querySelector('.export-menu summary')!.textContent='Xuất ảnh ↗';
  const status=$('status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
}
