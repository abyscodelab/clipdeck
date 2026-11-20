import React, {useEffect, useRef} from 'react';

/** A static ordered-dither field (4x4 Bayer matrix): ivory dots on a grid whose density follows a gradient. The same
 *  texture as the hero's live dither, used as quiet decoration across the page. Drawn once, and again on resize. */
type Shape =
  | 'down' // dense at the top, fading out downward
  | 'up' // dense at the bottom, fading out upward
  | 'radial' // dense at (x, y), fading out with distance
  | 'band'; // dense in the middle row, fading to both edges

const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);

export function Dither({shape, cell = 7, dot = 2, max = 0.9, x = 0.5, y = 0.5, reach = 0.6, color = '242, 243, 244', className, style}: {
  shape: Shape; cell?: number; dot?: number; max?: number; x?: number; y?: number; reach?: number; color?: string;
  className?: string; style?: React.CSSProperties;
}) {
  const cv = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = cv.current;
    const ctx = c?.getContext('2d');
    if (!c || !ctx) return;
    const draw = () => {
      const r = c.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const cols = Math.max(1, Math.floor(r.width / cell)), rows = Math.max(1, Math.floor(r.height / cell));
      c.width = Math.round(r.width * dpr);
      c.height = Math.round(r.height * dpr);
      ctx.clearRect(0, 0, c.width, c.height);
      ctx.fillStyle = `rgba(${color}, 1)`;
      const s = cell * dpr, d = dot * dpr, off = (s - d) / 2;
      const aspect = r.width / Math.max(1, r.height);
      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const u = (i + 0.5) / cols, v = (j + 0.5) / rows;
          let t: number;
          if (shape === 'down') t = 1 - v / reach;
          else if (shape === 'up') t = 1 - (1 - v) / reach;
          else if (shape === 'band') t = 1 - Math.abs(v - 0.5) * 2 / reach;
          else t = 1 - Math.hypot((u - x) * aspect, v - y) / (reach * Math.max(1, aspect));
          t = Math.max(0, Math.min(1, t)) * max;
          if (t > BAYER[(j & 3) * 4 + (i & 3)]) ctx.fillRect(i * s + off, j * s + off, d, d);
        }
      }
    };
    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(c);
    return () => ro.disconnect();
  }, [shape, cell, dot, max, x, y, reach, color]);
  return <canvas ref={cv} className={'dither' + (className ? ' ' + className : '')} style={style} aria-hidden="true" />;
}
