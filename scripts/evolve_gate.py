#!/usr/bin/env python3
"""Zero-cost RRSI-style acceptance gate for skill edits. No network, no LLM.

Adapted from the selection side of RRSI (google-research/rrsi, Apache-2.0):
a candidate replaces the incumbent only if it is admissible and its measured
gain pays for the context it adds. The proposer is whoever wrote the commit
(a person or this coding session); this script never generates edits.

Per candidate, in order:
  1. Edit budget   annealed L0 cap on changed files: b_t = max(b_min,
                   round(b_max * (1 - t/T))), t = number of past decisions.
  2. Critic        deterministic leakage/weakening denylist on the diff,
                   checked BEFORE evaluation is spent.
  3. Evaluate      scripts/offline_eval.py in clean worktrees of the
                   incumbent and the candidate. Guards are non-compensatory.
  4. Noise floor   gain must be >= delta (one rubric check by default; the
                   evaluator is deterministic, so noise is zero, and delta
                   only blocks zero-gain churn).
  5. Cost rule     relative context growth dC of the touched skills must
                   satisfy dC <= beta0 + beta1 * dS.
History is one JSONL record per decision (.evolve/history.jsonl, committed),
with hypothesis, component, dS, dC, verdict. `status` reports the stall flag
and components whose recent edits never gained (pruning candidates).

  evolve_gate.py judge <candidate-ref> --hypothesis TEXT --component NAME [--apply]
  evolve_gate.py status
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / ".evolve"
HISTORY = STATE / "history.jsonl"
CFG = {"T": 12, "b_min": 1, "b_max": 4, "beta0": 0.02, "beta1": 1.0, "w": 3, "n_prune": 4}

CRITIC = [
    (r"^\+.*\b(t\d{2}_[a-z_]+|scenario-\d+)\b", "scenario id in added line"),
    (r"^\+.*(harness_rubric|offline_eval|evolve_gate|checks\.json)", "scorer reference in added line"),
    (r"^-.*(?i:originality gate)", "originality gate line removed"),
    (r"^-.*(?i:never passed to `--image`)", "reference-upload ban removed"),
    (r"^-.*(?i:cost before spend|generate cost)", "cost gate line removed"),
    (r"^-.*(?i:unknown stays unknown)", "unknown-grade rule removed"),
]


def git(*a: str, cwd: Path = ROOT, check: bool = True) -> str:
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(a)} failed: {r.stderr.strip()}")
    return r.stdout


def history() -> list[dict]:
    if not HISTORY.exists():
        return []
    return [json.loads(x) for x in HISTORY.read_text().splitlines() if x.strip()]


def budget(t: int) -> int:
    return max(CFG["b_min"], round(CFG["b_max"] * (1 - t / CFG["T"])))


def evaluate_ref(ref: str, tag: str) -> dict:
    wt = STATE / "wt" / tag
    git("worktree", "remove", "--force", str(wt), check=False)
    git("worktree", "add", "--detach", str(wt), ref)
    try:
        r = subprocess.run([sys.executable, "-I", str(wt / "scripts" / "offline_eval.py"),
                            "--root", str(wt), "--json"], capture_output=True, text=True)
        if not r.stdout.strip():
            return {"admissible": False, "S": 0, "tokens_by_skill": {}, "error": r.stderr[-400:]}
        return json.loads(r.stdout)
    finally:
        git("worktree", "remove", "--force", str(wt), check=False)


def judge(cand: str, hypothesis: str, component: str, apply: bool) -> int:
    hist = history()
    t = len(hist)
    base = git("rev-parse", "HEAD").strip()
    cref = git("rev-parse", cand).strip()
    if git("merge-base", base, cref).strip() != base:
        sys.exit("candidate must be a descendant of the incumbent (HEAD); rebase it first")
    files = [f for f in git("diff", "--name-only", base, cref).split() if not f.startswith(".evolve/")]
    diff = git("diff", "-U0", base, cref, "--", *files) if files else ""
    rec = {"t": t, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "incumbent": base[:12],
           "candidate": cref[:12], "component": component, "hypothesis": hypothesis,
           "files": files, "budget": budget(t)}

    def decide(verdict: str, reason: str, **extra) -> int:
        rec.update(verdict=verdict, reason=reason, **extra)
        STATE.mkdir(exist_ok=True)
        with HISTORY.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(json.dumps({k: rec[k] for k in rec if k not in ("files",)}, indent=1))
        return 0 if verdict == "accept" else 1

    if not files:
        return decide("reject", "empty diff")
    if len(files) > rec["budget"]:
        return decide("reject", f"edit budget: {len(files)} files > b_t={rec['budget']}")
    hits = sorted({why for pat, why in CRITIC for line in diff.splitlines() if re.search(pat, line)})
    if hits:
        return decide("reject", "critic: " + "; ".join(hits))

    inc, can = evaluate_ref(base, "incumbent"), evaluate_ref(cref, "candidate")
    if not can.get("admissible"):
        bad = [g["guard"] for g in can.get("guards", []) if not g["pass"]] or [can.get("error", "?")]
        return decide("reject", f"guard failed: {bad}", S_inc=inc.get("S"), S_cand=can.get("S"))
    touched = {f.split("/")[0] for f in files if f.startswith("higgsfield-")}
    c_inc = sum(inc["tokens_by_skill"].get(s, 0) for s in touched) or 1
    c_can = sum(can["tokens_by_skill"].get(s, 0) for s in touched)
    dS = round(can["S"] - inc["S"], 4)
    dC = round((c_can - c_inc) / c_inc, 4)
    delta = 1.0 / max(1, can["total"])
    gained = [c["id"] for c, o in zip(can["checks"], inc["checks"]) if c["pass"] and not o["pass"]]
    lost = [c["id"] for c, o in zip(can["checks"], inc["checks"]) if o["pass"] and not c["pass"]]
    m = dict(S_inc=inc["S"], S_cand=can["S"], dS=dS, dC_rel=dC, delta=round(delta, 4),
             gained=gained, lost=lost)
    if lost:
        return decide("reject", f"regression on {lost}", **m)
    if dS < delta - 1e-9:
        return decide("reject", f"gain {dS} below noise floor {round(delta, 4)}", **m)
    if dC > CFG["beta0"] + CFG["beta1"] * dS:
        return decide("reject", f"cost rule: dC {dC} > beta0+beta1*dS "
                                f"{round(CFG['beta0'] + CFG['beta1'] * dS, 4)}", **m)
    if apply:
        git("merge", "--ff-only", cref)
    return decide("accept", "admissible, gain >= floor, cost paid" + (" (applied)" if apply else ""), **m)


def status() -> int:
    hist = history()
    t = len(hist)
    recent = hist[-CFG["w"]:]
    stalled = len(recent) == CFG["w"] and not any(r["verdict"] == "accept" for r in recent)
    comps: dict = {}
    for r in hist:
        comps.setdefault(r["component"], []).append(r)
    prune = [c for c, rs in comps.items()
             if len(rs) >= 2 and not any(r["verdict"] == "accept" for r in rs[-CFG["n_prune"]:])]
    acc = sum(r["verdict"] == "accept" for r in hist)
    print(json.dumps({"decisions": t, "accepted": acc, "next_budget": budget(t),
                      "stalled": stalled, "explore_hint": "try an untried component" if stalled else None,
                      "components_no_recent_gain": prune,
                      "falsified": [r["hypothesis"] for r in hist if r["verdict"] == "reject"][-5:]},
                     indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge")
    j.add_argument("candidate")
    j.add_argument("--hypothesis", required=True)
    j.add_argument("--component", required=True)
    j.add_argument("--apply", action="store_true")
    sub.add_parser("status")
    a = ap.parse_args()
    return judge(a.candidate, a.hypothesis, a.component, a.apply) if a.cmd == "judge" else status()


if __name__ == "__main__":
    sys.exit(main())
