#!/usr/bin/env python3
"""Self-test eval checks before they are trusted to score anything.

Every check may carry pass_example and fail_example. A must check has to match
its pass_example and not its fail_example; a must_not check the reverse. Also
flags checks that cannot pass by construction: a `before` literal that is
found inside the check's own pass_example (the dry-run line matching itself).

  check_selftest.py <checks.json> [--require-examples]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    strict = "--require-examples" in sys.argv
    data = json.loads(path.read_text())
    errors, missing, n = [], 0, 0
    for sid, spec in data.items():
        if not isinstance(spec, dict):
            continue
        for kind in ("must", "must_not"):
            for c in spec.get(kind, []):
                n += 1
                cid = f"{sid}:{c.get('id')}"
                try:
                    rx = re.compile(c["re"])
                except re.error as e:
                    errors.append(f"{cid}: bad regex: {e}")
                    continue
                pe, fe = c.get("pass_example"), c.get("fail_example")
                if pe is None or fe is None:
                    missing += 1
                    continue
                want_pass, want_fail = (True, False) if kind == "must" else (False, True)
                if bool(rx.search(pe)) != want_pass:
                    errors.append(f"{cid}: pass_example {'does not match' if want_pass else 'matches'}")
                if bool(rx.search(fe)) != want_fail:
                    errors.append(f"{cid}: fail_example {'does not match' if want_fail else 'matches'}")
                b = c.get("before")
                if b and kind == "must" and re.search(re.escape(b), pe):
                    m = rx.search(pe)
                    later = re.search(re.escape(b), pe)
                    if m and later and m.start() >= later.start():
                        errors.append(f"{cid}: unsatisfiable, 'before' literal matches the check's own text")
    for e in errors:
        print(f"error: {e}")
    print(f"{n} checks, {n - missing} with examples, {len(errors)} errors")
    return 1 if errors or (strict and missing) else 0


if __name__ == "__main__":
    sys.exit(main())
