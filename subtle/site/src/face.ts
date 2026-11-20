import type {Preset} from './data';

const hexRgb = (h: string) => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const lum = (h: string) => { const [r, g, b] = hexRgb(h); return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255; };
const sat = (h: string) => { const [r, g, b] = hexRgb(h); const mx = Math.max(r, g, b), mn = Math.min(r, g, b); return mx === 0 ? 0 : (mx - mn) / mx; };
const get = (o: any, path: string) => path.split('.').reduce((c: any, k) => (c == null ? c : c[k]), o);

/** How the headline's key word looks in the style that is playing: its highlight font, its most colourful colour (never too dark), its letter case. */
export function headlineFace(p: Preset, palette?: Record<string, string>) {
  const any = p as any;
  const f = any.emphasis?.font ?? any.behind?.bigFont ?? any.font;
  const cands: string[] = [];
  for (const path of ['emphasis.color', 'recipe.emphasis.color', 'activeColor', 'recipe.active.color', 'emphasis.fill', 'container.fill', 'behind.bigColor', 'color']) {
    let v = get(any, path);
    if (v && typeof v === 'object' && v.auto) v = palette?.[v.auto] ?? v.fallback;
    if (typeof v === 'string' && /^#[0-9a-f]{6}$/i.test(v) && lum(v) > 0.32) cands.push(v);
  }
  const color = cands.sort((a, b) => sat(b) - sat(a))[0] ?? '#F2F3F4';
  const fam: string = f?.family ?? 'Figtree';
  // optical size: condensed and script faces read small next to the 600-weight sans
  const scale = /Bebas|Anton/i.test(fam) ? 1.18 : /Caveat|Pinyon|Reenie|Gloria/i.test(fam) ? 1.12 : /Instrument|Playfair|Abril|Libre/i.test(fam) ? 1.08 : /Courier/i.test(fam) ? 0.9 : /Archivo|Black|Poppins|Montserrat|Corben/i.test(fam) ? 0.94 : 1;
  const caseMode: string = any.case ?? 'sentence';
  return {family: fam, weight: f?.weight ?? 600, color, scale, transform: caseMode === 'upper' ? 'uppercase' : caseMode === 'lower' ? 'lowercase' : 'none'} as const;
}
