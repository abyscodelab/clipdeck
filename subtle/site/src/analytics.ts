// PostHog for subtle.refs.video, in the same project as refs.video (676157). Every event carries `site: "subtle"`.
// It loads after the page has loaded and gone idle, through our own /ingest path (worker.js proxies it to PostHog),
// so it never slows the player and ad blockers don't drop it. The visitor id is a cookie on .refs.video, so a person who
// goes from Subtle to refs.video stays one person. No session replay here (the project only records on refs.video).
type PH = {capture: (event: string, props?: Record<string, unknown>) => unknown};

const KEY = 'phc_umZB9mrvzN4TiBNwwHPEhNHy9mZRooRbEDbFowx8e3JY'; // public project token
type Props = Record<string, unknown>;

let ph: PH | null = null;
const queue: [string, Props | undefined][] = [];

/** Send an event; events before PostHog has loaded wait and go out once it has. */
export function track(event: string, props?: Props) {
  if (ph) ph.capture(event, props);
  else if (queue.length < 50) queue.push([event, props]);
}

export function initAnalytics() {
  if (location.hostname !== 'subtle.refs.video') return; // not in dev or previews
  const start = () =>
    import('posthog-js').then(({default: posthog}) => {
      posthog.init(KEY, {
        api_host: '/ingest',
        ui_host: 'https://us.posthog.com',
        persistence: 'localStorage+cookie',
        cross_subdomain_cookie: true,
        capture_pageview: false, // sent below, after the site property is registered
        capture_pageleave: true,
        autocapture: true,
        disable_session_recording: true,
        loaded: (p) => {
          p.register({site: 'subtle'});
          p.capture('$pageview');
          ph = p;
          for (const [e, pr] of queue.splice(0)) p.capture(e, pr);
        },
      });
    }).catch(() => {});
  const idle = () => ('requestIdleCallback' in window ? requestIdleCallback(() => start(), {timeout: 3000}) : setTimeout(start, 1500));
  if (document.readyState === 'complete') idle();
  else addEventListener('load', idle, {once: true});
}

/** A refs.video link that says it came from Subtle. Archive pages take no extra query (the firewall checks /archive
 *  with anything but a single tag=), so those carry only that; the referrer still names subtle.refs.video. */
export function refsUrl(path = '/', tag?: string) {
  if (path.startsWith('/archive')) return `https://refs.video/archive${tag ? `?tag=${tag}` : ''}`;
  return `https://refs.video${path}?from=subtle&utm_source=subtle&utm_medium=page&utm_campaign=launch`;
}
export type CtaWhere = 'install_box' | 'after_tweak' | 'header' | 'footer';
export const ctaClick = (where: CtaWhere, style?: string) => track('subtle_refs_cta_clicked', {where, ...(style ? {style} : {})});

/** subtle_scrolled at 25, 50, 75 and 100% of the page, once each. */
export function trackScrollDepth() {
  const sent = new Set<number>();
  const on = () => {
    const h = document.documentElement;
    const pct = ((h.scrollTop + innerHeight) / Math.max(1, h.scrollHeight)) * 100;
    for (const d of [25, 50, 75, 100]) if (pct >= d - 0.5 && !sent.has(d)) { sent.add(d); track('subtle_scrolled', {depth: d}); }
    if (sent.size === 4) removeEventListener('scroll', on);
  };
  addEventListener('scroll', on, {passive: true});
}
