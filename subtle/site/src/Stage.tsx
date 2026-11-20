import React, {useEffect, useImperativeHandle, useMemo, forwardRef, useRef, useState} from 'react';
import {AbsoluteFill, Html5Audio, Html5Video, useVideoConfig} from 'remotion';
import {track} from './analytics';
import {Player, type PlayerRef} from '@remotion/player';
import {Captions, loadFonts, type CaptionsFile, type Style} from './engine';

// Fonts are served from /fonts; the engine resolves them through staticFile().
(window as any).remotion_staticBase = '/fonts';

/** The cut-out is drawn with WebGL from one packed video (the picture on the left half, the speaker's matte on the right),
 *  so it works in every browser with WebGL, Safari included, and can never drift from the picture. */
export const canCutout = (() => {
  try {
    return typeof document !== 'undefined' && !!document.createElement('canvas').getContext('webgl');
  } catch {
    return false;
  }
})();

const VS = `attribute vec2 p; varying vec2 uv; void main(){ uv = (p + 1.0) * 0.5; uv.y = 1.0 - uv.y; gl_Position = vec4(p, 0.0, 1.0); }`;
// mode 0: the picture; mode 1: the picture where the matte is white (premultiplied alpha), clear elsewhere
const FS = `precision mediump float; varying vec2 uv; uniform sampler2D t; uniform float mode;
void main(){
  vec3 c = texture2D(t, vec2(uv.x * 0.5, uv.y)).rgb;
  float a = mode > 0.5 ? texture2D(t, vec2(0.5 + uv.x * 0.5, uv.y)).r : 1.0;
  gl_FragColor = vec4(c * a, a);
}`;

const Packed = React.createContext<React.RefObject<HTMLVideoElement | null> | null>(null);

/** One layer drawn from the packed video's current frame: the background picture, or the speaker cut out over the words. */
const GLLayer: React.FC<{mode: 0 | 1; w: number; h: number}> = ({mode, w, h}) => {
  const src = React.useContext(Packed);
  const cv = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = cv.current;
    const gl = canvas?.getContext('webgl', {premultipliedAlpha: true, alpha: true, antialias: false});
    if (!canvas || !gl || !src) return;
    const sh = (type: number, code: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, code);
      gl.compileShader(s);
      return s;
    };
    const prog = gl.createProgram()!;
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog);
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, 'p');
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    gl.uniform1f(gl.getUniformLocation(prog, 'mode'), mode);
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    for (const [k, v] of [[gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR]])
      gl.texParameteri(gl.TEXTURE_2D, k, v);
    gl.viewport(0, 0, canvas.width, canvas.height);
    let stop = false;
    let rvfc = 0;
    let raf = 0;
    const draw = () => {
      const v = src.current;
      if (!v || v.readyState < 2) return;
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, v);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
    // Redraw on every presented video frame (requestVideoFrameCallback); animation frames where it is missing.
    const loop = () => {
      if (stop) return;
      draw();
      const v = src.current as any;
      if (v?.requestVideoFrameCallback) rvfc = v.requestVideoFrameCallback(loop);
      else raf = requestAnimationFrame(loop);
    };
    const kick = () => draw();
    const attach = () => {
      const v = src.current;
      if (!v) return void (raf = requestAnimationFrame(attach));
      v.addEventListener('seeked', kick);
      v.addEventListener('loadeddata', kick);
      loop();
    };
    attach();
    return () => {
      stop = true;
      const v = src.current as any;
      if (rvfc && v?.cancelVideoFrameCallback) v.cancelVideoFrameCallback(rvfc);
      cancelAnimationFrame(raf);
      v?.removeEventListener('seeked', kick);
      v?.removeEventListener('loadeddata', kick);
    };
  }, [src, mode]);
  return <canvas ref={cv} width={w} height={h} style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}} />;
};

type CompProps = {
  video?: string;
  person?: string;
  audio?: string;
  captions: CaptionsFile;
  style: Style;
  behind: boolean;
  fx: number;
};

const Comp: React.FC<CompProps> = ({video, person, audio, captions, style, behind}) => {
  const cover: React.CSSProperties = {width: '100%', height: '100%', objectFit: 'cover'};
  const {width, height} = useVideoConfig();
  const packedRef = useRef<HTMLVideoElement | null>(null);
  // A failed read or seek on the video (a dropped range request, a flaky connection) would otherwise throw and stop the
  // player. Instead the same file is loaded again, up to 3 times, and Remotion seeks it back to the current frame.
  const [retry, setRetry] = useState(0);
  const again = (src?: string) => (src && retry ? `${src}?r=${retry}` : src);
  const onMediaError = (e: Error) => {
    track('subtle_video_error', {message: String(e?.message ?? e).slice(0, 160), retry});
    setRetry((r) => (r < 3 ? r + 1 : r));
  };
  // `person` is the packed video (picture | matte, side by side). With WebGL, both the picture and the cut-out are drawn
  // from that one video element, so they always show the same frame. Without WebGL: the plain clip, words in front.
  if (person && canCutout) {
    return (
      <AbsoluteFill style={{background: '#000'}}>
        <Packed.Provider value={packedRef}>
          {/* the source: playing (Remotion keeps it in time, and its audio is the clip's), but never seen itself */}
          <Html5Video ref={packedRef} src={again(person)} onError={onMediaError} playsInline style={{...cover, position: 'absolute', opacity: 0, pointerEvents: 'none'}} />
          {audio && <Html5Audio src={again(audio)} onError={onMediaError} />}
          <GLLayer mode={0} w={width} h={height} />
          {behind ? (
            <>
              <Captions key={style.name + ':b'} captions={captions} style={style} layer="behind" />
              <GLLayer mode={1} w={width} h={height} />
              <Captions key={style.name + ':f'} captions={captions} style={style} layer="front" />
            </>
          ) : (
            <Captions key={style.name} captions={captions} style={style} layer="all" />
          )}
        </Packed.Provider>
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{background: '#000'}}>
      {video && <Html5Video src={again(video)} onError={onMediaError} style={cover} playsInline />}
      {audio && <Html5Audio src={again(audio)} onError={onMediaError} />}
      <Captions key={style.name} captions={captions} style={style} layer="all" />
    </AbsoluteFill>
  );
};

export type StageHandle = {toggleMute: () => boolean; togglePlay: () => void; restart: () => void; seek: (ms: number) => void};

type Props = {
  clipKey: string;
  video?: string;
  person?: string;
  audio?: string;
  captions: CaptionsFile;
  style: Style;
  behind: boolean;
  onPlaying?: (playing: boolean) => void;
  onMuted?: (muted: boolean) => void;
  onTime?: (ms: number) => void;
  startMuted?: boolean;
};

export const Stage = forwardRef<StageHandle, Props>(function Stage({clipKey, video, person, audio, captions, style, behind, onPlaying, onMuted, onTime, startMuted = true}, ref) {
  const player = useRef<PlayerRef>(null);
  const {width, height, fps, durationMs} = captions.video;
  const dur = Math.max(1, Math.ceil((durationMs * fps) / 1000 - 1e-6));
  // Fonts of the style to show are loaded before the style changes, so a switch never flashes empty.
  const [shown, setShown] = useState(style);
  const pending = useRef(style);
  pending.current = style;
  useEffect(() => {
    if (style.name === shown.name) return void setShown(style);
    let live = true;
    loadFonts(style).catch(() => {}).then(() => live && pending.current === style && setShown(style));
    return () => {
      live = false;
    };
  }, [style]);

  useImperativeHandle(ref, () => ({
    toggleMute() {
      const p = player.current;
      if (!p) return true;
      if (p.isMuted()) { p.unmute(); onMuted?.(false); return false; }
      p.mute(); onMuted?.(true); return true;
    },
    togglePlay() { player.current?.toggle(); },
    restart() { player.current?.seekTo(0); player.current?.play(); },
    seek(ms: number) { player.current?.seekTo(Math.round((ms * fps) / 1000)); },
  }));
  useEffect(() => {
    const p = player.current;
    if (!p) return;
    const on = () => onPlaying?.(true), off = () => onPlaying?.(false);
    const tick = (e: any) => onTime?.((e.detail.frame * 1000) / fps);
    p.addEventListener('play', on); p.addEventListener('pause', off); p.addEventListener('timeupdate', tick);
    return () => { p.removeEventListener('play', on); p.removeEventListener('pause', off); p.removeEventListener('timeupdate', tick); };
  }, [clipKey]);

  const inputProps = useMemo<CompProps>(() => ({video, person, audio, captions, style: shown, behind, fx: 0}), [video, person, audio, captions, shown, behind]);
  return (
    <Player
      key={clipKey}
      ref={player}
      component={Comp as any}
      inputProps={inputProps as any}
      compositionWidth={width}
      compositionHeight={height}
      fps={fps}
      durationInFrames={dur}
      style={{width: '100%', height: '100%'}}
      autoPlay
      loop
      initiallyMuted={startMuted}
      controls={false}
      clickToPlay
      doubleClickToFullscreen={false}
      spaceKeyToPlayOrPause={false}
    />
  );
});
