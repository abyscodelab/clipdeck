import React, {useEffect, useRef} from 'react';
import {hasAccent, pageText, type Edits, type Tweaks} from './tweaks';
import type {CPage} from './engine';
import type {Preset} from './data';
import type {StageHandle} from './Stage';
import {useLiveIndex} from './timeStore';
import {Icon} from './ui';

const SWATCHES = ['#FFE500', '#FFFFFF', '#FF4D7D', '#7CFF6B', '#86E4F0', '#B49BFF', '#FFB020'];

export type TweakProps = {
  preset: Preset; tw?: Tweaks; setTw: (p: Partial<Tweaks>) => void; bump: (d: number) => void;
  accentNow: string; sizeNow: number; yNow: number; caseNow: string;
  highlights: boolean; setHighlights: (f: (v: boolean) => boolean) => void;
  canBehind: boolean; behind: boolean; canCutout: boolean; setBehindOn: (f: (v: boolean) => boolean) => void;
  tweakedAny: boolean; reset: () => void; openWords: () => void;
};

export function TweakControls(p: TweakProps) {
  const {preset, tw} = p;
  return (
    <div className="tw">
      <div className="tw-row">
        <span className="lab">Accent</span>
        {hasAccent(preset) ? (
          <div className="swatches">
            {SWATCHES.map((c) => (
              <button key={c} className="sw" aria-label={`Accent ${c}`} aria-pressed={p.accentNow.toUpperCase() === c} onClick={() => p.setTw({accent: c})}><i style={{background: c}} /></button>
            ))}
            <label className="sw picker" title="Pick any colour">
              <input type="color" aria-label="Pick any accent colour" value={p.accentNow.length === 7 ? p.accentNow : '#ffffff'} onChange={(e) => p.setTw({accent: e.target.value.toUpperCase()})} />
              <i className="rainbow" />
            </label>
          </div>
        ) : <span className="hint">Keeps its own colour pairs</span>}
      </div>

      <div className="tw-row">
        <span className="lab">Size</span>
        <div className="stepper">
          <button className="round-btn" onClick={() => p.bump(-10)} aria-label="Smaller">−</button>
          <output>{p.sizeNow}%</output>
          <button className="round-btn" onClick={() => p.bump(10)} aria-label="Bigger">+</button>
        </div>
      </div>

      <div className="tw-row">
        <span className="lab">Case</span>
        <div className="seg" role="group" aria-label="Letter case">
          {([['upper', 'UPPER'], ['sentence', 'Aa'], ['lower', 'lower']] as const).map(([v, l]) => (
            <button key={v} aria-pressed={p.caseNow === v} onClick={() => p.setTw({case: v})}>{l}</button>
          ))}
        </div>
      </div>

      <div className="tw-col">
        <label className="lab" htmlFor="ypos">Position <code>{Math.round(p.yNow)}%</code></label>
        <input id="ypos" type="range" min="8" max="92" step="1" value={p.yNow} onChange={(e) => p.setTw({y: Number(e.target.value)})} />
        {tw?.y != null && <span className="hint">Pinned for every page (the prompt adds --placement off).</span>}
      </div>

      <div className="tw-row">
        <label className="lab" htmlFor="sh">Shadow</label>
        <button id="sh" className="switch" role="switch" aria-checked={tw?.shadow !== false} onClick={() => p.setTw({shadow: tw?.shadow === false ? undefined : false})}><i /></button>
      </div>
      <div className="tw-row">
        <label className="lab" htmlFor="hl">Highlights</label>
        <button id="hl" className="switch" role="switch" aria-checked={p.highlights} onClick={() => p.setHighlights((v) => !v)}><i /></button>
      </div>
      {p.canBehind && (
        <div className="tw-row">
          <label className="lab" htmlFor="bh">Behind you</label>
          <button id="bh" className="switch" role="switch" aria-checked={p.behind} disabled={!p.canCutout} onClick={() => p.setBehindOn((v) => !v)}><i /></button>
        </div>
      )}
      {p.canBehind && !p.canCutout && <p className="hint">The cut-out needs WebGL; here the big word is drawn in front.</p>}

      <div className="tw-foot">
        <button className="pill ghost" onClick={p.openWords}>{Icon.edit}<span>Edit words</span></button>
        {p.tweakedAny && <button className="link" onClick={p.reset}>Reset</button>}
      </div>
    </div>
  );
}

export function WordList({pages, edits, setEdit, seek}: {pages: CPage[]; edits: Edits; setEdit: (i: number, v: string | null) => void; seek: (ms: number) => void}) {
  const starts = React.useMemo(() => pages.map((p) => p.startMs), [pages]);
  const ends = React.useMemo(() => pages.map((p) => p.endMs), [pages]);
  const live = useLiveIndex(starts, ends);
  const liveRef = useRef<HTMLLIElement>(null);
  const box = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const li = liveRef.current, ol = box.current;
    if (!li || !ol || ol.contains(document.activeElement)) return;
    ol.scrollTo({top: li.offsetTop - ol.clientHeight / 2 + li.clientHeight / 2, behavior: 'smooth'});
  }, [live]);
  return (
    <ol className="words" ref={box}>
      {pages.map((p, i) => {
        const val = edits[i] ?? pageText(p);
        const t = (p.startMs / 1000).toFixed(1);
        return (
          <li key={i} ref={i === live ? liveRef : undefined} className={i === live ? 'live' : ''}>
            <button className="t" onClick={() => seek(p.startMs)} aria-label={`Jump to ${t} seconds`}>{t}</button>
            <input
              value={val}
              spellCheck={false}
              onFocus={() => seek(p.startMs)}
              onChange={(e) => setEdit(i, e.target.value === pageText(p) ? null : e.target.value)}
              aria-label={`Caption at ${t} seconds`}
            />
          </li>
        );
      })}
    </ol>
  );
}

/** A side drawer on desktop, a bottom sheet on phones. No dimming: the captions keep playing and changing while you type. */
export function Drawer({open, onClose, title, sub, children, size = 'tall'}: {open: boolean; onClose: () => void; title: string; sub?: string; children: React.ReactNode; size?: 'tall' | 'short'}) {
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const on = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', on);
    return () => window.removeEventListener('keydown', on);
  }, [open, onClose]);
  return (
    <aside className={`drawer ${size}${open ? ' open' : ''}`} role="dialog" aria-label={title} aria-hidden={!open} inert={!open}>
      <div className="grab" aria-hidden><i /></div>
      <header className="dhead">
        <h2>{title}{sub && <small>{sub}</small>}</h2>
        <button ref={btn} className="pill sm" onClick={onClose}>Done</button>
      </header>
      <div className="dbody">{children}</div>
    </aside>
  );
}
