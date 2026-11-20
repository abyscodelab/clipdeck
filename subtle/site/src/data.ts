import type {CaptionsFile, Style} from './engine';

/** Every preset, straight from the repo's styles/*.json (the same files `--style <name>` reads). */
const files = import.meta.glob('../../styles/*.json', {eager: true, import: 'default'}) as Record<string, any>;
export type Preset = Style & {label?: string; description?: string; variants?: Record<string, any>; group?: string};
export const PRESETS: Record<string, Preset> = {};
for (const [p, v] of Object.entries(files)) PRESETS[p.split('/').pop()!.replace('.json', '')] = v;

export type Section = {id: string; title: string; blurb: string; styles: string[]};

/** Strongest first (ratings from the long-clip contact sheet); the weaker ones close the list as "More". */
const TOP = ['cover', 'outline', 'magazine', 'stack', 'rise', 'sticker', 'duo', 'editorial', 'cinema', 'impact', 'block', 'highlighter', 'numeral', 'split', 'keyword', 'glide', 'serif', 'shine', 'newsroom', 'cards', 'punch', 'flip', 'accent'];
const LAST = ['poster', 'hype', 'karaoke', 'bottom', 'haiku', 'terminal', 'title', 'whisper']; // rated under 7 on the long clip
const MUSIC = ['downbeat', 'billboard', 'chalkline', 'singalong']; // engine styles for songs; not shown here
const rest = Object.keys(PRESETS).filter((n) => !MUSIC.includes(n) && !TOP.includes(n) && !LAST.includes(n));

export const CATEGORY: Record<string, string> = {};
for (const n of ['stack', 'sticker', 'impact', 'block', 'highlighter', 'punch', 'ticket', 'bottom', 'duo', 'keyword', 'outline', 'rise', 'numeral', 'flip', 'split', 'poster']) CATEGORY[n] = 'bold';
for (const n of ['editorial', 'glide', 'serif', 'shine', 'cards', 'newsroom', 'haiku', 'title', 'accent', 'cover', 'magazine', 'cinema']) CATEGORY[n] = 'elegant';
for (const n of ['glass', 'chip', 'quiet', 'whisper', 'terminal', 'hype', 'karaoke']) CATEGORY[n] = 'minimal';

export const isBehind = (n: string) => !!PRESETS[n]?.behind?.enabled;
export const SPEECH_ORDER = [...TOP, ...rest, ...LAST];
export const FILTERS = [
  {id: 'top', label: 'Top picks'},
  {id: 'behind', label: 'Behind you'},
  {id: 'bold', label: 'Bold'},
  {id: 'elegant', label: 'Editorial'},
  {id: 'minimal', label: 'Minimal'},
  {id: 'all', label: 'All'},
];
export function stylesFor(filter: string): string[] {
  if (filter === 'top') return TOP;
  if (filter === 'all') return SPEECH_ORDER;
  if (filter === 'behind') return SPEECH_ORDER.filter(isBehind);
  return SPEECH_ORDER.filter((n) => CATEGORY[n] === filter);
}

/** The one demo clip: 52 s of Sam Altman on David Senra's podcast, a vertical crop with a wide shot, close-ups and the host's question. */
export const CLIP = {video: '/demo/clip.mp4', poster: '/demo/poster.jpg', person: '/demo/packed.mp4'};

export type PackedCaptions = {video: CaptionsFile['video']; styles: Record<string, Omit<CaptionsFile, 'video' | 'version'>>; stylePatch?: Record<string, any>};
let cache: Promise<PackedCaptions> | undefined;
export function loadCaptions(): Promise<PackedCaptions> {
  return (cache ??= fetch('/demo/captions.json').then((r) => r.json()));
}

export const REPO = 'github.com/0xpratzyy/subtle';
export const INSTALL = {
  claude: 'git clone --depth 1 https://github.com/0xpratzyy/subtle ~/.claude/skills/subtle',
  codex: 'git clone --depth 1 https://github.com/0xpratzyy/subtle ~/.agents/skills/subtle',
};
