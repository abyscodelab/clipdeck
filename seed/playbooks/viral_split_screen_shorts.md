# Playbook: Viral Split-Screen Gaming Shorts (Facecam Top & Gameplay Bottom)

This playbook establishes the architectural guidelines and production specifications for generating viral 9:16 vertical gaming Shorts (TikTok, YouTube Shorts, Instagram Reels), reverse-engineered directly from top-performing live stream highlight clips (e.g., IShowSpeed GTA 6 series).

---

## 1. Frame-by-Frame Reverse-Engineering Analysis

### Reference Clip 1: `https://www.youtube.com/shorts/Me3jQIMeazQ`
- **Canvas Resolution**: `1080 x 1920` (9:16 Vertical aspect ratio).
- **Spatial Allocation**:
  - **Top Zone (Facecam)**: Exactly 50% (`1080 x 960px`). Tight crop on streamer's head and torso, framed slightly above eye level. Captures intense facial micro-expressions and frantic head movements.
  - **Bottom Zone (Gameplay)**: Exactly 50% (`1080 x 960px`). Center-cropped GTA 6 vehicle driving action with car centered in the lower-third.
  - **Middle Seam**: Positioned at `y = 960px`. Features a thin divider line that separates the two motion fields.
- **Captions & Hook Typography**:
  - **Single-Word / Kinetic Burst**: Subtitles pulse word-by-word at the seam (`y: 890 - 1030px`).
  - **Font**: Ultra-bold condensed sans-serif (`Impact` / `Arial Black`).
  - **Styling**: Solid white `#FFFFFF` with thick 4px black drop shadow/stroke (`#000000`), all uppercase.
  - **Z-Index & Occlusion**: Captions sit directly across the seam, preventing occlusion of both the streamer's mouth/chin and the game's dashboard.

---

### Reference Clip 2: `https://www.youtube.com/shorts/Lx4rCak99Qc`
- **Canvas Resolution**: `1080 x 1920` (9:16 Vertical aspect ratio).
- **Spatial Allocation**:
  - **Top Zone (Facecam)**: ~42% to 45% (`1080 x 860px` to `1080 x 900px`). Streamer reaction cam cropped from bottom-left corner of the broadcast stream, scaled to fill full width.
  - **Bottom Zone (Gameplay)**: ~55% to 58% (`1080 x 1020px` to `1080 x 1060px`). GTA 6 chase scene framed to show weapon reticle and fleeing police.
  - **Center Dividing Banner**: High-impact 2-line hook card pinned over the seam.
- **Captions & Hook Typography**:
  - **Line 1 (Hook Context)**: `"ISHOWSPEED COMMITS"` — Pure white `#FFFFFF`, 54pt, 4px black border.
  - **Line 2 (Action / High-Stakes)**: `"HIS FIRST CRIME IN GTA 6"` — Neon Magenta / Hot Pink (`#FF007F`), 48pt, 4px black border.
  - **Backing Plate**: Dark translucent rounded pill (`RGBA(0, 0, 0, 0.75)` / `fill=(0,0,0,195)`) extending horizontally from `x: 60px` to `x: 1020px`, providing high contrast against turbulent gameplay motion.

---

### Reference Clip 3: `https://www.youtube.com/shorts/hb9xdM0kcnA`
- **Canvas Resolution**: `720 x 1280` (scaled to 9:16).
- **Spatial Allocation**:
  - **Top Zone**: Narrative card and story context banner (`y: 0 - 240px`).
  - **Center Zone**: Main mission gameplay gameplay frame (`y: 240 - 1040px`).
  - **Floating PiP (Streamer)**: Picture-in-picture overlay at bottom right.
  - **Bottom Subtitle Line**: Single line dynamic transcription (`y: 1100 - 1200px`).
- **Core Lesson**: Pure gameplay without strong facecam presence suffers lower engagement on TikTok/Shorts compared to the stacked 50/50 split formula in References 1 & 2. The stacked split is the mandatory standard for gaming streamers.

---

## 2. Standard Layout Blueprint (1080 x 1920)

```
+-------------------------------------------------------------+ (0, 0)
|                                                             |
|                       TOP ZONE (47%)                        |
|                     STREAMER FACECAM                        |
|                                                             |
|   • Resolution: 1080 x 900px                                |
|   • Source: Crop from broadcast webcam box                  |
|     (e.g., Bottom-Left: x:0.0, y:0.52, w:0.35, h:0.48)      |
|   • Scaled with aspect-ratio preserving crop                |
|                                                             |
+=============================================================+ (0, 875)
|   +-----------------------------------------------------+   |
|   |  LINE 1: HOOK HEADLINE (WHITE #FFFFFF + 4px STROKE) |   | (0, 900)
|   |  LINE 2: ACTION KEYWORD (NEON YELLOW #F5FF1E)       |   |
|   +-----------------------------------------------------+   |
+=============================================================+ (0, 1005)
|                                                             |
|                      BOTTOM ZONE (53%)                      |
|                      GAMEPLAY ACTION                        |
|                                                             |
|   • Resolution: 1080 x 1020px                               |
|   • Source: Crop center 75% width of 16:9 gameplay stream   |
|     (x: 0.25, y: 0.0, w: 0.75, h: 1.0)                      |
|   • Scaled and filled to 1080 x 1020                        |
|                                                             |
+-------------------------------------------------------------+ (0, 1920)
```

---

## 3. Visual & Graphic Specifications

| Element | Specification | Values / Parameters |
| :--- | :--- | :--- |
| **Canvas Dimensions** | 9:16 Vertical HD | `1080 x 1920 px` at 30 or 60 FPS |
| **Top Zone (Facecam)** | Height & Position | `1080 x 900 px` (`y: 0` to `y: 900`) |
| **Bottom Zone (Gameplay)** | Height & Position | `1080 x 1020 px` (`y: 900` to `y: 1920`) |
| **Divider Seam** | Horizontal line | `y = 900 px`, 2-4px height, `#FFFFFF` at 30% opacity |
| **Hook Pill Backing** | Translucent rounded box | Coordinates: `(60, 872)` to `(1020, 1004)`, corner radius: 16px, background: `RGBA(0, 0, 0, 195)` |
| **Typography - Primary Font** | Heavy Condensed Sans | `Impact` or `Arial Black` |
| **Line 1 (Hook Title)** | Color & Stroke | Text: `#FFFFFF` (Solid White), Stroke: 4px solid `#000000`, Size: 52-56pt, ALL CAPS |
| **Line 2 (Action / Punchline)**| Color & Stroke | Text: `#F5FF1E` (Neon Lime) or `#FF007F` (Neon Magenta), Stroke: 4px solid `#000000`, Size: 46-50pt, ALL CAPS |

---

## 4. Audio, Pacing & Hook Rules

1. **The 1.5-Second Vocal Hook Rule**:
   - The first 1.5 seconds must feature an immediate audio spike: a streamer scream, gasp, exclamation (`"NO WAY"`, `"LOOK AT THIS"`), or gunshot.
   - Never start a clip with silence, inventory management, or loading screens.

2. **Dead-Air Suppression**:
   - Any pause in speech or game action exceeding 0.5 seconds must be automatically trimmed.

3. **Loudness Normalization**:
   - Audio must be processed through an integrated loudness filter normalized to `-14.0 LUFS` with a `-1.5 dBTP` true peak limit, preventing ear-destroying distortion while ensuring maximum punchiness on phone speakers.

---

## 5. Automated Pipeline Integration

The clipping daemon (`clipdeck/worker/supabase_clipper.py`) implements this playbook deterministically:
1. Slices raw broadcast segments from live HLS/YouTube streams using `yt-dlp` and `ffmpeg`.
2. Inspects streamer configuration or `layout_presets` table in Supabase for facecam bounding box coordinates.
3. Generates high-res RGBA alpha overlay PNG with Pillow (`PIL.ImageDraw`).
4. Executes FFmpeg `filter_complex` with dual-crop (`[cam_in]`, `[game_in]`), vertical stack (`vstack`), and alpha composite (`overlay`).
5. Uploads rendered `.mp4` and `.jpg` thumbnail to Supabase Storage, updating `moments` and `clips` tables.
