#!/usr/bin/env python3
"""Report whether a native playback job is new, resumable, complete, or stale."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024), b''): h.update(c)
    return h.hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('cache_dir')
    ap.add_argument('--state')
    args=ap.parse_args()
    cache=Path(args.cache_dir).expanduser().resolve()
    manifest_path=cache/'geometry-cache.json'
    if not manifest_path.exists(): print(f'STATUS_FAIL|reason=missing_cache|path={manifest_path}'); return 1
    m=json.loads(manifest_path.read_text(encoding='utf-8'))
    master=Path(m.get('source',{}).get('master_svg',''))
    if not master.exists(): print('STATUS_FAIL|reason=master_missing'); return 1
    if sha256_file(master)!=m.get('source',{}).get('sha256'):
        print('STATUS_STALE|reason=master_changed|action=rebuild_cache_and_reset_generated_layer'); return 2
    state_path=Path(args.state).expanduser().resolve() if args.state else cache.parent/'playback-state.json'
    if not state_path.exists():
        print(f"STATUS_NEW|cache_id={m.get('cache_id')}|next_batch=0|total_batches={m.get('stats',{}).get('batches',0)}")
        return 0
    s=json.loads(state_path.read_text(encoding='utf-8'))
    if s.get('cache_id')!=m.get('cache_id'):
        print('STATUS_STALE|reason=state_cache_mismatch|action=reset_generated_layer'); return 2
    next_batch=int(s.get('next_batch',0)); total=int(m.get('stats',{}).get('batches',0)); status=s.get('status','unknown')
    if status=='complete' and next_batch>=total:
        print(f'STATUS_COMPLETE|next_batch={next_batch}|total_batches={total}|state={state_path}'); return 0
    print(f'STATUS_RESUMABLE|next_batch={next_batch}|remaining={max(0,total-next_batch)}|total_batches={total}|state={state_path}')
    return 0
if __name__=='__main__': sys.exit(main())
