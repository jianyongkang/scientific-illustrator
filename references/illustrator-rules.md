# Illustrator runtime rules

## Ownership and safety

- Require Illustrator and the intended document to be open already.
- Never launch, restart, close, focus, move, resize, maximize, or minimize Illustrator.
- Draw only into a layer beginning with `SI_` that contains the hidden `__SI_GENERATED__` ownership marker.
- Never delete/replace a user layer merely because its name starts with `SI_`; require the ownership marker too.
- Bind resume state to the document fingerprint captured when playback begins.

## Native playback modes

- `FitMode=contain`: uniformly scale and center cached Master SVG coordinates inside the active artboard with a margin. Default for full redraws.
- `FitMode=artboard`: map Master SVG coordinates to the full active artboard, allowing non-uniform scale. Use only when authored for that artboard.
- `FitMode=none`: use 1:1 Master SVG user units anchored at the active artboard top-left.

## Layer/batch markers

- `__SI_GENERATED__`: proves the layer belongs to this Skill.
- `__SI_BATCH_PENDING_XXXXXX__`: incomplete batch; safe to remove/replay on resume.
- `__SI_BATCH_XXXXXX__`: completed batch; preserve during resume.

## Revision reset

When Master SVG changes, rebuild the cache and run playback with `-ResetGeneratedLayer`. The reset script may remove only a marked generated layer. Never use reset as a normal resume mechanism.

## Whole-SVG compatibility path

`place_svg.jsx` remains available for legacy/emergency import but is not the v2 default. Prefer native cache playback whenever fidelity constraints are supported by the playback-safe SVG contract.
