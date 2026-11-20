#!/usr/bin/env python3
"""Packs per-style captions.json files (made by the real pipeline, see site/README.md) into public/demo/captions.json.
usage: pack-demo.py <cap-dir>   (cap-dir holds <style>.json for every style on the demo clip)"""
import json, sys
from pathlib import Path
cap_dir = Path(sys.argv[1])
out = {"styles": {}}
for f in sorted(cap_dir.glob("*.json")):
    d = json.loads(f.read_text())
    out.setdefault("video", d["video"])
    out["styles"][f.stem] = {k: v for k, v in d.items() if k not in ("video", "version")}
dest = Path(__file__).resolve().parents[1] / "public" / "demo" / "captions.json"
dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
print(dest, dest.stat().st_size, len(out["styles"]))
