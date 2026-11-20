# subtle.refs.video

The showcase site for Subtle. Vite + React + TypeScript, and it runs the real caption engine in the browser:
`@remotion/player` (4.0.534, pinned like the renderer) plays the demo clip and draws `template/src/Captions.tsx` on top.
The engine is imported unchanged through the `@subtle` alias (`../template/src`); styles are read from `../styles/*.json`.

```bash
cd site && npm install
npm run dev            # http://127.0.0.1:5191 with `npx vite --port 5191`
npm run build          # type-check + static build into dist/
npm run preview
npx wrangler deploy --dry-run   # Cloudflare Workers static assets (no routes; attach the domain in the dashboard)
```

`npm run prep` (runs before dev and build) copies `../fonts` to `public/fonts`, because the engine loads fonts with `staticFile()`;
the site sets `window.remotion_staticBase = '/fonts'`.

## Demo media is not in the repo

`public/demo/` (the demo clip, its poster, per-style stills, `captions.json` with the transcript) and `public/og.jpg` are
gitignored: the clip is third-party material, so it is not published here. `npm run build` needs them, so make your own:
pick a clip you have the rights to, run steps 1 to 5 below with it, and put the results in `public/demo/` (`clip.mp4`,
`packed.mp4`, `poster.jpg`, `captions.json`, `stills/`, `stills/m/`, `stills/thumb/`) and a 1200x630 `public/og.jpg`.
Or point the site's data at any clip you like; the engine is the same.

## How the demo data is made (kept local in `public/demo/`)

Made with the real pipeline, not by hand, for one clip:

1. `python3 scripts/subtle.py <clip> --style <s> --stop-after group` for every style (English, `--lang en --vocab "GPT-4, OpenAI, Shopify"`). This also runs
   placement (`pages[].y`), cuts, legibility, the footage palette and, for the "behind the speaker" styles, the per-shot subject data
   (`shots`, `subject`, written by `scripts/shots.py`).
2. Highlights chosen the way SKILL.md asks (numbers, names, punchline, topic) and written with `scripts/emphasis.py --pick`
   (the transcript was read first; `GPT-4` and `2023` came out right with the vocabulary hint).
3. The person cut-out: `scripts/vision-matte matte`, then `video x matte` as a VP9 WebM with alpha (`person.webm`). The behind styles draw
   their giant words, then this cut-out, then the front line, exactly as `composite.sh` stacks them.
4. `scripts/pack-demo.py <cap-dir>` packs the per-style files into `captions.json`.
5. `stills/<style>.jpg` and `stills/thumb/` come from `template/stills.mjs` (batch stills, one bundle) composited on the source frame with
   `tests/styles_sheet.py`; `tests/out/styles-v3.jpg` is the contact sheet.

The clip we use on subtle.refs.video: 52 s (720x1280, 30 fps) of Sam Altman on David Senra's podcast, https://www.youtube.com/watch?v=kG8AoExkX40, a face-tracked vertical crop with a wide shot,
a close-up and the host's short question. Used only to demo captions and credited on the page. Not affiliated with or endorsed by Sam Altman, OpenAI or the show.
Neither the source nor the re-encoded `clip.mp4` is committed.

Behind the speaker is decided **per shot**: in a wide shot the giant word sits behind his head, in the close-up (23 to 28 s) it would be hidden, so the
style draws it in front or skips it and the words stay in the small line. Safari ignores the alpha channel of VP9, so there every giant word is drawn in front.
