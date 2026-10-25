#!/usr/bin/env python3
"""Closed generate -> measure -> regenerate loop with a hard budget.

Runs each planned job, fetches the result, measures it with teardown_media,
checks the job's hard constraints against the reference, and retries only the
failing jobs with the job's correction hints. Stops at the first pass, at
max_attempts per job, or when the total job budget is spent. Visual judgment
(look, motion, text, exclusions) stays with the agent: the loop writes
judge.md listing every frame to inspect.

  refine_loop.py --ref <ref>/teardown.json --plan plan.json --out <dir> [--dry-run]

plan.json:
{
  "max_attempts": 3,            # per job, including the first
  "max_jobs": 8,                # total generator calls across all jobs
  "jobs": [{
    "id": "shot1",
    "cmd": ["higgsfield", "generate", "create", "<model>", "--prompt", "{prompt}", "--wait", "--json"],
    "prompt": "9:16, warm neutral palette, macro of a pump bottle",
    "checks": ["aspect_ratio", "palette_distance_le_20"],
    "fixes": {"palette_distance_le_20": "muted warm beige and caramel tones only"}
  }]
}
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import teardown_media as tm  # noqa: E402

MEDIA_EXT = (".mp4", ".mov", ".webm", ".png", ".jpg", ".jpeg", ".webp", ".gif")
URL_RE = re.compile(r"(?:https?|file)://[^\s\"']+")


def find_media_url(obj) -> str | None:
    """First media URL in generator output (JSON or text)."""
    found: list[str] = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            found.extend(URL_RE.findall(x))

    walk(obj)
    media = [u for u in found if u.split("?")[0].lower().endswith(MEDIA_EXT)]
    return (media or found or [None])[0]


def build_cmd(job: dict, prompt: str) -> list[str]:
    return [a.replace("{prompt}", prompt) for a in job["cmd"]]


def run_job(job, prompt, dest: Path) -> tuple[Path | None, str]:
    r = subprocess.run(build_cmd(job, prompt), capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"generator exit {r.returncode}: {r.stderr.strip()[:300]}"
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        out = r.stdout
    url = find_media_url(out)
    if not url:
        return None, "no media URL in generator output"
    ext = Path(url.split("?")[0]).suffix or ".bin"
    path = dest.with_suffix(ext)
    try:
        with urllib.request.urlopen(url, timeout=300) as resp, open(path, "wb") as fh:
            fh.write(resp.read())
    except OSError as e:
        return None, f"download failed: {e}"
    return path, url


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", default="loop")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    ref = json.loads(Path(a.ref).read_text())
    plan = json.loads(Path(a.plan).read_text())
    max_attempts = int(plan.get("max_attempts", 3))
    budget = int(plan.get("max_jobs", len(plan["jobs"]) * max_attempts))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    if a.dry_run:
        for job in plan["jobs"]:
            print(json.dumps({"id": job["id"], "cmd": build_cmd(job, job["prompt"])}))
        print(f"budget: {budget} calls max, {max_attempts} attempts per job")
        return 0

    spent = 0
    report = {"budget": budget, "jobs": []}
    judge = ["# Visual judge checklist", "",
             "Inspect each frame against the spec: look, motion, text legibility, exclusions.", ""]
    for job in plan["jobs"]:
        prompt = job["prompt"]
        only = set(job.get("checks") or []) or None
        entry = {"id": job["id"], "status": "failed", "attempts": []}
        for n in range(1, max_attempts + 1):
            if spent >= budget:
                entry["status"] = "budget_exhausted"
                break
            spent += 1
            jdir = out / job["id"]
            jdir.mkdir(exist_ok=True)
            media, info = run_job(job, prompt, jdir / f"attempt_{n}")
            att = {"n": n, "prompt": prompt}
            if media is None:
                att["error"] = info
                entry["attempts"].append(att)
                continue
            td = tm.teardown(media, jdir / f"attempt_{n}_td", 4, 0.30)
            res = tm.compare_data(ref, td, only)
            att.update(source=info, file=media.name, result=res)
            entry["attempts"].append(att)
            judge.append(f"- {job['id']} attempt {n}: {jdir.name}/attempt_{n}_td/"
                         + ", ".join(tm.get(td, "frames") or []))
            if res["all_pass"]:
                entry["status"] = "passed"
                break
            failed = [c["constraint"] for c in res["checks"] if not c["pass"]]
            hints = [job.get("fixes", {}).get(f) for f in failed]
            hints = [h for h in hints if h]
            if not hints:
                entry["status"] = "failed_no_fix_hint"
                break
            prompt = f"{job['prompt']}. {' '.join(hints)}"
        report["jobs"].append(entry)

    report["calls_used"] = spent
    (out / "loop_report.json").write_text(json.dumps(report, indent=2))
    (out / "judge.md").write_text("\n".join(judge) + "\n")
    for j in report["jobs"]:
        print(f"{j['id']}: {j['status']} after {len(j['attempts'])} attempt(s)")
    print(f"calls used {spent}/{budget}; report {out / 'loop_report.json'}")
    return 0 if all(j["status"] == "passed" for j in report["jobs"]) else 1


if __name__ == "__main__":
    sys.exit(main())
