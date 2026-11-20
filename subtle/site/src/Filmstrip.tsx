import React, {memo, useState} from 'react';
import {FILTERS, PRESETS, isBehind, stylesFor, CATEGORY} from './data';
import {Icon, Reveal} from './ui';
import {Dither} from './Dither';

const CATNAME: Record<string, string> = {bold: 'Bold', elegant: 'Editorial', minimal: 'Minimal'};

function Frame({n, active, tweaked, onPick, onHover}: {n: string; active: boolean; tweaked: boolean; onPick: (n: string) => void; onHover: (n: string | null) => void}) {
  const p = PRESETS[n];
  const [loaded, setLoaded] = useState(false);
  return (
    <button
      data-style={n}
      className="f"
      aria-pressed={active}
      onClick={() => onPick(n)}
      onPointerEnter={(e) => { if (e.pointerType === 'mouse') onHover(n); }}
      onPointerLeave={() => onHover(null)}
      onFocus={(e) => { if (e.currentTarget.matches(':focus-visible')) onHover(n); }}
      onBlur={() => onHover(null)}
    >
      <span className="fr" style={{backgroundImage: `url(/demo/stills/thumb/${n}.jpg)`}}>
        <img src={`/demo/stills/m/${n}.jpg`} alt="" width="240" height="427" loading="lazy" decoding="async" className={loaded ? 'ld' : ''} onLoad={() => setLoaded(true)} ref={(el) => { if (el?.complete && el.naturalWidth) setLoaded(true); }} />
        {isBehind(n) && <i className="bh">Behind you</i>}
        <span className="tip">{p.description}</span>
      </span>
      <span className="lab"><b>{p.label ?? n}</b>{tweaked && <i className="mod" title="tweaked" />}</span>
      <span className="cat">{CATNAME[CATEGORY[n]] ?? 'Style'}</span>
    </button>
  );
}

export const Filmstrip = memo(function Filmstrip({names, active, filter, setFilter, tweakedSet, onPick, onHover, stripRef}: {
  names: string[]; active: string; filter: string; setFilter: (f: string) => void; tweakedSet: string; onPick: (n: string) => void; onHover: (n: string | null) => void; stripRef: React.RefObject<HTMLDivElement | null>;
}) {
  const by = (dir: number) => {
    const el = stripRef.current;
    if (el) el.scrollBy({left: dir * Math.max(240, el.clientWidth * 0.7), behavior: 'smooth'});
  };
  const tw = new Set(tweakedSet ? tweakedSet.split(',') : []);
  return (
    <section id="styles" className="strip-sec" aria-label="Caption styles">
      <Dither shape="down" reach={1} max={0.55} className="dz dz-strip" />
      <Reveal className="strip-head">
        <div>
          <h2>35 ways to caption one clip.</h2>
        </div>
        <div className="strip-tools">
          <div className="chips" role="group" aria-label="Filter styles">
            {FILTERS.map((f) => (
              <button key={f.id} className="chip" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>{f.label}<small>{stylesFor(f.id).length}</small></button>
            ))}
          </div>
          <div className="arrows">
            <button className="round-btn" onClick={() => by(-1)} aria-label="Scroll styles left">{Icon.left}</button>
            <button className="round-btn" onClick={() => by(1)} aria-label="Scroll styles right">{Icon.right}</button>
          </div>
        </div>
      </Reveal>
      <div className="strip-mask">
        <div className="strip" ref={stripRef} role="group" aria-label="Pick a style">
          {names.map((n) => <Frame key={n} n={n} active={n === active} tweaked={tw.has(n)} onPick={onPick} onHover={onHover} />)}
        </div>
      </div>
    </section>
  );
});
