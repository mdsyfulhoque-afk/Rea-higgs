# Media teardown

## Run the helper

```bash
python3 -I scripts/teardown_media.py <reference-copy> --out <work>/ref
```

Needs `ffprobe` and `ffmpeg` on PATH. It writes `teardown.json` (every field carries a grade), `frame_XX.jpg`, and `contact_sheet.jpg`. Read the contact sheet and at least the first, last, and one mid-shot frame yourself; numbers do not replace looking.

Options: `--frames N` (default 8), `--scene T` (scene-cut threshold, default 0.30; lower finds softer cuts such as dissolves, higher ignores flashes).

## What is measured (observed or derived)

Resolution, aspect ratio, duration, fps, bitrate, codecs, audio stream presence, shot count and lengths, palette and mean luma over sampled frames.

## What you read from the frames (record in the ledger)

- Shot type per shot: wide, medium, close, macro, insert, over-the-shoulder.
- Camera: static, handheld, push-in, pan, orbit. Judge motion across at least two frames; a single frame cannot show motion.
- Lighting: direction, hardness, color temperature, practicals.
- Grade: contrast, saturation, tint. Compare against the measured palette before naming a look.
- Typography and graphics: placement, weight, safe areas. Copy text as structure ("headline, 4 words, top third"), not verbatim.
- Pacing: shot-length rhythm, hook in the first 2 s, end card.
- Audio: if audible, structure only (VO, music bed, SFX hits). Do not transcribe protected lyrics or scripts.

## Not recoverable

Model identity, prompt, seed, true focal length, original color pipeline. Resemblance is at most `inferred`.

## Stills and thumbnails

The helper handles a single image the same way (no duration or shots). Add composition notes: subject placement on a thirds grid, negative space, text zones, face crop size.

## Re-check generated output

```bash
python3 -I scripts/teardown_media.py <generated-file> --out <work>/cand
python3 -I scripts/teardown_media.py --compare <work>/ref/teardown.json <work>/cand/teardown.json
```

The comparison checks only measurable hard constraints: aspect ratio, duration within 15 percent, shot count within one, palette distance at most 20. Judge look, text, and exclusions by eye.
