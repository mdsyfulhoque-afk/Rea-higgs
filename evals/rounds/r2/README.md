# Round 2: independent held-out (zero spend)

Scenarios and checks: `evals/heldout.json`, written by a separate agent that
saw only the pre-edit skill (a75d733), never the edits or the existing checks.
Every check passed its own pass/fail examples (`evals/check_selftest.py`).
Policy: Claude Haiku, blind packs, 6 scenarios x 2 trials per version.

| Version | B |
|---|---|
| original (a75d733) | 0.979 (47/48) |
| current (after both accepted edits) | 0.958 (46/48) |

Finding: the edits accepted in rounds 0 and 1 show no general gain on
independently written scenarios. The only difference is one check
(`ho01:asks_rights`): the current skill refuses the upload of a clip taken
from a competitor's page without asking about rights, while the independent
author expected a rights question. At k=2 this is within noise.

What this means: the bt06 gain in round 1 is real but narrow (multi-job loop
planning). The skill was already near ceiling for a model of Haiku's strength
on the authority rules; further edits should be judged on held-out first.
