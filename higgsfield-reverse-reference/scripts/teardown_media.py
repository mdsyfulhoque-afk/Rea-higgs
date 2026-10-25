#!/usr/bin/env python3
"""Measure a reference image/video locally and write teardown.json.

Stdlib only. Needs ffprobe/ffmpeg on PATH. Every field is tagged with an
evidence grade so downstream prompts can separate facts from guesses.

  teardown_media.py <file> --out <dir> [--frames 8] [--scene 0.30]
  teardown_media.py --compare <reference/teardown.json> <candidate/teardown.json>
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

PALETTE_BITS = 4  # 16 levels per channel
PALETTE_SIZE = 5
SAMPLE_PX = 32  # frames are downscaled to SAMPLE_PX x SAMPLE_PX for palette


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def need(tool: str) -> None:
    if shutil.which(tool) is None:
        sys.exit(f"error: {tool} not found on PATH; teardown degrades to visual inspection only")


def obs(value, grade="observed", **extra):
    return {"value": value, "grade": grade, **extra}


def probe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        sys.exit(f"error: ffprobe failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout)


def ratio(num: int, den: int) -> str:
    g = math.gcd(num, den) or 1
    return f"{num // g}:{den // g}"


def parse_rate(text: str | None) -> float | None:
    if not text or text in ("0/0", "N/A"):
        return None
    try:
        return float(Fraction(text))
    except (ValueError, ZeroDivisionError):
        return None


def palette_of(path: Path, at: float | None) -> list[dict]:
    cmd = ["ffmpeg", "-v", "error"]
    if at is not None:
        cmd += ["-ss", f"{at:.3f}"]
    cmd += ["-i", str(path), "-frames:v", "1", "-vf", f"scale={SAMPLE_PX}:{SAMPLE_PX}:flags=area",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    r = subprocess.run(cmd, capture_output=True)
    raw = r.stdout
    if len(raw) < SAMPLE_PX * SAMPLE_PX * 3:
        return []
    shift = 8 - PALETTE_BITS
    bins: Counter = Counter()
    for i in range(0, SAMPLE_PX * SAMPLE_PX * 3, 3):
        bins[(raw[i] >> shift, raw[i + 1] >> shift, raw[i + 2] >> shift)] += 1
    total = sum(bins.values())
    out = []
    for (r_, g_, b_), n in bins.most_common(PALETTE_SIZE):
        half = (1 << shift) // 2
        rgb = [(c << shift) + half for c in (r_, g_, b_)]
        out.append({"hex": "#%02x%02x%02x" % tuple(rgb), "share": round(n / total, 3)})
    return out


def luma_stats(palette: list[dict]) -> dict:
    if not palette:
        return {}
    lum = 0.0
    for p in palette:
        h = p["hex"].lstrip("#")
        r_, g_, b_ = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        lum += p["share"] * (0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_)
    w = sum(p["share"] for p in palette) or 1
    return {"mean_luma_0_255": round(lum / w, 1)}


def scene_cuts(path: Path, threshold: float) -> list[float]:
    r = run(["ffmpeg", "-v", "info", "-i", str(path), "-vf",
             f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"])
    return [round(float(m), 3) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def extract_frames(path: Path, out: Path, times: list[float]) -> list[str]:
    names = []
    for i, t in enumerate(times):
        name = f"frame_{i:02d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(path),
                        "-frames:v", "1", "-q:v", "3", str(out / name)], capture_output=True)
        if (out / name).exists():
            names.append(name)
    return names


def contact_sheet(out: Path, names: list[str]) -> str | None:
    if len(names) < 2:
        return None
    cols = min(4, len(names))
    rows = math.ceil(len(names) / cols)
    pattern = out / "frame_%02d.jpg"
    sheet = out / "contact_sheet.jpg"
    r = run(["ffmpeg", "-v", "error", "-y", "-i", str(pattern), "-vf",
             f"scale=320:-2,tile={cols}x{rows}", "-frames:v", "1", str(sheet)])
    return sheet.name if r.returncode == 0 and sheet.exists() else None


def teardown(path: Path, out: Path, n_frames: int, scene_thr: float) -> dict:
    need("ffprobe")
    need("ffmpeg")
    out.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    video = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    if video is None:
        sys.exit("error: no video/image stream found")
    audio = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    fmt = info.get("format", {})
    w, h = int(video["width"]), int(video["height"])
    dur = float(fmt.get("duration") or video.get("duration") or 0)
    is_still = dur == 0 or fmt.get("format_name", "").split(",")[0] in {"image2", "png_pipe", "jpeg_pipe", "webp_pipe"}
    fps = parse_rate(video.get("avg_frame_rate"))

    result: dict = {
        "source": path.name,
        "kind": obs("image" if is_still else "video"),
        "resolution": obs(f"{w}x{h}"),
        "aspect_ratio": obs(ratio(w, h), "derived", source="resolution"),
        "video_codec": obs(video.get("codec_name")),
    }
    if not is_still:
        result["duration_s"] = obs(round(dur, 3))
        if fps:
            result["fps"] = obs(round(fps, 3))
        if fmt.get("bit_rate"):
            result["bitrate_bps"] = obs(int(fmt["bit_rate"]))
        result["audio"] = obs([{"codec": a.get("codec_name"), "channels": a.get("channels"),
                                "sample_rate": a.get("sample_rate")} for a in audio]
                              if audio else "none")
        cuts = scene_cuts(path, scene_thr)
        bounds = [0.0] + cuts + [dur]
        shots = [round(b - a, 3) for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
        result["shot_count"] = obs(len(shots), "derived", method=f"ffmpeg scene>{scene_thr}")
        result["shot_lengths_s"] = obs(shots, "derived")
        if shots:
            result["avg_shot_s"] = obs(round(sum(shots) / len(shots), 3), "derived")
        times = sorted({round(min(max(dur * (i + 0.5) / n_frames, 0), max(dur - 0.05, 0)), 3)
                        for i in range(n_frames)} | {round(c + 0.04, 3) for c in cuts[:n_frames]})[: n_frames * 2]
    else:
        times = [0.0]

    names = extract_frames(path, out, times)
    result["frames"] = obs(names)
    sheet = contact_sheet(out, names)
    if sheet:
        result["contact_sheet"] = obs(sheet)
    palettes = [palette_of(path, None if is_still else t) for t in times[:n_frames]]
    merged: Counter = Counter()
    for pal in palettes:
        for p in pal:
            merged[p["hex"]] += p["share"]
    top = merged.most_common(PALETTE_SIZE)
    total = sum(v for _, v in top) or 1
    result["palette"] = obs([{"hex": k, "share": round(v / total, 3)} for k, v in top], "derived",
                            method=f"{PALETTE_BITS}-bit quantization over sampled frames")
    flat = [p for pal in palettes for p in pal]
    result["luma"] = obs(luma_stats(flat), "derived")
    result["not_recoverable"] = [
        "generator model identity", "prompts", "seed", "lens/focal length (inferable only, grade as inferred)",
        "original color pipeline",
    ]
    (out / "teardown.json").write_text(json.dumps(result, indent=2))
    return result


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def palette_distance(a: list[dict], b: list[dict]) -> float:
    """Share-weighted mean nearest-color distance, 0 (same) to 100 (opposite)."""
    if not a or not b:
        return 100.0
    total = 0.0
    for p in a:
        ra = hex_rgb(p["hex"])
        d = min(math.dist(ra, hex_rgb(q["hex"])) for q in b)
        total += p["share"] * d
    return round(100 * total / (255 * math.sqrt(3)) / (sum(p["share"] for p in a) or 1), 1)


def get(d: dict, key: str):
    v = d.get(key)
    return v["value"] if isinstance(v, dict) and "value" in v else None


def compare(ref_p: Path, cand_p: Path) -> dict:
    return compare_data(json.loads(ref_p.read_text()), json.loads(cand_p.read_text()))


def compare_data(ref: dict, cand: dict, only: set[str] | None = None) -> dict:
    checks = []

    def add(name, ok, ref_v, cand_v):
        checks.append({"constraint": name, "pass": bool(ok), "reference": ref_v, "candidate": cand_v})

    add("aspect_ratio", get(ref, "aspect_ratio") == get(cand, "aspect_ratio"),
        get(ref, "aspect_ratio"), get(cand, "aspect_ratio"))
    rd, cd = get(ref, "duration_s"), get(cand, "duration_s")
    if rd and cd:
        add("duration_within_15pct", abs(cd - rd) / rd <= 0.15, rd, cd)
    rs, cs = get(ref, "shot_count"), get(cand, "shot_count")
    if rs and cs:
        add("shot_count_within_1", abs(cs - rs) <= 1, rs, cs)
    dist = palette_distance(get(ref, "palette") or [], get(cand, "palette") or [])
    add("palette_distance_le_20", dist <= 20, 0, dist)
    if only:
        checks = [c for c in checks if c["constraint"] in only]
    return {"all_pass": all(c["pass"] for c in checks), "checks": checks}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--out", default="teardown")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--scene", type=float, default=0.30)
    ap.add_argument("--compare", nargs=2, metavar=("REF_JSON", "CAND_JSON"))
    a = ap.parse_args()
    if a.compare:
        print(json.dumps(compare(Path(a.compare[0]), Path(a.compare[1])), indent=2))
        return
    if not a.file:
        ap.error("file is required unless --compare is used")
    src = Path(a.file)
    if not src.is_file():
        sys.exit(f"error: {src} is not a file")
    res = teardown(src, Path(a.out), max(1, a.frames), a.scene)
    print(json.dumps({k: res[k] for k in res if k in {"kind", "resolution", "aspect_ratio", "duration_s",
                                                       "fps", "shot_count", "palette"}}, indent=2))
    print(f"wrote {Path(a.out) / 'teardown.json'}")


if __name__ == "__main__":
    main()
