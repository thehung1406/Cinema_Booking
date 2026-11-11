"""Export observed silver-label counts without publishing text or human identities."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--directory',default='.local/annotations/cinema-ai-assisted-v1')
    p.add_argument('--public-summary',default='docs/reports/evidence/2026-11-04-ai-labeling/summary.json')
    args=p.parse_args()
    base=Path(args.directory)
    partition=json.loads((base/'partition-manifest.json').read_text(encoding='utf-8'))
    run=base/'ai-run-v2'
    rows=[json.loads(line) for line in (run/'ai-labels.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    manifest=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    expected=set(partition['ai_train_ids'])
    assert len(rows)==len(expected) and {r['id'] for r in rows}==expected
    assert not {r['id'] for r in rows}&set(partition['blind_test_ids'])
    assert all(r.get('reviewer') is None and r.get('review_status')!='approved' for r in rows)
    for path in list((run/'batches').glob('*.json'))+list(run.glob('failed-*.json')):
        assert set(json.loads(path.read_text(encoding='utf-8'))['ids']).issubset(expected)
    silver=[r for r in rows if r['ai_decision']=='label']
    flagged=[r for r in rows if r['ai_decision']!='label']
    for name,records in [('silver-candidates.jsonl',silver),('deferred-candidates.jsonl',flagged)]:
        target=run/name
        if target.exists():
            raise ValueError('Summary outputs already exist; preserve prior snapshot')
        target.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    result=dict(observed_at=datetime.now(timezone.utc).isoformat(),stage='supplementary-ai-labeling-pilot',
        source_count=partition['source_count'],ai_processed=len(rows),ai_sentiment_labels=len(silver),
        ai_label_counts=dict(Counter(r['label'] for r in silver)),
        deferred_reasons=dict(Counter(r['ai_decision'] for r in flagged)),
        prior_human_decisions_preserved=partition['existing_human_decisions'],
        prior_human_family_rows_reserved=partition['development_family_rows'],
        blind_pilot_reserved=partition['blind_pilot_count'],blind_pilot_sent_to_ai=False,
        ai_rows_human_approved=0,accuracy_measured=False,primary_D1_admitted=False,
        failed_batch_calls_preserved=len(list(run.glob('failed-*.json'))),model=manifest['identity']['model'],
        model_digest=manifest['identity']['model_digest'],
        partition_sha256=hashlib.sha256((base/'partition-manifest.json').read_bytes()).hexdigest(),
        output_sha256=hashlib.sha256((run/'ai-labels.jsonl').read_bytes()).hexdigest(),
        note='Real review text, AI silver labels. Confidence is self-report; a 100-case pilot does not automatically meet final evaluation requirements.')
    target=Path(args.public_summary)
    if target.exists():
        raise ValueError('Use a new public snapshot; do not overwrite evidence')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
