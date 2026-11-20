import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {ctaClick, refsUrl, track} from './analytics';
import {loadFonts} from './engine';
import {CATEGORY, CLIP, INSTALL, PRESETS, REPO, SPEECH_ORDER, isBehind, loadCaptions, stylesFor, type PackedCaptions} from './data';
import {Stage, canCutout, type StageHandle} from './Stage';
import {buildOverride, currentAccent, isTweaked, mergedStyle, prepareCaptions, type Edits, type Tweaks} from './tweaks';
import {buildPrompt, styleJson} from './prompt';
import {copyText} from './copy';
import {timeStore} from './timeStore';
import {Ambient} from './Ambient';
import {Filmstrip} from './Filmstrip';
import {Drawer, TweakControls, WordList} from './Tweak';
import {How} from './Sections';
import {OfferBar, RefsFooter, RefsUpsell} from './RefsFooter';
import {Dither} from './Dither';
import {Icon, pad, useMedia} from './ui';
import {headlineFace} from './face';

const CATNAME: Record<string, string> = {bold: 'Bold', elegant: 'Editorial', minimal: 'Minimal'};

function readHash() {
  const q = new URLSearchParams(location.hash.replace(/^#/, ''));
  const st = q.get('style') ?? '';
  return {style: SPEECH_ORDER.includes(st) ? st : 'cover'};
}

export default function App() {
  const init = useMemo(readHash, []);
  const [styleName, setStyleName] = useState(init.style);
  const [filter, setFilter] = useState('top');
  const [tweaks, setTweaks] = useState<Tweaks>({});
  // one event per style someone settles on (scrubbing through with the arrows sends only the last)
  const firstStyle = useRef(true);
  useEffect(() => {
    if (firstStyle.current) { firstStyle.current = false; return; }
    const t = setTimeout(() => track('subtle_style_viewed', {style: styleName}), 600);
    return () => clearTimeout(t);
  }, [styleName]);
  const [edits, setEdits] = useState<Record<string, Edits>>({});
  const [highlights, setHighlights] = useState(true);
  const [behindOn, setBehindOn] = useState(true);
  const [pack, setPack] = useState<PackedCaptions | null>(null);
  const [muted, setMuted] = useState(true);
  const [playing, setPlaying] = useState(true);
  const [hover, setHover] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<null | 'tweak' | 'words'>(null);
  const [copied, setCopied] = useState('');
  const [faceName, setFaceName] = useState(init.style);
  const stage = useRef<StageHandle>(null);
  const stripRef = useRef<HTMLDivElement>(null);
  const progress = useRef<HTMLDivElement>(null);
  const firstScroll = useRef(true);
  const compact = useMedia('(max-width: 1100px)');

  useEffect(() => { (window as any).__stage = stage.current; });
  const names = stylesFor(filter);
  const preset = PRESETS[styleName];

  useEffect(() => {
    let live = true;
    loadCaptions().then((d) => live && setPack(d));
    return () => { live = false; };
  }, []);

  // back/forward and edited links follow the hash; the URL remembers the choice
  useEffect(() => {
    const on = () => setStyleName(readHash().style);
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  useEffect(() => { history.replaceState(null, '', `#style=${styleName}`); }, [styleName]);

  // fonts of every top style load in the background, so switching is instant
  useEffect(() => {
    const ric: any = (window as any).requestIdleCallback ?? ((f: () => void) => setTimeout(f, 1500));
    const id = ric(() => {
      (async () => {
        for (const n of [styleName, ...stylesFor('top').slice(0, 6)]) {
          try { await loadFonts(PRESETS[n] as any); } catch {}
        }
      })();
    });
    return () => (window as any).cancelIdleCallback?.(id);
  }, []);
  // the styles either side load their fonts as soon as one is shown, so ← → (and the strip) switch at once; then the rest
  useEffect(() => {
    const i = Math.max(0, names.indexOf(styleName));
    const near = [1, -1, 2, 3].map((d) => names[(i + d + names.length) % names.length]);
    const t = setTimeout(() => {
      (async () => {
        for (const n of [...near, ...names.filter((n) => !near.includes(n))]) {
          try { await loadFonts(PRESETS[n] as any); } catch {}
        }
      })();
    }, 120);
    return () => clearTimeout(t);
  }, [styleName, names]);
  // the headline word changes face once its font is ready
  useEffect(() => {
    let live = true;
    loadFonts(preset as any).catch(() => {}).then(() => live && setFaceName(styleName));
    return () => { live = false; };
  }, [styleName]);

  const base = pack?.styles[styleName];
  // one set of tweaks for every style (owner: a filter you set stays when you switch styles)
  const tw = tweaks;
  const pageEdits = edits[styleName] ?? {};
  const over = useMemo(() => buildOverride(preset, tw), [preset, tw]);
  const style = useMemo(() => mergedStyle(preset, over, pack?.stylePatch?.[styleName]), [preset, over, pack, styleName]);
  const captions = useMemo(
    () => (base && pack ? prepareCaptions(base, pack.video, {edits: pageEdits, highlights, y: tw?.y}) : null),
    [base, pack, pageEdits, highlights, tw?.y],
  );
  const canBehind = isBehind(styleName);
  const behind = canBehind && behindOn && canCutout;
  const palette = (base as any)?.palette as Record<string, string> | undefined;
  const tweakedAny = isTweaked(tw) || Object.keys(pageEdits).length > 0 || !highlights || !behindOn;
  const tweakedSet = '';
  const face = useMemo(() => headlineFace(PRESETS[faceName], (pack?.styles[faceName] as any)?.palette), [faceName, pack]);

  const pick = useCallback((n: string) => { setStyleName(n); setHover(null); }, []);
  const pickAndTop = useCallback((n: string) => {
    setStyleName(n);
    setHover(null);
    window.scrollTo({top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  }, []);

  // a style chosen from outside the shown filter keeps the strip honest
  useEffect(() => { if (!names.includes(styleName)) setFilter('all'); }, [styleName]);

  // keep the chosen frame centred in the strip (the page itself never scrolls)
  useEffect(() => {
    const el = stripRef.current?.querySelector<HTMLElement>(`[data-style="${styleName}"]`);
    const s = stripRef.current;
    if (!el || !s) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    s.scrollTo({left: el.offsetLeft - (s.clientWidth - el.clientWidth) / 2, behavior: firstScroll.current || reduce ? 'auto' : 'smooth'});
    firstScroll.current = false;
  }, [styleName, filter]);

  // the ← → buttons and the arrow keys step through the styles
  const step = (dir: 1 | -1) => {
    const i = names.indexOf(styleName);
    pick(names[(Math.max(0, i) + dir + names.length) % names.length]);
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return;
      const inStrip = !!stripRef.current?.contains(t);
      if (!(e.key === 'ArrowRight' || e.key === 'ArrowLeft') || e.metaKey || e.ctrlKey || e.altKey) return;
      e.preventDefault();
      const dir = e.key === 'ArrowRight' ? 1 : -1;
      const i = names.indexOf(styleName);
      const n = names[(Math.max(0, i) + dir + names.length) % names.length];
      pick(n);
      if (inStrip) requestAnimationFrame(() => stripRef.current?.querySelector<HTMLElement>(`[data-style="${n}"]`)?.focus({preventScroll: true}));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const doCopy = async (id: string, text: string) => {
    const ok = await copyText(text);
    if (ok) { setCopied(id); setTimeout(() => setCopied((c) => (c === id ? '' : c)), 1700); }
    track('subtle_copied', {what: id, style: styleName, tweaked: Object.keys(tweaks).length > 0, ok});
  };
  const promptText = () => buildPrompt({preset, tweaks: tw, highlights, behindOn: !canBehind || behindOn, edits: pageEdits, pages: base?.pages ?? []});

  const setTw = (patch: Partial<Tweaks>) => { setTweaks((m) => ({...m, ...patch})); track('subtle_tweaked', {keys: Object.keys(patch), style: styleName}); };
  const bump = (d: number) => setTweaks((m) => ({...m, size: Math.max(60, Math.min(180, (m.size ?? 100) + d))}));
  const reset = () => {
    setTweaks({});
    setEdits((m) => { const {[styleName]: _x, ...r} = m; return r; });
    setHighlights(true); setBehindOn(true);
  };
  const setEdit = useCallback((i: number, v: string | null) => {
    setEdits((m) => {
      const cur = {...(m[styleName] ?? {})};
      if (v == null) delete cur[i]; else cur[i] = v;
      return {...m, [styleName]: cur};
    });
  }, [styleName]);

  // the playhead
  const onTime = useCallback((ms: number) => {
    timeStore.set(ms);
    const d = pack?.video.durationMs;
    if (progress.current && d) progress.current.style.transform = `scaleX(${Math.min(1, ms / d)})`;
  }, [pack]);

  useEffect(() => {
    if (drawer && compact) document.querySelector('.phone-col')?.scrollIntoView({block: 'start', behavior: 'smooth'});
  }, [drawer, compact]);

  const accentNow = tw?.accent ?? currentAccent(preset, palette);
  const sizeNow = tw?.size ?? 100;
  const yNow = tw?.y ?? preset.position.y;
  const caseNow = tw?.case ?? preset.case;
  const preview = hover && hover !== styleName ? hover : null;
  const num = SPEECH_ORDER.indexOf(styleName) + 1;
  const tweakProps = {
    preset, tw, setTw, bump, accentNow, sizeNow, yNow, caseNow, highlights, setHighlights, canBehind, behind, canCutout, setBehindOn,
    tweakedAny, reset, openWords: () => setDrawer('words'),
  };
  const sheetH = drawer === 'words' ? '58dvh' : drawer === 'tweak' ? '46dvh' : '0px';
  const label = preset.label ?? preset.name;
  const note = canBehind && !canCutout ? 'This browser has no WebGL, so the big words sit in front.' : canBehind && behind ? 'Behind him on the wide shots; on the close-up (23 to 28 s) the word stays out of his face.' : '';

  const nowInfo = (
    <div className="now" aria-live="polite">
      <p className="kicker">Now showing <span>{pad(num)} / {SPEECH_ORDER.length}</span></p>
      <h2 key={styleName} className="swap">{label}</h2>
      <p className="tags">
        <span>{CATNAME[CATEGORY[styleName]] ?? 'Style'}</span>
        {canBehind && <span className="bhtag">Behind you</span>}
      </p>
      <p key={styleName + 'd'} className="desc swap">{preset.description}</p>
      <p className="cli"><code>--style {preset.name}</code></p>
    </div>
  );

  return (
    <>
      <OfferBar />
      <header className="top">
        <a className="brand" href={refsUrl('/')} aria-label="Refs" onClick={() => ctaClick('header', styleName)}>
          <img src="/brand/refs-symbol-white.svg" alt="" width="18" height="20" />
          <span>refs</span>
        </a>
        <nav aria-label="Page">
          <a href="#styles">Styles</a>
          <a href="#how">How it works</a>
          <a className="pill ghost" href={`https://${REPO}`} target="_blank" rel="noreferrer">{Icon.gh}<span>GitHub</span></a>
        </nav>
      </header>

      <main data-sheet={drawer ?? ''} style={{'--sheet-h': sheetH} as React.CSSProperties}>
        <section className="hero" aria-label="Caption studio">
          <div className="hero-head">
            <h1>
              <span className="l1 up" style={{'--d': '60ms'} as any}>Subtitles worth</span>
              <span className="l2 up" style={{'--d': '140ms', '--fs': face.scale} as any}>
                <span
                  key={faceName}
                  className="word"
                  style={{fontFamily: `"${face.family}", Figtree, sans-serif`, fontWeight: face.weight, color: face.color, textTransform: face.transform}}
                >stealing.</span>
              </span>
            </h1>
          </div>

          <div className="stage up" style={{'--d': '320ms'} as any}>
            <Ambient poster={CLIP.poster} />
            <div className="stage-grid">
              {!compact && <aside className="now-card">{nowInfo}</aside>}

              <div className="phone-col">
                {/* prev / next: big round buttons on both sides of the phone (also the ← → keys) */}
                <button type="button" className="nav-arrow prev" aria-label="Previous style" onClick={() => step(-1)}>
                  <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </button>
                <button type="button" className="nav-arrow next" aria-label="Next style" onClick={() => step(1)}>
                  <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </button>
                <div className="phone" onClick={(e) => { if (!(e.target as HTMLElement).closest('button, a')) stage.current?.togglePlay(); }}>
                  <div className="bezel">
                    <div className="screen">
                      <img className="poster" src={CLIP.poster} alt="" />
                      {captions ? (
                        <div className="stagewrap"><Stage
                          ref={stage}
                          clipKey="long"
                          video={CLIP.video}
                          person={CLIP.person}
                          captions={captions}
                          style={style}
                          behind={behind}
                          onPlaying={setPlaying}
                          onMuted={setMuted}
                          onTime={onTime}
                          startMuted={muted}
                        /></div>
                      ) : <div className="loading">Loading captions…</div>}
                      {preview && (
                        <div className="peek" aria-hidden>
                          <img src={`/demo/stills/${preview}.jpg`} alt="" />
                          <span className="peeklabel">Preview · {PRESETS[preview].label ?? preview}</span>
                        </div>
                      )}
                      <div className="ctl">
                        <button className="round" onClick={() => { const m = stage.current?.toggleMute(); if (m != null) setMuted(m); }} aria-label={muted ? 'Unmute' : 'Mute'}>
                          {muted ? Icon.mute : Icon.sound}{muted && <span className="lbl">Tap for sound</span>}
                        </button>
                        <span className="grow" />
                        <button className="round" onClick={() => stage.current?.restart()} aria-label="Restart">{Icon.restart}</button>
                        <button className="round" onClick={() => stage.current?.togglePlay()} aria-label={playing ? 'Pause' : 'Play'}>{playing ? Icon.pause : Icon.play}</button>
                      </div>
                      <div className="playhead" aria-hidden><div ref={progress} /></div>
                    </div>
                  </div>
                </div>
              </div>

              {!compact && (
                <aside className="tweak-card" aria-label="Tweak">
                  <p className="kicker">Tweak <span>{label}</span></p>
                  <TweakControls {...tweakProps} />
                </aside>
              )}
            </div>

            {compact && <div className="now-compact">{nowInfo}</div>}

            <p className="sub">35 caption styles for Claude Code, six of them behind the speaker. Open source, runs on your Mac. <span className="dsk">Everything on this page is the real engine, running live.</span></p>

            <div className="cta">
              <button className="pill primary big" onClick={() => doCopy('prompt', promptText())}>
                {copied === 'prompt' ? Icon.check : Icon.copy}<span>{copied === 'prompt' ? 'Copied' : 'Copy prompt'}</span>
              </button>
              <div className="cta-sub">
                {compact && <button className="txt" onClick={() => setDrawer('tweak')}>{Icon.sliders}<span>Tweak</span></button>}
                <button className="txt" onClick={() => doCopy('json', styleJson(preset, tw))}>{copied === 'json' ? Icon.check : null}<span>{copied === 'json' ? 'Copied' : 'Style JSON'}</span></button>
                <button className="txt" onClick={() => doCopy('install', INSTALL.claude)}>{copied === 'install' ? Icon.check : null}<span>{copied === 'install' ? 'Copied' : 'Install'}</span></button>
              </div>
            </div>
            <p className="credit">Clip: Sam Altman on David Senra's podcast (<a href="https://www.youtube.com/watch?v=kG8AoExkX40" target="_blank" rel="noreferrer">source</a>). Used only to demo captions; not affiliated with or endorsed by Sam Altman, OpenAI or the show.</p>
          </div>
        </section>

        <Filmstrip names={names} active={styleName} filter={filter} setFilter={setFilter} tweakedSet={tweakedSet} onPick={pick} onHover={setHover} stripRef={stripRef} />
        <How copied={copied} doCopy={doCopy} />
        <RefsUpsell />
      </main>

      <div className="dz-sep" aria-hidden="true"><Dither shape="band" reach={1} max={0.5} /></div>
      <RefsFooter />

      {/* mobile sticky bar */}
      <div className={'bar' + (drawer ? ' hide' : '')}>
        <div className="bar-name"><b>{label}</b><span>{CATNAME[CATEGORY[styleName]] ?? 'Style'}{canBehind ? ' · behind you' : ''}</span></div>
        <button className="round-btn solid" onClick={() => setDrawer('tweak')} aria-label="Tweak">{Icon.sliders}</button>
        <button className="pill primary" onClick={() => doCopy('prompt', promptText())}>
          {copied === 'prompt' ? Icon.check : Icon.copy}<span>{copied === 'prompt' ? 'Copied' : 'Copy prompt'}</span>
        </button>
      </div>

      {/* tweak sheet (phones, tablets) */}
      {compact && (
        <Drawer open={drawer === 'tweak'} onClose={() => setDrawer(null)} title="Tweak" sub={label} size="short">
          <TweakControls {...tweakProps} openWords={() => setDrawer('words')} />
        </Drawer>
      )}
      <Drawer open={drawer === 'words'} onClose={() => setDrawer(null)} title="Edit words" sub={label}>
        <p className="hint">Click a line and retype it. The captions update live.</p>
        <WordList pages={base?.pages ?? []} edits={pageEdits} setEdit={setEdit} seek={(ms) => stage.current?.seek(ms)} />
      </Drawer>
    </>
  );
}

