#!/usr/bin/env python3
"""Run offline self-tests for scientific-illustrator v2 Python utilities."""
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
PYTHON = sys.executable

def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([PYTHON, *args], text=True, capture_output=True)
    if result.returncode != expect:
        raise AssertionError(f"command failed: {' '.join(args)}\nexpected={expect} got={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result

def main() -> int:
    with tempfile.TemporaryDirectory(prefix='si-v2-self-test-') as tmp:
        root=Path(tmp); work=root/'work'
        created=run(str(HERE/'prepare_job.py'), str(work)); assert 'JOB_OK' in created.stdout
        job=next(work.glob('si_job_*')); svg=job/'master.svg'
        run(str(HERE/'bootstrap_svg.py'), str(svg), '--title', 'A & B', '--width', '800', '--height', '600')
        text=svg.read_text(encoding='utf-8'); assert 'A &amp; B' in text
        rects=''.join(f'<rect id="r{i}" x="{(i%10)*60}" y="{(i//10)*45}" width="40" height="25" fill="#eef2ff" stroke="#112233" stroke-width="1"/>' for i in range(65))
        text=text.replace('<g id="artwork"></g>', '<g id="artwork">'+rects+'<path id="curve" d="M20 380 C120 300 220 460 320 380 S520 300 620 380" fill="none" stroke="#cc3300" stroke-width="3"/></g>')
        text=text.replace('<g id="labels" class="si-text"></g>', '<g id="labels" class="si-text"><text id="label" x="20" y="450" font-size="18">Input signal</text></g>')
        svg.write_text(text, encoding='utf-8')
        qa=run(str(HERE/'svg_qa.py'), str(svg), '--strict', '--playback'); assert 'QA_OK' in qa.stdout
        manifest=job/'text-manifest.json'; manifest.write_text(json.dumps({'labels':[{'id':'label-001','text':'Input signal','required':True,'count':1,'status':'resolved'}]}), encoding='utf-8')
        assert 'TEXT_QA_OK' in run(str(HERE/'text_manifest_qa.py'), str(manifest), str(svg)).stdout
        cache=job/'cache'
        out=run(str(HERE/'prepare_geometry_cache.py'), str(svg), '--cache-dir', str(cache), '--batch-size', '30'); assert 'CACHE_OK' in out.stdout
        assert 'CACHE_QA_OK' in run(str(HERE/'cache_qa.py'), str(cache), '--master-svg', str(svg), '--strict').stdout
        m=json.loads((cache/'geometry-cache.json').read_text(encoding='utf-8'))
        assert m['stats']['atoms']==67 and m['stats']['paths']==66 and m['stats']['texts']==1
        assert m['stats']['batches']>=2
        atoms=json.loads((cache/'atoms.json').read_text(encoding='utf-8'))['atoms']
        assert [a['paint_index'] for a in atoms]==list(range(len(atoms)))
        assert atoms[-1]['type']=='text' and atoms[-1]['text']=='Input signal'
        status=run(str(HERE/'playback_status.py'), str(cache)); assert 'STATUS_NEW' in status.stdout

        bad=job/'bad-marker.svg'
        bad.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><defs><marker id="a"><path d="M0 0L5 2L0 4Z"/></marker></defs><line x1="0" y1="0" x2="50" y2="50" stroke="#000" marker-end="url(#a)"/></svg>', encoding='utf-8')
        fail=run(str(HERE/'svg_qa.py'), str(bad), '--strict', '--playback', expect=1); assert 'native_playback_unsupported' in fail.stdout

        svg.write_text(svg.read_text(encoding='utf-8')+'\n', encoding='utf-8')
        stale=run(str(HERE/'cache_qa.py'), str(cache), '--master-svg', str(svg), '--strict', expect=1); assert 'master_sha256_changed_rebuild_cache' in stale.stdout
        stale_status=run(str(HERE/'playback_status.py'), str(cache), expect=2); assert 'STATUS_STALE' in stale_status.stdout
    print('SELF_TEST_OK|python_utilities=7|geometry_cache=validated|resume_contract=validated')
    return 0
if __name__=='__main__': raise SystemExit(main())
