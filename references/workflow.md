# v2 local redraw workflow

## Control plane

Use `master.svg` as the semantic vector source of truth. Use `cache/geometry-cache.json` plus immutable `cache/batches/*.json` as the execution plan. Use `playback-state.json` only as the mutable checkpoint. Treat Illustrator as the native playback/inspection target, not as the canonical source for redraw revisions.

## Sequence

1. Run `doctor.ps1 -RequireIllustratorOpen`.
2. Create a unique job with `prepare_job.py`.
3. Inspect the reference/current artboard and record all visible text in `text-manifest.json` when non-trivial.
4. Let the active model author a true-vector `master.svg` from semantic understanding.
5. Run `svg_qa.py --strict --playback` and text QA.
6. Run `prepare_geometry_cache.py` exactly once for that Master SVG revision.
7. Run `cache_qa.py`.
8. Run `run_playback.ps1`; keep one Illustrator COM connection for all batches.
9. Export a preview and compare it with the reference.
10. If correction is required, edit Master SVG, rebuild the cache, reset only the marked generated layer, and replay from batch zero.
11. If execution is interrupted without a Master SVG change, rerun the same playback command and resume from the first incomplete batch.
12. Export `preview_final.png`, save a new AI working copy/PDF, and run output QA.

## Recovery invariant

A batch is complete only after Illustrator renames its group to `__SI_BATCH_XXXXXX__` and the runner advances `next_batch` in `playback-state.json`. A group named `__SI_BATCH_PENDING_XXXXXX__` is incomplete and may be removed/replayed safely. Never remove completed batch groups during a normal resume.

## Revision invariant

Bind the cache to the SHA256 of `master.svg`. If that SHA changes, mark the cache stale. Rebuild the cache and reset only the Skill-generated layer; never attempt to continue a changed Master SVG against old playback state.
