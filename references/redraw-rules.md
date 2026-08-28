# Redraw rules

## Reconstruction order

1. Match artboard and panel structure.
2. Match major object positions and relative sizes.
3. Match connector topology and arrow direction.
4. Match labels and typographic hierarchy.
5. Match color families and emphasis.
6. Add secondary details after structure is correct.

## Geometry

- Prefer semantic primitives and simple paths over noisy traced paths.
- Reuse dimensions, radii, stroke widths, arrowheads, and spacing values.
- Use meaningful group IDs for modules and panels.
- Keep repeated subjects structurally consistent while keeping repeated editable objects separate when appropriate.

## Typography

- Keep text live in SVG and Illustrator whenever practical.
- Preserve hierarchy through size, weight, alignment, and placement rather than effects.
- Do not convert all text to outlines for convenience.
- Never invent unreadable scientific labels; mark them unresolved in the manifest.

## Color

- Use a controlled palette with stable semantic assignments.
- Avoid many near-duplicate colors unless the reference requires a quantitative scale.
- Keep text and thin connectors legible against their backgrounds.

## Scientific meaning

Preserve arrow direction, polarity, causal order, labels, units, state names, panel relationships, and quantitative encodings. Simplify decorative texture before scientific structure.

## Vector integrity

Do not embed the reference image in the final SVG. Avoid blur, raster filters, external resources, and effects likely to rasterize during Illustrator import when a clean vector construction is possible.
