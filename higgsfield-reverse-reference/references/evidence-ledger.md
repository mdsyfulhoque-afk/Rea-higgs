# Evidence ledger

Borrowed from the evidence discipline used in reverse-engineering tooling: separate what was seen from what was concluded, and keep both.

## Grades

| Grade | Meaning | Allowed use |
|---|---|---|
| `observed` | Directly visible or measured (resolution, a visible headline, a cut at 2.1 s). | Hard prompt constraint. |
| `derived` | Computed from observed facts by a stated method (aspect ratio, fps, average shot length, palette). | Hard prompt constraint. |
| `inferred` | A reasoned guess about cause or intent ("shot on a long lens", "Kling-like motion", "teal-orange grade"). | Soft hint only. Phrase as "reads as", never "is". |
| `unknown` | Not recoverable or not checked. | Omit from the prompt. List under open questions. |

## Demotion rules

- An inference with a single supporting signal is demoted to `unknown`. Keep it only with a second independent signal (for example both the contact sheet and the motion across frames).
- Anything about the generator (which model, which prompt, which seed) is `unknown` unless the file's own metadata states it. Visual resemblance to a model's look is at most `inferred`.
- Text read from pixels is `observed` only when legible at full resolution; otherwise `inferred`.
- Never promote a grade because several sources agree on a guess; only an independent measurement can.

## Format (`ledger.md`)

```
| id | claim | grade | evidence | used as |
|----|-------|-------|----------|---------|
| L1 | 9:16, 1080x1920 | observed | ffprobe | hard |
| L2 | 4 shots, avg 2.1 s | derived | scene cuts > 0.30 | hard |
| L3 | warm key light from camera left | observed | frames 02, 05 | hard |
| L4 | reads as 35 mm handheld | inferred | slight sway frames 03-06 | soft |
| L5 | audio is VO + music bed | unknown | not analyzed | omit |
```

`used as` is one of `hard`, `soft`, `omit`, `excluded` (originality gate).

## Originality gate entries

Record anything that must not be copied as `excluded`: recognizable faces, logos, brand names, characters, verbatim on-screen text or voiceover, distinctive set pieces that would make the output read as a copy. The spec lists them under exclusions and the prompts must not mention them.

## Worked example

Reference: a 9:16 skincare ad, 14 s.

- Hard: `9:16`, `~14 s`, `5 shots`, warm neutral palette (`#e9d8c4`, `#b98f6a`), soft window light, macro product shots in shots 2 and 4.
- Soft: reads as slow push-ins; reads as shallow depth of field.
- Excluded: the brand wordmark, the on-screen model's face, the tagline text.
- Open: whether the VO is synthetic; the original lens.
