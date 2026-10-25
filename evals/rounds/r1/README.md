# Round 1: blind behavioral trials (zero spend)

Policy: Claude Haiku subagents, one per pack, given only the skill text and one
scenario (`scripts/blind_pack.py`), never the checks. Scored with
`evals/run_evals.py` against `evals/checks.json` after the bt05/bt06 check fixes.

| Set | Skill version | Scenarios x trials | B |
|---|---|---|---|
| old | before stop-conditions edit (a76257a) | 10 x 1 | 0.909 (40/44) |
| new | after stop-conditions edit | 10 x 1 | 0.932 (41/44) |
| inc | incumbent, bt06 only | 1 x 3 | 0.733 (11/15) |
| cand | Plan-stage loop dry-run edit, bt06 only | 1 x 3 | 1.000 (15/15) |

Findings:
- The stop-conditions edit raised the static rubric by 0.36 but behavior by one
  check at k=1, which is within noise. The static rubric overstated it.
- The Plan-stage loop edit is a real behavioral gain on bt06 (3/3 vs 1/3 full
  passes) and was accepted by the gate in behavioral mode. The static rubric
  could not see it (already saturated at 1.0).
- Three checks were wrong and were fixed before final scoring: bt05 and bt06
  required post-approval steps the skill forbids; bt06 `dry_run_first` could
  never pass.

Limits: Haiku stands in for a weaker policy; k is small; scenarios and checks
were written by the same author as the edits.
