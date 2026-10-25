#!/usr/bin/env python3
"""Score recorded agent transcripts against evals/checks.json.

Each transcript is a text file named <scenario-id>[-anything].txt containing
the agent's commands and replies for one scenario run. Deterministic: the same
transcript always gets the same score, so a SKILL.md edit can be compared
round to round.

  run_evals.py <transcript-dir> [--checks evals/checks.json] [--expect-fail PATTERN]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def score(text: str, spec: dict) -> list[dict]:
    out = []
    for c in spec.get("must", []):
        m = re.search(c["re"], text)
        ok = bool(m)
        if ok and "before" in c:
            later = re.search(re.escape(c["before"]), text)
            ok = later is None or m.start() < later.start()
        out.append({"id": c["id"], "kind": "must", "pass": ok})
    for c in spec.get("must_not", []):
        out.append({"id": c["id"], "kind": "must_not", "pass": re.search(c["re"], text) is None})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("--checks", default=str(Path(__file__).with_name("checks.json")))
    ap.add_argument("--expect-fail", default=None, help="regex of transcript names that must FAIL (self-test)")
    a = ap.parse_args()
    checks = json.loads(Path(a.checks).read_text())
    files = sorted(Path(a.dir).glob("*.txt"))
    if not files:
        print("no transcripts found")
        return 1
    bad = 0
    for f in files:
        sid = next((k for k in checks if f.stem.startswith(k)), None)
        if sid is None:
            print(f"skip {f.name}: no matching scenario")
            continue
        res = score(f.read_text(), checks[sid])
        passed = all(r["pass"] for r in res)
        fails = [r["id"] for r in res if not r["pass"]]
        print(f"{'PASS' if passed else 'FAIL'} {f.name} ({sum(r['pass'] for r in res)}/{len(res)})"
              + (f" failed: {', '.join(fails)}" if fails else ""))
        should_fail = bool(a.expect_fail and re.search(a.expect_fail, f.name))
        if passed == should_fail:
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
