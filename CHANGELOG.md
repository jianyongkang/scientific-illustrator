# Changelog

## 2.0.0

- Changed the default Illustrator path from whole-SVG placement to native atom playback.
- Added one-time Master SVG parsing and immutable SHA-bound geometry caches.
- Added path/text atom normalization with SVG curves, transforms, simple CSS, and live text support.
- Added ordinary 20-50 atom batching with complex-atom singleton support.
- Added one persistent Illustrator COM session for the full playback run.
- Added completed/pending batch markers and external `playback-state.json` for safe interruption recovery.
- Added document/cache identity checks to prevent resuming into the wrong Illustrator document.
- Added playback-safe SVG QA for unsupported marker/paint-server/mask/clip/filter constructs.
- Added cache integrity/freshness QA and playback status inspection.
- Kept third-party vectorization APIs and network dependencies out of the workflow.
- Retained whole-SVG placement only as a compatibility fallback.

## 1.1.0

- Added isolated jobs, text-manifest QA, strict SVG QA, safe generated-layer replacement, runtime checks, and output verification.
