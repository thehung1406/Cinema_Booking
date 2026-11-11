"""Summarize real reviewer scores, tied to immutable actual RAG traces."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

CRITERIA = ('correctness','groundedness','citation','refusal')


def score(run_path, worksheet):
    run = json.loads(Path(run_path).read_text(encoding='utf-8'))
    cases = {r['id']: r for r in run['cases']}
    seen, ratings, pending = set(), [], []
    with Path(worksheet).open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            identifier = row['id']
            if identifier not in cases or identifier in seen:
                raise ValueError('Unknown or duplicate review ID')
            seen.add(identifier)
            case = cases[identifier]
            path = Path(case['trace_file'])
            if not path.is_absolute():
                path=Path(run_path).resolve().parent/path
            if row['trace_sha256'] != case['trace_sha256'] or hashlib.sha256(path.read_bytes()).hexdigest() != case['trace_sha256']:
                raise ValueError('Trace checksum changed; score the original frozen answer')
            trace = json.loads(path.read_text(encoding='utf-8'))
            if row['question'] != trace['question'] or row['answer'] != (trace['answer'] or ''):
                raise ValueError('Question or model answer was edited')
            reviewer = row.get('reviewer','').strip()
            values = {k: row.get(k,'').strip() for k in CRITERIA}
            if not reviewer and not any(values.values()):
                pending.append(identifier)
                continue
            if not reviewer or case['state'] != 'completed':
                raise ValueError('Named reviewer and a completed generation required')
            if any(v not in {'0','1','2','N/A'} for v in values.values()):
                raise ValueError('Each criterion requires 0, 1, 2 or explicit N/A')
            if values['correctness'] == 'N/A':
                raise ValueError('Correctness must be scored, including unjustified abstention')
            ratings.append(dict(id=identifier, reviewer=reviewer, **{k:None if v=='N/A' else int(v) for k,v in values.items()}, note=row.get('note','')))
    if seen != cases.keys():
        raise ValueError('Worksheet must retain every benchmark row')
    summary = {}
    for criterion in CRITERIA:
        observed = [r[criterion] for r in ratings if r[criterion] is not None]
        summary[criterion] = dict(scored=len(observed), mean_0_to_2=statistics.mean(observed) if observed else None)
    return dict(stage='human-scores-on-ai-authored-development-cases', total=len(cases), human_reviewed=len(ratings),
        pending=len(pending), independent_held_out_gold=False, summary=summary, ratings=ratings,
        run_sha256=hashlib.sha256(Path(run_path).read_bytes()).hexdigest(),
        worksheet_sha256=hashlib.sha256(Path(worksheet).read_bytes()).hexdigest())


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run', required=True)
    p.add_argument('--worksheet', required=True)
    p.add_argument('--output', required=True)
    args=p.parse_args()
    target=Path(args.output)
    if target.exists():
        raise ValueError('Use a new score snapshot; do not replace prior human evidence')
    report=score(args.run,args.worksheet)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='ratings'},indent=2))


if __name__=='__main__':
    main()
