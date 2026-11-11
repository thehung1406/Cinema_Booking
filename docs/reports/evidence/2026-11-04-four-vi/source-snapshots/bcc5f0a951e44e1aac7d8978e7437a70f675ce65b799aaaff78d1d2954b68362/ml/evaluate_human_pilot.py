"""Frozen, single-reviewer film pilot. Human labels never enter model prompts.

This is development evaluation, separate from the locked primary research test.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import random
import time

import httpx

from ml import auto_annotate as annotator
from ml.data import read_jsonl, write_jsonl, text_of, near_duplicate

LABELS=('negative','neutral','positive')
ABSTAIN='abstain'
ROOT=Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def measure(gold,predictions):
    if not gold or len(gold)!=len(predictions) or any(y not in LABELS for y in gold):
        raise ValueError('Aligned nonempty three-class human labels required')
    if any(p not in (*LABELS,ABSTAIN) for p in predictions):
        raise ValueError('Unknown model prediction')
    per_class={}
    matrix=[[0]*4 for _ in LABELS]
    for y,p in zip(gold,predictions):
        matrix[LABELS.index(y)][(*LABELS,ABSTAIN).index(p)]+=1
    for label in LABELS:
        tp=sum(y==label and p==label for y,p in zip(gold,predictions))
        fp=sum(y!=label and p==label for y,p in zip(gold,predictions))
        fn=sum(y==label and p!=label for y,p in zip(gold,predictions))
        precision=tp/(tp+fp) if tp+fp else 0.
        recall=tp/(tp+fn) if tp+fn else 0.
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.
        per_class[label]=dict(precision=precision,recall=recall,f1=f1,support=gold.count(label))
    correct=sum(y==p for y,p in zip(gold,predictions))
    covered=sum(p!=ABSTAIN for p in predictions)
    return dict(count=len(gold),correct=correct,accuracy_vs_single_reviewer=correct/len(gold),
        macro_f1=sum(v['f1'] for v in per_class.values())/3,coverage=covered/len(gold),
        covered_accuracy=correct/covered if covered else None,abstentions=len(gold)-covered,
        per_class=per_class,confusion_matrix=matrix,gold_order=list(LABELS),prediction_order=[*LABELS,ABSTAIN])


def intervals(rows,predictions,repetitions=1000):
    groups=defaultdict(list)
    for i,row in enumerate(rows):groups[row['group_id']].append(i)
    families=list(groups.values())
    randomizer=random.Random(42)
    scores=[]
    for _ in range(repetitions):
        indices=[i for _ in families for i in randomizer.choice(families)]
        scores.append(measure([rows[i]['label'] for i in indices],[predictions[i] for i in indices]))
    def bounds(key):
        values=sorted(s[key] for s in scores)
        return [values[int(.025*(len(values)-1))],values[int(.975*(len(values)-1))]]
    return dict(method='text-family bootstrap, percentile 95%, seed 42',repetitions=repetitions,
        family_count=len(families),accuracy=bounds('accuracy_vs_single_reviewer'),macro_f1=bounds('macro_f1'),
        note='Conditional descriptive interval on an enriched pilot and one reviewer; not population accuracy.')


def masked_reviews(rows):
    return [dict(id=f'r{i}',text=row['text']) for i,row in enumerate(rows)]


def prepare(base,output):
    if output.exists():raise ValueError('Choose a new frozen evaluation directory')
    gold=read_jsonl(base/'gold-pilot-human.jsonl')
    original=read_jsonl(base/'gold-pilot-pending.jsonl')
    if [(r['id'],r['text'],r['group_id']) for r in gold]!=[(r['id'],r['text'],r['group_id']) for r in original]:
        raise ValueError('Human text, IDs or groups changed')
    if not gold or any(r.get('review_status')!='approved' or r.get('label') not in LABELS or not r.get('reviewer')
        or r.get('synthetic') is not False or r.get('annotation_mode')!='blind-gold-pilot'
        or r.get('suggested_label') for r in gold):
        raise ValueError('Complete blind human decisions required; no AI hints or synthetic text')
    partition=load(base/'partition-manifest.json')
    assert {r['id'] for r in gold}==set(partition['blind_test_ids'])
    assert not {r['id'] for r in gold}&set(partition['ai_train_ids'])
    prior=load(base/'ai-run-v2/manifest.json')
    if prior['identity']['code_sha256']!=sha(annotator.__file__) or prior['system_prompt']!=annotator.SYSTEM:
        raise ValueError('Annotation protocol differs from the pre-gold labeling run')
    bank=[]
    for name in ('lr','visobert','mbert','xlmr','videberta','phobert'):
        directory=ROOT/'pipelines/ml/runs/advisor-v3/uts2017-bank'/name/'42'
        meta=load(directory/'metadata.json')
        names=['metadata.json','model.joblib'] if name=='lr' else ['metadata.json','config.json','model.safetensors','tokenizer_config.json']
        bank.append(dict(id=name,path=str(directory),backend=meta['backend'],model_version=meta['model_version'],
            seed=42,files_sha256={n:sha(directory/n) for n in names if (directory/n).is_file()}))
    output.mkdir(parents=True)
    write_jsonl(output/'human-snapshot.jsonl',gold)
    protocol=dict(created_at=datetime.now(timezone.utc).isoformat(),stage='single-reviewer-human-film-development-pilot',
        human_count=len(gold),reviewer_count=len({r['reviewer'] for r in gold}),human_label_counts=dict(Counter(r['label'] for r in gold)),
        human_sha256=sha(output/'human-snapshot.jsonl'),source_human_sha256=sha(base/'gold-pilot-human.jsonl'),
        partition_sha256=sha(base/'partition-manifest.json'),prior_annotation_manifest_sha256=sha(base/'ai-run-v2/manifest.json'),
        qwen=prior['identity'],system_prompt=prior['system_prompt'],bank_models=bank,
        decoding=dict(temperature=0,num_predict=1100,num_ctx=4096,long_text_num_ctx=8192,character_budget=4200),
        primary_metrics=['accuracy against the single reviewer, abstentions wrong','Macro F1 over all three fixed labels'],
        bank_selection='All six pre-existing baselines, seed 42, fixed before this film pilot; Bank trained, not movie fine-tuned.',
        bootstrap=dict(unit='near-duplicate text family',repetitions=1000,seed=42),
        primary_research_final_test_opened=False,pilot_consumed_for_development=True,
        code_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),Path(annotator.__file__),ROOT/'pipelines/ml/predictor.py']},
        limitations=['One human reviewer; no second-person agreement or adjudication yet.',
            'Original 600 were enriched by publisher suggestions, not naturally sampled movie reviews.',
            'Only text-family separation; no film/author IDs for film-disjoint claims.',
            'These outcomes are development evidence, not a final held-out acceptance result.',
            'Pretrained-model exposure to public source text cannot be ruled out.',
            'No automatic promotion of Bank classifiers or AI silver labels into primary D1.'])
    annotator.atomic_json(output/'protocol.json',protocol)
    return protocol


def checked(output):
    protocol=load(output/'protocol.json')
    if sha(output/'human-snapshot.jsonl')!=protocol['human_sha256']:
        raise ValueError('Frozen human snapshot changed')
    return protocol,read_jsonl(output/'human-snapshot.jsonl')


def save_metrics(output,name,rows,predictions,extra):
    assert [r['id'] for r in rows]==[r['id'] for r in predictions]
    labels=[p.get('label') or ABSTAIN for p in predictions]
    report=dict(model=name,stage='single-reviewer-human-film-development-pilot',
        **measure([r['label'] for r in rows],labels),bootstrap_95=intervals(rows,labels),**extra,
        disagreement_ids=[r['id'] for r,p in zip(rows,labels) if r['label']!=p],
        human_error_categories_reviewed=False,production_promoted=False)
    write_jsonl(output/f'{name}-predictions.jsonl',predictions)
    annotator.atomic_json(output/f'{name}-metrics.json',report)
    print(json.dumps(dict(model=name,accuracy=report['accuracy_vs_single_reviewer'],macro_f1=report['macro_f1'],coverage=report['coverage'])),flush=True)


def evaluate_qwen(output,origin):
    protocol,rows=checked(output)
    if protocol['qwen']['code_sha256']!=sha(annotator.__file__):raise ValueError('Frozen labeler code changed')
    folder=output/'qwen-traces';folder.mkdir(exist_ok=True)
    done={}
    for file in folder.glob('batch-*.json'):
        for item in load(file).get('predictions',[]):done[item['id']]=item
    queue=list(annotator.batches([r for r in rows if r['id'] not in done],protocol['qwen']['batch_size']))
    number=max([int(p.stem.split('-')[1]) for p in folder.glob('batch-*.json')],default=0)
    with httpx.Client(base_url=origin,trust_env=False,follow_redirects=False,timeout=180) as client:
        response=client.get('/api/tags');response.raise_for_status()
        runtime=next(m for m in response.json()['models'] if m['name']==protocol['qwen']['model'])
        if runtime['digest']!=protocol['qwen']['model_digest']:raise ValueError('Model digest changed')
        response=client.post('/api/chat',json=dict(model=runtime['name'],stream=False,think=False,keep_alive='5m',
            messages=[dict(role='user',content='Ready')],options=dict(num_predict=1)));response.raise_for_status()
        while queue:
            batch=queue.pop(0);number+=1
            request=dict(model=runtime['name'],stream=False,think=False,keep_alive='5m',format=annotator.schema(len(batch)),
                options=dict(temperature=0,num_predict=1100,num_ctx=4096 if sum(len(r['text']) for r in batch)<=4200 else 8192),
                messages=[dict(role='system',content=protocol['system_prompt']),dict(role='user',content=json.dumps({'reviews':masked_reviews(batch)},ensure_ascii=False))])
            trace=dict(ids=[r['id'] for r in batch],request_body=request,human_labels_in_prompt=False)
            start=time.perf_counter()
            try:
                response=client.post('/api/chat',json=request);response.raise_for_status()
                body=response.json();trace['response_content']=body['message']['content']
                parsed=annotator.validate(json.loads(trace['response_content']),len(batch))
                predictions=[dict(id=row['id'],label=parsed[f'r{i}']['label'],category=parsed[f'r{i}']['category'],
                    reason=parsed[f'r{i}']['reason'],confidence_self_report=parsed[f'r{i}']['confidence']) for i,row in enumerate(batch)]
                trace.update(state='completed',elapsed_seconds=time.perf_counter()-start,predictions=predictions)
            except (ValueError,KeyError,httpx.HTTPError) as exc:
                trace.update(state='failed',error_type=type(exc).__name__,elapsed_seconds=time.perf_counter()-start)
                annotator.atomic_json(folder/f'failed-{number:04d}.json',trace)
                if len(batch)>1:
                    queue[:0]=[[r] for r in batch];continue
                predictions=[dict(id=batch[0]['id'],label=None,category='model_error')]
                trace['predictions']=predictions
            annotator.atomic_json(folder/f'batch-{number:04d}.json',trace)
            done.update({r['id']:r for r in predictions})
            print(json.dumps(dict(qwen_predicted=len(done),total=len(rows))),flush=True)
    save_metrics(output,'qwen3-4b',rows,[done[r['id']] for r in rows],dict(model_digest=runtime['digest'],
        protocol_matches_pre_gold_run=True,gold_labels_sent_to_model=False,
        latency_note='Batch inference on local Ollama; not directly comparable to CPU single-item classifier latency.'))


def evaluate_bank(output):
    protocol,rows=checked(output)
    from ml.predictor import load_predictor, validate_scores
    import torch
    torch.set_num_threads(4)
    for model in protocol['bank_models']:
        result=output/f"{model['id']}-metrics.json"
        if result.exists():continue
        directory=Path(model['path'])
        if any(sha(directory/name)!=value for name,value in model['files_sha256'].items()):raise ValueError('Bank artifact changed')
        predictions=[]
        start=time.perf_counter()
        try:
            predict,version=load_predictor(model['backend'],str(directory))
            for row in rows:
                scores=predict(row['text']);validate_scores(scores)
                predictions.append(dict(id=row['id'],label=max(scores,key=scores.get),scores=scores))
            save_metrics(output,model['id'],rows,predictions,dict(model_version=version,trained_domain='Bank',
                movie_fine_tuned=False,seed=42,device='cpu',elapsed_seconds=time.perf_counter()-start))
        except Exception as exc:
            annotator.atomic_json(output/f"{model['id']}-unavailable.json",dict(model=model['id'],state='unavailable',error_type=type(exc).__name__))
            raise
        finally:
            load_predictor.cache_clear();gc.collect()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','qwen','bank'])
    p.add_argument('--base',default=str(ROOT/'.local/annotations/cinema-ai-assisted-v1'))
    p.add_argument('--output',default=str(ROOT/'.local/annotations/cinema-ai-assisted-v1/evaluation-v1'))
    p.add_argument('--origin',default='http://127.0.0.1:11434')
    args=p.parse_args();output=Path(args.output).resolve()
    if args.action=='prepare':
        protocol=prepare(Path(args.base),output)
        print(json.dumps(dict(human_count=protocol['human_count'],label_counts=protocol['human_label_counts'],reviewers=protocol['reviewer_count'],final_test=False)))
    elif args.action=='qwen':evaluate_qwen(output,args.origin)
    else:evaluate_bank(output)


if __name__=='__main__':main()
