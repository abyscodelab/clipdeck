#!/usr/bin/env node
// Renders ONLY the caption layer, transparent (ProRes 4444 + alpha). ffmpeg composites later.
// node template/render.mjs --captions captions.json --style style.json --layer all|behind|front|mask --out overlay.mov
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const fontsDir = path.resolve(here, '..', 'fonts');

function parseArgs(argv) {
  const o = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const k = a.slice(2);
    const v = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : 'true';
    o[k] = v;
  }
  return o;
}
const args = parseArgs(process.argv.slice(2));
const die = (m) => {
  console.error(m);
  process.exit(1);
};
if (!args.captions || !args.style || (!args.out && !args.png)) {
  die('usage: node render.mjs --captions <captions.json> --style <style.json> [--layer all|behind|front|mask] --out <overlay.mov>\n' +
      '       optional: --concurrency n  --frames a-b  --still <frame> --png <file>');
}
const layer = args.layer ?? 'all';
if (!['all', 'behind', 'front', 'mask'].includes(layer)) die('--layer must be all, behind, front or mask');
const rp = (p) => path.resolve(process.cwd(), p);
const captions = JSON.parse(fs.readFileSync(rp(args.captions), 'utf8'));
const style = JSON.parse(fs.readFileSync(rp(args.style), 'utf8'));
const fontSpecs = (o, out = []) => {
  if (o && typeof o === 'object') {
    if (typeof o.file === 'string' && typeof o.family === 'string') out.push(o);
    else for (const v of Object.values(o)) fontSpecs(v, out);
  }
  return out;
};
for (const f of fontSpecs(style)) {
  if (!fs.existsSync(path.join(fontsDir, f.file))) die(`font not found: ${path.join(fontsDir, f.file)}`);
}

if (!fs.existsSync(path.join(here, 'node_modules', 'remotion'))) {
  console.error('template/node_modules is missing, running npm ci (first run only)...');
  const r = spawnSync('npm', ['ci', '--no-audit', '--no-fund'], {cwd: here, stdio: 'inherit'});
  if (r.status !== 0) die('npm ci failed');
}

const {bundle} = await import('@remotion/bundler');
const {renderMedia, renderStill, selectComposition} = await import('@remotion/renderer');

const t0 = Date.now();
const inputProps = {captions, style, layer};
// The bundle is a throwaway copy of the renderer (about 30 MB): always remove it, or repeated runs fill the disk.
const bundleDir = fs.mkdtempSync(path.join(os.tmpdir(), 'subtle-bundle-'));
const cleanup = () => { try { fs.rmSync(bundleDir, {recursive: true, force: true}); } catch {} };
process.on('exit', cleanup);
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => { cleanup(); process.exit(1); });
const serveUrl = await bundle({
  entryPoint: path.join(here, 'src', 'index.ts'),
  publicDir: fontsDir,
  outDir: bundleDir,
  // Independent renders may run concurrently from this package.
  enableCaching: false,
});
const findBrowser = () => {
  if (process.env.PUPPETEER_EXECUTABLE_PATH && fs.existsSync(process.env.PUPPETEER_EXECUTABLE_PATH)) {
    return process.env.PUPPETEER_EXECUTABLE_PATH;
  }
  const candidates = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium',
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return null;
};
const chromiumExecutable = findBrowser();

const composition = await selectComposition({
  serveUrl,
  id: 'Captions',
  inputProps,
  ...(chromiumExecutable ? {browserExecutable: chromiumExecutable} : {}),
  logLevel: 'error',
});

if (args.still != null) {
  const out = rp(args.png ?? args.out);
  fs.mkdirSync(path.dirname(out), {recursive: true});
  await renderStill({
    composition,
    serveUrl,
    inputProps,
    frame: Number(args.still),
    imageFormat: 'png',
    output: out,
    ...(chromiumExecutable ? {browserExecutable: chromiumExecutable} : {}),
    logLevel: 'error',
  });
  console.log(JSON.stringify({out, frames: 1, seconds: +((Date.now() - t0) / 1000).toFixed(1)}));
} else {
  const out = rp(args.out);
  fs.mkdirSync(path.dirname(out), {recursive: true});
  let frameRange = null;
  if (args.frames) {
    const [a, b] = args.frames.split('-').map(Number);
    frameRange = [a, b ?? a];
  }
  await renderMedia({
    composition,
    serveUrl,
    inputProps,
    codec: 'prores',
    proResProfile: '4444',
    pixelFormat: 'yuva444p10le',
    imageFormat: 'png',
    muted: true,
    overwrite: true,
    outputLocation: out,
    concurrency: args.concurrency ? Number(args.concurrency) : null,
    frameRange,
    ...(chromiumExecutable ? {browserExecutable: chromiumExecutable} : {}),
    logLevel: 'error',
  });
  const frames = frameRange ? frameRange[1] - frameRange[0] + 1 : composition.durationInFrames;
  console.log(JSON.stringify({out, frames, seconds: +((Date.now() - t0) / 1000).toFixed(1)}));
}
