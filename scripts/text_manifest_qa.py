#!/usr/bin/env python3
"""Validate required text-manifest labels against live text in an SVG."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

WS_RE = re.compile(r"\s+")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def normalize(text: str) -> str:
    return WS_RE.sub(" ", text or "").strip()


def collect_live_text(svg_path: Path) -> list[str]:
    root = ET.parse(svg_path).getroot()
    values: list[str] = []
    for elem in root.iter():
        if local_name(elem.tag) == "text":
            value = normalize("".join(elem.itertext()))
            if value:
                values.append(value)
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Check required manifest labels against SVG live text.")
    parser.add_argument("manifest_path")
    parser.add_argument("svg_path")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_path)
    svg_path = Path(args.svg_path)
    if not manifest_path.is_file():
        print(f"TEXT_QA_FAIL|reason=missing_manifest|path={manifest_path}")
        return 1
    if not svg_path.is_file():
        print(f"TEXT_QA_FAIL|reason=missing_svg|path={svg_path}")
        return 1

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"TEXT_QA_FAIL|reason=manifest_parse_error|detail={exc}")
        return 1

    labels = data.get("labels")
    if not isinstance(labels, list):
        print("TEXT_QA_FAIL|reason=labels_not_list")
        return 1

    failures: list[str] = []
    required: Counter[str] = Counter()
    unresolved = 0
    seen_ids: set[str] = set()

    for index, item in enumerate(labels, start=1):
        if not isinstance(item, dict):
            failures.append(f"label_{index}_not_object")
            continue
        label_id = str(item.get("id", f"label-{index:03d}"))
        if label_id in seen_ids:
            failures.append(f"duplicate_id:{label_id}")
        seen_ids.add(label_id)
        status = str(item.get("status", "resolved")).lower()
        is_required = bool(item.get("required", True))
        count = item.get("count", 1)
        if not isinstance(count, int) or count < 1:
            failures.append(f"bad_count:{label_id}")
            continue
        if status == "unresolved":
            unresolved += 1
            continue
        text = normalize(str(item.get("text", "")))
        if is_required and not text:
            failures.append(f"empty_required_text:{label_id}")
        elif is_required:
            required[text] += count

    try:
        live_values = collect_live_text(svg_path)
    except ET.ParseError as exc:
        print(f"TEXT_QA_FAIL|reason=svg_parse_error|detail={exc}")
        return 1

    actual = Counter(live_values)
    missing: list[str] = []
    for text, needed in required.items():
        have = actual[text]
        if have < needed:
            missing.append(f"{text!r}:{have}/{needed}")

    failures.extend(f"missing:{item}" for item in missing)
    if failures:
        print(
            f"TEXT_QA_FAIL|manifest={manifest_path}|svg={svg_path}"
            f"|required={sum(required.values())}|live_text_nodes={len(live_values)}"
            f"|unresolved={unresolved}|failures={';'.join(failures)}"
        )
        return 1

    print(
        f"TEXT_QA_OK|manifest={manifest_path}|svg={svg_path}"
        f"|required={sum(required.values())}|live_text_nodes={len(live_values)}"
        f"|unresolved={unresolved}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
