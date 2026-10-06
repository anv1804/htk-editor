import type { MapScene, SceneLayer } from './map-scene-model';
export type SceneImages = Map<string, HTMLImageElement>;

export function drawLayer(ctx: CanvasRenderingContext2D, scene: MapScene, layer: SceneLayer, images: SceneImages, camera = 0) {
  ctx.imageSmoothingEnabled = false;
  const offset = Math.round(camera * (1 - layer.parallax));
  const assets = new Map(scene.assets.map(a => [a.id, a]));
  for (const item of layer.items) {
    const a = assets.get(item.assetId), img = images.get(item.assetId);
    if (!a || !img) continue;
    ctx.save();
    ctx.translate(item.x + offset + (item.flipX ? a.w : 0), item.y + (item.flipY ? a.h : 0));
    ctx.scale(item.flipX ? -1 : 1, item.flipY ? -1 : 1);
    ctx.drawImage(img, 0, 0);
    ctx.restore();
  }
}

/** Shared preview/export compositor; opacity applies to the whole layer. */
export function renderScene(target: HTMLCanvasElement, scene: MapScene, images: SceneImages, camera = 0) {
  if (target.width !== scene.width) target.width = scene.width;
  if (target.height !== scene.height) target.height = scene.height;
  const ctx = target.getContext('2d')!;
  ctx.clearRect(0, 0, target.width, target.height);
  ctx.imageSmoothingEnabled = false;
  let scratch: HTMLCanvasElement | undefined;
  for (const layer of scene.layers) {
    if (!layer.visible || layer.opacity === 0) continue;
    if (layer.opacity === 1) { drawLayer(ctx, scene, layer, images, camera); continue; }
    if (!scratch) { scratch = document.createElement('canvas'); scratch.width = scene.width; scratch.height = scene.height; }
    const c = scratch.getContext('2d')!; c.clearRect(0, 0, scratch.width, scratch.height);
    drawLayer(c, scene, layer, images, camera);
    ctx.globalAlpha = layer.opacity; ctx.drawImage(scratch, 0, 0); ctx.globalAlpha = 1;
  }
}
