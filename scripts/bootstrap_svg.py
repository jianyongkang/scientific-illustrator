#!/usr/bin/env python3
"""Create a structured SVG scaffold for scientific redraw work."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path

SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <title>{title}</title>
  <defs>
    <style>
      .si-text {{ font-family: Arial, Helvetica, sans-serif; fill: #111111; }}
      .si-line {{ fill: none; stroke: #222222; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }}
    </style>
  </defs>
  <g id="background"></g>
  <g id="panels"></g>
  <g id="artwork"></g>
  <g id="connectors"></g>
  <g id="labels" class="si-text"></g>
  <g id="annotations"></g>
</svg>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a structured scientific SVG canvas.")
    parser.add_argument("output", help="Output SVG path")
    parser.add_argument("--width", type=int, default=1600, help="Canvas width")
    parser.add_argument("--height", type=int, default=1200, help="Canvas height")
    parser.add_argument("--title", default="Scientific figure redraw", help="SVG title")
    args = parser.parse_args()

    if args.width <= 0 or args.height <= 0:
        raise SystemExit("width and height must be positive")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        SVG_TEMPLATE.format(width=args.width, height=args.height, title=escape(args.title)),
        encoding="utf-8",
    )
    print(f"BOOTSTRAP_OK|svg={out}|width={args.width}|height={args.height}")


if __name__ == "__main__":
    main()
