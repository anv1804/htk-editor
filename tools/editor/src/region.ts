/** Four-connected selection, bounded to this frame and the seed's color. */
export function connectedRegion(data: Uint8ClampedArray, width: number, height: number,
  x: number, y: number, tolerance: number): number[] {
  if (x < 0 || y < 0 || x >= width || y >= height) return [];
  const start = y * width + x, seed = start * 4;
  const seen = new Uint8Array(width * height), queue = [start], result: number[] = [];
  seen[start] = 1;
  for (let cursor = 0; cursor < queue.length; cursor++) {
    const at = queue[cursor]!, p = at * 4;
    if ((data[p+3]! > 0) !== (data[seed+3]! > 0)) continue;
    if (data[p+3] && Math.max(...[0,1,2].map(c => Math.abs(data[p+c]! - data[seed+c]!))) > tolerance) continue;
    result.push(at);
    for (const next of [at % width ? at-1 : -1, at % width < width-1 ? at+1 : -1, at-width, at+width]) {
      if (next >= 0 && next < seen.length && !seen[next]) { seen[next] = 1; queue.push(next); }
    }
  }
  return result;
}
