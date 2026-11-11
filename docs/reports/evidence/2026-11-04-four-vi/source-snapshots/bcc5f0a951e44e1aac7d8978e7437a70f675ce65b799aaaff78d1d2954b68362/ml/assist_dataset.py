"""Reserve a blind pilot before AI labeling; preserve every existing human decision."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random

from ml.data import near_duplicate, read_jsonl, text_of, write_jsonl


def prepare(source, output, human_work=None, target=100, seed=20261104):
    output=Path(output)
    if output.exists():
        raise ValueError('Choose a new version; existing human work must never be overwritten')
    rows=read_jsonl(source)
    if not 1<=target<len(rows)-50:
        raise ValueError('Positive blind pilot size and a separate training pool required')
    if len({r['id'] for r in rows})!=len(rows) or any(r.get('synthetic') is not False for r in rows):
        raise ValueError('Real-text source with unique IDs required')
    originals={r['id']:r for r in rows}
    humans=[]
    if human_work and not Path(human_work).is_file():
        raise ValueError('Specified human work is missing; omit the option only when there is no prior human work')
    if human_work and Path(human_work).exists():
        for row in read_jsonl(human_work):
            if row['id'] not in originals or row['text']!=originals[row['id']]['text']:
                raise ValueError('Human work differs from the original source')
            if row.get('review_status')=='approved':
                if not row.get('reviewer') or row.get('label') not in {'negative','neutral','positive'}:
                    raise ValueError('Invalid existing human decision')
                humans.append(row)
    # Whole near-duplicate families stay together. Decisions do not affect grouping.
    parent=list(range(len(rows)))
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    texts=[text_of(row) for row in rows]
    for i in range(len(rows)):
        for j in range(i):
            if rows[i]['group_id']==rows[j]['group_id'] or near_duplicate(texts[i],texts[j]):
                parent[find(i)]=find(j)
    families={}
    for i,row in enumerate(rows):
        families.setdefault(find(i),[]).append(row)
    human_ids={r['id'] for r in humans}
    development,eligible=[],[]
    for family in families.values():
        (development if any(r['id'] in human_ids for r in family) else eligible).append(family)
    random.Random(seed).shuffle(eligible)
    holdout,train=[],[]
    for family in eligible:
        (holdout if len(holdout)<target else train).extend(family)
    if len(holdout)<target or len(train)<50:
        raise ValueError('Not enough independent families for the requested pilot')
    def clean(grouped,mode):
        result=[]
        for row in grouped:
            family=families[find(next(i for i,r in enumerate(rows) if r['id']==row['id']))]
            group_hash=hashlib.sha256('\n'.join(sorted(r['id'] for r in family)).encode()).hexdigest()
            result.append({k:row[k] for k in ('id','text','source','license','synthetic')} | dict(
                group_id='assist-family:'+group_hash,original_group_id=row['group_id'],
                label=None,reviewer=None,review_status='pending',annotation_mode=mode,
                annotation_origin='pending-human-blind-pilot' if mode=='blind-gold-pilot' else 'pending-ai-labeling'))
        return result
    blind=clean(holdout,'blind-gold-pilot')
    silver=clean(train,'ai-assisted')
    assert not {r['group_id'] for r in blind}&{r['group_id'] for r in silver}
    output.mkdir(parents=True)
    write_jsonl(output/'train-ai-pending.jsonl',silver)
    write_jsonl(output/'gold-pilot-pending.jsonl',blind)
    write_jsonl(output/'existing-human-decisions.jsonl',humans)
    manifest=dict(created_at=datetime.now(timezone.utc).isoformat(),stage='supplementary-silver-label-pilot-not-primary-D1',
        source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),source_count=len(rows),seed=seed,
        existing_human_decisions=len(humans),development_family_rows=sum(map(len,development)),
        ai_train_candidates=len(silver),blind_pilot_count=len(blind),near_duplicate_threshold=.88,
        split_policy='Whole exact/near-duplicate text families; existing human decisions and their families excluded from AI training and new pilot.',
        blind_test_ids=[r['id'] for r in blind],ai_train_ids=[r['id'] for r in silver],
        limitations=['The original 600 were enriched by publisher-suggested class, not naturally distributed.',
            'Film/author identifiers are absent; no claim of film-disjoint evaluation.',
            '100 is a development pilot target, not a guaranteed final evaluation sample size.',
            'AI labels are silver; no human reviewer or primary benchmark admission is invented.'])
    (output/'partition-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument('input')
    p.add_argument('--output',required=True)
    p.add_argument('--human-work')
    p.add_argument('--holdout',type=int,default=100)
    args=p.parse_args()
    result=prepare(args.input,args.output,args.human_work,args.holdout)
    print(json.dumps({k:v for k,v in result.items() if not k.endswith('_ids')},indent=2))


if __name__=='__main__':
    main()
