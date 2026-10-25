#!/usr/bin/env python3
"""Zero-cost, deterministic evaluation of a skills tree. No network, no LLM.

Score S = fraction of harness rubric checks passed (evals/harness_rubric.json).
Cost C = estimated context tokens of each skill's SKILL.md + references
(chars / 4; an estimate, labeled as such). Guards are non-compensatory: any
failure makes the tree inadmissible regardless of S.

  offline_eval.py [--root DIR] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def section(text: str, heading: str) -> str | None:
    m = re.search(rf"^(#+)\s+{re.escape(heading)}[^\n]*\n", text, re.M)
    if not m:
        return None
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    return rest[: end.start()] if end else rest


def rubric(root: Path) -> list[dict]:
    spec = json.loads((root / "evals" / "harness_rubric.json").read_text())
    out = []
    for skill, checks in spec.items():
        if skill.startswith("_"):
            continue
        for c in checks:
            p = root / skill / c["file"]
            text = p.read_text() if p.exists() else ""
            scope = section(text, c["section"]) if c.get("section") else text
            ok = False
            if scope is not None:
                m = re.search(c["re"], scope, re.S)
                ok = bool(m)
                if ok and c.get("before"):
                    later = re.search(c["before"], scope)
                    ok = later is not None and m.start() < later.start()
            out.append({"skill": skill, "id": c["id"], "pass": ok})
    return out


def context_tokens(root: Path) -> dict:
    est = {}
    for sd in sorted(root.glob("higgsfield-*")):
        n = len((sd / "SKILL.md").read_text()) if (sd / "SKILL.md").exists() else 0
        n += sum(len(f.read_text()) for f in (sd / "references").glob("*.md")) if (sd / "references").is_dir() else 0
        est[sd.name] = n // 4
    return est


def guard(name: str, cmd: list[str], cwd: Path) -> dict:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return {"guard": name, "pass": r.returncode == 0, "tail": (r.stdout + r.stderr)[-400:]}


def guards(root: Path) -> list[dict]:
    py = sys.executable
    g = [guard("validate_skills", [py, "-I", "scripts/validate-skills.py"], root),
         guard("eval_runner_selftest", [py, "-I", "evals/run_evals.py", "evals/fixtures",
                                        "--expect-fail", "bad"], root)]
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        td = Path(tempfile.mkdtemp())
        s = root / "higgsfield-reverse-reference" / "scripts" / "teardown_media.py"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180:d=1",
                        "-r", "24", str(td / "a.mp4")], capture_output=True)
        ok = all(subprocess.run([py, "-I", str(s), str(td / "a.mp4"), "--out", str(td / o)],
                                capture_output=True).returncode == 0 for o in ("r", "c"))
        cmp_ = subprocess.run([py, "-I", str(s), "--compare", str(td / "r/teardown.json"),
                               str(td / "c/teardown.json")], capture_output=True, text=True)
        g.append({"guard": "teardown_roundtrip", "pass": ok and '"all_pass": true' in cmp_.stdout,
                  "tail": cmp_.stdout[-200:]})
        shutil.rmtree(td, ignore_errors=True)
    else:
        g.append({"guard": "teardown_roundtrip", "pass": True, "tail": "skipped: ffmpeg missing (unknown)"})
    return g


def evaluate(root: Path) -> dict:
    checks = rubric(root)
    gs = guards(root)
    tok = context_tokens(root)
    passed = sum(c["pass"] for c in checks)
    return {"S": round(passed / max(1, len(checks)), 4), "passed": passed, "total": len(checks),
            "C_tokens_est": sum(tok.values()), "tokens_by_skill": tok,
            "admissible": all(g["pass"] for g in gs), "guards": gs, "checks": checks}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = evaluate(Path(a.root).resolve())
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"S={res['S']} ({res['passed']}/{res['total']})  C~{res['C_tokens_est']} tokens (est)  "
              f"admissible={res['admissible']}")
        for g in res["guards"]:
            print(f"  guard {'ok ' if g['pass'] else 'FAIL'} {g['guard']}")
        for c in res["checks"]:
            if not c["pass"]:
                print(f"  miss {c['skill']}:{c['id']}")
    return 0 if res["admissible"] else 1


if __name__ == "__main__":
    sys.exit(main())
