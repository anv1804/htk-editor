/** Portable, native-size map props. Pure helpers shared by the map and tests. */
export interface MapLibraryAsset {
  id: string;
  name: string;
  src: string;
  w: number;
  h: number;
  pivotX: number;
  pivotY: number;
}

export function parseMapAssets(value: unknown): MapLibraryAsset[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > 512) throw new Error('Thư viện map không hợp lệ.');
  const ids = new Set<string>();
  let pixels = 0, bytes = 0;
  return value.map(raw => {
    if (!raw || typeof raw !== 'object') throw new Error('Asset map không hợp lệ.');
    const a = raw as MapLibraryAsset;
    if (typeof a.id !== 'string' || !a.id.startsWith('custom-') || ids.has(a.id) ||
        typeof a.name !== 'string' || a.name.length > 160 ||
        typeof a.src !== 'string' || !/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(a.src) ||
        !Number.isInteger(a.w) || !Number.isInteger(a.h) || a.w < 1 || a.h < 1 || a.w*a.h > 1048576 ||
        !Number.isFinite(a.pivotX) || !Number.isFinite(a.pivotY) ||
        a.pivotX < 0 || a.pivotX > a.w || a.pivotY < 0 || a.pivotY > a.h) {
      throw new Error('Ảnh hoặc điểm đặt chân của asset không hợp lệ.');
    }
    ids.add(a.id); pixels += a.w*a.h; bytes += a.src.length;
    if (pixels > 4194304 || bytes > 28*1024*1024) throw new Error('Thư viện map quá lớn; hãy chia thành nhiều project.');
    return { id:a.id, name:a.name, src:a.src, w:a.w, h:a.h, pivotX:a.pivotX, pivotY:a.pivotY };
  });
}

export function assetPlacement(a: Pick<MapLibraryAsset, 'w'|'h'|'pivotX'|'pivotY'>, x: number, y: number, tileSize: number) {
  // Click targets the center of the tile's lower edge; pixels are never stretched.
  return { x:x+.5-a.pivotX/tileSize, y:y+1-a.pivotY/tileSize, width:a.w, height:a.h };
}
