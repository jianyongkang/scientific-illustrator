# Visual QA checklist

Compare the exported Illustrator preview against the reference only when the runtime can actually view both.

Check scientific meaning first: object identity, arrow direction, connector topology, panel membership, labels, legends, axes, and repeated motifs. Then check geometry, spacing, proportions, line widths, colors, text hierarchy, z-order, and alignment.

For a non-trivial redraw, do not stop after the first successful native playback if visible discrepancies remain. Correct `master.svg`, rerun strict playback QA and text QA, rebuild the cache, reset only the marked generated layer, replay, and export a new numbered preview.

Do not claim visual matching when only structural/cache QA was possible.
