# Model-authored semantic vectorization

## Principle

Use the active multimodal model as the semantic vector author. The model should inspect the reference and deliberately reconstruct editable scientific objects. Local scripts must not attempt to call ChatGPT again and must not depend on a third-party vectorization API.

## Prefer semantic reconstruction over blind tracing

For labels, arrows, boxes, axes, membranes, pathways, icons, and repeated scientific motifs, infer the intended object and author clean geometry. Do not preserve pixel noise merely because it exists in the source raster.

Use live `<text>` for normal labels. Keep arrows as a connector path plus an explicit arrowhead path/polygon. Keep repeated elements separate. Preserve scientific topology and direction before decorative similarity.

## When a raster-like subject is complex

Approximate the meaningful silhouette with deliberate Bezier paths, or preserve the complex raster outside the vector redraw when the user explicitly wants a mixed-media figure. Never hide a reference raster inside the Master SVG and call it vectorized.

## Master SVG requirements

- include explicit width, height, and viewBox;
- use solid fills/strokes;
- prefer simple path topology;
- avoid marker references, gradients, paint servers, masks, clipping, filters, `<use>`, and external resources;
- keep live text readable and match text manifest content;
- use document order as final paint order.
