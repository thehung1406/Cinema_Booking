"""One explicitly scoped four-corpus training run, with honest silver admission."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from ml.data import read_jsonl,reviewed,text_of,near_duplicate,fingerprint
from ml.task_spec import label_order
from ml.dataset_audit import audit
from ml.train_sentiment import train_prepared

ROOT=Path(__file__).resolve().parents[2]


def validate(directory,supervision):
    from rapidfuzz import fuzz,process
    rows={name:read_jsonl(directory/f'{name}.jsonl') for name in ('train','validation','test')}
    if supervision=='AI-silver-train-human-development-evaluation':
        from ml.train_film_silver_pilot import validate_inputs
        validate_inputs(rows['train'],rows['validation'],rows['test'])
        task=json.loads((directory/'task.json').read_text(encoding='utf-8'))
        if task.get('supervision')!=supervision or task.get('evaluation_stage')!='previously-consumed-development-pilot':
            raise ValueError('Missing explicit silver/development declaration')
    else:
        report=audit(directory)
        if not report['admissible']:raise ValueError('; '.join(report['problems']))
    for left,right in [('train','validation'),('train','test'),('validation','test')]:
        a,b=rows[left],rows[right]
        if {r['id'] for r in a}&{r['id'] for r in b} or {r['group_id'] for r in a}&{r['group_id'] for r in b}:
            raise ValueError('Cross-split ID/group leakage')
        texts=[text_of(r) for r in b]
        for row in a:
            text=text_of(row)
            for candidate,score,index in process.extract_iter(text,texts,scorer=fuzz.ratio,score_cutoff=87.999999):
                if near_duplicate(text,candidate):raise ValueError('Cross-split near-duplicate leakage')
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--dataset',required=True);p.add_argument('--model',required=True)
    p.add_argument('--output',required=True);p.add_argument('--batch-size',type=int)
    p.add_argument('--segmenter-path');p.add_argument('--seed',type=int,default=42)
    args=p.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8'))
    dataset=next(d for d in config['datasets'] if d['id']==args.dataset)
    model=next(m for m in config['models'] if m['id']==args.model)
    directory=ROOT/dataset['path']
    if list(label_order(directory))!=dataset['labels']:raise ValueError('Config/data labels differ')
    if args.seed not in config['seeds']:raise ValueError('Seed not in frozen protocol')
    rows=validate(directory,dataset['supervision'])
    settings=dict(config['training'])
    if args.batch_size:
        if args.batch_size not in [settings['batch_size'],*config['oom_fallback_batch_sizes']]:raise ValueError('Undeclared batch size')
        effective=settings['batch_size']*settings['gradient_accumulation_steps']
        settings['batch_size']=args.batch_size;settings['gradient_accumulation_steps']=effective//args.batch_size
    training_args=SimpleNamespace(data=str(directory),output=args.output,seed=args.seed,
        backend=model.get('backend','transformers'),model=model.get('checkpoint','tfidf-logistic-regression'),
        revision=model.get('revision'),preprocessing=model['preprocessing'],
        segmenter_path=args.segmenter_path if model['preprocessing']=='vncorenlp' else None,**settings)
    train_prepared(training_args,rows,supervision=dataset['supervision'])
