#!/usr/bin/env python3
"""Verify scientific-illustrator output files exist and have plausible signatures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"
PDF_SIG = b"%PDF-"
AI_SIGNATURES = (b"%PDF-", b"%!PS-Adobe-")


def check_file(label: str, value: str | None, min_bytes: int, signatures: tuple[bytes, ...] | None = None):
    if not value:
        return None
    path = Path(value)
    if not path.exists():
        return False, f"{label}:missing:{path}"
    if not path.is_file():
        return False, f"{label}:not_file:{path}"
    size = path.stat().st_size
    if size < min_bytes:
        return False, f"{label}:too_small:{size}:{path}"
    if signatures:
        max_len = max(len(sig) for sig in signatures)
        with path.open("rb") as fh:
            head = fh.read(max_len)
        if not any(head.startswith(sig) for sig in signatures):
            return False, f"{label}:bad_signature:{path}"
    return True, f"{label}:ok:{size}:{path}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify AI/PDF/PNG deliverables.")
    parser.add_argument("--ai", help="AI working-copy path")
    parser.add_argument("--pdf", help="PDF path")
    parser.add_argument("--png", help="PNG preview path")
    args = parser.parse_args()

    if not any((args.ai, args.pdf, args.png)):
        parser.error("provide at least one of --ai, --pdf, or --png")

    results = [
        check_file("ai", args.ai, 1024, AI_SIGNATURES),
        check_file("pdf", args.pdf, 512, (PDF_SIG,)),
        check_file("png", args.png, 128, (PNG_SIG,)),
    ]
    results = [r for r in results if r is not None]
    failures = [detail for ok, detail in results if not ok]
    details = "|".join(detail for _, detail in results)

    if failures:
        print(f"OUTPUT_QA_FAIL|{details}")
        return 1

    print(f"OUTPUT_QA_OK|{details}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
