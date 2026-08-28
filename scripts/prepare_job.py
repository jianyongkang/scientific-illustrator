#!/usr/bin/env python3
"""Create a collision-safe task workspace for scientific-illustrator."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def allocate(root: Path, prefix: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for i in range(1, 10000):
        candidate = root / f"{prefix}_{i:04d}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise SystemExit("no available job name below 10000")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a unique scientific-illustrator job workspace.")
    parser.add_argument("root", help="Parent work directory, outside the installed skill when possible")
    parser.add_argument("--prefix", default="si_job", help="Job directory prefix")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    job = allocate(root, args.prefix)
    for name in ("source", "previews", "output"):
        (job / name).mkdir()

    manifest = {
        "schema": 2,
        "job_id": job.name,
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "master_svg": "master.svg",
        "text_manifest": "text-manifest.json",
        "geometry_cache": "cache/geometry-cache.json",
        "playback_state": "playback-state.json",
        "status": "created",
    }
    (job / "job.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (job / "text-manifest.json").write_text('{\n  "labels": []\n}\n', encoding="utf-8")

    print(
        "JOB_OK"
        f"|job={job}"
        f"|master={job / 'master.svg'}"
        f"|text_manifest={job / 'text-manifest.json'}"
        f"|previews={job / 'previews'}"
        f"|output={job / 'output'}"
        f"|cache={job / 'cache'}"
        f"|playback_state={job / 'playback-state.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
