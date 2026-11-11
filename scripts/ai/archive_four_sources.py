"""Preserve exact source variants and disclose an end-of-run hash race.

The sole historical CLI edit removed an unused segmentation argument from
normalize/LR runs. Fitting, data, hyperparameters and numerical results did not
change. Existing metadata is retained, never rewritten to conceal provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipelines'))
from ml.auto_annotate import atomic_json


def digest(raw):return hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,default=ROOT/'.local/research/four-vi-v1');args=p.parse_args()
    current={path.name:path.read_bytes() for path in (ROOT/'pipelines/ml').glob('*.py')}
    new=b"revision=model.get('revision'),preprocessing=model['preprocessing'],\n        segmenter_path=args.segmenter_path if model['preprocessing']=='vncorenlp' else None,**settings)"
    old=b"revision=model.get('revision'),preprocessing=model['preprocessing'],segmenter_path=args.segmenter_path,**settings)"
    if current['train_four_dataset.py'].count(new)!=1:raise ValueError('Historical source edit no longer matches; do not guess old code')
    legacy=dict(current);legacy['train_four_dataset.py']=current['train_four_dataset.py'].replace(new,old)
    if digest(legacy['train_four_dataset.py'])!='36256e22a0626375ea80bdef58d36474c2f2e13d22aec3f0da905a219c0aded9':
        raise ValueError('Reconstructed historical bytes do not match original run hashes')
    variants={digest(v['train_four_dataset.py']):v for v in (legacy,current)}
    archive_ids={}
    for cli,files in variants.items():
        hashes={name:digest(raw) for name,raw in sorted(files.items())}
        identifier=digest(json.dumps(hashes,sort_keys=True).encode());archive_ids[cli]=identifier
        folder=args.runs/'source-snapshots'/identifier/'ml';folder.mkdir(parents=True,exist_ok=True)
        for name,raw in files.items():
            path=folder/name
            if path.exists() and path.read_bytes()!=raw:raise ValueError('Source archive already differs')
            if not path.exists():path.write_bytes(raw)
    entries=[]
    for path in args.runs.glob('runs/*/*/*/metadata.json'):
        meta=json.loads(path.read_text(encoding='utf-8'));recorded=meta['pipeline_sha256']
        cli=recorded['train_four_dataset.py']
        if cli not in variants:raise ValueError('Unknown recorded CLI version')
        if any(digest(variants[cli][name])!=value for name,value in recorded.items()):
            raise ValueError('Archived source does not match recorded pipeline hashes')
        # For nonsegmented models the old CLI uniquely left the supplied path
        # in requested_arguments; the new CLI always supplies None. This is
        # evidence of the loaded CLI, independently of file bytes read later.
        loaded=cli
        if meta['text_preprocessing']=='normalize' and meta['requested_arguments'].get('segmenter_path'):
            loaded=digest(legacy['train_four_dataset.py'])
        note=dict(recorded_pipeline_source_snapshot_id=archive_ids[cli],
            loaded_cli_source_snapshot_id=archive_ids[loaded],recorded_cli_sha256=cli,loaded_cli_sha256=loaded,
            inference_basis='Recorded namespace segmenter_path distinguishes the two known CLI versions for nonsegmented models; both byte versions verified against actual run hashes.',
            source_hash_captured_at_completion_differs_from_loaded_cli=loaded!=cli,
            core_fitting_sha256=recorded['train_sentiment.py'],numerical_results_or_metadata_rewritten=False,
            scope='Only unused segmenter metadata argument changed for normalize models; no training/preprocessing/hyperparameter change.')
        atomic_json(path.parent/'source-provenance.json',note)
        entries.append(dict(run=path.parent.relative_to(args.runs).as_posix(),**note))
    atomic_json(args.runs/'source-provenance-summary.json',dict(runs=len(entries),
        hash_capture_races=sum(r['source_hash_captured_at_completion_differs_from_loaded_cli'] for r in entries),entries=entries,
        future_driver='Freezes source/config bytes before launching a fitting subprocess; executes only that source snapshot.'))
    print(json.dumps(dict(archived_variants=len(variants),runs=len(entries),disclosed_hash_races=sum(r['source_hash_captured_at_completion_differs_from_loaded_cli'] for r in entries))))


if __name__=='__main__':main()
