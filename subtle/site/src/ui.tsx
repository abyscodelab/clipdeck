import React, {useEffect, useRef, useState, useSyncExternalStore} from 'react';

const svg = (p: React.SVGProps<SVGSVGElement>, d: React.ReactNode) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden {...p}>{d}</svg>;
export const Icon = {
  mute: svg({width: 18, height: 18}, <><path d="M11 5 6 9H2v6h4l5 4V5z" /><path d="m22 9-6 6M16 9l6 6" /></>),
  sound: svg({width: 18, height: 18}, <><path d="M11 5 6 9H2v6h4l5 4V5z" /><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14" /></>),
  play: <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M7 4.5v15l13-7.5z" /></svg>,
  pause: <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M6 4h4v16H6zM14 4h4v16h-4z" /></svg>,
  restart: svg({width: 16, height: 16, strokeWidth: 2.2}, <><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" /></>),
  sliders: svg({width: 18, height: 18}, <><path d="M4 7h10M18 7h2M4 17h2M10 17h10" /><circle cx="16" cy="7" r="2" /><circle cx="8" cy="17" r="2" /></>),
  copy: svg({width: 16, height: 16}, <><rect x="9" y="9" width="12" height="12" rx="3" /><path d="M5 15V6a2 2 0 0 1 2-2h9" /></>),
  check: svg({width: 16, height: 16, strokeWidth: 2.6}, <path d="m5 12.5 4.5 4.5L19 7" />),
  left: svg({width: 18, height: 18, strokeWidth: 2.2}, <path d="m15 5-7 7 7 7" />),
  right: svg({width: 18, height: 18, strokeWidth: 2.2}, <path d="m9 5 7 7-7 7" />),
  close: svg({width: 18, height: 18, strokeWidth: 2.2}, <path d="M6 6l12 12M18 6 6 18" />),
  edit: svg({width: 16, height: 16}, <><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4z" /></>),
  gh: <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.15.08 1.76 1.19 1.76 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.13v3.16c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5z" /></svg>,
};

/** Fades its children up the first time they scroll into view. */
export function Reveal({children, delay = 0, className = '', as: Tag = 'div'}: {children: React.ReactNode; delay?: number; className?: string; as?: any}) {
  const ref = useRef<HTMLElement>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!('IntersectionObserver' in window)) return void setOn(true);
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setOn(true); io.disconnect(); } }, {rootMargin: '0px 0px -6% 0px', threshold: 0.04});
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return <Tag ref={ref} className={`rv${on ? ' in' : ''} ${className}`} style={{'--d': `${delay}ms`} as React.CSSProperties}>{children}</Tag>;
}

export function useMedia(q: string): boolean {
  return useSyncExternalStore(
    (cb) => { const m = window.matchMedia(q); m.addEventListener('change', cb); return () => m.removeEventListener('change', cb); },
    () => window.matchMedia(q).matches,
    () => false,
  );
}

export const pad = (n: number) => String(n).padStart(2, '0');
