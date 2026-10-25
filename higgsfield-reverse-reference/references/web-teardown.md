# Web page and app teardown

Use for landing-page heroes, site visual systems, and packaged-app UI references. The goal is a visual and motion spec, not a code copy.

## Order of preference

1. **Browser inspection** of the live page, with the user's consent for any signed-in view. Record computed styles, not guesses: font families and weights, type scale, colors, spacing, border radius, shadows, hero media type, scroll behavior, animation durations and easing.
2. **Screenshots at set widths** (390, 768, 1440). Treat them as `observed`.
3. **REA MCP**, only if its tools are already connected and the claim depends on what the page or app ships (bundled fonts, animation libraries, which assets load). Follow REA's own skill for connection and recovery; do not run its setup unprompted. Use passive observation only. Keep the target to what the user supplied and is entitled to inspect.

Do not scrape behind a login, defeat bot protection, or extract credentials, tokens, or private API responses. Do not copy source code, copyrighted copy, or proprietary assets; record structure and measurements.

## Record in the ledger

| Area | Capture |
|---|---|
| Type | families, weights, size scale, line height (computed styles are `observed`) |
| Color | palette from computed styles and the dominant media; contrast ratios (`derived`) |
| Layout | grid, max width, section order, hero composition |
| Motion | trigger (load, scroll, hover), duration, easing, what moves; mark intent as `inferred` |
| Media | hero image/video count, aspect ratios, loop length, format |
| Performance cue | heavy media vs lightweight, only if measured |

## Hand-off

- Visual system into `higgsfield-brandkit` (palette, type) or `higgsfield-websites` (layout, motion constraints).
- Hero media into `higgsfield-generate`, using the media spec (aspect ratio, loop length, palette) as hard constraints.
- Third-party fonts or assets seen on the reference are not reused; pick licensed or generated equivalents.
