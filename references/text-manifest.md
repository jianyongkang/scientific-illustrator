# Text manifest

Use a text manifest for non-trivial reference figures so label completeness can be checked independently from visual appearance.

Create `<job>/text-manifest.json` with this shape:

```json
{
  "labels": [
    {
      "id": "label-001",
      "text": "Input signal",
      "required": true,
      "count": 1,
      "status": "resolved"
    },
    {
      "id": "label-002",
      "text": "",
      "required": false,
      "count": 1,
      "status": "unresolved",
      "note": "Unreadable small label at lower right"
    }
  ]
}
```

For each resolved visible label, preserve the exact text and line breaks when legible. Use `count` when the same label must appear multiple times. Keep `required=true` for text that must be present in the final vector.

Use `status=unresolved` rather than guessing unreadable scientific text. `text_manifest_qa.py` validates resolved required labels against live `<text>`/`<tspan>` content in the Master SVG.

The manifest is a completeness check, not an OCR substitute. Visual QA still verifies position, size, hierarchy, rotation, and label-to-object association.
