import {INSTALL, REPO, type Preset} from './data';
import {buildOverride, isTweaked, mergedStyle, pageText, type Edits, type Tweaks} from './tweaks';
import type {CPage} from './engine';

export type PromptInput = {
  preset: Preset;
  tweaks?: Tweaks;
  highlights: boolean;
  behindOn: boolean;
  edits: Edits;
  pages: CPage[];
};

const fmt = (ms: number) => (ms / 1000).toFixed(1) + 's';

export function styleJson(preset: Preset, tweaks?: Tweaks): string {
  return JSON.stringify(mergedStyle(preset, buildOverride(preset, tweaks)), null, 2) + '\n';
}

export function buildPrompt(i: PromptInput): string {
  // One prompt that a fresh Claude Code (or Codex) session can run start to finish: setup, the style with every choice
  // made on the page, the run, and the check before handing the video back.
  const {preset, tweaks} = i;
  const name = preset.name;
  const over = buildOverride(preset, tweaks);
  const tweaked = isTweaked(tweaks);
  const behindStyle = !!preset.behind?.enabled;
  const styleArg = tweaked ? `~/${name}.custom.json` : name;
  const L: string[] = [];
  L.push(
    `Caption a video with Subtle, the open-source caption skill: https://${REPO}`,
    'It runs locally on this Mac. Nothing is uploaded and no API key is needed.',
    '',
    'Video: ~/Movies/my-video.mp4',
    '(If that path is still the placeholder above or the file is missing, ask me which video to caption before doing anything else.)',
    '',
    '## 1. Set up (skip whatever is already done)',
    `- Install the skill: \`${INSTALL.claude}\`. If that folder already exists, update it with \`git -C ~/.claude/skills/subtle pull\`. (In Codex use \`~/.agents/skills/subtle\` instead.)`,
    '- From the skill folder, run `bash scripts/doctor.sh` and install anything it reports missing (`brew install ffmpeg node uv`, and `xcode-select --install` for Swift). The first run also downloads the speech model (about 1.6 GB) and the renderer packages.',
    '',
    '## 2. Caption it',
    'Read the skill\'s SKILL.md and follow its steps (transcribe, group, pick the highlights, render, check) with these choices:',
    `- Style: \`${name}\`${preset.description ? `: ${preset.description}` : ''}${behindStyle ? ' (a behind-the-speaker style: needs macOS for the cut-out)' : ''}`,
  );
  const flags: string[] = [];
  if (!i.highlights) flags.push('`--emphasis off` (no highlighted words)');
  if (behindStyle && !i.behindOn) flags.push('`--behind off` (draw the giant words in front of me, not behind)');
  if (tweaks?.y != null) flags.push('`--placement off` (keep the caption exactly where the style puts it)');
  if (flags.length) L.push(`- Options: ${flags.join('; ')}.`);
  if (tweaked) {
    const parts: string[] = [];
    if (tweaks?.accent) parts.push(`accent colour ${tweaks.accent}`);
    if (tweaks?.size != null && tweaks.size !== 100) parts.push(`text size ${tweaks.size}% of the preset`);
    if (tweaks?.y != null) parts.push(`vertical position ${tweaks.y}% of the frame height`);
    if (tweaks?.case) parts.push({upper: 'UPPERCASE', sentence: 'Sentence case', lower: 'lowercase'}[tweaks.case]);
    if (tweaks?.shadow === false) parts.push('no shadow');
    L.push(`- My tweaks: ${parts.join(', ')}. Deep-merge this override over \`styles/${name}.json\`, save the result as \`${styleArg}\`, and pass \`--style ${styleArg}\` in every step:`, '```json', JSON.stringify(over, null, 2), '```');
  }
  const edited = Object.keys(i.edits).map(Number).sort((a, b) => a - b).filter((k) => i.pages[k]);
  if (edited.length) {
    L.push('- Word fixes: after the group step, edit `<name>.captions.json` so these pages read as below (keep each page\'s timing and spread its words evenly), then render with `--captions <name>.captions.json`:');
    for (const k of edited) L.push(`  - at ${fmt(i.pages[k].startMs)}: "${i.edits[k].trim()}" (was "${pageText(i.pages[k]).trim()}")`);
  }
  L.push(
    `- The final render is \`python3 scripts/subtle.py "<video>" --style ${styleArg}${flags.length ? ' ' + flags.map((f) => f.split('`')[1]).join(' ') : ''}\` from the skill folder (plus \`--captions\` if you edited the words).`,
    '',
    '## 3. Check before you hand it over',
    'Open `<name>.preview.jpg` and look at every page: the words must be readable, spelled right, and clear of my face. If something is off, fix it and render again.',
    'Then give me the paths to `<name>.captioned.mp4` and `<name>.srt`, and tell me in one line which words you highlighted and why.',
  );
  return L.join('\n');
}
