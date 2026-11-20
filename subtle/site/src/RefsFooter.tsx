import {useEffect, useRef, useState} from 'react';
import './refs-footer.css';
import {Dither} from './Dither';
import {ctaClick, refsUrl} from './analytics';

/* The Refs site footer, ported from refs.video (web/src/components/footer.tsx): the site's links laid out as clips on a
   V1/A1 edit timeline, a playhead drifting across that lights the clip under it; hover, focus or a drag on the ruler
   takes it over. Links point at refs.video. */

const R = 'https://refs.video';
const FROM = '?from=subtle&utm_source=subtle&utm_medium=page&utm_campaign=launch';
const DUR = 44, DRIFT = 0.2, REST = 12.5;
const timecode = (x: number) => { const t = Math.max(0, Math.round(x)), m = Math.floor((t % 3600) / 60), q = t % 60; return `${m < 10 ? '0' : ''}${m}:${q < 10 ? '0' : ''}${q}`; };
const TICKS = Array.from({length: DUR + 1}, (_, s) => s);

type Clip = {href: string; label: string; a: number; b: number; left: number; width: number; ext?: boolean};
const V1: Clip[] = [
  {href: `${R}/archive`, label: 'Archive', a: 0, b: 13, left: 0, width: 29.5455},
  {href: `${R}/channels${FROM}`, label: 'Channels', a: 13, b: 25, left: 29.5455, width: 27.2727},
  {href: `${R}/connect${FROM}`, label: 'Add to Claude', a: 26.5, b: 36, left: 60.2273, width: 21.5909},
  {href: `${R}/pricing${FROM}`, label: 'Pricing', a: 36, b: 44, left: 81.8182, width: 18.1818},
];
const A1: Clip[] = [
  {href: `${R}/about`, label: 'About', a: 0.5, b: 6.5, left: 1.1364, width: 13.6364},
  {href: `${R}/how-we-measure`, label: 'Method', a: 6.5, b: 13, left: 14.7727, width: 14.7727},
  {href: `${R}/source-policy`, label: 'Source policy', a: 13, b: 24, left: 29.5455, width: 25.0},
  {href: `${R}/terms`, label: 'Terms', a: 24, b: 30, left: 54.5455, width: 13.6364},
  {href: `${R}/privacy`, label: 'Privacy', a: 30, b: 37, left: 68.1818, width: 15.9091},
  {href: 'https://x.com/pratyushrungta', label: 'Contact', a: 37.5, b: 44, left: 85.2273, width: 14.7727, ext: true},
];

export function RefsFooter() {
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = root.current; if (!el) return;
    const box = el.querySelector<HTMLElement>('.lf-lanes'), ph = el.querySelector<HTMLElement>('.lf-ph'), tc = el.querySelector<HTMLElement>('.lf-tc'), ruler = el.querySelector<HTMLElement>('[data-ruler]');
    if (!box || !ph || !tc || !ruler) return;
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const s = {t: REST, hold: false, drag: false, visible: false, raf: 0, last: 0, w: 1, sec: -1, left: false};
    const clips = [...box.querySelectorAll<HTMLElement>('[data-clip]')].map((c) => ({el: c, a: +c.dataset.a!, b: +c.dataset.b!, on: false}));
    const draw = () => {
      const x = (s.t / DUR) * s.w; ph.style.transform = `translate3d(${x.toFixed(1)}px,0,0)`;
      const sec = Math.floor(s.t); if (sec !== s.sec) { s.sec = sec; tc.textContent = timecode(sec); }
      const left = x > s.w - 40; if (left !== s.left) { s.left = left; tc.dataset.side = left ? 'left' : 'right'; }
      for (const c of clips) { const on = s.t >= c.a && s.t < c.b; if (on !== c.on) { c.on = on; c.el.toggleAttribute('data-live', on); } }
    };
    const tick = (now: number) => { s.raf = 0; if (!s.hold) s.t = (s.t + Math.min(0.1, (now - s.last) / 1000) * DRIFT) % DUR; s.last = now; draw(); if (s.visible && !s.hold) s.raf = requestAnimationFrame(tick); };
    const run = () => { if (!still && !s.raf && s.visible && !s.hold) { s.last = performance.now(); s.raf = requestAnimationFrame(tick); } };
    const stop = () => { cancelAnimationFrame(s.raf); s.raf = 0; };
    let pending = 0;
    const paint = () => { if (!pending) pending = requestAnimationFrame(() => { pending = 0; draw(); }); };
    const hold = (on: boolean) => { s.hold = on; if (on) stop(); else run(); };
    const seek = (cx: number) => { const r = box.getBoundingClientRect(); s.t = Math.min(DUR - 0.001, Math.max(0, ((cx - r.left) / r.width) * DUR)); paint(); };
    const onMove = (e: PointerEvent) => { if (e.pointerType === 'touch' && !s.drag) return; if (!s.hold) hold(true); seek(e.clientX); };
    const onLeave = (e: PointerEvent) => { if (e.pointerType !== 'touch' && !s.drag) hold(false); };
    const onDown = (e: PointerEvent) => { s.drag = true; ruler.setPointerCapture(e.pointerId); hold(true); seek(e.clientX); };
    const up = (e: PointerEvent) => { if (!s.drag) return; s.drag = false; ruler.releasePointerCapture(e.pointerId); if (e.pointerType === 'touch') hold(false); };
    const onFocusIn = (e: FocusEvent) => { const c = (e.target as Element).closest<HTMLElement>('[data-clip]'); if (!c) return; s.t = +c.dataset.a! + 0.01; hold(true); paint(); };
    const onFocusOut = (e: FocusEvent) => { if (!box.contains(e.relatedTarget as Node)) hold(false); };
    box.addEventListener('pointermove', onMove);
    box.addEventListener('pointerleave', onLeave);
    ruler.addEventListener('pointerdown', onDown);
    ruler.addEventListener('pointerup', up);
    ruler.addEventListener('pointercancel', up);
    box.addEventListener('focusin', onFocusIn);
    box.addEventListener('focusout', onFocusOut);
    const ro = new ResizeObserver(() => { s.w = Math.max(1, box.getBoundingClientRect().width); draw(); });
    ro.observe(box);
    const io = new IntersectionObserver((en) => { s.visible = en[0].isIntersecting; if (s.visible) run(); else stop(); });
    io.observe(el);
    return () => {
      stop(); cancelAnimationFrame(pending); ro.disconnect(); io.disconnect();
      box.removeEventListener('pointermove', onMove); box.removeEventListener('pointerleave', onLeave);
      ruler.removeEventListener('pointerdown', onDown); ruler.removeEventListener('pointerup', up); ruler.removeEventListener('pointercancel', up);
      box.removeEventListener('focusin', onFocusIn); box.removeEventListener('focusout', onFocusOut);
    };
  }, []);

  const clip = (c: Clip) => (
    <li key={c.label} className="lf-clip" data-clip data-a={c.a} data-b={c.b} style={{left: `calc(${c.left}% + 1px)`, width: `calc(${c.width}% - 2px)`}}>
      <a href={c.href} {...(c.ext ? {target: '_blank', rel: 'noopener noreferrer'} : {})}>
        <span className="lf-lbl">{c.label}{c.ext && <span className="lf-ext" aria-hidden="true"> ↗</span>}</span>
      </a>
    </li>
  );

  return (
    <footer className="lf" ref={root}>
      <div className="lf-in">
        <a className="lf-wm" href={`${R}${FROM}`}><span aria-hidden className="lf-sym" />refs</a>
        <p className="lf-blurb">Films that moved people, measured cut by cut. Subtle is Refs' open-source caption library; the clip on this page is used only to demo captions.</p>
        <div className="lf-tl">
          <div className="lf-trk" aria-hidden="true"><div className="lf-trk-gap" /><div className="lf-trk-row"><span className="lf-num">V1</span></div><div className="lf-trk-row"><span className="lf-num">A1</span></div></div>
          <div className="lf-lanes">
            <div className="lf-ruler" data-ruler aria-hidden="true">
              {TICKS.map((s) => (
                <span key={s} className={`lf-t${s % 5 === 0 ? ' lf-t5' : ''}`} style={{left: `${((s / DUR) * 100).toFixed(4)}%`}}><i />{s % 10 === 0 && s > 0 && <b className="lf-num">{timecode(s)}</b>}</span>
              ))}
            </div>
            <nav aria-label="Refs">
              <ul role="list" className="lf-track">{V1.map(clip)}</ul>
              <ul role="list" className="lf-track">{A1.map(clip)}</ul>
            </nav>
            <div className="lf-ph" aria-hidden="true"><span className="lf-ph-h" /><span className="lf-ph-l" /><span className="lf-tc lf-num" data-side="right">00:13</span></div>
          </div>
        </div>
        <div className="lf-foot"><span>© 2026 Refs · Subtle is MIT · fonts SIL OFL</span><span className="lf-label">End of reel <span className="lf-dot" aria-hidden="true" /></span></div>
      </div>
    </footer>
  );
}

/** Real films from the Refs library with their real measurements (refs MCP search_videos, 19 Nov 2026). */
type Film = {ref: string; id: string; by: string; thumb: string; shots: number; cpm: number; bpm?: number};
const tw = (p: string) => `https://pbs.twimg.com/${p}?name=small`;
const FILMS: Film[] = [
  {ref: 'REF-3252', id: '1981371951894667279', by: 'LTX Studio', thumb: tw('amplify_video_thumb/1981371797661765633/img/bhlpvR6Sm3_-YnsN.jpg'), shots: 25, cpm: 30.6, bpm: 144},
  {ref: 'REF-4798', id: '1782782211399279076', by: 'Perplexity', thumb: tw('ext_tw_video_thumb/1782779590324162560/pu/img/33yZVuc2SN61r523.jpg'), shots: 35, cpm: 29.6, bpm: 145},
  {ref: 'REF-1835', id: 'yt-If-SN1yG2kE', by: 'BMW', thumb: 'https://i.ytimg.com/vi/If-SN1yG2kE/mqdefault.jpg', shots: 43, cpm: 33.6},
  {ref: 'REF-3204', id: '1894447062206615868', by: 'Factory', thumb: tw('ext_tw_video_thumb/1894438362091581440/pu/img/MxsWlTVSLIeDM0Oi.jpg'), shots: 13, cpm: 12.5, bpm: 123},
  {ref: 'REF-3828', id: '1840757312912564366', by: 'Wispr Flow', thumb: tw('ext_tw_video_thumb/1840737594386391040/pu/img/HGeYQSicgtTWSw3A.jpg'), shots: 17, cpm: 10.4, bpm: 94},
  {ref: 'REF-3758', id: '2082876358397477109', by: 'Hebbia', thumb: tw('media/HOfcte6WQAAhj7I.jpg'), shots: 3, cpm: 3.3, bpm: 112},
  {ref: 'REF-5304', id: '2115050943557537966', by: 'Bitget Wallet', thumb: tw('amplify_video_thumb/2115041643409887232/img/xc1UL-OCPctZsEY5.jpg'), shots: 19, cpm: 22, bpm: 92},
  {ref: 'REF-3418', id: '1952732150928724043', by: 'Google DeepMind', thumb: tw('media/Gxl_qUNX0AE0d1N.jpg'), shots: 25, cpm: 10.1},
  {ref: 'REF-4968', id: '1994353194420547837', by: 'Kimi', thumb: tw('amplify_video_thumb/1994343511559409664/img/iOCSG4f-Q2Gi7PfD.jpg'), shots: 9, cpm: 12, bpm: 84},
  {ref: 'REF-4806', id: '1797976337849995414', by: 'Captions', thumb: tw('ext_tw_video_thumb/1797974373745278976/pu/img/pmfuO4kgrhQquoCn.jpg'), shots: 19, cpm: 32.2, bpm: 129},
  {ref: 'REF-5386', id: '2105341653468774723', by: 'Reflect', thumb: tw('amplify_video_thumb/2104982548606562304/img/IJq32DJsLsNSDDvY.jpg'), shots: 1, cpm: 0, bpm: 100},
  {ref: 'REF-5796', id: '2045655599468134649', by: 'Creator', thumb: tw('amplify_video_thumb/2045653532036968448/img/yN5IDLgEuR1lb-_j.jpg'), shots: 9, cpm: 5.3, bpm: 110},
];

/** One row of the reel: the films twice over, so the loop is seamless. */
function ReelRow({films, reverse}: {films: Film[]; reverse?: boolean}) {
  const all = [...films, ...films];
  return (
    <div className={'reel-row' + (reverse ? ' rev' : '')}>
      <ul className="reel-track" role="list">
        {all.map((f, i) => (
          <li key={f.ref + i} aria-hidden={i >= films.length || undefined}>
            <a href={`${R}/v/${f.id}${FROM}`} tabIndex={i >= films.length ? -1 : undefined}>
              <img src={f.thumb} alt={`${f.by} launch film`} loading="lazy" decoding="async" referrerPolicy="no-referrer" />
              <span className="reel-ref">{f.ref}</span>
              <span className="reel-meta">
                <b>{f.by}</b>
                <span>{f.shots} {f.shots === 1 ? 'shot' : 'shots'}{f.cpm ? ` · ${f.cpm} cuts/min` : ''}{f.bpm ? ` · ${f.bpm} BPM` : ''}</span>
              </span>
              {/* a cut map: one tick per shot, like the film pages on Refs */}
              <span className="reel-cuts" aria-hidden="true">{Array.from({length: Math.min(f.shots, 40)}, (_, k) => <i key={k} />)}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The Refs upsell above the footer: Subtle does the captions, Refs has the whole film. */
export function RefsUpsell() {
  return (
    <section className="upsell" aria-labelledby="up-h">
      <div className="up-in">
        <Dither shape="radial" x={0.02} y={1} reach={0.5} max={0.8} className="dz dz-up-l" />
        <Dither shape="radial" x={0.98} y={1} reach={0.5} max={0.8} className="dz dz-up-r" />
        <div className="reel" aria-label="Films from the Refs library">
          <ReelRow films={FILMS.slice(0, 6)} />
          <ReelRow films={FILMS.slice(6)} reverse />
        </div>
        <h2 id="up-h">Captions are one cut. <span>Refs has the whole film.</span></h2>
        <p className="up-sub">5,400+ launch videos taken apart shot by shot: timing, cuts, palette, type, motion and sound, each with a written blueprint. Plug it into Claude and it plans your launch film from real references.</p>
        <ul className="up-facts" role="list">
          <li><b>5,400+</b><span>launch films, measured</span></li>
          <li><b>15</b><span>plates per film</span></li>
          <li><b>MCP</b><span>for Claude Code, Codex, Cursor</span></li>
        </ul>
        <div className="up-cta">
          <a className="pill primary big" href={refsUrl('/')} onClick={() => ctaClick('footer')}>Explore Refs</a>
          <a className="pill ghost big" href={refsUrl('/connect')} onClick={() => ctaClick('footer')}>Add Refs to Claude</a>
        </div>
      </div>
    </section>
  );
}


/** The offer bar above the header, like refs.video's: Refs Pro's first year at 50% off (REFS50, applied at checkout with
 *  no code) and a live countdown to when the offer ends. Gone once it has ended. */
const OFFER_ENDS = Date.parse('2026-11-30T18:29:59Z'); // end of 30 Nov in India, as FIRST_YEAR_OFFER_UNTIL on refs.video
export function OfferBar() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const left = OFFER_ENDS - now;
  if (left <= 0) return null;
  const d = Math.floor(left / 864e5), h = Math.floor(left / 36e5) % 24, m = Math.floor(left / 6e4) % 60, sec = Math.floor(left / 1e3) % 60;
  const two = (n: number) => String(n).padStart(2, '0');
  const clock = <span className="ob-clock" role="timer" aria-label={`${d} days ${h} hours ${m} minutes left`}>{d > 0 && <>{d}<i>d</i> </>}{two(h)}<i>:</i>{two(m)}<i>:</i>{two(sec)}</span>;
  return (
    <div className="ob">
      <span className="long"><b>Refs</b>: launch films, broken down for Claude · Pro <b>50% off</b> · ends in {clock} ·</span>
      <span className="short"><b>Refs</b> Pro <b>50% off</b> · {clock} ·</span>
      <a href={refsUrl('/pricing') + '#yearly'} onClick={() => ctaClick('header')}>Claim →</a>
    </div>
  );
}
