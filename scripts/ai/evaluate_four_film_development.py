"""Evaluate six saved film models on the previously consumed 100-case pilot.

This never opens any official corpus test and never relabels human decisions.
"""
import argparse
import gc
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipelines'))
from ml.data import read_jsonl,fingerprint
from ml.evaluate_human_pilot import save_metrics,sha
from ml.predictor import load_predictor,validate_scores
from ml.auto_annotate import atomic_json


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,default=ROOT/'.local/research/four-vi-v1')
    args=p.parse_args();protocol=json.loads((args.runs/'protocol.json').read_text(encoding='utf-8'))
    dataset=next(d for d in protocol['config']['datasets'] if d['id']=='cinema-silver');data=ROOT/dataset['path']
    observed=fingerprint(data)
    if observed!=protocol['identity']['data_sha256']['cinema-silver']:raise ValueError('Frozen film data changed')
    rows=read_jsonl(data/'test.jsonl');output=args.runs/'film-development-evaluation';output.mkdir(exist_ok=True)
    for model in protocol['config']['models']:
        path=args.runs/'runs/cinema-silver'/model['id']/'42'
        metadata=json.loads((path/'metadata.json').read_text(encoding='utf-8'))
        if metadata['data_sha256']!=observed:raise ValueError('Wrong film artifact')
        if (output/(model['id']+'-metrics.json')).exists():
            prior=json.loads((output/(model['id']+'-metrics.json')).read_text(encoding='utf-8'))
            if prior['training_metadata_sha256']!=sha(path/'metadata.json'):raise ValueError('Completed evaluation differs')
            continue
        predictor,version=load_predictor(metadata['backend'],str(path))
        predictions=[]
        for row in rows:
            scores=predictor(row['text']);validate_scores(scores)
            predictions.append(dict(id=row['id'],label=max(scores,key=scores.get),scores=scores))
        save_metrics(output,model['id'],rows,predictions,dict(model_version=version,training_metadata_sha256=sha(path/'metadata.json'),
            supervision=dataset['supervision'],human_count=100,human_reviewer_count=1,
            evaluation_stage='previously-consumed-human-film-development-pilot',final_test=False,
            human_labels_used_for_training=False,selection_split='36 old human validation labels',inference_device='CPU'))
        del predictor;load_predictor.cache_clear();gc.collect()
    atomic_json(output/'protocol.json',dict(training_protocol_sha256=sha(args.runs/'protocol.json'),
        data_sha256=observed,human_pilot_count=len(rows),primary_final_test_opened=False,
        note='Same 100 previously used human film development decisions; not an untouched final test.'))
