/** Map art stays at its authored pixel size. Grid spacing is only a placement aid. */
export interface SceneAsset {
  id: string; name: string; src: string; w: number; h: number;
  pivotX: number; pivotY: number; category: string; sourceFile?: string; originalSrc?: string;
}
export interface SceneItem { id: string; assetId: string; x: number; y: number; flipX: boolean; flipY: boolean }
export interface SceneLayer {
  id: string; name: string; visible: boolean; locked: boolean; opacity: number;
  parallax: number; items: SceneItem[];
}
export interface CollisionRect { id: string; x: number; y: number; w: number; h: number; oneWay: boolean }
export interface MapScene {
  version: 3; name: string; width: number; height: number;
  assets: SceneAsset[]; layers: SceneLayer[]; collisions: CollisionRect[];
}
export const SCENE_LIMITS = { pixels: 16777216, assetPixels: 16777216, totalPixels: 67108864, bytes: 128 * 1024 * 1024 };
export const uid = () => crypto.randomUUID();
export const createLayer = (name: string): SceneLayer => ({ id: uid(), name, visible: true, locked: false, opacity: 1, parallax: 1, items: [] });
export const newScene = (): MapScene => ({ version: 3, name: 'Map mới', width: 1920, height: 1080, assets: [], layers: [createLayer('Địa hình'), createLayer('Vật thể')], collisions: [] });
export const snapPixel = (n: number, step = 1) => Math.round(n / step) * step;
export function placeAsset(asset: SceneAsset, x: number, y: number, step = 1): SceneItem {
  return { id: uid(), assetId: asset.id, x: snapPixel(x, step) - asset.pivotX, y: snapPixel(y, step) - asset.pivotY, flipX: false, flipY: false };
}
export function snapshot(scene: MapScene): MapScene {
  return { ...scene, assets: scene.assets.map(a => ({ ...a })), layers: scene.layers.map(l => ({ ...l, items: l.items.map(i => ({ ...i })) })), collisions: scene.collisions.map(c => ({ ...c })) };
}
const record = (v: unknown): Record<string, any> => {
  if (!v || typeof v !== 'object' || Array.isArray(v)) throw new Error('Dữ liệu map không hợp lệ.');
  return v as Record<string, any>;
};
const list = (v: unknown, max: number): any[] => {
  if (!Array.isArray(v) || v.length > max) throw new Error('Danh sách trong map vượt giới hạn.');
  return v;
};
const text = (v: unknown) => {
  if (typeof v !== 'string' || !v.length || v.length > 200) throw new Error('Tên hoặc ID không hợp lệ.');
  return v;
};
const integer = (v: unknown, low: number, high: number) => {
  if (typeof v !== 'number' || !Number.isInteger(v) || v < low || v > high) throw new Error('Kích thước hoặc tọa độ không hợp lệ.');
  return v;
};
const number = (v: unknown, low: number, high: number) => {
  if (typeof v !== 'number' || !Number.isFinite(v) || v < low || v > high) throw new Error('Thông số lớp không hợp lệ.');
  return v;
};
const bool = (v: unknown) => { if (typeof v !== 'boolean') throw new Error('Trạng thái lớp không hợp lệ.'); return v; };
export function readScene(value: unknown): MapScene {
  const p = record(value);
  if (p.version !== 3) throw new Error('Cần Project Map phiên bản 3. Project v2 vẫn được giữ trong trình duyệt.');
  const width = integer(p.width, 1, 8192), height = integer(p.height, 1, 8192);
  if (width * height > SCENE_LIMITS.pixels) throw new Error('Map tối đa 16 triệu pixel.');
  const ids = new Set<string>();
  const id = (v: unknown) => { const s = text(v); if (ids.has(s)) throw new Error('ID trùng trong project.'); ids.add(s); return s; };
  let pixels = 0, bytes = 0, count = 0;
  const assets = list(p.assets, 512).map(v => {
    const a = record(v), w = integer(a.w, 1, 8192), h = integer(a.h, 1, 8192);
    if (w * h > SCENE_LIMITS.assetPixels || (pixels += w * h) > SCENE_LIMITS.totalPixels) throw new Error('Thư viện vượt giới hạn pixel.');
    if (typeof a.src !== 'string' || !/^data:image\/(png|webp|jpeg);base64,[A-Za-z0-9+/=]+$/.test(a.src) || (bytes += a.src.length) > SCENE_LIMITS.bytes) throw new Error('Ảnh của project không hợp lệ hoặc quá lớn.');
    if (a.originalSrc !== undefined && (typeof a.originalSrc !== 'string' || !/^data:image\/(png|webp|jpeg);base64,[A-Za-z0-9+/=]+$/.test(a.originalSrc) || (bytes += a.originalSrc.length) > SCENE_LIMITS.bytes)) throw new Error('Ảnh gốc không hợp lệ hoặc project quá lớn.');
    return { id: id(a.id), name: text(a.name), src: a.src, w, h, pivotX: integer(a.pivotX, 0, w), pivotY: integer(a.pivotY, 0, h), category: text(a.category), ...(typeof a.sourceFile === 'string' ? { sourceFile: a.sourceFile.slice(0, 500) } : {}), ...(a.originalSrc ? { originalSrc: a.originalSrc } : {}) };
  });
  const known = new Set(assets.map(a => a.id));
  const layers = list(p.layers, 64).map(v => {
    const l = record(v);
    const items = list(l.items, 10000).map(v => {
      const i = record(v); if (!known.has(i.assetId) || ++count > 10000) throw new Error('Vật thể thiếu ảnh hoặc vượt giới hạn.');
      return { id: id(i.id), assetId: String(i.assetId), x: integer(i.x, -65536, 65536), y: integer(i.y, -65536, 65536), flipX: bool(i.flipX), flipY: bool(i.flipY) };
    });
    return { id: id(l.id), name: text(l.name), visible: bool(l.visible), locked: bool(l.locked), opacity: number(l.opacity, 0, 1), parallax: number(l.parallax, 0, 2), items };
  });
  if (!layers.length) throw new Error('Map cần ít nhất một lớp.');
  const collisions = list(p.collisions, 5000).map(v => {
    const c = record(v); return { id: id(c.id), x: integer(c.x, -65536, 65536), y: integer(c.y, -65536, 65536), w: integer(c.w, 1, 8192), h: integer(c.h, 1, 8192), oneWay: bool(c.oneWay) };
  });
  return { version: 3, name: text(p.name), width, height, assets, layers, collisions };
}

export function packagePath(value: unknown): string {
  if (typeof value !== 'string' || !value || value.startsWith('/') || /[\\:]/.test(value) || value.split('/').some(p => !p || p === '.' || p === '..')) throw new Error('Đường dẫn trong gói map không hợp lệ.');
  return value;
}
export type ImageSource = { src: string; w: number; h: number };
/** Import baked layers once; object copies become library entries, never duplicate instances. */
export async function sceneFromLayout(value: unknown, load: (path: string) => Promise<ImageSource>): Promise<MapScene> {
  const data = record(value), canvas = record(data.canvas);
  const width = integer(canvas.width, 1, 8192), height = integer(canvas.height, 1, 8192);
  if (width * height > SCENE_LIMITS.pixels) throw new Error('Map quá lớn.');
  if ((data.origin && data.origin !== 'top_left') || (data.blend && data.blend !== 'source_over')) throw new Error('Gói map cần gốc trên trái và blend source_over.');
  const assets: SceneAsset[] = [], layers: SceneLayer[] = [];
  const cached = new Map<string, SceneAsset>();
  let pixels = 0;
  async function asset(file: unknown, category: string) {
    const path = packagePath(file);
    if (cached.has(path)) return cached.get(path)!;
    const image = await load(path);
    if ((pixels += image.w * image.h) > SCENE_LIMITS.totalPixels) throw new Error('Thư viện map quá lớn.');
    const a = { ...image, id: uid(), name: path.split('/').pop()!.replace(/\.png$/i, ''), pivotX: Math.floor(image.w / 2), pivotY: image.h, category, sourceFile: path };
    assets.push(a); cached.set(path, a); return a;
  }
  const entries = list(data.layers, 64).map(record).sort((a, b) => number(a.z ?? 0, -10000, 10000) - number(b.z ?? 0, -10000, 10000));
  for (const l of entries) {
    const a = await asset(l.file, 'layer'), layer = createLayer(typeof l.name === 'string' ? l.name : a.name);
    layer.locked = true;
    layer.visible = l.visible === undefined ? true : bool(l.visible);
    layer.opacity = number(l.opacity ?? data.opacity ?? 1, 0, 1);
    layer.parallax = number(l.parallax ?? 1, 0, 2);
    layer.items = [{ id: uid(), assetId: a.id, x: integer(l.x ?? 0, -65536, 65536), y: integer(l.y ?? 0, -65536, 65536), flipX: false, flipY: false }];
    layers.push(layer);
  }
  for (const o of list(data.objects ?? [], 448)) await asset(record(o).file, 'module');
  layers.push(createLayer('Module mới'));
  return readScene({ version: 3, name: typeof data.name === 'string' ? data.name : 'Map các lớp đồng bộ', width, height, assets, layers, collisions: [] });
}
