# Spec to generation

## Spec template (`spec.md`)

```
Goal: recreate | restyle | analyze
Output: <type, aspect ratio, duration, shot count>
Hard constraints (observed/derived): ...
Soft hints (inferred, "reads as"): ...
Exclusions (originality gate): ...
Open questions: ...
Shot list: # | length | shot type | camera | light | action | text zone
Plan: job | model | cost | notes
```

## Prompt assembly

1. Start from the shot list, one prompt per shot or per image. Do not use `--count` to get different shots.
2. Write hard constraints as plain description: "9:16, warm neutral palette, soft window light from the left, macro of a pump bottle". Use the measured palette as color words and, when helpful, hex values.
3. Add soft hints with hedged verbs ("slow push-in feel"). Omit anything graded `unknown`.
4. Never include excluded names, faces, logos, or verbatim text. Describe a replacement original subject instead.
5. Identity: if the output needs a person, use a Soul Character the user trained (`higgsfield-soul-id`), never the reference's face.

## Model routing

Run `higgsfield model list` and `higgsfield model get <model> --json` and choose from the live catalog by capability (duration, aspect ratio, audio, image input). Use `higgsfield-generate` references for routing defaults. Do not hardcode a model because the reference "looks like" it.

## Cost gate

```bash
higgsfield generate cost <model> ...   # same flags as the create command
```

Show the total for the plan. One job can proceed on the user's go-ahead; multi-job plans need explicit approval of the total first.

## Reference media as input

Default: reference media is analyzed only and never uploaded. Pass it as `--image` / `--video` only for `restyle` and only if the user owns it or confirms rights. Copying a third party's exact composition is out of scope.

## Delivery

Return the asset URLs with one line per hard constraint (pass/fail from the comparison step), plus the open questions. Keep `ledger.md`, `spec.md`, and `teardown.json` in the working directory and mention where they are only if asked.
