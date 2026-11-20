# Architecture and file contracts

Everything runs locally. The pipeline is a chain of small tools that pass JSON and video files through one work folder.

```
video.mp4
  └─ scripts/transcribe.py   → words.json      (mlx-whisper, word timestamps, cached by file hash)
  └─ scripts/lyrics.py       → words.json      (optional, --lyrics: the lyrics file's words on the transcript's timings)
  └─ scripts/beats.py        → beats.json      (music styles only: tempo, beats, bar starts; ffmpeg + numpy, cached)
  └─ scripts/cuts.py         → cuts.json       (ffmpeg scene score: hard cuts, flashes ignored; ffmpeg only)
  └─ scripts/group.py        → captions.json   (number tokens, pages, lines, rule-picked highlights; pages split at cuts; needs a style)
  └─ scripts/placement.py    → captions.json   (adds pages[].y: off the face and hands; scripts/vision-subject, Apple Vision)
  └─ scripts/emphasis.py     → captions.json   (optional: Claude or the user changes the highlights; refreshes holds and giant words)
  └─ scripts/legibility.py   → captions.json   (per-page background measurement, `legibility` + `palette`; numpy, runs through uv)
  └─ scripts/shots.py        → captions.json   (behind styles and `split`: per-shot subject data `shots` and a 400 ms `subject` timeline; marks giant words that do not fit behind as `front`)
  └─ scripts/vision-matte    → check JSON, matte.mp4   (behind mode only; Apple Vision)
  └─ template/render.mjs     → overlay.mov     (Remotion: transparent caption layer, ProRes 4444)
  └─ scripts/composite.sh    → <name>.captioned.mp4   (ffmpeg: video + text [+ matted person])
  └─ scripts/verify.py       → preview.jpg + checks JSON
```

Remotion renders **only the caption layer** with an alpha channel. ffmpeg does the compositing. This keeps renders fast
(Chrome never decodes the source video) and makes behind mode a plain three-layer stack:

```
layer 1  source video
layer 2  big "behind" words          (overlay-behind.mov)
layer 3  source video × matte alpha  (the person)
layer 4  small fallback caption line (overlay-front.mov)
```

Without behind mode there is one overlay (`--layer all`) on top of the video. Styles with a glass or chip container add a
fifth input, the blur mask (`--layer mask`): the source is blurred under it before the overlay goes on.

## words.json

```json
{
  "version": 1,
  "source": { "sha256": "…", "durationMs": 8041, "fps": 24, "width": 720, "height": 1280 },
  "language": "en",
  "model": "mlx-community/whisper-large-v3-turbo",
  "words": [ { "text": "India", "startMs": 0, "endMs": 780, "prob": 0.99 } ]
}
```

`text` has no leading or trailing spaces; punctuation stays attached to its word.

## captions.json

```json
{
  "version": 1,
  "video": { "width": 720, "height": 1280, "fps": 24, "durationMs": 8041 },
  "style": "glide",
  "cuts": [4042, 7542],
  "pages": [
    {
      "startMs": 0, "endMs": 1260, "y": 74,
      "words": [
        { "text": "India", "startMs": 0,    "endMs": 780,  "line": 0, "emphasis": false },
        { "text": "has",   "startMs": 780,  "endMs": 1020, "line": 0, "emphasis": false },
        { "text": "$5,000", "startMs": 1020, "endMs": 1960, "line": 0, "emphasis": true, "reason": "price" }
      ]
    }
  ],
  "big": [ { "text": "gold", "startMs": 1980, "endMs": 2620 }, { "text": "$5,000", "startMs": 4100, "endMs": 5000, "front": true } ]
}
```

- `legibility`, `legibilitySummary` and `palette` are written by `scripts/legibility.py`, see "Legibility and palette" below.
- A page is what is on screen at once. `line` is 0 or 1 (max 2 lines).
- Pages never overlap. A page ends when the next one starts, or at most 400 ms after its last word (700 ms when the page
  has a highlighted word, so it holds a beat longer where there is room).
- `cuts` (optional) lists the hard cuts of the picture in ms, each the first frame of the new shot. No page straddles one:
  `group.py` splits a page at a cut (a word belongs to the shot holding its midpoint), joins a tiny split-off piece to a
  neighbouring page of the same shot when there is room, and clips a page's start and end to its shot. Absent when there
  are none, when `--cuts off` is used, and for music styles.
- `pages[i].y` (optional) is where page *i* sits, in percent of the frame height, set by `scripts/placement.py`. The renderer
  uses it instead of the style's `position.y` for that page (every style, through `pageStyle` in `engine/layout.ts`).
  A page without `y` sits at the style's `position.y`. Edit it freely; a `--captions` file that already has `y` is not re-placed.
- `emphasis` marks the highlighted words; `reason` says in one line why that word was picked (`price`, `year`, `name`,
  or whatever Claude or the user wrote). At most 1 per page, 2 on pages of 5 words or more.
- A word's `text` may hold a whole amount with a space in it (`"₹1 lakh"`, `"$5 million"`). It is still one word: one
  box in the layout, never split across lines or pages.
- `big` exists only for styles with `behind.enabled`: the 1 to 2 word beats drawn large behind the person. Text is stored
  as spoken; the renderer applies the style's case.

## Legibility and palette

Footage decides whether thin, light type reads. `scripts/legibility.py` (run by `subtle.py` after grouping, before the render; `--legibility off`
and `--palette off` skip the two halves) measures the footage and writes three keys into `captions.json`:

```json
"legibility": [ { "page": 0, "contrast": 2.78, "busy": 0.78, "bg": "#83725C", "boost": 0.83 } ],
"legibilitySummary": { "mode": "halo", "pages": 9, "boosted": 9, "meanBoost": 0.82, "maxBoost": 0.87, "minContrast": 2.4, "meanBusy": 0.77 },
"palette": { "accent": "#FFF599", "accent2": "#9FD8FF", "ink": "#FFFEF8", "shade": "#17110A", "bg": "#826F59", "contrast": 8.0 }
```

**Measure.** For each page it reads 3 frames across the page's time and looks at the region the text will cover, estimated from the preset
(`position`, `size`, `lineHeight`, the page's line count and character count, `marginX`; not a render). `contrast` is the WCAG ratio between the
ink (`color`, and the accent colour when the page has a highlight; words not yet spoken at `anim.dim` opacity) and the part of the background that is hardest
for it (the brightest quarter under light ink, the darkest under dark ink). `busy` (0..1) is mean edge strength and spread of the luminance, which
film grain does not saturate. `bg` is the mean colour. `boost` (0..1) is how much help the page needs: the target contrast is 4.5:1 on a calm
background rising to 10.5:1 on a very busy one, and `boost` is the shortfall on a scale that reaches 1 at 1.2:1 (0 for white on a calm dark background).
For a `plate` style the ink is measured against the plate over the footage. `boost` is 0 for `none` styles.

**Draw.** `template/src/engine/legibility.tsx` turns `boost` into help in the style's own taste. A preset may declare

```json
"legibility": { "mode": "halo", "max": 1, "strength": 1 }
```

| `mode` | What is drawn | Default for |
|---|---|---|
| `halo` | layered soft shadows hugging the glyphs, in the scene's `palette.shade` (a warm near-black on a warm room) | any preset with no `container` |
| `scrim` | a feathered band across the frame behind the caption block, soft top and bottom, at most 55% dark | (`terminal`) |
| `stroke` | a thin outline round the glyphs (SVG dilate), width grows with `boost` | |
| `plate` | the style's own container gets darker: the style calls `plateFill(fill, useLegibility())` (`glass`) | |
| `none` | nothing: boxed or full-frame styles that carry their own background | any preset with a `container` |

`max` caps `boost` for that style (a delicate style asks for less), `strength` scales the effect; `"accent": false` leaves the highlight colour out of the contrast measurement (`terminal`: its highlight is dark text on its own green block). Below a boost of 0.04 nothing is drawn, so on clean footage the
render is identical to a render without the feature. Nothing is drawn in `mask` mode or in the `behind` layer. A variant can set its own mode
(`singalong:lit` is `halo`, the plain `singalong` has its own field and is `none`).

**Palette.** Any colour in a preset may be a token, `{ "auto": "accent" | "accent2" | "ink" | "shade", "fallback": "#rrggbb" }`. The renderer replaces it with
`captions.palette[...]`, or with the fallback when the file has no palette (`--palette off`, or a hand-written file). Tokens are used in `glide` (`activeColor`),
`keyword` (`emphasis.color`, `behind.bigColor`), `shine` (`color`, the contrasting `accent2`), `accent` (`color`), `hype` (`activeColor`), `highlighter`, `haiku` and `karaoke` (`emphasis.color`).
`legibility.py` picks the palette by k-means (k = 6, fixed seed) on 8 downsampled frames: the dominant hue of the saturated clusters, then candidate accents at that hue,
about 20 degrees either side and at the split-complement, at four saturations, always at full brightness. Each candidate is scored on contrast against the
background as it looks under the halo (the caption-zone luminance, 75th percentile page, darkened by `SHIELD` = 65%), harmony with the scene, vibrancy and distance from the wall's own
hue; the winner is paled toward white until it reaches 4.5:1 where the scene allows it (it never ends below 3:1, the WCAG limit for large text). `accent2` is the best candidate at the split-complement or opposite hue (a cooler second colour), paled the same way. `ink` is a
near-white tinted toward the accent, `shade` a near-black tinted toward the scene hue, `bg` the measured caption-zone colour, `contrast` the accent's ratio.
Colours the preset fixes in place (a style's identity, e.g. terminal green) are not tokens and never change.

## Music: beats, lyrics and line pages

`scripts/beats.py song --out beats.json` writes `{"bpm", "times" (ms, every beat), "downbeats" (ms, bar starts, 4/4
assumed), "clarity" (0..1)}`. It uses the spectral flux of a log spectrogram for onsets, autocorrelation for the tempo
and dynamic programming for the beats; the downbeat is the beat of each four with the most bass. The runner uses the
grid only when `clarity` is 0.25 or more (plain speech scores about 0.2, music 0.35 and up); otherwise the pages follow the words.

`scripts/lyrics.py words.json lyrics.txt --out words.json` aligns the lyrics file to the transcript word by word
(longest matching runs first). A matched word keeps the transcript's timing and takes the file's spelling; a stretch
heard differently is re-spread over the same time; a sung run the file leaves out (a repeated chorus, ad-libs) stays
as heard; a line that was never sung is dropped. Each word gets `lyricLine`.

A music preset sets these in `page` (read by `group.py`):

| Key | Meaning |
|---|---|
| `unit: "line"` | a page is made of lyric lines (from `lyricLine`, else from phrases); `maxWords` and `maxCharsPerLine` are per line, and a longer line is cut into even pieces |
| `linesPerPage` | lines on a page (1 for `downbeat` / `billboard`, 4 for `chalkline` / `singalong`); each word's `line` is 0 to `linesPerPage - 1` |
| `blockGapMs` | a pause longer than this starts a new page even if the page has room |
| `snap: "beat"` or `"bar"` | the page starts on the beat (or bar line) at or just before its first word (a word may come up to 0.3 beat early) |
| `hold: true` | the page stays until the next one starts, unless the gap is longer than 8 beats |

`captions.json` then carries `"beats": {"bpm", "times", "downbeats"}` for the renderer. A preset with
`"group": "music"` is listed under "Music / lyric" and makes the runner look for the beat.

`"variants": {"<name>": {…}}` in any preset holds colourways: `--style ticket:yellow` deep-merges
`variants.yellow` over the preset and renders that.

An input with no picture (a song) gets a black canvas (`--canvas 9:16 | 16:9 | 1:1 | 4:5`, 30 fps).

## Numbers and highlights

`scripts/spoken_numbers.py` runs inside `group.py`, before the words are grouped. It rewrites every way a transcriber
writes an amount into one token that spans the time of the words it replaced:

| Heard | Token |
|---|---|
| "five thousand dollars", "5000 dollars", "$5000" | `$5,000` |
| "forty percent", "40 per cent" | `40%` |
| "one lakh rupees", "Rs. 5 lakh", "5 crore rupees" | `₹1 lakh`, `₹5 lakh`, `₹5 crore` |
| "five million dollars" | `$5 million` |
| "nineteen ninety one", "1991" | `1991` (years get no separator) |
| "1500000", "1500000 rupees" | `1,500,000`, `₹15,00,000` |
| "three times", "one of them", "a million reasons" | unchanged: small spelled numbers stay words |

`--numbers western|indian` fixes the digit grouping (`auto` uses Indian grouping for rupee amounts and Hindi speech);
`--numbers off` keeps the transcript as heard.

`scripts/emphasis.py` holds the rules and the command line for picks:

- `rule_picks(pages, mode, forced)`: `auto` scores each word (price 10, percentage, year, number 9+, acronym or name 7,
  contrast word 6, count word 5.5), takes the best 1 or 2 per page, lowers a repeated name each time it comes back, and
  on a stretch with nothing certain guesses one long word, marked `long word (a guess)`. `numbers` keeps only the number
  kinds. `off` keeps only forced words.
- `--show`, `--pick PAGE:WORD=reason`, `--drop PAGE:WORD`, `--clear`, `--mode`: how Claude reads and changes the picks.
- `finalise(captions, style)` runs at the end of every call and of `group.py`: it lengthens highlighted pages and rebuilds
  `big` for styles with a giant word (numbers first, then hand picks, then names, guesses last, when two are too close).

## Style JSON (`styles/<name>.json`)

Sizes are **percent of frame height** unless a key says otherwise, so one preset works at any resolution.
Animation lengths are in frames at 30 fps; the renderer converts them to the video's frame rate.

```json
{
  "name": "glide",
  "label": "Glide",
  "description": "One-line description shown to the user.",
  "engines": ["remotion"],
  "font": { "family": "Inter Bold", "file": "Inter-Bold.ttf", "weight": 700 },
  "emphasisFont": { "family": "Pinyon Script", "file": "PinyonScript-Regular.ttf", "weight": 400 },
  "case": "sentence",
  "size": 3.9,
  "wideScale": 1.3,
  "lineHeight": 1.2,
  "letterSpacing": 0,
  "color": "#FFFFFF",
  "activeColor": "#F5F258",
  "shadow": { "x": 0, "y": 0.19, "blur": 0.37, "color": "rgba(0,0,0,0.35)" },
  "position": { "y": 52, "marginX": 6 },
  "page": { "maxWords": 5, "maxCharsPerLine": 24, "maxCharsPerLineWide": 40, "maxLines": 1, "minFrames": 14, "maxFrames": 75, "gapBreakMs": 350 },
  "anim": { "type": "glide", "scriptScale": 2.8, "scriptIn": 5 },
  "behind": { "enabled": false }
}
```

Fixed keys every preset must have: `name` (equal to the file name), `label`, `description`, `engines`, `font`, `case` (`upper` |
`sentence` | `lower`), `size`, `wideScale` (multiplier applied when the video is wider than tall), `color`, `position`, `page`,
`anim.type` (the key in the style registry). `group.py` reads only `page`, `case` and `behind`. Everything else belongs to the renderer.

Optional keys a style may use (the engine loads every `{family, file, weight}` object it finds, so a style can name any font in `fonts/`):

| Key | Meaning |
|---|---|
| `emphasisFont` | second font for emphasis words (script or serif italic) |
| `noteFont` | handwriting font for a note line |
| `activeColor`, `dimColor` | accent colour; colour of words not yet spoken |
| `position.x` | horizontal centre in % of width (default 50); `position.marginX` is the side margin in % |
| `position.flex` | `[low, high]`: the range (% of height) placement may move a page's centre within; `0` fixes the style at `position.y`. Absent: `[y - 12, y + 12]`, with the top end kept above 84 (or at `y` if that is lower). The preset `y` is always inside the range. `chalkline`, `downbeat`, `billboard`, `singalong`, `keyword` and every music style keep their own place whatever this says |
| `container` | `{kind: pill \| chip \| block, fill, highlight, padX, padY, radius}`; padding in em of the font size |
| `backdropBlur` | px at 1080p to blur the video under the container (`--layer mask` carries the shape); 0 or absent for none |
| `anim.*` | timings (frames at 30 fps), scales and offsets read by that style's component |
| `behind` | giant words behind the speaker, see below |
| `legibility` | `{mode, max, strength}`: automatic help on busy footage, see "Legibility and palette" |
| `{auto, fallback}` | any colour may be a token filled from `captions.palette`, see "Legibility and palette" |

`anim` keys are private to each style. The ones the bundled styles read (frames are at 30 fps; sizes in em of the font size unless noted):

| Style | `anim` keys |
|---|---|
| `glide` | `scriptScale` (script word size against the sans), `scriptBold` (px at 1080p: extra copies of the hairline script, thickens it), `scriptIn`, `scriptFrom` (start scale), `wordIn`, `glowBlur`, `pageOut` |
| `glass`, `karaoke`, `chip` | `dim` (opacity of words not yet spoken), `wordIn`, `pageIn`, `pageOut`, `pageScaleFrom` |
| `whisper` | `wipe` (frames per word), `feather` (soft edge, em), `wordBlur`, `pageBlur`, `pageOut` |
| `terminal` | `cps` (characters a second), `blink` (cursor period) |
| `keyword` | `bigIn`, `bigOut`, `overshoot`, `slide`, `smallIn`, `smallRise` |
| `accent` | `italicScale`, `drift` (px at 1080p), `pageIn`, `pageOut` |
| `title` | `typeMax`, `trackFrom` (starting letter spacing), `slideX`, `noteSize`, `noteTypeMax`, `pageOut` |
| `hype` | `mode` (`page`: the whole key page takes the accent colour; `word`: only the key word), `pageIn`, `pageOut` |
| `block` | `lineIn`, `rise`, `blur` (motion blur on entry), `exitDrop`, `pageOut` |
| `impact` | `letterIn`, `stagger`, `arc`, `rise`, `rotate`, `scaleFrom`, `drift`, `stroke`, `strokeColor`, `shadowY`, `shadowColor` |
| `bottom` | none: words appear on their own frame with no animation |
| `stack` | `pileWidth` (% of width), `pitch` (line overlap), `keyScale`, `popIn`, `popFrom`, `stroke`, `shadowY` |
| `serif` | `gradTop`, `gradBottom` (the top-lit gradient), `wordIn`, `wordBlur`, `shadowBlur`, `shadowColor`, `pageOut` |
| `shine` | `band` (width of the light band), `sweep` (frames), `delay`, `lightColor`, `glow`, `glowBlur`, `wordIn`, `pageOut` |
| `sticker` | none (the bubble is `container`: `fill`, `padX`, `height`, `radius`, `offset` of each line to the right of the one above; the stack tilts 0.4° to 3° by page) |
| `ticket` | none (the label is `container`: `fill`, `padX`, `padY`; the tilt cycles through −3° to +4° by page and segment) |
| `highlighter` | `padX`, `padY` (box padding, em), `gap` (word spacing multiplier), `handoff` (frames the box takes to hop) |
| `haiku` | `stroke` (dark outline, em of the word), `bold` (thickening stroke in its own colour, em): one word per page, hard cuts |
| `duo` | `leadFont`, `tailFont`, `leadSize`, `tailSize` (% of height), `leadTrack` (letter spacing, em), `softColor`, `leadIn`, `tailIn`, `pageOut` |
| `editorial` | `rowGap`, `afterGap` (baseline distance of the lines above and below the keyword, in sans sizes), `keyInset`, `keyIn` (frames), `keyFrom` (start scale), `keyBlur` |
| `downbeat` | `inFrames` (entry length), `moves` (entry move per line, cycled: `spin` `up` `down` `left` `wipe`), `stagger` (frames between the lines of a page), `fills` (line width as a share of the frame, cycled), `maxSize`, `connectorSize` (% of height), `fields` (`{bg, fg}` list, cycled), `fieldBars` (bars per colour field), `fieldPages` (pages per field without beats), `accentField` (field index for a page with an emphasised word); top-level `lineFonts` is the font list lines take in turn. Vertical frames (`*Tall` keys): `fillsTall`, `maxSizeTall`, `maxWidthTall` (line width limit), `gapTall` (line gap factor), `maxStackTall` / `minStackTall` (stack height share, max / min), `maxStretchTall` (the full-size lines are stretched taller to reach `minStackTall`), `connectorSizeTall`, `connectorFillTall`, `condensedTall` (`lineFonts` indexes an emphasised line takes) |
| `billboard` | `tones` (name → colour), `pairs` (`[background, text]` tone names, cycled), `flipBeats` (beats between pair changes), `popFrames`, `popFrom` (small word's start scale), `fillBig`, `fillSmall` (word width as a share of the frame; the big word may exceed 1), `maxBig`, `maxSmall` (font size, % of height), `spots` (block position per page: `tl` `br` `c`). Vertical frames: one word per line, `tallBig` / `tallSmall` (word width as a share of the frame), `tallStack` (max stack height share), `tallMin` + `tallStretch` (a short stack is stretched taller, up to that factor, to own the frame), `tallGap`, `tallEmWeight` (extra height for the emphasised word). Number tokens never bleed |
| `chalkline` | `bg`, `vignette`, `grain` (chalk texture, 0 for none), `boilFps`, `wobble` (px at 1080p), `stepFrames`, `minSteps`, `maxSteps` (write-on steps per word), `indent` (% of width per line, cycled), `underlineFrames`, `underlineSteps`, `clearFrames` (fade before the page clears), `inks` (colour list per line, `null` = `color`) |
| `singalong` | `mode` (`wipe` or `lit`), `field` (background colour, `null` for none), `pulse` (scale kick of the line being sung on each beat), `pulseFrames`, `litIn`, `dim` (`lit`: opacity of words not yet sung), `pageIn`, `pageOut`; `activeColor` is the colour of the sung part |

A style that has a blur container must draw the same container shape in `mask` mode. Styles without one render an all-black mask.

`behind` (used by `keyword`):

```json
"behind": { "enabled": true, "bigY": 26, "bigWidth": 90, "bigMaxSize": 22, "bigOpacity": 1, "bigColor": "#D6FCA5",
            "bigFont": { "family": "Inter Bold", "file": "Inter-Bold.ttf", "weight": 700 },
            "maxBigWords": 1, "maxChars": 9, "minHoldMs": 900, "everyMs": 1700 }
```

`bigY` is the vertical centre of the giant word in % of height; the orchestrator sets it per video from `vision-matte check`.
A giant word that is a number (`"front": true` in `captions.big`) is never put behind the speaker, because hidden digits
change its meaning: it is drawn in front, at `frontY` (% of height, below the face; the orchestrator sets it about a
third of the frame under `bigY`) and at most `frontWidth`% of the frame wide. Hand-edit `front` in `captions.big` to
move any word to the front or back.
The giant word fills `bigWidth`% of the frame width (never larger than `bigMaxSize`% of the height).

## Recipe styles (`anim.type: "recipe"`)

`template/src/styles/recipe.tsx` is one generic style driven entirely by a `recipe` block in the style JSON, so a caption
treatment needs no new TSX. All top-level keys stay as in any style (`font`,
`case`, `size`, `color`, `shadow`, `position`, `page`, `backdropBlur`...); `group.py` reads `page` and `case` as usual.
Lengths are in **em** of the font size, frames are at 30 fps (scaled to the video's fps), every key is optional.

```json
"anim": {"type": "recipe"},
"recipe": {
  "unit": "word", "enter": {"kind": "pop", "frames": 6, "ease": "out-back", "overshoot": 1.12},
  "exit": {"kind": "cut"}, "upcoming": {"opacity": 0}, "active": {"color": "#C8FF2E", "scale": 1.1},
  "stroke": {"width": 0.08, "color": "#000"}, "emphasis": {"color": "#C8FF2E"}
}
```

| Key | Default | Meaning |
|---|---|---|
| `unit` | `word` | What animates in: `word` (each word as it is spoken), `line` (each line when its first word is spoken), `page` (the whole page at page start). |
| `enter.kind` | `fade` | `none` `fade` `pop` (scale up with overshoot) `rise` (from below) `drop` (from above) `slide-left` (moves left, starts right) `slide-right` `wipe` (soft left-to-right reveal) `blur-in` `typewriter` (characters of the unit in order) `scale-down` (starts large, settles). |
| `enter.frames` | 6 | Length of the entrance. |
| `enter.ease` | `out-cubic` | `out-cubic` `out-back` `out-expo` `linear` (`typewriter` is always linear). |
| `enter.distance` | 0.4 | Travel in em for `rise` `drop` `slide-*`; blur radius scale for `blur-in`; extra start scale for `scale-down` (0.4 = starts at 1.4x). |
| `enter.overshoot` | 1.12 | Peak scale of `pop` (start scale is 0.6, `1` means no overshoot). |
| `enter.stagger` | 0 | Frames between successive words of a `line` / `page` unit (and of a `word` unit when `upcoming.opacity` > 0). |
| `exit.kind` | `cut` | How the page leaves, over its last frames: `cut` `fade` `drop` `rise` `blur-out` `scale-up`. |
| `exit.frames` | 4 | Length of the exit. |
| `upcoming.opacity` | 0 | Opacity of a word that is on screen but not yet spoken. **Above 0.01 the whole page (or line) enters at the page start and unspoken words sit at this opacity** (karaoke look). At 0, `word` units appear only when spoken; for `line` / `page` units 0 means "no dimming" (treated as 1). |
| `upcoming.color` | `null` (= `color`) | Colour of an unspoken word. |
| `active.color` | `null` | Colour of the word being spoken. |
| `active.scale` | 1 | Scale of the spoken word (about its centre; 3-frame blend in and out). |
| `active.opacity` | 1 | Opacity of the spoken word. |
| `active.plate` | `null` | `{color, radius, padX, padY}` (em) box behind the spoken word (a hopping highlighter). Defaults: `rgba(255,255,255,0.9)`, 0.2, 0.2, 0.1. |
| `active.underline` | `null` | `{color, thickness, offset}` (em; defaults text colour, 0.07, 0.14) line under the spoken word, growing as it is spoken. |
| `spoken.color`, `spoken.opacity` | `null`, 1 | Look of a word after it was spoken. |
| `plate` | `null` | A plate behind the text: `{kind: page \| line \| word, color, radius, padX, padY, backdropBlur}` (em, except `backdropBlur` in px at 1080p). Defaults `rgba(0,0,0,0.6)`, 0.3, 0.4, 0.15, 0. `page` = one card for the block, `line` = one per line, `word` = one per word. `backdropBlur` blurs the video under the plate (same mask pipeline as `glass`; it is read from here, or from the top-level `backdropBlur`). The block is kept `padX` clear of the side margins. |
| `stroke` | `null` | `{width, color}` outline, `width` in em as the **visible** outer thickness. |
| `emphasis.color` | `null` | Colour of words with `emphasis: true`; wins over the state colours. |
| `emphasis.scale` | 1 | Size multiplier in the layout (the line grows around it). |
| `emphasis.font` | `null` | A `{family, file, weight}` from `fonts/` for emphasis words. |
| `emphasis.plate`, `emphasis.underline` | `null` | Same shapes as `active.plate` / `active.underline`, shown for emphasis words as soon as they enter. |
| `emphasis.case` | `null` | `upper` `lower` `sentence` for emphasis words (default: the style `case`). |
| `align` | `center` | `center` `left` `right`: line alignment inside the block; `position.x` is the centre of the block. |
| `rotate` | 0 | Degrees, the whole block about its centre. |
| `uppercaseEmphasisOnly` | false | Words keep their typed case, emphasis words are upper-cased. |

Precedence of a word's colour: `emphasis.color`, then the state colour (`active` / `spoken` / `upcoming`), then `color`.
Draw order, back to front: page and line plates, word plates, underlines, text (with `stroke`); the style's `shadow` is applied
to the text only. Bundled examples: `newsroom`, `cards`, `punch`, `quiet`.

## Renderer CLI (`template/render.mjs`)

```
node template/render.mjs --captions <captions.json> --style <style.json> --layer all|behind|front|mask --out <overlay.mov>
node template/render.mjs ... --still <frame> --png <file>      # one PNG
node template/render.mjs ... --frames 24-72                    # only that frame range
```

- Output: ProRes 4444 with alpha (`yuva444p10le`), same width, height, fps and duration as `captions.video`.
- `--layer all` draws everything. `--layer behind` draws only the giant words (`captions.big`). `--layer front` draws only the page captions.
- `--layer mask` draws the style's containers as solid white shapes on opaque black, same timing and geometry as the visible containers, no text.
  ffmpeg blurs the video under it. All black for styles without a container.
- Fonts load from `fonts/` in this repo. No network access at render time.
- First run installs `template/node_modules` (the script says so and runs `npm install`).

## Renderer code (`template/src/`)

```
engine/   types, ease, time (page timing, per-word state), layout (measure, wrap, fit), draw (words, containers, reveals), fonts,
          legibility (halo / scrim / stroke / plate from captions.legibility, palette tokens)
styles/   one file per style + index.ts (the registry)
Captions.tsx   picks the style from the registry, lays out each page, calls the style's components
```

Everything is drawn in one full-frame SVG, positioned by baseline. All animation is a pure function of the frame number.

### How to add a style

1. **Preset.** Copy a file in `styles/` to `styles/<name>.json`. Set `name`, `label`, `description`, fonts, `size`, `color`, `page`
   (words per page and per line) and `anim.type` to `<name>`. Put timings and scales your style needs under `anim`.
2. **Component.** Create `template/src/styles/<name>.tsx` and export a `StyleDef`:

   ```tsx
   import {Word, fadeIn, f30} from '../engine';
   import type {PageProps, StyleDef} from '../engine';

   const Page: React.FC<PageProps> = ({st, f, L, ws, since, left, mode}) => (
     <g>{L.words.map((box, i) => <Word key={i} box={box} fill={st.color} opacity={fadeIn(ws[i].since, f30(3, f.fps)).opacity} />)}</g>
   );
   export const mine: StyleDef = {Page};
   ```

3. **Register.** Add `<name>` to `template/src/styles/index.ts`.
4. **Check.** `npx tsc --noEmit -p template`, then `bash tests/smoke.sh` (it loops over `styles/`).

`PageProps` gives the page that is on screen: `st` (the preset), `f` (`W`, `H`, `fps`, `wide`), `page`, `L` (layout: one box per word with
`left`, `w`, `baseline`, `fs`, `font`; plus `lines`, `left`, `top`, `blockW`, `blockH`), `ws` (per word: `state` upcoming | active | spoken,
`progress` 0..1 while spoken, `since` frames since the word started, negative before), `since` / `left` (frames since the page started / until it ends)
and `mode` (`visible` or `mask`). Optional `StyleDef` fields: `spec(page, st)` returns per-word overrides before layout (font, size multiplier, text,
extra space after), `layout(st, f)` returns layout options (alignment, padding kept free for a container), `hasMask` says the style draws containers in `mask`
mode, `Big` draws giant words for `--layer behind`, `minShow` keeps short pages up for a minimum number of frames.

Building blocks in `engine/draw.tsx`: `Word`, `Xf` (scale / shift / fade / filter a group), `Container` (pill, chip or block; white shape in `mask` mode),
`FeatherMask` (soft left-to-right wipe), and the reveals `fadeIn`, `riseIn`, `blurIn`, `scaleFromBaseline`, `fadeOut`. Easing and colour mixing are in
`engine/ease.ts`. Rules: sizes in % of frame height (use `f.H`), text must stay inside the side margins (the layout shrinks it to fit), words keep their
place while they animate, and nothing may depend on anything but the frame number.

## How each style shows emphasis

`emphasis: true` on a word marks it. A token may hold digits, commas, currency signs, a percent sign and one space (`"25,000"`, `"$5,000"`, `"10%."`, `"₹1 lakh"`); it is always one word box and is never split. Colours, fonts and scale live in the preset's optional `emphasis` object (private keys per style), so users can edit them. Where a style changes the font, weight or size of the word, the change goes through `spec` so the layout measures the word that way and keeps it inside the side margins.

| Style | Emphasised word | `emphasis` keys |
|---|---|---|
| `glide` | calligraphic script; a token with a digit or currency sign uses a serif italic (larger than the sans) instead | `numberFont`, `numberScale` |
| `accent` | serif italic (`emphasisFont`) | none |
| `hype` | accent colour (`anim.mode`: whole page or only the word) | none |
| `bottom` | `activeColor` (yellow) | none |
| `impact` | `activeColor` | none |
| `shine` | stronger glow after the light sweep | none |
| `stack` | `activeColor`, larger (`anim.keyScale`) | none |
| `chip` | inverted chip: dark rounded rectangle, light text, pops in when spoken | `fill`, `color`, `padX`, `chipHeight`, `chipIn` |
| `keyword` | a small word that is not a giant word takes the pale-lime colour (the other small words are off-white) | `color` |
| `karaoke` | brighter accent colour and a scale-up when spoken (room reserved in the layout) | `color`, `scale` |
| `block` | the line holding the word gets a second block colour | `fill` |
| `glass` | heavier weight and a warm accent colour once spoken | `font`, `color` |
| `whisper` | white instead of warm yellow, one weight heavier | `font`, `color` |
| `terminal` | inverse video: a block behind the word, dark text | `fill`, `color` |
| `title` | accent colour, in the title and in the handwritten note | `color` |
| `serif` | warm gold top-lit gradient instead of silver | `gradTop`, `gradBottom` |
| `sticker` | its line gets a brighter bubble and a larger word | `fill`, `scale` |
| `ticket` | alone on a big label (split at render time), in the hot colour | `color`, `scale` |
| `highlighter` | alone, large, in the finished (lime) colour, with the box behind it (split at render time) | `color`, `scale` |
| `haiku` | italic serif, lighter yellow, a little larger | `font`, `color`, `scale` |
| `duo` | it is the headline word (the longest word when none is marked) | none |
| `editorial` | it is the keyword: italic serif in red, about 3x the sans (the last content word when none is marked) | `font`, `color`, `scale`, `letterSpacing` |
| `downbeat` | its own line, the largest on the page, and the page goes onto the accent field colour | `fill`, `maxSize` |
| `billboard` | it is the big word, wider than the frame (the longest word when none is marked) | `fill` |
| `chalkline` | larger, upper-case, in the emphasis font, with a hand-drawn underline stroke | `scale`, `underline`, `caps` |
| `singalong` | a warmer, brighter fill when sung (`wipe`) or full white (`lit`), and a little larger | `color`, `scale` |

### Glyph fallback

Every bundled font was checked against `0-9 $ ₹ € £ % , . x`. Only the Rupee sign is missing, in four families. `engine/fonts.ts` (`GLYPH_GAPS`, `fontWithGlyphs`) lists those files; `layoutPage` draws and measures a word that contains a missing character in the fallback font, and `loadFonts` loads the fallbacks.

| Font file | Missing | Fallback |
|---|---|---|
| `CourierPrime-Bold.ttf`, `CourierPrime-Regular.ttf` | ₹ | `Inter-Bold.ttf`, `Inter-Regular.ttf` |
| `InstrumentSerif-Italic.ttf`, `InstrumentSerif-Regular.ttf` | ₹ | `PlayfairDisplay-MediumItalic.ttf` |
| `PinyonScript-Regular.ttf` | ₹ | `PlayfairDisplay-MediumItalic.ttf` |
| `ArchivoBlack-Regular.ttf` | ₹ | `Montserrat-Black.ttf` |

All other font files cover every checked character. A new font that lacks a glyph needs one line in `GLYPH_GAPS`.

## Music styles and the beat

`downbeat`, `billboard`, `chalkline` and `singalong` (preset `"group": "music"`) are for lyric videos. They read `captions.beats`
(`{bpm, times, downbeats}` in ms, written by `group.py --beats`) through `engine/beats.ts`:

- `beatGrid(captions, fps)` turns the beats into frames (cached; `null` when the file has no `beats`). `beatIndex`, `beatNumber`,
  `barIndex`, `sinceBeat` and `snapToBeat` answer "which beat / bar is it" and "how long since the last beat". Every helper takes the
  `null` grid and falls back to the page's own start (or a page counter), so a music style also works on plain speech.
- **Pages start on the beat.** The preset's `page` block asks `group.py` for `unit: "line"`, `snap: "beat"` or `"bar"` and `hold: true`;
  the renderer then rounds a page's start and end to the nearest frame (only when `beats` is present; other captions floor as before),
  so the cut lands on the beat frame and held pages meet with no gap.
- `downbeat`: the lines of a page enter on the page's beat, two frames apart; the colour field flips every `fieldBars` bars.
- `billboard`: the big word comes with the page; the small word pops on the beat at or just before it is sung; the tone pair changes
  every `flipBeats` beats and on every page.
- `chalkline`: a page is a block of up to four lyric lines that starts on a bar; lines write on with the words (not locked to beats),
  redrawn with a seeded jitter at `boilFps`.
- `singalong`: the block cuts in on the bar; the line being sung gives a small scale pulse on every beat. Variant `lit` starts pages on the beat.

Variants live in the preset's `variants` object (`singalong:lit`, `chalkline:marker`) and are deep-merged over the preset.
The engine draws up to four lines per page (`layoutPage` caps a word's `line` at 3). Fonts with no rupee sign are listed in `GLYPH_GAPS`:
Abril Fatface and Corben Bold fall back to `PlayfairDisplay-BlackItalic.ttf`; Gloria Hallelujah and Reenie Beanie fall back to `Caveat-SemiBold.ttf`.

## vision-matte CLI (`scripts/vision-matte/`)

```
scripts/vision-matte/build.sh                      # swiftc → scripts/vision-matte/.build/vision-matte
vision-matte check <video> [--samples 12] [--band-height 0.14]   # JSON on stdout
vision-matte matte <video> --out <matte.mp4> [--quality accurate|balanced|fast] [--no-ema]
```

`check` JSON:

```json
{ "samples": 12, "personFrames": 12, "meanArea": 0.51, "meanWidth": 1.0, "motion": 0.014, "softFraction": 0.029,
  "bigY": 0.28, "bandCoverage": 0.31, "recommend": "behind", "reason": "person in 12 of 12 samples" }
```

`bigY` is where the big word should sit (fraction of the height): the tool slides a band as tall as the word down the
frame and picks the place where the person covers about 30% of it (usually the head, so both ends of the word stay clear). `bandCoverage` is that share.

`recommend` is `"behind"` or `"skip"`. Skip when: a person is in under 60% of samples; mean mask motion between samples
is high (cuts, pans); the person covers more than 50% of the best band (the word would be hidden) or less than 8% (nothing
would be behind them); or the soft-edge fraction is above 8%.

`matte` writes a video with the same frame count, size and frame rate as the source: white is the person, black is the
background, soft edges are kept. It prints one JSON line with `frames`, `msPerFrame` and `quality`.

## Cuts and placement

Two steps keep captions out of the way of the picture. Both run before the render and write into `captions.json`.

**Cuts** (`scripts/cuts.py`, ffmpeg only). `ffmpeg select='gt(scene,..)'` on a 320 px copy gives a score per frame. A cut needs a
score of at least 0.30 (`THRESHOLD`: jump cuts on the same person scored 0.34 to 0.42, new scenes 0.5 to 0.95, gestures and
turns under 0.2). Two cuts closer than 220 ms are a flash or a whip pan and are both dropped; of two cuts closer than 350 ms
the stronger stays; a "cut" in the first 350 ms is the video starting. Times are snapped to the frame grid and cached in
`<work>/cuts.json`. Flag `--cuts off` skips it. `python3 scripts/cuts.py video.mp4 [--threshold 0.3]` prints the list.

**Placement** (`scripts/placement.py`, `scripts/vision-subject`). Per page it looks at three frames (15%, 50%, 85% of the page) and at
the first frames of each shot, asks `vision-subject` for faces, hands and the person's share of each horizontal band, and
picks the y inside the style's `position.flex` range with the lowest cost:

```
cost(y) = 100 * conflict + 0.25 * busy + 0.01 * |y - ref|
conflict = mean over samples of 3 * (share of the caption box covered by a face box) + 2 * (same for hand boxes)
           face boxes grow 2.5% / 3.5% (x / y) of the frame, hand boxes 3% / 4% (the product in the hand)
busy     = share of the box's rows the person fills (the emptier band reads better)
ref      = the previous page's y inside a shot, the style's y at a cut
```

The caption box is approximated from the style (size, line count, character count, container padding; `stack` and `sticker` have
their own rules). Stability: a page keeps the previous page's y while it is still clear (under 1% of its box covered), so
captions move only when the subject moves under them; at a cut the position is decided again from the preset. `y` is
rounded to half a percent. Flag `--placement off` skips it. Without macOS, Xcode command line tools or a readable picture
(a song on a black canvas, music styles) every page keeps the style's y and `notes` says so. Results are cached next to the
transcript, in `~/.cache/subtle/<sha256>/subject.v1.json` (`SUBTLE_CACHE` moves it).

### vision-subject CLI (`scripts/vision-subject/`)

```
scripts/vision-subject/build.sh                                 # swiftc → scripts/vision-subject/.build/vision-subject
vision-subject sample <video> --times 0.5,1.2,3 [--bands 24]    # or --times-file <file>; JSON on stdout
```

```json
{ "bands": 24, "frames": [ { "t": 0.5, "faces": [[0.25, 0.26, 0.54, 0.30]], "hands": [[0.82, 0.67, 0.17, 0.25]], "person": [0.0, 0.1, "…24 values"] } ] }
```

Boxes are `[x, y, w, h]` as fractions of the upright frame, origin top left. `faces` come from `VNDetectFaceRectanglesRequest`,
`hands` from `VNDetectHumanHandPoseRequest` (the bounds of the confident joints, up to four hands), `person` from
`VNGeneratePersonSegmentationRequest` (balanced): per band, the share of the width the person covers. macOS 13+, Apple
frameworks only.

## Behind the speaker, per shot (`scripts/shots.py`)

A close-up fills the frame, so a word behind the speaker would be hidden; a wide shot leaves room. The decision is per shot (the spans between
`cuts`), not for the video. `shots.py` (macOS, vision-subject, the same cached samples as `placement.py`) writes two keys into `captions.json`:

```json
"shots":   [ {"startMs": 0, "endMs": 23700, "person": 1.0, "bands": [0, 0.01, 0.22, ...24], "face": [0.35, 0.18, 0.31, 0.17], "behind": true, "y": 16.0, "cover": 0.3} ],
"subject": [ {"ms": 0, "bands": [...24], "face": [x, y, w, h]}, ... ]
```

`bands` is the share of each horizontal band the person covers. A shot is `behind: true` when a window the height of the style's word (`behind.bandHeight`,
fraction of the frame) can sit where the person covers `behind.target` (default 0.3) of it, covers at most 45% on average and 55% in any row. Otherwise
the shot's giant words get `front: true` and `close: true` (`emphasis.py` repeats this whenever it rebuilds `big`). `subject` is the same data every 400 ms: a style places
each word where the person is while it is up (`subjectIn`, `behindY`, `shoulderY`, `placeX` in `template/src/engine/shots.ts` and `styles/behind-kit.ts`).
Styles read `BigProps.layer` (`all` means no cut-out: draw in front) and `behind.skipFront` (a word that cannot go behind is not drawn; it stays in the small line).
Extra `behind` keys: `bandHeight`, `target`, `overlap` (share of the word the head covers), `kinds` (`number`, `name`, `word`), `numbersBehind`, `minWords`; `maxBigWords` may be 3.
A front style that places words around the face (`split`) sets top-level `"subject": true` to get the same data.

New styles: `cover`, `outline`, `poster`, `rise`, `numeral` (behind); `magazine`, `flip`, `cinema` (recipe), `split` (front). `template/stills.mjs` renders many stills with one bundle and
`tests/styles_sheet.py` builds the contact sheet (three layers and the person cut-out stacked like `composite.sh`).
