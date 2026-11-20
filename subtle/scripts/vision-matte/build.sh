#!/bin/sh
# Build vision-matte into ./.build/vision-matte (macOS 13+, Xcode command line tools).
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
if ! command -v swiftc >/dev/null 2>&1; then
  echo "build.sh: swiftc not found. Install the Xcode command line tools: xcode-select --install" >&2
  exit 1
fi
mkdir -p "$HERE/.build"
swiftc -O -swift-version 5 -target "$(uname -m)-apple-macosx13.0" \
  "$HERE/main.swift" -o "$HERE/.build/vision-matte"
echo "built $HERE/.build/vision-matte"
