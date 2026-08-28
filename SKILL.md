---
name: scientific-illustrator
description: Reconstruct, draw, edit, and quality-check scientific figures as editable native vector objects in the user's already-open Adobe Illustrator document on Windows. Use for paper-figure redraws, mechanism diagrams, workflows, graphical abstracts, review figures, reference-image recreation, or continued Illustrator drawing when the model should semantically rebuild the figure, preserve live text, parse one Master SVG into an immutable geometry cache, play native PathItem/text atoms in paint order through one persistent Illustrator session, resume safely after interruption, inspect previews, and export new AI/PDF deliverables without third-party vectorization APIs.
---

# Scientific Illustrator v2

Use this default local workflow:

`reference/current AI -> isolated job -> text manifest -> AI-authored Master SVG -> playback-safe QA -> one-time geometry cache -> persistent native Illustrator playback -> preview -> correction/reset/replay -> AI/PDF finalization -> output QA`

Do not use a third-party vectorization API. Do not make scripts call ChatGPT or another model. Let the active model inspect the reference and author the semantic vector plan; let deterministic local scripts cache, validate, play, resume, and export it.

Read `references/workflow.md`, `references/ai-vectorization.md`, `references/native-playback.md`, `references/text-manifest.md`, and `references/illustrator-rules.md` before a non-trivial redraw. Read `references/visual-qa.md` before judging a preview.

## Runtime contract

- Target Windows 10/11 x64, PowerShell 5.1+, Python 3.11-3.14, and Adobe Illustrator 2026 (30.x preferred).
- Require Illustrator and the intended target document to already be open. Never launch, restart, close, focus, move, resize, maximize, or minimize Illustrator.
- Treat the active Illustrator document when playback starts as the target. Bind resume state to that document identity and refuse to resume into a different document.
- Keep job files outside the installed Skill directory.
- Keep the reference raster outside final vector artwork.

Run before Illustrator work:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1 -RequireIllustratorOpen
```

## 1. Create one isolated job

```powershell
python scripts\prepare_job.py .\work
```

Use the returned job directory as the only task root. Keep one `master.svg` as the canonical vector source and one `playback-state.json` as the execution checkpoint.

## 2. Let the model reconstruct semantics

Inspect the uploaded reference or current artboard and reconstruct what the figure means, not only its pixel boundary.

- Identify panels, objects, labels, arrows, connector topology, repeated motifs, color families, and z-order.
- Create `text-manifest.json` for non-trivial figures before drawing. Preserve uncertain labels as unresolved instead of inventing text.
- Author `master.svg` directly from model understanding using explicit vector primitives and live text.
- Prefer `path`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `text`, `tspan`, and `g`.
- Draw arrowheads as explicit polygons/paths. Do not rely on SVG markers for native playback.
- Avoid gradients, masks, clipping, filters, `<use>`, raster `<image>`, scripts, external resources, and paint servers.
- Keep repeated subjects consistent and separate repeated small objects so they stay individually editable.

Bootstrap when useful:

```powershell
python scripts\bootstrap_svg.py <job>\master.svg --width 1600 --height 1200
```

Use `references/ai-vectorization.md` and `references/redraw-rules.md` for authoring conventions.

## 3. Gate the Master SVG before playback

Run strict structural and playback compatibility QA:

```powershell
python scripts\svg_qa.py <job>\master.svg --strict --playback
```

When a text manifest exists, also run:

```powershell
python scripts\text_manifest_qa.py <job>\text-manifest.json <job>\master.svg
```

Fix every failure. Do not silently drop an unsupported SVG feature during playback.

## 4. Parse the Master SVG exactly once

Create an immutable geometry cache for this exact Master SVG revision:

```powershell
python scripts\prepare_geometry_cache.py <job>\master.svg `
  --cache-dir <job>\cache `
  --batch-size 30
```

Then validate cache integrity and source freshness:

```powershell
python scripts\cache_qa.py <job>\cache --master-svg <job>\master.svg --strict
```

Treat `<job>\cache` as immutable. Never edit batch JSON by hand. Never reopen/reparse `master.svg` during playback. If `master.svg` changes, rebuild the cache with `--replace` and reset the generated Illustrator layer before replay.

## 5. Play native Illustrator objects through one persistent session

Use the v2 playback runner, not whole-SVG placement, for the normal redraw path:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_playback.ps1 `
  -CacheDir <job>\cache `
  -LayerName SI_redraw `
  -FitMode contain
```

The runner must:

- obtain the already-running Illustrator COM object once and retain it for the full session;
- create native `PathItem` geometry and live text in ascending Master SVG paint order;
- use ordinary batches of 20-50 atoms (default target 30); isolate genuinely complex atoms when required;
- write completed batch markers into the generated `SI_` layer;
- update `playback-state.json` only after a batch succeeds;
- preserve every completed batch after interruption;
- remove only a stale `__SI_BATCH_PENDING_*` group for the current incomplete batch, then replay that batch;
- refuse to draw into or delete an unmarked user layer.

For visibly slower one-object-at-a-time playback, set a small delay explicitly, for example `-InterObjectDelayMs 30`. Keep delay `0` by default for speed.

Check recovery state without touching Illustrator:

```powershell
python scripts\playback_status.py <job>\cache
```

Resume an interrupted job by running the same `run_playback.ps1` command again. Do not reset the generated layer when merely resuming.

## 6. Correct a Master SVG revision safely

When visual inspection requires a geometry/text correction:

1. edit only `master.svg` and `text-manifest.json` as needed;
2. rerun `svg_qa.py --strict --playback` and text QA;
3. rebuild the geometry cache with `--replace`;
4. reset only the Skill-generated layer and replay from batch zero:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_playback.ps1 `
  -CacheDir <job>\cache `
  -LayerName SI_redraw `
  -FitMode contain `
  -ResetGeneratedLayer
```

Use `-FitMode artboard` only when the Master SVG was authored in active-artboard coordinates/aspect ratio. Keep `place_svg.jsx` only as a compatibility/emergency whole-SVG import path, not the v2 default.

## 7. Preview and visually inspect

Export a PNG after the first completed playback and after meaningful corrections:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\invoke_illustrator_jsx.ps1 `
  -Script jsx\export_preview.jsx `
  -PngPath <job>\previews\preview_01.png `
  -PreviewScale 150
```

Inspect the preview against the reference when the runtime can actually view the generated image. Do not claim visual matching if the runtime could not inspect the preview.

## 8. Finalize without overwriting user files

Choose new output paths. Do not overwrite the original AI or existing outputs by default.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\invoke_illustrator_jsx.ps1 `
  -Script jsx\finalize_outputs.jsx `
  -AiCopyPath <job>\output\figure_SI.ai `
  -PdfPath <job>\output\figure_SI.pdf
```

Run output QA:

```powershell
python scripts\output_qa.py `
  --ai <job>\output\figure_SI.ai `
  --pdf <job>\output\figure_SI.pdf `
  --png <job>\previews\preview_final.png
```

## Completion gate

Report completion only when all applicable conditions hold:

- the Master SVG passes strict playback-safe vector QA;
- required live text passes manifest QA;
- the exact Master SVG revision was parsed once into a cache and that cache passes integrity/freshness QA;
- one persistent Illustrator connection completed every batch or a resumed session completed the remaining batches;
- no stale pending batch remains and `playback-state.json` reports completion;
- generated content stays inside marked `SI_` layers and user artwork remains untouched;
- the reference raster is not embedded in final artwork;
- a preview was exported and any claimed visual comparison was actually performed;
- the original AI was not overwritten by default;
- the new AI working copy and PDF exist and pass output QA.

State any unverified Illustrator-specific limitation explicitly instead of implying it was tested.
