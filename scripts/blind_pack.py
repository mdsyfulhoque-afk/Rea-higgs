#!/usr/bin/env python3
"""Write one blind-trial prompt per scenario for a given skill tree.

The pack holds the skill text (SKILL.md + references) and one scenario's
request and observations. It never contains the checks. A separate agent
reads exactly one pack file and writes its transcript; evals/run_evals.py
scores the transcripts. No API key: the agent runs on whatever session
quota already exists.

  blind_pack.py --root <skills-tree> --out <dir> [--skill higgsfield-reverse-reference]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

WRAPPER = """You are an AI agent with the skill below loaded. DRY-RUN: no tool executes
and nothing is generated. The OBSERVATIONS block is what your tools would
return. Write the full transcript of how you would handle the request:
- a line starting with "$ " for every shell command you would run, in order,
  with real flags and paths;
- plain lines for everything you would tell the user;
- if you would ask the user a question and wait, ask it and end there.
Follow the skill exactly. Act it out; do not describe it.
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skill", default="higgsfield-reverse-reference")
    ap.add_argument("--checks", default=str(Path(__file__).resolve().parent.parent / "evals" / "checks.json"))
    a = ap.parse_args()
    sd = Path(a.root) / a.skill
    skill = (sd / "SKILL.md").read_text()
    for ref in sorted((sd / "references").glob("*.md")):
        skill += f"\n\n=== {ref.relative_to(sd)} ===\n{ref.read_text()}"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for sid, spec in json.loads(Path(a.checks).read_text()).items():
        if "request" not in spec:
            continue
        (out / f"{sid}.prompt.md").write_text(
            f"{WRAPPER}\n=== SKILL ===\n{skill}\n\n=== REQUEST ===\n{spec['request']}\n\n"
            f"=== OBSERVATIONS ===\n{spec['observations']}\n")
        n += 1
    print(f"wrote {n} packs to {out}")


if __name__ == "__main__":
    main()
