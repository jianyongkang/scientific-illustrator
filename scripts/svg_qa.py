#!/usr/bin/env python3
"""Validate SVG artwork for vector-first Illustrator import."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

CONTENT_TAGS = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text"}
HIDDEN_CONTAINER_TAGS = {"defs", "clipPath", "mask", "marker", "symbol", "metadata"}
RASTER_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
RISKY_EFFECT_TAGS = {"filter", "feGaussianBlur", "feImage", "foreignObject", "script"}
URL_RE = re.compile(r"url\(([^)]+)\)", re.IGNORECASE)
STYLE_HIDE_RE = re.compile(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def is_hidden(elem: ET.Element, inherited: bool) -> bool:
    if inherited:
        return True
    name = local_name(elem.tag)
    if name in HIDDEN_CONTAINER_TAGS:
        return True
    if elem.attrib.get("display", "").strip().lower() == "none":
        return True
    if elem.attrib.get("visibility", "").strip().lower() == "hidden":
        return True
    style = elem.attrib.get("style", "")
    return bool(STYLE_HIDE_RE.search(style))


def walk(elem: ET.Element, hidden: bool = False):
    now_hidden = is_hidden(elem, hidden)
    yield elem, now_hidden
    for child in list(elem):
        yield from walk(child, now_hidden)


def href_of(elem: ET.Element) -> str:
    href = elem.attrib.get("href", "")
    if href:
        return href
    for key, value in elem.attrib.items():
        if key.endswith("href"):
            return value
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SVG for vector-first Illustrator import.")
    parser.add_argument("svg_path", help="SVG file path")
    parser.add_argument("--strict", action="store_true", help="Promote structural warnings and risky effects to failures")
    parser.add_argument("--json", action="store_true", help="Emit one JSON object instead of pipe-delimited output")
    parser.add_argument("--playback", action="store_true", help="Enforce constructs supported by native atom playback")
    args = parser.parse_args()

    svg_path = Path(args.svg_path)
    if not svg_path.exists():
        payload = {"ok": False, "reason": "missing_file", "svg": str(svg_path)}
        print(json.dumps(payload) if args.json else f"QA_FAIL|reason=missing_file|svg={svg_path}")
        return 1

    try:
        tree = ET.parse(svg_path)
    except ET.ParseError as exc:
        payload = {"ok": False, "reason": "parse_error", "detail": str(exc)}
        print(json.dumps(payload) if args.json else f"QA_FAIL|reason=parse_error|detail={exc}")
        return 1

    root = tree.getroot()
    if local_name(root.tag) != "svg":
        payload = {"ok": False, "reason": "root_not_svg"}
        print(json.dumps(payload) if args.json else "QA_FAIL|reason=root_not_svg")
        return 1

    counts: Counter[str] = Counter()
    visible_counts: Counter[str] = Counter()
    ids: Counter[str] = Counter()
    failures: list[str] = []
    warnings: list[str] = []
    raster_refs: list[str] = []
    external_refs: list[str] = []
    data_uri_hits = 0
    risky_effects: Counter[str] = Counter()
    playback_unsupported: list[str] = []

    for elem, hidden in walk(root):
        name = local_name(elem.tag)
        counts[name] += 1
        if not hidden and name in CONTENT_TAGS:
            visible_counts[name] += 1

        elem_id = elem.attrib.get("id")
        if elem_id:
            ids[elem_id] += 1

        if name == "image":
            ref = href_of(elem).strip().strip("'\"")
            raster_refs.append(ref or "<embedded-or-empty>")

        if name in RISKY_EFFECT_TAGS:
            risky_effects[name] += 1

        if args.playback and not hidden and name in {"use", "pattern", "linearGradient", "radialGradient", "clipPath", "mask", "marker", "symbol"}:
            playback_unsupported.append(f"element:{name}")
        if args.playback and name == "style" and elem.text:
            css_lower = elem.text.lower()
            if "url(" in css_lower:
                playback_unsupported.append("paint_server:css")
            for risky_css in ("marker-start", "marker-mid", "marker-end", "clip-path", "mask:", "filter:"):
                if risky_css in css_lower:
                    playback_unsupported.append("css:" + risky_css.rstrip(":"))

        if args.playback:
            for attr_name, attr_value in elem.attrib.items():
                local_attr = attr_name.rsplit("}", 1)[-1] if "}" in attr_name else attr_name
                if local_attr in {"clip-path", "mask", "filter", "marker-start", "marker-mid", "marker-end"}:
                    if str(attr_value).strip() and str(attr_value).strip().lower() != "none":
                        playback_unsupported.append(f"attr:{local_attr}")
                if local_attr in {"fill", "stroke"} and "url(" in str(attr_value).lower():
                    playback_unsupported.append(f"paint_server:{local_attr}")
            style_text = str(elem.attrib.get("style", "")).lower()
            if "url(" in style_text:
                playback_unsupported.append("paint_server:style")

        for value in elem.attrib.values():
            if not isinstance(value, str):
                continue
            lower = value.lower()
            if "data:image/" in lower:
                data_uri_hits += 1
            if lower.startswith(("http://", "https://", "file://")):
                external_refs.append(value)
            for match in URL_RE.findall(value):
                ref = match.strip().strip("'\"")
                low_ref = ref.lower()
                if low_ref.startswith("data:image/") or low_ref.endswith(RASTER_EXTENSIONS):
                    raster_refs.append(ref)
                elif low_ref and not low_ref.startswith("#"):
                    external_refs.append(ref)

    content_count = sum(visible_counts.values())
    duplicate_ids = [name for name, count in ids.items() if count > 1]

    if not root.attrib.get("viewBox"):
        warnings.append("missing_viewBox")
    if not root.attrib.get("width") or not root.attrib.get("height"):
        warnings.append("missing_explicit_dimensions")
    if counts.get("image", 0):
        failures.append(f"contains_image_tags:{counts['image']}")
    if data_uri_hits:
        failures.append(f"contains_raster_data_uri:{data_uri_hits}")
    if raster_refs and not counts.get("image", 0):
        failures.append(f"contains_raster_reference:{len(raster_refs)}")
    if external_refs:
        failures.append(f"contains_external_reference:{len(external_refs)}")
    if counts.get("foreignObject", 0):
        failures.append(f"contains_foreignObject:{counts['foreignObject']}")
    if counts.get("script", 0):
        failures.append(f"contains_script:{counts['script']}")
    if args.playback and playback_unsupported:
        unique_playback = sorted(set(playback_unsupported))
        failures.append("native_playback_unsupported:" + "+".join(unique_playback))
    if content_count == 0:
        failures.append("no_visible_drawable_content")
    if duplicate_ids:
        warnings.append(f"duplicate_ids:{len(duplicate_ids)}")

    effect_count = sum(risky_effects.values())
    if effect_count:
        warnings.append(f"risky_effects:{effect_count}")

    text_count = counts.get("text", 0)
    path_count = counts.get("path", 0)
    if text_count == 0 and path_count >= 40:
        warnings.append("no_live_text_many_paths")

    strict_promotable = {"missing_viewBox", "missing_explicit_dimensions"}
    if args.strict:
        for warning in list(warnings):
            if warning in strict_promotable or warning.startswith("duplicate_ids:") or warning.startswith("risky_effects:"):
                failures.append(warning)
                warnings.remove(warning)

    summary = {
        "path": path_count,
        "rect": counts.get("rect", 0),
        "circle": counts.get("circle", 0),
        "ellipse": counts.get("ellipse", 0),
        "line": counts.get("line", 0),
        "polyline": counts.get("polyline", 0),
        "polygon": counts.get("polygon", 0),
        "text": text_count,
        "image": counts.get("image", 0),
        "group": counts.get("g", 0),
        "visible_content": content_count,
    }

    ok = not failures
    if args.json:
        print(json.dumps({"ok": ok, "svg": str(svg_path), "summary": summary, "warnings": warnings, "failures": failures}, ensure_ascii=False))
    else:
        summary_str = "|".join(f"{k}={v}" for k, v in summary.items())
        warn_str = ",".join(warnings) if warnings else "none"
        if failures:
            print(f"QA_FAIL|svg={svg_path}|{summary_str}|warnings={warn_str}|failures={','.join(failures)}")
        else:
            print(f"QA_OK|svg={svg_path}|{summary_str}|warnings={warn_str}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
