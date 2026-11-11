"""Frozen development comparison of actual character chunking variants."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from scripts.ai.evaluate_rag import evaluate


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--corpus',nargs='+',required=True)
    p.add_argument('--cases',default='pipelines/knowledge/rag-development-v2.jsonl')
    p.add_argument('--output',required=True)
    p.add_argument('--endpoint',default='http://127.0.0.1:8012')
    args=p.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('New output version required; do not overwrite evidence')
    output.mkdir(parents=True)
    variants=[(600,0),(1200,0),(1200,120)]
    protocol=dict(created_at=datetime.now(timezone.utc).isoformat(),stage='ai-authored-development',
        variants=[dict(size_characters=size,overlap_characters=overlap) for size,overlap in variants],
        strategies=['lexical','bm25','dense','hybrid','rerank'],k=3,
        input_sha256={str(path):hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in [*args.corpus,args.cases]},
        note='AI-authored queries and draft KB; no final configuration selection or independent-gold claim.')
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    rows=[]
    for size,overlap in variants:
        result=evaluate(args.corpus,args.cases,protocol['strategies'],3,args.endpoint,args.endpoint,True,size,overlap)
        (output/f'chunks-{size}-{overlap}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for run in result['runs']:
            rows.append(dict(size_characters=size,overlap_characters=overlap,strategy=run['strategy'],
                state=run['state'],**run.get('summary',{})))
        (output/'summary.json').write_text(json.dumps(dict(stage=protocol['stage'],results=rows),indent=2)+'\n',encoding='utf-8')
        print(json.dumps(dict(chunk_size=size,overlap=overlap,strategies_completed=sum(r['state']=='completed' for r in result['runs']))),flush=True)


if __name__=='__main__':
    main()
