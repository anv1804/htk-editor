import { state, corrections, correctionContext, paintLayer, paintContext, baseMap, profileState, setProfileState } from './state';
import { $, status, download, loadImage } from './utils';
import { settings, invalidate, remember, render, grid, checkpoint, fitViewToScreen, showTab } from './editor';
import { connectedRegion } from './region';

export function fillRegion(canvas: HTMLCanvasElement, x: number, y: number) {
  const g = grid();
  if (!g || !state.outfit || state.busy) return;
  const source = document.createElement('canvas'); source.width = g.w; source.height = g.h;
  const ctx = source.getContext('2d')!;
  const layerSource = document.body.dataset.view === 'layer' ? state.outfitLayerImage
    : document.body.dataset.view === 'headwear' ? state.headwearLayerImage : state.result;
  ctx.drawImage(canvas.id === 'outfitCanvas' ? state.outfit : layerSource || state.outfit,
    g.x,g.y,g.w,g.h,0,0,g.w,g.h);
  if (canvas.id !== 'outfitCanvas') ctx.drawImage(paintLayer,g.x,g.y,g.w,g.h,0,0,g.w,g.h);
  const selected = connectedRegion(ctx.getImageData(0,0,g.w,g.h).data,g.w,g.h,x,y,
    Number(($('fillTolerance') as HTMLInputElement).value));
  if (!selected.length) return;
  checkpoint(corrections,g,[paintLayer]);
  const mode = ($('fillAction') as HTMLSelectElement).value;
  const colors: Record<string,string> = {base:'#ff0000',outfit:'#0000ff',erase:'#00ff00'};
  paintContext.fillStyle = ($('paintColor') as HTMLInputElement).value;
  correctionContext.fillStyle = colors[mode] || '#0000ff';
  for (const index of selected) {
    const px=g.x+index%g.w, py=g.y+Math.floor(index/g.w);
    paintContext.clearRect(px,py,1,1); correctionContext.clearRect(px,py,1,1);
    (mode === 'color' ? paintContext : correctionContext).fillRect(px,py,1,1);
    if (mode === 'color' && canvas.id === 'editCanvas' && ['headwear','layer'].includes(document.body.dataset.view || '')) {
      correctionContext.fillStyle = document.body.dataset.view === 'headwear' ? '#ffc800' : '#0000ff';
      correctionContext.fillRect(px,py,1,1);
    }
  }
  invalidate(`Đã sửa ${selected.length} pixel trong frame ${g.frame+1}. Bấm Xử lý để cập nhật bản xuất.`);
  render(); remember();
}

export function setupWorkflow(setSource: (kind: 'base'|'outfit'|'greenBase'|'headBase'|'bodyBase',url: string)=>Promise<void>) {
  const button = (id: string,text: string) => {
    const b=document.createElement('button'); b.id=id; b.textContent=text; return b;
  };
  const project=document.createElement('div'); project.className='project-actions';
  const save=button('saveProject','Lưu dự án'); const open=button('openProject','Mở dự án');
  const input=document.createElement('input'); input.type='file'; input.accept='.json'; input.hidden=true;
  project.append(open,save,input); document.querySelector('header > div:last-of-type')!.prepend(project);
  save.onclick=()=>{
    if (!state.base || !state.outfit) return status('Chọn đủ ảnh trước khi lưu dự án.',true);
    const values=Object.fromEntries(settings.map(id=>[id,id==='outline' ? ($<HTMLInputElement>(id)).checked : ($<HTMLInputElement>(id)).value]));
    const png=(img:HTMLImageElement)=>{ const c=document.createElement('canvas'); c.width=img.width;c.height=img.height;c.getContext('2d')!.drawImage(img,0,0);return c.toDataURL(); };
    const data={format:'hkt-outfit-project',version:1,base:png(state.base),outfit:png(state.outfit),
      greenBase:state.greenBase ? png(state.greenBase) : null,
      headBase:state.headBase ? png(state.headBase) : null,
      bodyBase:state.bodyBase ? png(state.bodyBase) : null,
      corrections:corrections.toDataURL(),paint:paintLayer.toDataURL(),profile:profileState.key ? baseMap.toDataURL() : null,
      profileKey:profileState.key,values,frame:($('frame') as HTMLInputElement).value};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data)],{type:'application/json'}));
    download(url,'outfit-project.json'); setTimeout(()=>URL.revokeObjectURL(url),1000);
    status('Đã lưu ảnh nguồn, mask, lớp màu và thiết lập vào dự án.');
  };
  open.onclick=()=>{if (!state.busy) input.click();};
  input.onchange=async()=>{
    const file=input.files?.[0]; if (!file || state.busy) return;
    try {
      if (file.size>64*1024*1024) throw new Error('Dự án vượt quá 64 MB.');
      const p=JSON.parse(await file.text());
      if (p.format!=='hkt-outfit-project' || p.version!==1) throw new Error('Không đúng định dạng dự án Outfit Studio.');
      // Older projects predate the optional logo restoration setting.
      p.values = { ...p.values, logoCleanup: p.values?.logoCleanup ?? 'auto' };
      const urls=[p.base,p.outfit,p.corrections,p.paint,...(p.profile?[p.profile]:[]),...(p.greenBase?[p.greenBase]:[]),...(p.headBase?[p.headBase]:[]),...(p.bodyBase?[p.bodyBase]:[])];
      if (urls.some(url=>typeof url!=='string' || !url.startsWith('data:image/png;base64,'))) throw new Error('Dự án phải chứa ảnh PNG nhúng.');
      const images=await Promise.all(urls.map(loadImage));
      const base=images[0]!;
      if (base.width*base.height>4194304 || images.some(im=>im.width!==base.width || im.height!==base.height)) throw new Error('Các lớp dự án sai kích thước.');
      for (const id of settings) {
        const el=$<HTMLInputElement|HTMLSelectElement>(id), value=p.values?.[id];
        if (id==='outline') { if (typeof value!=='boolean') throw new Error('Thiết lập viền không hợp lệ.'); }
        else if (el instanceof HTMLSelectElement) { if (![...el.options].some(o=>o.value===String(value))) throw new Error(`Thiết lập ${id} không hợp lệ.`); }
        else if (!Number.isFinite(Number(value)) || (el.min!=='' && Number(value)<Number(el.min)) || (el.max!=='' && Number(value)>Number(el.max))) throw new Error(`Thiết lập ${id} không hợp lệ.`);
      }
      if (base.width%Number(p.values.cols) || base.height%Number(p.values.rows)) throw new Error('Grid không khớp kích thước ảnh.');
      await setSource('base',p.base); await setSource('outfit',p.outfit);
      if (p.greenBase) await setSource('greenBase',p.greenBase);
      else if (state.greenBase) {
        state.greenBase=null;
        ($('greenBasePreview') as HTMLImageElement).removeAttribute('src');
        $('greenBaseDrop').classList.remove('loaded');
        $('greenBaseMeta').textContent='';
      }
      if (p.headBase) await setSource('headBase',p.headBase);
      else if (state.headBase) {
        state.headBase=null;
        ($('headBasePreview') as HTMLImageElement).removeAttribute('src');
        $('headBaseDrop').classList.remove('loaded');
        $('headBaseMeta').textContent='';
      }
      if (p.bodyBase) await setSource('bodyBase',p.bodyBase);
      else if (state.bodyBase) {
        state.bodyBase=null;
        ($('bodyBasePreview') as HTMLImageElement).removeAttribute('src');
        $('bodyBaseDrop').classList.remove('loaded');
        $('bodyBaseMeta').textContent='';
      }
      for (const id of settings) { if (id==='outline') ($<HTMLInputElement>(id)).checked=p.values[id]; else ($<HTMLInputElement>(id)).value=p.values[id]; }
      correctionContext.drawImage(images[2]!,0,0); paintContext.drawImage(images[3]!,0,0);
      const savedProfile = p.profile ? images[4] : null;
      if (savedProfile) { baseMap.width=base.width; baseMap.height=base.height; baseMap.getContext('2d')!.drawImage(savedProfile,0,0); setProfileState(typeof p.profileKey==='string'?p.profileKey:null,p.base,`${p.values.cols}:${p.values.rows}`); }
      ($('frame') as HTMLInputElement).value=String(Math.max(1,Math.min(Number(p.frame)||1,Number(p.values.cols)*Number(p.values.rows))));
      $('colors').dispatchEvent(new Event('change'));
      invalidate('Đã mở dự án. Bấm Xử lý sprite để dựng kết quả.'); render(); remember();
    } catch(e) { status(e instanceof Error?e.message:'Không mở được dự án.',true); }
    input.value='';
  };

  const fillButton=button('fillTool','Tô vùng'); fillButton.className='tool-btn'; fillButton.dataset.brushVal='fill'; fillButton.title='Tô vùng liên thông (G)';
  document.querySelector('[data-brush-val="color"]')!.after(fillButton);
  ($('brush') as HTMLSelectElement).add(new Option('Tô vùng','fill'));
  const options=document.createElement('div'); options.className='editing-options';
  options.innerHTML='<strong>Sửa vùng pixel</strong><label>Thao tác tô vùng<select id="fillAction"><option value="outfit">Khôi phục vải gốc</option><option value="base">Cắt để lộ base</option><option value="color">Tô màu đã chọn</option><option value="erase">Xóa trong suốt</option></select></label><label>Độ lệch màu<input id="fillTolerance" type="range" min="0" max="60" value="18"></label><p>G: tô vùng · U: giữ vải · R: lộ base · B: cọ màu. Mỗi lần tô chỉ tác động trong frame hiện tại.</p>';
  $('rightPanel').firstElementChild!.prepend(options);
  const updateFill=()=>{ options.hidden=($('brush') as HTMLSelectElement).value!=='fill'; };
  $('brush').addEventListener('change',updateFill); updateFill();
  const presets=document.createElement('div'); presets.className='processing-presets';
  for (const [label,value] of [['Giữ màu gốc','0'],['Gọn 32 màu','32'],['Chi tiết 64','64']]) {
    const b=button(`preset${value}`,label!); b.onclick=()=>{
      ($('colors') as HTMLSelectElement).value=value!;
      ($('paint') as HTMLSelectElement).value='4';
      $('colors').dispatchEvent(new Event('change'));
    }; presets.append(b);
  }
  $('colors').closest('div.border')!.prepend(presets);
  const note=document.createElement('p'); note.className='palette-warning'; note.id='paletteHint';
  $('paint').closest('div.border')!.append(note);
  const updatePalette=()=>{
    const raw=($('colors') as HTMLSelectElement).value==='0';
    ($('paint') as HTMLSelectElement).disabled=raw;
    note.textContent=raw?'Giữ màu gốc: không gom màu, ảnh có thể còn hàng nghìn sắc độ. Chọn 32/64 màu để làm gọn.':'Phác lại sáng/tối và màu vải theo từng frame, không làm mờ viền; màu da base và nét tô tay được khóa.';
  };
  $('colors').addEventListener('change',updatePalette);
  updatePalette();
  // Runs after persisted settings are restored as well.
  document.addEventListener('studio-ready',updatePalette);
  const views=document.createElement('div'); views.className='view-modes';
  for (const [key,label] of [['compare','So sánh'],['result','Kết quả'],['base-layer','Base'],['layer','Outfit'],['headwear','Tóc / mũ']]) {
    const b=button(`view-${key}`,label!); b.dataset.view=key;
    b.onclick=()=>{
      document.body.dataset.view=key;
      if (key==='compare') showTab('inspector');
      views.querySelectorAll('button').forEach(el=>el.setAttribute('aria-pressed',String(el===b)));
      const labelEl=$('editCanvas').closest('.viewport-card')!.querySelector('.viewport-header > span');
      if (labelEl) labelEl.textContent=key==='layer'?'● Lớp outfit':key==='headwear'?'● Tóc / băng cài / mũ':key==='base-layer'?'● Base · tham chiếu':'● Kết quả';
      render(); fitViewToScreen();
    };
    b.setAttribute('aria-pressed',String(key==='compare')); views.append(b);
  }
  $('inspectorTab').parentElement!.before(views);
  const bar=document.createElement('div'); bar.className='studio-status'; bar.append($('status'));
  $('bottomSplitter').before(bar);
  let resizeTimer=0;
  window.addEventListener('resize',()=>{
    window.clearTimeout(resizeTimer);
    resizeTimer=window.setTimeout(fitViewToScreen,120);
  });
}
