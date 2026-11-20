import React, {useEffect, useRef} from 'react';

/** Behind the phone: the playing picture, re-drawn a few times a second as an ordered (Bayer-matrix) dither of tiny ivory
 *  dots. It follows the clip's light and dark like a screen lighting the room, but stays a quiet, technical texture. */
const CELL = 7; // css px per dither cell
const DOT = 2; // css px dot size
// 4x4 Bayer matrix, thresholds in 0..1
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);

export function Ambient({poster}: {poster: string}) {
  const cv = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = cv.current;
    const ctx = c?.getContext('2d');
    if (!c || !ctx) return;
    const small = document.createElement('canvas');
    const sctx = small.getContext('2d', {willReadFrequently: true});
    if (!sctx) return;
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let cols = 0, rows = 0, dpr = 1;
    const size = () => {
      const r = c.getBoundingClientRect();
      dpr = Math.min(2, window.devicePixelRatio || 1);
      cols = Math.max(8, Math.floor(r.width / CELL));
      rows = Math.max(8, Math.floor(r.height / CELL));
      c.width = Math.round(cols * CELL * dpr);
      c.height = Math.round(rows * CELL * dpr);
      small.width = cols;
      small.height = rows;
    };
    // draw a source (video or poster) as dots: crop it to the grid's aspect, then threshold each cell against the matrix
    const render = (src: CanvasImageSource, sw: number, sh: number) => {
      if (!cols) return;
      const want = cols / rows, have = sw / sh;
      let sx = 0, sy = 0, cw = sw, ch = sh;
      if (have > want) { cw = sh * want; sx = (sw - cw) / 2; } else { ch = sw / want; sy = (sh - ch) / 2; }
      try { sctx.drawImage(src, sx, sy, cw, ch, 0, 0, cols, rows); } catch { return; }
      const px = sctx.getImageData(0, 0, cols, rows).data;
      ctx.clearRect(0, 0, c.width, c.height);
      ctx.fillStyle = 'rgba(242, 243, 244, 0.9)';
      const s = CELL * dpr, d = DOT * dpr, off = (s - d) / 2;
      for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
          const i = (y * cols + x) * 4;
          // luminance, with a contrast curve so mid-tones break up into a pattern instead of a flat field
          const l = (0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2]) / 255;
          const v = Math.min(1, Math.max(0, (l - 0.18) * 1.6));
          if (v > BAYER[(y & 3) * 4 + (x & 3)]) ctx.fillRect(x * s + off, y * s + off, d, d);
        }
      }
    };
    size();
    const ro = new ResizeObserver(size);
    ro.observe(c);
    const img = new Image();
    img.src = poster;
    img.onload = () => render(img, img.naturalWidth, img.naturalHeight);
    const tick = () => {
      if (document.hidden) return;
      const v = document.querySelector<HTMLVideoElement>('.screen video');
      if (!v || v.readyState < 2 || !v.videoWidth) return;
      // the packed video holds picture | matte side by side: take the picture half
      const sw = v.videoWidth / v.videoHeight > 0.8 ? v.videoWidth / 2 : v.videoWidth;
      render(v, sw, v.videoHeight);
    };
    const id = still ? 0 : window.setInterval(tick, 200);
    return () => { window.clearInterval(id); ro.disconnect(); };
  }, [poster]);
  return <div className="ambient" aria-hidden><canvas ref={cv} /></div>;
}
