import { loadImage, readFile } from './utils';
import { packagePath, readScene, sceneFromLayout } from './map-scene-model';
import type { MapScene, ImageSource } from './map-scene-model';

export async function imageSource(src: string): Promise<ImageSource> {
  const img = await loadImage(src);
  if (img.width > 8192 || img.height > 8192 || img.width * img.height > 16777216) throw new Error('Ảnh tối đa 16 triệu pixel, mỗi chiều tối đa 8192.');
  return { src, w: img.width, h: img.height };
}

export async function openFolder(files: File[]): Promise<MapScene> {
  const paths = new Map(files.map(f => [f.webkitRelativePath || f.name, f]));
  const manifests = [...paths].filter(([p]) => p.split('/').pop() === 'layout.json');
  if (manifests.length !== 1) throw new Error('Chọn folder chứa một layout.json và các PNG tương ứng.');
  const [path, file] = manifests[0]!, base = path.slice(0, -'layout.json'.length);
  if (file.size > 1048576) throw new Error('Layout quá lớn.');
  let bytes = 0;
  return sceneFromLayout(JSON.parse(await file.text()), async name => {
    const image = paths.get(base + packagePath(name));
    if (!image) throw new Error(`Thiếu file: ${name}`);
    if ((bytes += image.size) > 96 * 1024 * 1024) throw new Error('Gói map vượt 96 MB.');
    return imageSource(await readFile(image));
  });
}

export async function openDemo(): Promise<MapScene> {
  const base = '/assets/map-layer-reference/';
  const response = await fetch(base + 'layout.json');
  if (!response.ok) throw new Error('Không tải được bộ map mẫu.');
  return sceneFromLayout(await response.json(), async path => {
    const response = await fetch(base + packagePath(path));
    if (!response.ok) throw new Error(`Không tải được ${path}.`);
    return imageSource(await readFile(await response.blob() as File));
  });
}

export async function openZip(file: File): Promise<MapScene> {
  if (file.size > 23 * 1024 * 1024) throw new Error('ZIP tối đa 23 MB. Với gói lớn hơn, dùng Nhập folder.');
  const response = await fetch('/api/map-assets/bundle', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ archive: await readFile(file) }) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Không mở được gói map.');
  return sceneFromLayout(result.layout, async path => {
    const src = result.images[packagePath(path)];
    if (typeof src !== 'string') throw new Error(`Thiếu ảnh ${path}.`);
    return imageSource(src);
  });
}

let database: Promise<IDBDatabase> | undefined;
function db() {
  return database ??= new Promise<IDBDatabase>((resolve, reject) => {
    const req = indexedDB.open('hkt-map-studio-v3', 1);
    req.onupgradeneeded = () => req.result.createObjectStore('projects');
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
export async function saveScene(scene: MapScene): Promise<void> {
  const connection = await db();
  return new Promise((resolve, reject) => {
    const tx = connection.transaction('projects', 'readwrite');
    tx.objectStore('projects').put(scene, 'current');
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}
export async function restoreScene(): Promise<MapScene | null> {
  const connection = await db();
  return new Promise((resolve, reject) => {
    const req = connection.transaction('projects').objectStore('projects').get('current');
    req.onsuccess = () => { try { resolve(req.result ? readScene(req.result) : null); } catch (e) { reject(e); } };
    req.onerror = () => reject(req.error);
  });
}
export function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
