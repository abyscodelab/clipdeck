// Static assets don't answer Range requests, and a video the browser can't seek breaks the player.
// This serves byte ranges for the demo media; everything else goes straight to the assets.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    // PostHog through our own origin (src/analytics.ts), so ad blockers don't drop it; the visitor's IP goes along for geo
    if (url.pathname.startsWith("/ingest/")) {
      const host = url.pathname.startsWith("/ingest/static/") ? "us-assets.i.posthog.com" : "us.i.posthog.com";
      const target = new URL(url.pathname.replace(/^\/ingest/, "") + url.search, `https://${host}`);
      const headers = new Headers(request.headers);
      headers.delete("cookie");
      headers.set("host", host);
      const ip = request.headers.get("cf-connecting-ip");
      if (ip) headers.set("x-forwarded-for", ip);
      return fetch(target, { method: request.method, headers, body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body, redirect: "follow" });
    }
    const range = request.headers.get("range");
    if (!range || !/\.(mp4|webm|mov|mp3|m4a)$/i.test(url.pathname)) return env.ASSETS.fetch(request);
    const res = await env.ASSETS.fetch(new Request(url.toString(), { method: "GET" }));
    if (!res.ok) return res;
    const buf = await res.arrayBuffer();
    const size = buf.byteLength;
    const m = /bytes=(\d*)-(\d*)/.exec(range);
    if (!m) return new Response(buf, { headers: res.headers });
    let start = m[1] === "" ? size - Number(m[2]) : Number(m[1]);
    let end = m[1] === "" || m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1);
    if (!(start >= 0 && start <= end && start < size)) {
      return new Response(null, { status: 416, headers: { "content-range": `bytes */${size}` } });
    }
    const headers = new Headers(res.headers);
    headers.set("content-range", `bytes ${start}-${end}/${size}`);
    headers.set("content-length", String(end - start + 1));
    headers.set("accept-ranges", "bytes");
    return new Response(buf.slice(start, end + 1), { status: 206, headers });
  },
};
