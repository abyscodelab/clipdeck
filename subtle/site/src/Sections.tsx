import React, {memo, useState} from 'react';
import {CATEGORY, INSTALL, PRESETS, REPO, SPEECH_ORDER, isBehind} from './data';
import {Icon, Reveal, pad} from './ui';
import {Dither} from './Dither';

const CATNAME: Record<string, string> = {bold: 'Bold', elegant: 'Editorial', minimal: 'Minimal'};
const SHOWCASE = ['cover', 'keyword', 'outline', 'numeral'];
const TILTS = [-4.5, -1.6, 1.6, 4.5];

export const Showcase = memo(function Showcase({onPick}: {onPick: (n: string) => void}) {
  return (
    <section id="behind" className="behind">
      <div className="perf" aria-hidden />
      <div className="behind-in">
        <Reveal className="behind-copy">
          <p className="kicker">Behind you</p>
          <h2>Words that sit behind&nbsp;you.</h2>
          <p>Found per shot, never over your face. On a wide shot the giant word slips behind the speaker; on a close-up it steps aside.</p>
        </Reveal>
        <div className="frames">
          {SHOWCASE.map((n, i) => (
            <Reveal key={n} delay={i * 90} className="fwrap">
              <button className="frame" style={{'--tilt': `${TILTS[i]}deg`, '--i': i} as React.CSSProperties} onClick={() => onPick(n)} aria-label={`Try ${PRESETS[n].label ?? n} in the player`}>
                <img src={`/demo/stills/${n}.jpg`} alt="" width="360" height="640" loading="lazy" decoding="async" />
                <span className="fnum">{pad(i + 1)}</span>
                <span className="fcap"><b>{PRESETS[n].label ?? n}</b><i>Try it live</i></span>
              </button>
            </Reveal>
          ))}
        </div>
      </div>
      <div className="perf" aria-hidden />
    </section>
  );
});

export const Gallery = memo(function Gallery({onPick, active}: {onPick: (n: string) => void; active: string}) {
  return (
    <section id="gallery" className="gallery">
      <Reveal className="sec-head">
        <p className="kicker">Contact sheet</p>
        <h2>Every style, one frame each.</h2>
        <p>All 35 on the same shot. Pick one and it plays in the player above.</p>
      </Reveal>
      <Reveal className="sheet">
        <div className="perf" aria-hidden />
        <ul>
          {SPEECH_ORDER.map((n, i) => (
            <li key={n}>
              <button className="cell" aria-pressed={n === active} onClick={() => onPick(n)} aria-label={`Play ${PRESETS[n].label ?? n}`}>
                <span className="cn">{pad(i + 1)}</span>
                <span className="ci">
                  <img
                    src={`/demo/stills/m/${n}.jpg`}
                    srcSet={`/demo/stills/m/${n}.jpg 240w, /demo/stills/${n}.jpg 360w`}
                    sizes="(min-width: 1100px) 150px, (min-width: 760px) 18vw, 30vw"
                    alt="" width="240" height="427" loading="lazy" decoding="async"
                  />
                  {isBehind(n) && <i className="bh">Behind you</i>}
                </span>
                <span className="cl"><b>{PRESETS[n].label ?? n}</b><i>{CATNAME[CATEGORY[n]] ?? 'Style'}</i></span>
              </button>
            </li>
          ))}
        </ul>
        <div className="perf" aria-hidden />
      </Reveal>
    </section>
  );
});

export function How({copied, doCopy}: {copied: string; doCopy: (id: string, t: string) => void}) {
  const [codex, setCodex] = useState(false);
  const cmd = codex ? INSTALL.codex : INSTALL.claude;
  return (
    <section id="how" className="how">
      <Dither shape="radial" x={0.92} y={0.12} reach={0.42} max={0.75} className="dz dz-how" />
      <Reveal className="sec-head">
        <h2>Three steps. No upload, no key.</h2>
      </Reveal>
      <ol>
        <Reveal as="li" delay={0}>
          <Dither shape="radial" x={1} y={0} reach={0.55} max={0.85} cell={6} className="dz dz-card" />
          <span className="n">01</span>
          <h3>Install it</h3>
          <p>Clone Subtle into your agent's skills folder. One line.</p>
          <div className="term">
            <div className="term-bar">
              <i /><i /><i />
              <div className="seg small" role="group" aria-label="Agent">
                <button aria-pressed={!codex} onClick={() => setCodex(false)}>Claude Code</button>
                <button aria-pressed={codex} onClick={() => setCodex(true)}>Codex</button>
              </div>
            </div>
            <div className="term-line">
              <code><span className="ps">$</span> {cmd}</code>
              <button className="copy-ico" onClick={() => doCopy('install2', cmd)} aria-label="Copy install command">{copied === 'install2' ? Icon.check : Icon.copy}</button>
            </div>
          </div>
        </Reveal>
        <Reveal as="li" delay={90}>
          <Dither shape="radial" x={1} y={0} reach={0.55} max={0.85} cell={6} className="dz dz-card" />
          <span className="n">02</span>
          <h3>Point Claude at your video</h3>
          <p>It transcribes on your Mac, groups the words and picks the highlights.</p>
          <button type="button" className="term quote copyable" onClick={() => doCopy('ask', 'add captions to ~/Movies/talk.mp4')} aria-label="Copy the example request"><div className="term-line"><code><span className="ps">&gt;</span> add captions to ~/Movies/talk.mp4</code>{copied === 'ask' ? Icon.check : Icon.copy}</div></button>
        </Reveal>
        <Reveal as="li" delay={180}>
          <Dither shape="radial" x={1} y={0} reach={0.55} max={0.85} cell={6} className="dz dz-card" />
          <span className="n">03</span>
          <h3>Pick a style</h3>
          <p>Choose one here, tweak it, and hit <b>Copy prompt</b>. Paste it into Claude Code and you get the finished video, the .srt and an editable captions file.</p>
        </Reveal>
      </ol>
    </section>
  );
}

export function Footer() {
  return (
    <footer>
      <div className="foot">
        <a className="brand" href="https://refs.video"><img src="/brand/refs-symbol-white.svg" alt="" width="16" height="18" /><span>made by Refs</span></a>
        <p className="fnote">The demo clip is third-party footage used only to show captions (credit under the player). Fonts are open (SIL OFL).</p>
        <p className="flinks"><a href={`https://${REPO}`} target="_blank" rel="noreferrer">GitHub</a><span aria-hidden>·</span><a href={`https://${REPO}/blob/main/LICENSE`} target="_blank" rel="noreferrer">MIT licence</a></p>
      </div>
    </footer>
  );
}
