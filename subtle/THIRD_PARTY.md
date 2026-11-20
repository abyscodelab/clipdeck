# Third-party software, models and fonts

Subtle's own code is MIT (see `LICENSE`). It calls or bundles the items below. Nothing here needs an API key.

## Bundled in this repository

| Item | Licence | Where |
|---|---|---|
| Inter (Regular, Medium, SemiBold, Bold) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-Inter.txt` |
| Poppins (Medium, SemiBold, SemiBold Italic, Bold, ExtraBold, Black) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-Poppins.txt` |
| Montserrat (Medium, Bold, ExtraBold, Black) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-Montserrat.txt` |
| Pinyon Script | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-PinyonScript.txt` |
| Instrument Serif (Regular, Italic) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-InstrumentSerif.txt` |
| Playfair Display (Medium Italic, Black Italic) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-PlayfairDisplay.txt` |
| Caveat (SemiBold) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-Caveat.txt` |
| Courier Prime (Regular, Bold) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-CourierPrime.txt` |
| Anton | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-Anton.txt` |
| Bebas Neue | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-BebasNeue.txt` |
| Archivo Black | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-ArchivoBlack.txt` |
| Abril Fatface | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-AbrilFatface.txt` |
| Libre Baskerville (variable weight) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-LibreBaskerville.txt` |
| Corben (Bold) | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-Corben.txt` |
| Gloria Hallelujah | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-GloriaHallelujah.txt` |
| Reenie Beanie | SIL Open Font License 1.1 | `fonts/`, `fonts/OFL-ReenieBeanie.txt` |

The Montserrat and Inter files are static weights cut from the upstream variable fonts with fontTools
(`fonttools varLib.instancer`), with the family name set to match the weight. All other font files are unmodified
copies from https://github.com/google/fonts.

## Installed or called at run time (not bundled)

| Item | Licence | How Subtle uses it |
|---|---|---|
| Remotion (`remotion`, `@remotion/*`) | Remotion License: free for individuals and for companies of up to 3 people; larger companies need a Company License. Text: https://github.com/remotion-dev/remotion/blob/main/LICENSE.md, terms: https://www.remotion.dev/docs/license | `npm ci` in `template/` on first render. Renders the caption layer. **If your company has more than 3 people, check the Remotion licence before using Subtle.** |
| React, React DOM | MIT | installed with Remotion |
| mlx-whisper (ml-explore/mlx-examples) | MIT | transcription, run through `uv` or `pip install mlx-whisper` |
| Whisper large-v3-turbo weights (`mlx-community/whisper-large-v3-turbo`) | MIT (OpenAI Whisper) | downloaded from Hugging Face on first transcription (about 1.6 GB) |
| ffmpeg / ffprobe | LGPL or GPL depending on the build | must already be installed; used for audio extraction, compositing and frame grabs |
| Apple Vision framework | part of macOS | person segmentation for behind mode (`scripts/vision-matte`) and face/hand detection for placement (`scripts/vision-subject`) |
| NumPy (BSD-3-Clause), Pillow (MIT-CMU) | as stated | `scripts/verify.py` (both) and `scripts/beats.py` (NumPy) |

## Optional, never bundled and never called by default

| Item | Licence | Note |
|---|---|---|
| WhisperX | BSD-2-Clause | forced alignment for tighter word edges. Not wired in yet; if you run it yourself, write its word times into `words.json` (format in `docs/ARCHITECTURE.md`) and pass `--words`. |
| RobustVideoMatting | GPL-3.0 | an alternative matte for difficult hair. Subtle does not include or link it. If you install and run it yourself, pass its alpha video in place of `matte.mp4` (white = person). Mind the GPL if you redistribute it. |

Not used on purpose: BRIA RMBG 1.4 / 2.0 (non-commercial licence).

## Showcase site demo clip (not in this repository)

The showcase site at https://subtle.refs.video plays a 52-second clip of a public podcast interview (Sam Altman on
David Senra's podcast, https://www.youtube.com/watch?v=kG8AoExkX40) to demo captions only. The clip, its stills and
transcript belong to their owners, are credited on the page, are gitignored here and are not part of Subtle's MIT
licence. Not affiliated with or endorsed by Sam Altman, OpenAI or the show.

## Demo images

The stills in `docs/stills/` (and the contact sheets built from them) are frames of the same third-party clip: Sam Altman
on David Senra's podcast (https://www.youtube.com/watch?v=kG8AoExkX40), with Subtle's captions drawn on top. They are
used only to show what the captions look like. The footage belongs to its owners, is not covered by Subtle's MIT licence,
and is not affiliated with or endorsed by Sam Altman, OpenAI or the show.
