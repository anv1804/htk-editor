export type LayerView = 'result' | 'outfit' | 'headwear' | 'base';

/** Apply pending edits using the same exclusive layer ownership as exports. */
export function previewLayerEdits(output: Uint8ClampedArray, base: Uint8ClampedArray,
  source: Uint8ClampedArray, labels: Uint8ClampedArray, paint: Uint8ClampedArray,
  mask: Uint8ClampedArray, view: LayerView) {
  if (view === 'base') return;
  for (let i = 0; i < output.length; i += 4) {
    const marked = labels[i + 3]! >= 128;
    const hair = marked
      ? labels[i]! > 200 && labels[i + 1]! > 100 && labels[i + 2]! < 100
      : mask[i] === 255 && mask[i + 1] === 200 && mask[i + 2] === 0;
    if (marked) {
      const reveal = labels[i]! > 200 && labels[i + 1]! < 100;
      const erase = labels[i + 1]! > 200 && labels[i]! < 100;
      const keep = labels[i + 2]! > 200 && labels[i]! < 100;
      if (reveal) {
        if (view === 'result') output.set(base.subarray(i, i + 4), i);
        else output.fill(0, i, i + 4);
      } else if (erase || (hair && view === 'outfit') || (keep && view === 'headwear')) {
        output.fill(0, i, i + 4);
      } else if (keep || hair) output.set(source.subarray(i, i + 4), i);
    }
    if (paint[i + 3]! >= 128 && (view === 'result' || (view === 'headwear') === hair)) {
      output.set(paint.subarray(i, i + 4), i);
      output[i + 3] = 255;
    }
  }
}
