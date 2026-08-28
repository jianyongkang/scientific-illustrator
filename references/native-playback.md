# Native playback contract

## Purpose

Make Illustrator visibly and structurally receive native editable objects rather than one monolithic placed SVG. The Master SVG is parsed once into path/text atoms; the playback engine creates those atoms in exact paint order.

## Cache files

- `cache/geometry-cache.json`: source hash, viewBox, parser version, batch index, statistics.
- `cache/atoms.json`: full normalized atom list for diagnostics; do not use it as mutable state.
- `cache/batches/batch_XXXXXX.json`: immutable playback units.
- `playback-state.json`: mutable resume checkpoint outside the cache.

## Atom model

A path atom contains one or more subpaths. Every point stores an anchor, incoming Bezier handle, and outgoing Bezier handle. A text atom stores live string content, position, font family/size, anchor alignment, rotation, and solid fill/stroke style.

The parser normalizes `rect`, rounded `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, and SVG path commands `M/L/H/V/C/S/Q/T/A/Z` into native Bezier geometry. It also applies supported transforms and simple class/id/tag CSS rules before caching.

## Playback restrictions

Require solid native geometry. Reject features that the native runner cannot faithfully preserve, including marker references, gradients/paint servers, masks, clipping, filters, `<use>`, raster images, scripts, and external resources. Draw arrowheads as explicit geometry.

Filled multi-subpath paths are rejected because holes/compound fill behavior cannot be guaranteed by the current native runner. Split them into explicit fidelity-safe shapes before caching.

## Ordering

Create atoms in ascending `paint_index`. Later atoms must remain above earlier atoms. Keep completed batches in the generated layer. Use a hidden `__SI_GENERATED__` marker to distinguish Skill-owned layers from user layers.

## Batching

Use 20-50 ordinary atoms per batch; default to 30. Allow a genuinely complex path to be a singleton. Do not reparse Master SVG between batches.

## Persistent connection

`run_playback.ps1` must call `Marshal.GetActiveObject('Illustrator.Application')` once and reuse the same COM object for the entire run. Do not launch Illustrator automatically and do not reacquire Illustrator per batch.

## Idempotent resume

For batch N:

1. if `__SI_BATCH_N__` exists, treat the batch as already complete;
2. if `__SI_BATCH_PENDING_N__` exists, remove that pending group only;
3. create a new pending group and all its native atoms;
4. rename it to the completed batch marker only after all atom creation succeeds;
5. advance `playback-state.json` only after Illustrator reports batch success.

This allows interruption during a batch without duplicating completed work.
