---
version: 0.13.0
name: higgsfield-reverse-reference
description: |
  Reverse-engineer a reference image, video, ad, thumbnail, or live web page into an evidence-graded production spec, then rebuild an original version through the Higgsfield CLI. Every claim is labeled observed, derived, inferred, or unknown; only observed and derived facts become hard prompt constraints. Optionally uses the REA MCP for browser or packaged-app evidence. Use when: "recreate this ad", "make something like this video", "what model/style/camera made this", "break down this reference", "reverse engineer this look", "match this shot list", "teardown this landing page hero". Chain: teardown first, then higgsfield-generate (or brandkit / product-photoshoot / youtube-thumbnail) with the approved spec. NOT for: copying a person's identity, logo, character, or exact composition (use higgsfield-soul-id for the user's own identity); plain generation with no reference (use higgsfield-generate); extracting protected source code, DRM, or credentials.
argument-hint: "<reference-path-or-url> [--goal recreate|restyle|analyze] [--out <dir>]"
allowed-tools: Bash
---

# Higgsfield Reverse Reference

Turn "I like this" into a defensible spec, then into an original asset. The teardown is the product; generation is the last step.

## Authority rules (apply every turn)

1. **Four evidence grades, never blended.** `observed` (directly measured or visible), `derived` (computed from observed, e.g. fps from frame times), `inferred` (best guess about cause, e.g. "likely 35mm lens"), `unknown`. See `references/evidence-ledger.md`.
2. **Only observed and derived facts may become hard constraints** in a prompt. Inferences become soft hints or are dropped. Unknown stays unknown; never fill it with a confident guess.
3. **Originality gate.** Extract style, structure, pacing, palette, lighting, camera, and copy-structure. Never carry over a recognizable person, logo, brand mark, character, or verbatim text. Reference media is analyzed locally; it is never passed to `--image` / `--video` unless the user owns it or says they have rights, and then only for restyle goals.
4. **Smallest sufficient output.** Return the spec summary and the generation plan, not the full ledger, unless asked. Keep the ledger on disk.
5. **Cost before spend.** Print `higgsfield generate cost ...` for the plan and get approval before any paid batch above one job.
6. **Never invent model names.** Run `higgsfield model list` and pick from the live catalog.

## Bootstrap

1. `higgsfield` missing: `curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh`.
2. `higgsfield account status` shows `Session expired` or `Not authenticated`: ask the user to run `higgsfield auth login`, then wait.
3. Local tooling check (analysis only, none of it needs credentials): `ffprobe`, `ffmpeg`, `python3`. Missing media tools degrade the teardown to visual inspection; say so in the ledger as `unknown`, do not install unrelated software.

## Stage flow

| Stage | Do | Output |
|---|---|---|
| 0. Intake | Resolve reference type (image / video / web page / packaged app) and goal (`recreate`, `restyle`, `analyze`). Ask one compact question only if the goal is unclear. | goal + type |
| 1. Capture | Local file: copy to a working dir, never edit the original. URL: fetch with the user's browser or REA; do not scrape behind a login. | working copy |
| 2. Measure | Run `scripts/teardown_media.py` for media; see `references/media-teardown.md`. Web/app: `references/web-teardown.md`. | `teardown.json` |
| 3. Read | Look at extracted contact-sheet frames yourself. Record shot types, camera moves, lighting, color grade, typography, pacing, audio structure. | ledger entries |
| 4. Grade | Assign each entry a grade. Cross-check one inference against a second signal before keeping it; otherwise demote to `unknown`. | `ledger.md` |
| 5. Spec | Compile the production spec: hard constraints (observed/derived), soft hints (inferred), exclusions (originality gate), open questions. | `spec.md` |
| 6. Plan | Map the spec to Higgsfield jobs: model choice from the live catalog, per-shot prompts, aspect ratio, duration, cost. Present for approval. | plan |
| 7. Generate | Hand off to the owning skill with the approved spec. Verify each result against the hard constraints (see QA). | assets |

## Routing after the spec

- Video ad or motion piece: `higgsfield-generate` (single clips or workflows); narrated explainer structure: `higgsfield-video-explainer`.
- Product still or ad pack: `higgsfield-product-photoshoot` or `higgsfield-generate` Marketing Studio.
- Thumbnail or cover: `higgsfield-youtube-thumbnail` (the reference is style-only there too).
- Brand look: `higgsfield-brandkit` (palette and type findings feed its intake).
- Landing-page hero or site: `higgsfield-websites`, with generated hero assets from `higgsfield-generate`.

Do not batch-ask questions across skills. Finish the teardown, then enter exactly one downstream skill at a time.

## QA after generation

Compare each output to the hard constraints only: aspect ratio, duration, shot count, palette within tolerance (`scripts/teardown_media.py --compare`), text legibility, absence of excluded elements. Report pass/fail per constraint in one line each. A miss on a hard constraint triggers one targeted regeneration, not a full rerun. Soft hints are never graded as failures.

## Optional: REA for deeper evidence

REA (reverse-engineering MCP) is useful only when the claim depends on a shipped page, bundle, or packaged app, for example "which font and easing does this site actually ship". If REA tools are already connected, use them for passive observation of a target the user supplied. If not, do not run setup; fall back to browser inspection (`references/web-teardown.md`). Never use REA to bypass protections, extract credentials, or analyze targets the user does not have the right to inspect.

## References

- `references/evidence-ledger.md`: grades, ledger format, demotion rules, worked example.
- `references/media-teardown.md`: what to measure in images and video, helper script usage, what is not recoverable.
- `references/web-teardown.md`: browser and REA procedure for pages and apps, what to record.
- `references/spec-to-generation.md`: spec template, prompt assembly from graded facts, model routing, cost gate.
