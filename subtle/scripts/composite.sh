#!/usr/bin/env bash
# Put the rendered caption layers on the video with ffmpeg.
#
#   composite.sh --video in.mp4 --overlay overlay.mov --out out.mp4
#   composite.sh --video in.mp4 --behind overlay-behind.mov --matte matte.mp4 --front overlay-front.mov --out out.mp4
#   composite.sh --video in.mp4 --overlay overlay.mov --blur-mask mask.mov --blur 20 --out out.mp4   (frosted glass)
#
# Behind mode stacks: video, big words, the person (video × matte), then the small caption line.
# Glass styles: --blur-mask is the style's containers as white on black; the video is blurred under them (--blur is
# the radius in px at 1080p) before the caption layer goes on top.
# The source audio is kept. Output is H.264 (yuv420p) at the source frame rate.
set -euo pipefail
video=""; overlay=""; behind=""; front=""; matte=""; out=""; crf=18; preset="medium"; blurmask=""; blur=20
while [ $# -gt 0 ]; do
  case "$1" in
    --video) video="$2"; shift 2;;
    --overlay) overlay="$2"; shift 2;;
    --behind) behind="$2"; shift 2;;
    --front) front="$2"; shift 2;;
    --matte) matte="$2"; shift 2;;
    --blur-mask) blurmask="$2"; shift 2;;
    --blur) blur="$2"; shift 2;;
    --out) out="$2"; shift 2;;
    --crf) crf="$2"; shift 2;;
    --preset) preset="$2"; shift 2;;
    *) echo "composite.sh: unknown option $1" >&2; exit 2;;
  esac
done
[ -n "$video" ] && [ -n "$out" ] || { echo "composite.sh: --video and --out are required" >&2; exit 2; }
enc=(-c:v libx264 -crf "$crf" -preset "$preset" -pix_fmt yuv420p -movflags +faststart)
aud=(-map "0:a?" -c:a aac -b:a 192k)

if [ -n "$behind" ]; then
  [ -n "$matte" ] || { echo "composite.sh: --behind needs --matte" >&2; exit 2; }
  if [ -n "$front" ]; then
    ffmpeg -v error -y -i "$video" -i "$behind" -i "$matte" -i "$front" -filter_complex \
      "[0:v]split=2[bg][src];[2:v]format=gray[m];[src][m]alphamerge[fg];[bg][1:v]overlay=format=auto[b1];[b1][fg]overlay=format=auto[b2];[b2][3:v]overlay=format=auto,format=yuv420p[v]" \
      -map "[v]" "${aud[@]}" "${enc[@]}" -shortest "$out"
  else
    ffmpeg -v error -y -i "$video" -i "$behind" -i "$matte" -filter_complex \
      "[0:v]split=2[bg][src];[2:v]format=gray[m];[src][m]alphamerge[fg];[bg][1:v]overlay=format=auto[b1];[b1][fg]overlay=format=auto,format=yuv420p[v]" \
      -map "[v]" "${aud[@]}" "${enc[@]}" -shortest "$out"
  fi
else
  [ -n "$overlay" ] || { echo "composite.sh: give --overlay, or --behind with --matte" >&2; exit 2; }
  if [ -n "$blurmask" ]; then
    # blur radius scales with the frame: the style gives it in px at 1080p (the shorter side)
    short=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$video" | awk -Fx '{print ($1<$2)?$1:$2}')
    sigma=$(awk -v b="$blur" -v s="$short" 'BEGIN{printf "%.2f", b*s/1080*0.6}')
    ffmpeg -v error -y -i "$video" -i "$blurmask" -i "$overlay" -filter_complex \
      "[0:v]split=2[bg][pre];[pre]gblur=sigma=${sigma}[bl];[1:v]format=gray[m];[bl][m]alphamerge[blm];[bg][blm]overlay=format=auto[b0];[b0][2:v]overlay=format=auto,format=yuv420p[v]" \
      -map "[v]" "${aud[@]}" "${enc[@]}" -shortest "$out"
  else
    ffmpeg -v error -y -i "$video" -i "$overlay" -filter_complex "[0:v][1:v]overlay=format=auto,format=yuv420p[v]" \
      -map "[v]" "${aud[@]}" "${enc[@]}" -shortest "$out"
  fi
fi
echo "{\"out\": \"$out\"}"
