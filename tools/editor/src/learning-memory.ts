const prefix = 'outfit-learning:v1:';
export interface LearningMemory {
  version: 1;
  mask: string;
  paint: string;
  pixels: number;
  updatedAt: number;
}

/** Scope feedback to the actual source images and grid, never just filename. */
export async function learningKey(base: string, outfit: string, rows: number, cols: number) {
  const bytes = new TextEncoder().encode(JSON.stringify([base, outfit, rows, cols]));
  const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return prefix + [...hash].map(v => v.toString(16).padStart(2, '0')).join('');
}

export function readLearning(storage: Storage, key: string): LearningMemory | null {
  try {
    const value = JSON.parse(storage.getItem(key) || 'null');
    if (value?.version !== 1 || !value.mask?.startsWith('data:image/png;base64,') ||
        !value.paint?.startsWith('data:image/png;base64,') || !Number.isFinite(value.pixels)) return null;
    return value;
  } catch { return null; }
}

export function writeLearning(storage: Storage, key: string, value: LearningMemory) {
  // Keep earlier confirmed records if browser quota prevents this save.
  storage.setItem(key, JSON.stringify(value));
}

export function mergeConfirmedPixels(previous: Uint8ClampedArray, current: Uint8ClampedArray,
  reset?: Uint8ClampedArray) {
  if (previous.length!==current.length || (reset && reset.length!==current.length)) throw new Error('Grid changed');
  const merged=previous.slice();
  for (let i=0;i<merged.length;i+=4) {
    if (reset && reset[i+3]!>=128) merged.fill(0,i,i+4);
    if (current[i+3]!>=128) merged.set(current.subarray(i,i+4),i);
  }
  return merged;
}
