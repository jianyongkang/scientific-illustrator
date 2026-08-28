#!/usr/bin/env python3
"""Validate geometry-cache integrity, source freshness, batch coverage, and ordering."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('cache_dir')
    ap.add_argument('--master-svg')
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()
    root = Path(args.cache_dir).expanduser().resolve()
    manifest_path = root / 'geometry-cache.json'
    failures, warnings = [], []
    if not manifest_path.exists():
        print(f"CACHE_QA_FAIL|reason=missing_manifest|path={manifest_path}")
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f"CACHE_QA_FAIL|reason=manifest_parse|detail={exc}")
        return 1
    if manifest.get('schema') != 2: failures.append('schema_not_2')
    cache_id = manifest.get('cache_id', '')
    batches = manifest.get('batches', [])
    if not isinstance(batches, list) or not batches: failures.append('no_batches')
    expected_paint = 0
    seen_ids = set()
    total_atoms = 0
    for expected_index, meta in enumerate(batches if isinstance(batches, list) else []):
        if meta.get('index') != expected_index: failures.append(f'noncontiguous_batch_index:{expected_index}')
        batch_path = root / str(meta.get('file', ''))
        if not batch_path.exists(): failures.append(f'missing_batch_file:{expected_index}'); continue
        try: payload = json.loads(batch_path.read_text(encoding='utf-8'))
        except Exception: failures.append(f'bad_batch_json:{expected_index}'); continue
        if payload.get('cache_id') != cache_id: failures.append(f'cache_id_mismatch:{expected_index}')
        atoms = payload.get('atoms', [])
        if len(atoms) != payload.get('atom_count') or len(atoms) != meta.get('atom_count'): failures.append(f'atom_count_mismatch:{expected_index}')
        if args.strict and len(atoms) > 1 and not (20 <= len(atoms) <= 50):
            if expected_index not in {0, len(batches)-1}: warnings.append(f'nonstandard_batch_size:{expected_index}:{len(atoms)}')
        for atom in atoms:
            atom_id = atom.get('id')
            if atom_id in seen_ids: failures.append(f'duplicate_atom_id:{atom_id}')
            seen_ids.add(atom_id)
            if atom.get('paint_index') != expected_paint: failures.append(f'paint_gap:{expected_paint}')
            expected_paint += 1; total_atoms += 1
            if atom.get('type') not in {'path','text'}: failures.append(f'unsupported_atom_type:{atom.get("type")}')
            if atom.get('type') == 'path':
                subpaths = atom.get('subpaths', [])
                if not subpaths: failures.append(f'empty_path_atom:{atom_id}')
                for sp in subpaths:
                    if len(sp.get('points', [])) < 2: failures.append(f'degenerate_subpath:{atom_id}')
    stats_atoms = manifest.get('stats', {}).get('atoms')
    if stats_atoms != total_atoms: failures.append(f'total_atom_mismatch:{stats_atoms}:{total_atoms}')
    master = Path(args.master_svg).expanduser().resolve() if args.master_svg else Path(manifest.get('source', {}).get('master_svg',''))
    if master and master.exists():
        current = sha256_file(master)
        if current != manifest.get('source', {}).get('sha256'): failures.append('master_sha256_changed_rebuild_cache')
    else:
        warnings.append('master_not_checked')
    ok = not failures
    if ok:
        print(f"CACHE_QA_OK|cache={root}|cache_id={cache_id}|atoms={total_atoms}|batches={len(batches)}|warnings={','.join(warnings) if warnings else 'none'}")
        return 0
    print(f"CACHE_QA_FAIL|cache={root}|failures={','.join(failures)}|warnings={','.join(warnings) if warnings else 'none'}")
    return 1

if __name__ == '__main__':
    sys.exit(main())
