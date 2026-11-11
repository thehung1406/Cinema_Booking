"""Share labels/IDs, not review text or real reviewer names; restore pinned text.

Human pseudonyms refer only to people already present in confirmed source data.
No model output is assigned a human pseudonym or an approved status.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipelines'))
from ml.data import read_jsonl,write_jsonl,reviewed
from ml.auto_annotate import atomic_json
from ml.evaluate_human_pilot import sha

SOURCE_URL='https://raw.githubusercontent.com/AlyThien/ViMovieABSA-A-Vietnamese-Aspect-Based-Sentiment-Dataset-for-Movie-Reviews-with-Reliability-Decompos/2ceae3b15ece8f9a6c24f7b73465d940b0f8ce18/final_dataset.csv'
SOURCE_SHA='1cd36b495b42878a56e10ce1afd97e82a75cfb319f447ca8a9a49d938865d811'


def semantic_sha(rows):
    payload=[{key:r[key] for key in ('id','text','label','group_id')} for r in rows]
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def export(directory,output):
    parts={name:read_jsonl(directory/f'{name}.jsonl') for name in ('train','validation','test')}
    for name in ('validation','test'):reviewed(parts[name])
    identities=sorted({r['reviewer'] for name in ('validation','test') for r in parts[name]})
    mapping={name:f'confirmed-human-pseudonym-{i+1}' for i,name in enumerate(identities)}
    exported={}
    for name,rows in parts.items():
        values=[]
        for r in rows:
            silver=name=='train'
            if silver and (r.get('reviewer') or r.get('review_status')!='ai_labeled_unreviewed'):raise ValueError('Silver must stay unreviewed')
            item={key:r[key] for key in ('id','label','group_id','source','license','synthetic','annotation_origin','review_status')}
            item.update(source_row=int(r['id'].rsplit(':',1)[1]),text_sha256=hashlib.sha256(r['text'].encode()).hexdigest(),
                reviewer=None if silver else mapping[r['reviewer']])
            if silver:item.update(ai_label=r['ai_label'],annotation_mode='ai-assisted',suggestion_model=r['suggestion_model'],suggestion_model_digest=r['suggestion_model_digest'])
            values.append(item)
        exported[name]=values
    pack=dict(source_url=SOURCE_URL,source_sha256=SOURCE_SHA,labels=exported,
        semantic_sha256={name:semantic_sha(rows) for name,rows in parts.items()},
        original_private_file_sha256={name:sha(directory/f'{name}.jsonl') for name in parts},
        task=json.loads((directory/'task.json').read_text(encoding='utf-8')),
        source_manifest=json.loads((directory/'source_manifest.json').read_text(encoding='utf-8')),
        note='Label-only snapshot of actual earlier annotations. Human identifiers are pseudonyms for confirmed source reviewers, never AI-generated human approval. Original private file hashes and model input semantic hashes have different purposes; restoring omits names/notes/timestamps and therefore changes whole-file hashes.')
    atomic_json(output,pack)
    print(json.dumps(dict(rows=sum(len(r) for r in parts.values()),raw_text_exported=False,real_names_exported=False,output=str(output))))


def restore(pack_path,output,source_csv=None):
    if output.exists():raise ValueError('Choose a new directory; never overwrite annotations')
    pack=json.loads(pack_path.read_text(encoding='utf-8'))
    if pack['source_url']!=SOURCE_URL or pack['source_sha256']!=SOURCE_SHA:raise ValueError('Unexpected source')
    if source_csv:raw=source_csv.read_bytes()
    else:
        import httpx
        response=httpx.get(SOURCE_URL,timeout=120,follow_redirects=True);response.raise_for_status();raw=response.content
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise ValueError('Pinned raw source SHA mismatch')
    original=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));parts={}
    for name,records in pack['labels'].items():
        rows=[]
        for record in records:
            row=record.copy();text=original[row.pop('source_row')]['text'];expected=row.pop('text_sha256')
            if hashlib.sha256(text.encode()).hexdigest()!=expected:raise ValueError('Source text differs from annotated text')
            row['text']=text;rows.append(row)
        if semantic_sha(rows)!=pack['semantic_sha256'][name]:raise ValueError('Model inputs or grouping changed')
        if name!='train':reviewed(rows)
        elif any(r.get('reviewer') or r['review_status']!='ai_labeled_unreviewed' for r in rows):raise ValueError('Silver approval altered')
        parts[name]=rows
    output.mkdir(parents=True)
    for name,rows in parts.items():write_jsonl(output/f'{name}.jsonl',rows)
    atomic_json(output/'task.json',pack['task']);atomic_json(output/'source_manifest.json',pack['source_manifest'])
    atomic_json(output/'reproduction_manifest.json',dict(label_pack_sha256=sha(pack_path),semantic_sha256=pack['semantic_sha256'],
        raw_source_sha256=SOURCE_SHA,human_identifiers='Pseudonyms for original confirmed people; no reviewer names, notes or timestamps restored.',
        bitwise_original_private_jsonl_identical=False,model_inputs_labels_grouping_and_order_identical=True))
    print(json.dumps(dict(output=str(output),semantic_inputs_verified=True)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['export','restore'])
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source-csv',type=Path)
    args=p.parse_args()
    if args.action=='export':export(args.input,args.output)
    else:restore(args.input,args.output,args.source_csv)
