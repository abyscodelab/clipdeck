// Copies the engine's fonts (../fonts) to public/fonts so staticFile() resolves them in the Player. Not committed.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.resolve(here, '../../fonts');
const dst = path.resolve(here, '../public/fonts');
fs.mkdirSync(dst, {recursive: true});
for (const f of fs.readdirSync(src)) {
  const a = path.join(src, f), b = path.join(dst, f);
  if (!fs.existsSync(b) || fs.statSync(a).size !== fs.statSync(b).size) fs.copyFileSync(a, b);
}
