export type RingStyle = { palette: number[][]; border: number; detail: number; shadow: number; enableShadow?: boolean; texture: boolean; crest: boolean; corner: string; frameStyle: string };

export function drawOrnateRing(ctx: CanvasRenderingContext2D, size: number, style: RingStyle) {
  const layer = document.createElement('canvas'); layer.width = layer.height = size;
  const brush = layer.getContext('2d')!;
  const colors = style.palette && style.palette.length >= 5 ? style.palette : [
    [76, 111, 48],
    [220, 235, 185],
    [10, 16, 14],
    [215, 185, 110],
    [70, 160, 130]
  ];
  const blendRgb = (a: number[], b: number[], t: number) => [
    Math.round(a[0]! + (b[0]! - a[0]!) * t),
    Math.round(a[1]! + (b[1]! - a[1]!) * t),
    Math.round(a[2]! + (b[2]! - a[2]!) * t)
  ];
  const rail = colors[0]!, light = colors[1]!, ink = colors[2]!, trim = colors[3]!, gem = colors[4]!;
  const dot = (x: number, y: number, color: number[], alpha = 1) => {
    brush.fillStyle = alpha < 1 ? `rgba(${color.join(',')},${alpha})` : `rgb(${color.join(',')})`;
    brush.fillRect(x, y, 1, 1);
  };
  const center = (size - 1) / 2, radius = size / 2 - 5, width = Math.max(2, Math.min(style.border, Math.max(3, Math.floor(size / 4))));
  
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const dx = x - center, dy = y - center, dist = Math.hypot(dx, dy);
      if (dist === 0) continue;
      const depth = radius - dist;
      if (depth >= 0 && depth < width) {
        const ldot = -(dx + dy) / (dist * 1.4142);
        if (depth < 1) {
          dot(x, y, ink);
        } else if (depth >= width - 1) {
          dot(x, y, ink);
        } else if (depth < 2) {
          if (ldot > 0.35) dot(x, y, ldot > 0.8 ? [255, 252, 230] : light);
          else if (ldot < -0.3) dot(x, y, blendRgb(rail, ink, 0.45));
          else dot(x, y, rail);
        } else if (depth >= width - 2) {
          if (ldot < -0.3) dot(x, y, blendRgb(rail, light, 0.5));
          else if (ldot > 0.3) dot(x, y, blendRgb(rail, ink, 0.6));
          else dot(x, y, rail);
        } else {
          const midFactor = 1.0 - Math.abs(depth - width / 2) / (width / 2);
          if (ldot > 0.3) dot(x, y, blendRgb(rail, light, 0.35 + 0.35 * midFactor));
          else if (ldot < -0.3) dot(x, y, blendRgb(rail, ink, 0.45));
          else dot(x, y, rail);
          if (style.texture && (x * 7 + y * 11) % 17 === 0) dot(x, y, gem);
        }
      } else if (depth >= width && depth < width + 1.8) {
        const ldot = -(dx + dy) / (dist * 1.4142);
        if (ldot > 0.2) dot(x, y, ink, Math.min(0.5, ldot * 0.45));
      }
    }
  }

  const hasCrest = Boolean(style.crest);
  if (hasCrest) {
    const mid = Math.round(center);
    const claspR = Math.max(1, Math.min(3, Math.floor(width / 2)));
    const cardinals: [number, number][] = [
      [mid, Math.round(center - radius + width / 2)],
      [Math.round(center + radius - width / 2), mid],
      [mid, Math.round(center + radius - width / 2)],
      [Math.round(center - radius + width / 2), mid]
    ];
    for (const [cx, cy] of cardinals) {
      for (let oy = -claspR; oy <= claspR; oy++) {
        for (let ox = -claspR; ox <= claspR; ox++) {
          const metric = Math.abs(ox) + Math.abs(oy);
          if (metric <= claspR) {
            dot(cx + ox, cy + oy, metric === claspR ? ink : trim);
          }
        }
      }
      dot(cx, cy, gem);
      dot(cx - 1, cy - 1, [255, 255, 255]);
      dot(cx + 1, cy + 1, ink);
    }

    if (style.detail >= 1) {
      const count = 4 + style.detail * 4;
      for (let i = 0; i < count; i++) {
        if (i % (count / 4) === 0) continue;
        const angle = (i + 0.5) * Math.PI * 2 / count;
        const cx = Math.round(center + (radius - width / 2) * Math.cos(angle));
        const cy = Math.round(center + (radius - width / 2) * Math.sin(angle));
        if (style.frameStyle === 'bamboo') {
          for (let oy = -1; oy <= 1; oy++) {
            for (let ox = -1; ox <= 1; ox++) {
              if (Math.abs(ox) + Math.abs(oy) <= 1) dot(cx + ox, cy + oy, trim);
            }
          }
          dot(cx, cy, light);
        } else if (style.corner === 'cloud') {
          dot(cx, cy, trim);
          dot(cx - 1, cy - 1, light);
        } else {
          dot(cx, cy, gem);
          dot(cx - 1, cy, light);
        }
      }
    }
  }

  if (style.shadow && style.enableShadow !== false) {
    const shadow = document.createElement('canvas');
    shadow.width = shadow.height = size;
    const sc = shadow.getContext('2d')!;
    sc.drawImage(layer, 0, 0);
    sc.globalCompositeOperation = 'source-in';
    sc.fillStyle = `rgba(${ink.join(',')},${Math.min(0.65, (45 + style.shadow * 25) / 255)})`;
    sc.fillRect(0, 0, size, size);
    const offset = Math.min(2, style.shadow);
    ctx.drawImage(shadow, offset, offset);
  }
  ctx.drawImage(layer, 0, 0);
}
