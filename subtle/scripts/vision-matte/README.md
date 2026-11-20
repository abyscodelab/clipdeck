# vision-matte

Small Swift CLI that cuts the person out of a video using Apple Vision, for the Subtle "words behind the speaker" caption mode. macOS 13+, Apple frameworks only (AVFoundation, Vision, CoreImage, Accelerate). `matte` also needs `ffmpeg` on PATH.

## Build

    ./build.sh        # writes .build/vision-matte (needs swiftc / Xcode command line tools)

## Use

    vision-matte check <video> [--samples 12]
    vision-matte matte <video> --out <matte.mp4> [--quality accurate|balanced|fast] [--no-ema]

`check` prints one JSON object (samples, personFrames, meanArea, meanWidth, motion, softFraction, recommend, reason). It runs the `balanced` model on N evenly spaced frames. `meanWidth` is averaged over frames where the person covers at least 4% of the frame. It skips when: a person is in under 60% of samples, `motion` is above 0.20, `meanWidth` is above 0.70, or `softFraction` is above 0.08. The 0.20 motion limit is a guess: the test clips sat at 0.014 to 0.028.

`matte` decodes every frame (rotated phone videos are turned upright first), segments it, cleans the mask, and writes a grayscale H.264 video (white = person) with the same frame count, size and fps as the source. Odd sizes are padded by one pixel for the encoder. Progress goes to stderr; the final JSON line (frames, msPerFrame, quality, width, height, fps, emaSkippedFrames) goes to stdout.

## Flicker fixes (applied in this order)

1. Blur (3x3 tent, about 1 px), then a smoothstep from 0.35 to 0.65. Edges stay soft; the mask is never binarised.
2. Temporal EMA: `m = 0.6*m_t + 0.4*m_prev`. Skipped on a frame when the mean abs difference to the previous mask is above 0.012 (fast motion would ghost). `--no-ema` turns it off.
3. Erode 1 px (3x3 min) so no background halo is left.
4. On a 4x coarse grid: remove blobs under 2% of the frame and fill holes under 1% that do not touch the border. Large gaps (between arm and body, say) can be filled if under 1%, which is a known trade-off.

## Speed

Apple Silicon, 720x1280: about 43 ms/frame accurate, 12 ms balanced, 6 ms fast (whole pipeline including decode and encode).
