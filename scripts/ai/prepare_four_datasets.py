"""Pinned Vietnamese four-corpus comparison, with explicit silver/binary scope.

No scraping, invented labels, reviewer impersonation, or corpus re-licensing.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import random
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipelines'))
from ml.data import read_jsonl,write_jsonl,text_of,near_duplicate,reviewed
from ml.auto_annotate import atomic_json
from ml.evaluate_human_pilot import sha

REVISION='4b11ec2e4e97839600e6035b49d1645c79023354'
VISFD_SOURCE='https://github.com/LuongPhan/UIT-ViSFD/tree/'+REVISION


def candidates(query,choices):
    from rapidfuzz import process,fuzz
    return (index for _,score,index in process.extract_iter(query,choices,scorer=fuzz.ratio,score_cutoff=87.999999))


def remove_overlap(rows,reference):
    texts=[text_of(r) for r in reference]
    kept=[];removed=[]
    for row in rows:
        text=text_of(row)
        if any(near_duplicate(text,texts[i]) for i in candidates(text,texts)):
            removed.append(row['id'])
        else:kept.append(row)
    return kept,removed


def families(rows):
    parent=list(range(len(rows)));texts=[text_of(r) for r in rows]
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,text in enumerate(texts):
        for j in candidates(text,texts[:i]):
            if near_duplicate(text,texts[j]):parent[root(i)]=root(j)
    groups={}
    for i,row in enumerate(rows):groups.setdefault(root(i),[]).append(row)
    for group in groups.values():
        family=hashlib.sha256('\n'.join(sorted(r['id'] for r in group)).encode()).hexdigest()
        for row in group:row['group_id']='text-family:'+family
    return list(groups.values())


def group_split(rows):
    groups=families(rows);random.Random(42).shuffle(groups)
    target={label:count for label,count in Counter(r['label'] for r in rows).items()}
    parts={name:[] for name in ('train','validation','test')};counts={name:Counter() for name in parts}
    # Whole-family allocation, including conflicting-label families; never split
    # duplicates just to force an exact stratified row count.
    for group in sorted(groups,key=len,reverse=True):
        composition=Counter(r['label'] for r in group)
        def deficit(name):
            fraction={'train':.7,'validation':.15,'test':.15}[name]
            return sum((target[label]*fraction-counts[name][label])/max(1,target[label]*fraction)*n for label,n in composition.items())
        name=max(parts,key=deficit);parts[name].extend(group);counts[name].update(composition)
    return parts


def save(directory,parts,task,manifest):
    if directory.exists():raise ValueError('Refusing to overwrite versioned corpus: '+str(directory))
    for rows in parts.values():
        if {r['label'] for r in rows}!=set(task['labels']):raise ValueError('A split is missing a declared class')
    directory.mkdir(parents=True)
    for name,rows in parts.items():write_jsonl(directory/f'{name}.jsonl',rows)
    atomic_json(directory/'task.json',task)
    manifest.update(created_at=datetime.now(timezone.utc).isoformat(),near_duplicate_threshold=.88,
        split_sha256={name:sha(directory/f'{name}.jsonl') for name in parts},
        splits={name:dict(count=len(rows),labels=dict(Counter(r['label'] for r in rows))) for name,rows in parts.items()})
    atomic_json(directory/'source_manifest.json',manifest)
    print(json.dumps(dict(dataset=directory.name,**manifest['splits'])),flush=True)


def visfd(raw,output):
    import httpx
    raw.mkdir(parents=True,exist_ok=True)
    with httpx.Client(timeout=120,follow_redirects=True) as client:
        for name in ('README.md','UIT-ViSFD.zip'):
            path=raw/name
            response=client.get(f'https://raw.githubusercontent.com/LuongPhan/UIT-ViSFD/{REVISION}/{name}')
            response.raise_for_status()
            if path.exists() and path.read_bytes()!=response.content:raise ValueError('Pinned source changed')
            path.write_bytes(response.content)
    archive=zipfile.ZipFile(raw/'UIT-ViSFD.zip');parts={};excluded={};original={}
    for name,member in [('train','Train.csv'),('validation','Dev.csv'),('test','Test.csv')]:
        records=list(csv.DictReader(io.StringIO(archive.read(member).decode('utf-8-sig'))));original[name]=len(records)
        rows=[];excluded[name]=[]
        for i,row in enumerate(records):
            labels=re.findall(r'\{GENERAL#([^}]+)\}',row['label'])
            identifier=f'uit-visfd:{member}:{i}'
            if not labels:excluded[name].append(identifier);continue
            if len(labels)!=1 or labels[0] not in ('Negative','Neutral','Positive'):raise ValueError('Unexpected GENERAL label')
            text=row['comment']
            rows.append(dict(id=identifier,text=text,label=labels[0].lower(),group_id='visfd:'+hashlib.sha256(text_of({'text':text}).encode()).hexdigest(),
                source=VISFD_SOURCE,license='Author permits non-commercial research; no SPDX license specified',
                reviewer='external-publisher:LuongPhan/UIT-ViSFD',review_status='approved',synthetic=False,
                annotation_origin='publisher-human-GENERAL-aspect',original_split=name))
        parts[name]=rows
    parts['validation'],dev_removed=remove_overlap(parts['validation'],parts['test'])
    parts['train'],train_removed=remove_overlap(parts['train'],parts['validation']+parts['test'])
    save(output,parts,dict(labels=['negative','neutral','positive'],task='GENERAL-aspect-polarity',language='vi',
        supervision='publisher-human',scope='Only explicitly annotated GENERAL aspect; other aspects are not collapsed; absent GENERAL is excluded, never neutral.'),
        dict(source=VISFD_SOURCE,revision=REVISION,archive_sha256=sha(raw/'UIT-ViSFD.zip'),readme_sha256=sha(raw/'README.md'),
        permission_evidence='Author README abstract: freely available for research purposes; commercial contact separately required.',
        license_spdx=None,original_counts=original,excluded_absent_GENERAL_ids=excluded,
        validation_removed_matching_test=dev_removed,train_removed_matching_validation_or_test=train_removed,
        test_preserved='All publisher test rows with an explicit GENERAL label; original labels and order preserved.',
        rating_used_for_labels=False))


def shopee(raw,output):
    source=load_json(raw/'source-manifest.json')
    if sha(raw/'source.zip')!=source['archive_sha256']:raise ValueError('Source archive SHA mismatch')
    archive=zipfile.ZipFile(raw/'source.zip');member='shopee_reviews_dataset.jsonl'
    records=[json.loads(line) for line in archive.read(member).decode('utf-8-sig').splitlines() if line.strip()]
    rows=[]
    for i,row in enumerate(records):
        if row['label'] not in ('negative','positive'):raise ValueError('Unexpected publisher label')
        rows.append(dict(id=f'shopee:v1:{i}',text=row['review'],label=row['label'],group_id='',source=source['source'],
            license='Apache-2.0 (publisher dataset card; underlying platform rights not independently verified)',
            reviewer='external-publisher:dduongdev',review_status='approved',synthetic=False,
            annotation_origin='publisher-semantic-label-method-not-independently-verified'))
    save(output,group_split(rows),dict(labels=['negative','positive'],task='binary-sentiment',language='vi',supervision='publisher-labels',
        scope='Original review file only; no unaccented augmentation, artificial neutral, or rating-to-label mapping.'),
        dict(source=source['source'],version=source['version'],archive_sha256=source['archive_sha256'],
        member=member,original_count=len(records),publisher_method='Card says semantic-content labels; per-row human-vs-model status unspecified.',
        license_spdx='Apache-2.0',seed=42,split_policy='70/15/15 approximate by whole exact/near text family'))


def cinema(base,output):
    from ml.train_film_silver_pilot import validate_inputs
    from ml.evaluate_human_pilot import checked
    protocol,pilot=checked(base/'evaluation-v1')
    train=read_jsonl(base/'ai-run-v2/silver-candidates.jsonl');validation=read_jsonl(base/'existing-human-decisions.jsonl')
    validate_inputs(train,validation,pilot)
    save(output,dict(train=train,validation=validation,test=pilot),dict(labels=['negative','neutral','positive'],
        task='film-sentiment-weak-supervision',language='vi',supervision='AI-silver-train-human-development-evaluation',
        scope='426 unreviewed AI train labels, 36 earlier human validation decisions, 100 single-reviewer human development evaluation; NOT a final untouched test.',
        evaluation_stage='previously-consumed-development-pilot',production_eligible=False),
        dict(source='https://github.com/AlyThien/ViMovieABSA-A-Vietnamese-Aspect-Based-Sentiment-Dataset-for-Movie-Reviews-with-Reliability-Decompos',
        revision='2ceae3b15ece8f9a6c24f7b73465d940b0f8ce18',human_snapshot_sha256=protocol['human_sha256'],
        license_spdx='CC-BY-4.0 (publisher)',human_reviewer_count=1,primary_human_gold_D1_admitted=False,
        partition_sha256=protocol['partition_sha256'],annotation_model='qwen3:4b',annotation_model_digest=protocol['qwen']['model_digest'],
        labels_are_unchanged=True,reviewer_names_private=True))


def load_json(path):return json.loads(path.read_text(encoding='utf-8'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',choices=['visfd','shopee','cinema'])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--raw',type=Path)
    args=p.parse_args()
    if args.dataset=='visfd':visfd(args.raw or ROOT/'.local/datasets/uit-visfd-v1',args.output)
    elif args.dataset=='shopee':shopee(args.raw or ROOT/'.local/datasets/kaggle-shopee-v1',args.output)
    else:cinema(args.raw or ROOT/'.local/annotations/cinema-ai-assisted-v1',args.output)
