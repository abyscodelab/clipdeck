#!/usr/bin/env bash
# Render every style on one clip and build the contact sheet.
#   bash tests/render_all.sh [clip] [outdir] [extra subtle.py flags...]
# Default clip: tests/clips/room-speaker.mp4 (a woman in a warm, busy room; tests/clips/ is git-ignored). Output: <outdir>/<style>.mp4 + .captions.json and <outdir>/sheet.jpg.
# Words come from the clip's real transcript (whisper, cached); WORDS=path uses a words.json instead (e.g. tests/sample-words.json).
# Test media and renders stay out of git (tests/clips/ and tests/out/ are ignored).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLIP="${1:-$ROOT/tests/clips/room-speaker.mp4}"
OUT="${2:-$ROOT/tests/out/all}"
shift 2 2>/dev/null || true
WORDS="${WORDS-}"
mkdir -p "$OUT"
for json in "$ROOT"/styles/*.json; do
  s="$(basename "$json" .json)"
  python3 "$ROOT/scripts/subtle.py" "$CLIP" --style "$s" --out "$OUT/$s.mp4" --work "$OUT/.work/$s" ${WORDS:+--words "$WORDS"} "$@" >"$OUT/$s.log" 2>&1 || { echo "FAILED: $s (see $OUT/$s.log)"; continue; }
  cp "$OUT/.work/$s/captions.json" "$OUT/$s.captions.json"
  echo "ok: $s"
done
python3 "$ROOT/tests/contact_sheet.py" "$OUT" --out "$OUT/sheet.jpg"
