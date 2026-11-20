---
name: subtle
description: Transcribe and render animated captions or export SRT locally from video or audio. Use for word-by-word subtitles, highlighted keywords or prices, Hinglish captions, text behind a speaker, or beat-synced lyric videos. Includes 39 styles, editable word timings, and visual checks for the finished render.
---

# Subtle: beautiful captions for any video

You add animated captions to a video with the tools in this folder. Everything runs on the user's machine. Nothing is
uploaded and no key is needed. Run commands from this skill's folder (the folder holding this file).

## Inputs

| Input | Default | Notes |
|---|---|---|
| video path | required | any file ffmpeg reads |
| style | `glide` | any name from the Styles tables below, `name:variant` for a colourway (`ticket:yellow`, `singalong:lit`, `chalkline:marker`), or a path to your own style JSON |
| lyrics | none | music styles: a text file with the right words, one lyric line per line. Its words replace the transcript's, on the sung timings |
| canvas | `9:16` | for an input with no picture (a song): the frame to draw on: `9:16`, `16:9`, `1:1` or `4:5` |
| emphasis | `auto` | `auto`: highlight numbers, prices, names and contrast words. `numbers`: numbers only. `off`: no highlights |
| emphasis-words | none | words to highlight for sure: `--emphasis-words 'gold, $5,000'` |
| numbers | `auto` | spoken numbers become one token (`$5,000`, `40%`, `₹5 lakh`). `western` or `indian` sets the digit grouping; `off` keeps the transcript as heard |
| behind | `auto` | `auto`: with `--style keyword`, put the giant word behind the speaker if the subject check passes. `on`: force it. `off`: draw it in front |
| placement | `auto` | `auto`: each page moves off the face and the hands (macOS, Apple Vision), inside the style's `position.flex` range, and only when it has to. `off`: every page keeps the style's `y` |
| cuts | `auto` | `auto`: find hard cuts with ffmpeg; no page straddles one. `off`: ignore cuts |
| language | detect | `--lang en`, `--lang hi`; `--hinglish` writes Hindi in Latin letters |
| vocab | none | names and brand words Whisper should spell right: `--vocab "Refs, Claude"` |
| legibility | `auto` | `auto`: measure what is behind every page and add a soft halo, scrim or outline where the type would not read; clean dark footage is left untouched. `off`: draw the preset as it is |
| palette | `auto` | `auto`: styles with an accent colour (`glide`, `keyword`, `shine`, `accent`, `hype`, `highlighter`, `haiku`, `karaoke`) take it from the footage: a colour that suits the scene and reads on it. `off`: the preset's colours |
| aspect | `source` | `9:16`, `1:1`, `4:5`, `16:9` centre-crop the video first |

If the user did not name a style, use `glide` and say which other styles exist. Ask nothing else up front.

## Steps

1. **Check dependencies.** Run `bash scripts/doctor.sh`, adding `--from-timings` when using `--words` or `--captions`.
   Resolve any dependencies required for the requested workflow before rendering.
2. **Transcribe.** `python3 scripts/subtle.py "<video>" --stop-after transcribe [--lang ..] [--vocab ".."] [--hinglish]`
   It prints the transcript. Read it.
   - Fix wrong names with `--replace heard=Shown` (repeatable) or better `--vocab`.
   - For Hindi or Hinglish, check names and transliteration against the audio. Flag uncertain words.
3. **Group.** `python3 scripts/subtle.py "<video>" --style <style> --stop-after group`.
   Keep the transcription flags from step 2. For a song, pass the chosen music style and any supplied
   `--lyrics <file>` and `--canvas <ratio>`. For video, add the requested `--aspect` if needed.
   This writes `<name>.captions.json` and prints the words the rules highlighted. Spoken numbers are already single
   tokens here: "five thousand dollars" is `$5,000`, "forty percent" is `40%`, "one lakh rupees" is `₹1 lakh`.
4. **Pick the highlights. This is your job, and it is what makes the captions good.**
   `python3 scripts/emphasis.py "<name>.captions.json" --style <style> --show` prints every page with the highlighted
   words in [brackets] and the reason for each. The rules find numbers and names; they cannot tell what matters.
   Read the pages and decide, in this order of priority:
   1. numbers, prices, percentages, dates and counts (`$5,000`, `3x`, `1991`, `40%`);
   2. names, brands and places;
   3. the punchline or contrast word (`never`, `free`, `broke`);
   4. the topic noun, the first time it appears.

   At most 1 highlight per page, 2 on pages of 5 words or more. Never filler words (`the`, `really`, `that's`).
   Remove the rule guesses that are not the point of their line. Then save your picks, each with a one-line reason:
   ```
   python3 scripts/emphasis.py "<name>.captions.json" --style <style> \
     --pick '21:25,000=the size of the hoard' --pick '38:broke=the turn of the story' --drop '34:smuggling'
   ```
   `PAGE:WORD` uses the page number and the word as `--show` prints them. Use single quotes, or the shell eats `$5`.
   `--clear` removes every highlight first if you would rather start from nothing.
5. **Render.** `python3 scripts/subtle.py "<video>" --style <style> --captions "<name>.captions.json"`
   Keep the same `--canvas` or `--aspect` as in step 3.
   The transcript is cached, so this does not transcribe again. The first render installs the renderer (about a minute).
   In a hurry, or running with no one to pick: skip steps 3 and 4 and render directly with
   `python3 scripts/subtle.py "<video>" --style <style>`; the rules pick the highlights (`--emphasis auto`).
6. **Verify.** The command prints JSON with `ok`, `warnings` and `preview` (a contact sheet). **Open the preview image
   and look at it** before you say anything. Check: text readable, inside the cyan safe-area box, not over the face,
   and the highlighted words are the ones that matter. Placement moves captions off the face and hands on its own; `notes` says
   how many pages moved and how many cuts it found. A caption still on the face: lower `position.flex` in the style or pass `--placement off`.
   - Warning about the safe area or an overflowing line: lower `--max-words`, or use a style with smaller type.
   - Warning about low contrast: switch to a style with a container: `glass`, `chip` or `block`. The grouping `notes` say how many pages
     needed help and the weakest contrast; `<name>.captions.json` has one `legibility` line per page.
   - `keyword`: numbers are drawn large in front of the speaker, never behind (hidden digits would change them). `numeral` is the exception: it is built for numerals behind the speaker.
   - Behind styles (`keyword`, `cover`, `outline`, `poster`, `rise`, `numeral`) decide **per shot**: `notes` says how many shots leave room. In a close-up the giant word is drawn in front or skipped (the words stay in the small line); in a wide shot it goes behind the head.
   - `keyword`, a big word mostly hidden: it is dropped automatically (see `notes`). To change which words go big,
     edit `big` in `<name>.captions.json`, then re-render with `--captions <name>.captions.json`.
   - Behind effect skipped (see `notes`): tell the user why; the big words were drawn in front of the speaker instead.
   - A music style: read the grouping `notes` for the beat grid ("120 BPM, 129 beats"). "no steady beat found" means the pages
     follow the words; say so. With `--lyrics`, `notes` says how many lyric words were found in the audio: under about
     60% usually means the wrong lyrics file or a transcript in the wrong language.
7. **Hand over.** Give the paths: `<name>.captioned.mp4`, `<name>.srt`, `<name>.captions.json`, `<name>.preview.jpg`,
   and the one-line command to try another style.

## Styles

Caption styles:

| Style | Looks like | Best for |
|---|---|---|
| `glide` | Key words in a large calligraphic script, the small words in bold white sans, on one baseline. | default; editorial talking heads |
| `glass` | One frosted-glass pill per page in soft lowercase; upcoming words are dim and brighten as they are spoken. | calm, premium, any footage |
| `whisper` | Lowercase warm-yellow text; each word is revealed by a soft left-to-right wipe and the page dissolves with a blur. | soft, intimate delivery |
| `terminal` | Green monospace typed character by character with a blinking block cursor. | tech, code, developer content |
| `keyword` | One giant pale-lime keyword behind the speaker, the other words small and stacked beside it. | one person, steady camera, macOS (uses the person matte) |
| `cover` | One giant serif italic word behind the head like a magazine masthead; the rest small and tracked in front. | one person, a wide shot with some headroom (macOS) |
| `outline` | A giant hollow word behind the speaker that draws on, then fills as it is spoken. | one person, a wide shot (macOS) |
| `poster` | Two or three words stacked behind the speaker, each line its own face fitted to the same width (needs headroom: weak on tight shots). | wide shots with plenty of headroom (macOS) |
| `rise` | The giant word climbs out from behind the speaker's shoulders letter by letter. | one person, a wide shot (macOS) |
| `numeral` | Numbers, years and names go giant behind the speaker, digits rolling like an odometer. | talks full of numbers, dates and names (macOS) |
| `magazine` | A tight justified block: big serif-italic keywords, small grotesk capitals for the glue words. | ad supers, launch films, any footage |
| `flip` | Every letter flips in like a split-flap tile, with a motion trail. | hooks, playful edits |
| `cinema` | Tiny wide-tracked serif capitals, slow blur fades, arthouse-trailer subtitles. | trailers, quiet interviews |
| `split` | Words alternate to the two sides of the speaker and step down around the head, never over the face. | one person in a wide shot (macOS) |
| `accent` | Pale-lime sans in very short pages, with the key word in a light serif italic; soft fade with a small drift. | launch films, quiet editorial |
| `chip` | A light rounded chip that hugs the page; words turn from grey to black as they are spoken. | explainers; readable on any footage |
| `title` | A typed title whose letter spacing collapses as the letters arrive, with a small handwritten note under it. | section headers and lists |
| `hype` | A calm medium-weight line in soft white with a gentle shadow; the key word turns warm yellow. Hard cut in, no outline. | authority, education |
| `block` | Every line in its own warm coloured block with depth; lines rise in with motion blur and pile up as a stack. | bold brand colour, promos |
| `impact` | Heavy round caps; every letter bounces in along an arc with overshoot and a little tilt, on a hard offset shadow. | hooks, high energy |
| `bottom` | Big bold caps low in the frame that build word by word with no animation; the key word is yellow. | fast speech, zero delay |
| `stack` | A tilted, overlapping pile of words, each at its own size and angle, key words in yellow; the tilt mirrors on alternate pages. | social cuts, poster feel |
| `serif` | Display serif italic filled with a top-lit silver gradient; quiet and luxurious. | luxury, titles |
| `shine` | Serif italic in one accent colour; a diagonal band of light sweeps across each word, then a soft glow fades. | one accent colour, premium titles |
| `karaoke` | The whole line shows dim; each word turns solid as it is spoken. One weight, no motion. | long lines, product videos |
| `sticker` | Rounded pink bubbles, one per line, each new line offset to the right of the last and stacked like typed messages; the stack tilts a little more on every page. Words are dark until spoken, then white. | chatty, casual, story time |
| `ticket` | A hard-edged label tight around the text, tilted a different angle on every page. The hot word sits alone on a big label, filler phrases on a small one. Hard cuts. Colourway: yellow. Also: `ticket:yellow`. | edits with rhythm: the key word alone and big |
| `highlighter` | Bold caps with one flat box behind the word being spoken, hopping from word to word. A finished word turns lime; the hot word comes alone, large. | follow-the-speech captions, podcasts |
| `haiku` | One small condensed serif word at a time in acid yellow. Hard cuts, no box. A hot word turns italic and a lighter yellow. | cinematic talking heads, slow delivery |
| `duo` | A big condensed caps headline word with a tiny spaced-out lead-in above and a bold italic tail below. The lead-in fades in, the headline cuts in, the tail fades in. | Hinglish and any line with the key word in the middle |
| `editorial` | A bold sans lowercase line with the keyword set about three times larger in a high-contrast italic serif in cinema red, overlapping the sans. Lower-left third. | magazine feel, fashion, opinion |
| `newsroom` | Bold yellow sans, every word on screen at once, the spoken word turns white; soft black outline, lower third. | news explainers, any footage |
| `cards` | White serif on a dark rounded card, the phrase appears at once, key words in red italic. | essays, interviews, serif-card look |
| `punch` | Heavy upper-case sans popping in word by word with overshoot; the spoken word swells and turns lime, thick outline. | short-form creator edits |
| `quiet` | Lowercase medium sans, each line rises gently into place; no box, refined shadow. | premium brand films |

Music / lyric styles (pages start on the beat; use them for songs and for speech set to music):

| Style | Looks like | Best for |
|---|---|---|
| `downbeat` | Bold caps on flat colour fields, one to four words a page. Lines spin or slide in with overshoot on the beat; the field flips colour every few bars. | kinetic lyric videos, hooks set to music |
| `billboard` | A fat lowercase serif, one or two words so big they bleed off the frame. Three flat tones swap between text and background; the pair changes every two beats. | pop songs, poster-style lyric videos |
| `chalkline` | Hand-written lines that write on, left to right, over a dark chalkboard. Lines pile up down the page and indent in steps, then the page clears. The key word is bigger and gets a hand-drawn underline. Variant marker: coloured marker on paper. Also: `chalkline:marker`. | quiet, human songs; acoustic |
| `singalong` | A block of up to four lyric lines; the sung part of each line fills with a soft colour, letter by letter, as it is sung. Variant lit: no fill, words light up over the picture. Also: `singalong:lit`. | karaoke and sing-along videos; `singalong:lit` over footage |

## Editing by hand

`<name>.captions.json` holds every page, word, line break, highlight (`emphasis`) and its `reason` (format:
`docs/ARCHITECTURE.md`). Edit it, run `python3 scripts/emphasis.py <file> --style <style>` once so page holds and giant
words follow your edit, and re-render with `--captions <file>`. A style is one JSON file in `styles/`; copy one, change fonts, colours, size or
timing, and pass its path to `--style`.

## Rules

- Never upload the video or its audio anywhere. Do not call paid caption APIs.
- Do not force the behind effect on fast pans, sports, or a subject that fills the frame: the matte lags and the text
  glitches. Trust the subject check.
- Keep the user's words. Fix spelling; never rewrite what was said.
