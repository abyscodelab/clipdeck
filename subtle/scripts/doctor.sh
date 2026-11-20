#!/usr/bin/env bash
# Checks everything Subtle needs and prints a one-line install for whatever is missing.
# Exit code 0: captions can be made. Exit code 1: something required is missing.
# Pass --from-timings to check a workflow that starts from --words or --captions.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
missing=0
ok()   { printf "  ok       %-13s %s\n" "$1" "$2"; }
bad()  { printf "  MISSING  %-13s %s\n" "$1" "$2"; missing=1; }
note() { printf "  optional %-13s %s\n" "$1" "$2"; }

echo "Subtle doctor"
os="$(uname -s)"; arch="$(uname -m)"

if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  ok ffmpeg "$(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f1-3)"
else
  bad ffmpeg "install: brew install ffmpeg   (Linux: sudo apt install ffmpeg)"
fi

if command -v python3 >/dev/null 2>&1; then
  ok python3 "$(python3 --version 2>&1)"
else
  bad python3 "install: brew install python"
fi

if command -v node >/dev/null 2>&1; then
  major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  if [ "$major" -ge 18 ]; then ok node "$(node --version)"; else bad node "Node 18 or newer is needed (found $(node --version)): brew install node"; fi
else
  bad node "install: brew install node"
fi

# Verification and beat detection use inline dependency metadata with uv.
if command -v uv >/dev/null 2>&1; then
  ok uv "$(uv --version 2>/dev/null)"
elif python3 -c "import numpy, PIL" >/dev/null 2>&1; then
  ok numpy+pillow "importable from python3"
else
  bad numpy+pillow "install uv or install numpy and pillow in your Python environment"
fi

if [ "${1:-}" = "--from-timings" ]; then
  note mlx-whisper "skipped for supplied word timings"
elif [ "$os" != "Darwin" ] || [ "$arch" != "arm64" ]; then
  bad mlx-whisper "local transcription needs Apple Silicon macOS. Supply --words or --captions and run doctor with --from-timings."
elif command -v uv >/dev/null 2>&1; then
  ok mlx-whisper "will run through uv; the first run downloads the model"
elif python3 -c "import mlx_whisper" >/dev/null 2>&1; then
  ok mlx-whisper "importable from python3"
else
  bad mlx-whisper "install uv or install mlx-whisper in your Python environment"
fi

# Renderer packages (installed on first render).
if [ -d "$ROOT/template/node_modules/remotion" ]; then
  ok remotion "installed in template/node_modules"
else
  note remotion "not installed yet: the first render runs 'npm ci' in template/ (about a minute)"
fi

# Behind mode.
if [ "$os" = "Darwin" ]; then
  if command -v swiftc >/dev/null 2>&1; then
    if [ -x "$HERE/vision-matte/.build/vision-matte" ]; then
      ok behind-mode "vision-matte is built"
    else
      note behind-mode "swift found; vision-matte builds on first use (scripts/vision-matte/build.sh)"
    fi
  else
    note behind-mode "needs Swift: xcode-select --install   (every other style works without it)"
  fi
else
  note behind-mode "needs macOS (Apple Vision). Every other style works here."
fi

if [ "$missing" -eq 0 ]; then echo "Ready."; else echo "Fix the MISSING lines above, then run this again."; fi
exit "$missing"
