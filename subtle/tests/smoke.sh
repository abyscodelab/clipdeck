#!/usr/bin/env bash
# Smoke test without any video: group the sample words and render one transparent still per style in styles/.
# Needs python3 and node. Run from anywhere: bash tests/smoke.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 "$ROOT/tests/test_group.py"
python3 "$ROOT/tests/test_emphasis.py"
python3 "$ROOT/tests/test_music.py"
python3 "$ROOT/tests/test_placement.py"
python3 "$ROOT/tests/test_legibility.py"
count=0
for json in "$ROOT"/styles/*.json; do
  style="$(basename "$json" .json)"
  python3 "$ROOT/scripts/group.py" "$ROOT/tests/sample-words.json" --style "$json" --out "$TMP/$style.json" --emphasis "gold,three,won" >/dev/null
  node "$ROOT/template/render.mjs" --captions "$TMP/$style.json" --style "$json" --layer all --still 54 --png "$TMP/$style.png" >/dev/null
  [ -s "$TMP/$style.png" ] || { echo "FAILED: no still for $style"; exit 1; }
  # the mask layer (backdrop blur) must render too; styles without a blur container give an all-black mask
  node "$ROOT/template/render.mjs" --captions "$TMP/$style.json" --style "$json" --layer mask --still 54 --png "$TMP/$style.mask.png" >/dev/null
  [ -s "$TMP/$style.mask.png" ] || { echo "FAILED: no mask still for $style"; exit 1; }
  echo "ok: $style renders (all + mask)"
  count=$((count + 1))
done
[ "$count" -gt 0 ] || { echo "FAILED: no styles found"; exit 1; }
echo "smoke test passed ($count styles)"
