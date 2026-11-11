"""Actual RAG IN/OUT on AI-authored development cases; human scores stay blank."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import time

import httpx
from sqlalchemy import create_engine
from sqlmodel import Session

from ai_service.config import Settings
from ai_service.llm import grounded_answer
from ai_service.models import Base
from ai_service.rag import retrieve, upsert_document
from ai_service.schemas import DocumentWrite
from ml.data import read_jsonl
from scripts.ai.evaluate_rag import measure


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(corpus, cases_file, output, strategy, embedding_url, reranker_url):
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new benchmark directory; previous evidence must remain intact")
    cases = read_jsonl(cases_file)
    if not cases or len({q['id'] for q in cases}) != len(cases):
        raise ValueError("Nonempty, unique development case IDs required")
    if any(q.get('annotation_origin') != 'ai-authored-development' or not q.get('synthetic') for q in cases):
        raise ValueError("This runner is for explicitly AI-authored development cases, not independent gold")
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', llm_provider='ollama', llm_timeout_seconds=20)
    output.mkdir(parents=True)
    (output / 'traces').mkdir()
    dependencies = [('embedding', embedding_url)] if strategy in {'dense','hybrid','rerank'} else []
    if strategy == 'rerank':
        dependencies.append(('reranker', reranker_url))
    runtime = {}
    with httpx.Client(timeout=180, trust_env=False) as client:
        for name, origin in dependencies:
            response = client.get(origin.rstrip('/') + '/health/ready')
            response.raise_for_status()
            runtime[name] = response.json()
        response = client.get(settings.llm_base_url + '/api/tags')
        response.raise_for_status()
        runtime['model'] = next({'name':m['name'], 'digest':m['digest']} for m in response.json()['models'] if m['name'] == settings.llm_model)
        start = time.perf_counter()
        response = client.post(settings.llm_base_url + '/api/chat', json=dict(model=settings.llm_model,
            messages=[dict(role='user', content='Ready')], options=dict(num_predict=1), think=False, stream=False, keep_alive='5m'))
        response.raise_for_status()
        runtime['llm_warmup_ms'] = (time.perf_counter()-start)*1000
    report = dict(stage='ai-authored-development-not-independent-gold', created_at=datetime.now(timezone.utc).isoformat(),
        approval='Draft sources temporarily enabled only in SQLite RAM', strategy=strategy, k=3,
        runtime=runtime, input_sha256={str(p):digest(p) for p in [*corpus, cases_file]},
        code_sha256={str(p):digest(p) for p in [Path(__file__), Path('services/ai-service/src/ai_service/llm.py'),
            Path('services/ai-service/src/ai_service/rag.py'), Path('services/ai-service/src/ai_service/grounding.py'),
            Path('services/ai-service/src/ai_service/schemas.py')]},
        human_evaluated=False, planned=len(cases), cases=[])
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            for path in corpus:
                for draft in json.loads(Path(path).read_text(encoding='utf-8')):
                    validated = DocumentWrite.model_validate({k:v for k,v in draft.items() if k != 'approved'}).model_dump()
                    upsert_document(db, validated | {'approved': True})
            start = time.perf_counter()
            retrieve(db, cases[0]['question'], scope=cases[0]['scope'], strategy=strategy, embedding_url=embedding_url, reranker_url=reranker_url)
            report['retrieval_warmup_ms'] = (time.perf_counter()-start)*1000
            for q in cases:
                start = time.perf_counter()
                item = dict(id=q['id'], question=q['question'], scope=q['scope'], expected_answerable_development=q['expected_answerable'],
                    state='running', sources=[], answer=None, generation_trace={})
                try:
                    sources = retrieve(db, q['question'], scope=q['scope'], strategy=strategy, embedding_url=embedding_url, reranker_url=reranker_url)
                    item['retrieval_ms'] = (time.perf_counter()-start)*1000
                    item['sources'] = sources
                    item['retrieval_metrics_development'] = measure(sources, q['expected'], 3)
                    item['answer'] = grounded_answer(settings, q['question'], sources, trace=item['generation_trace']) if sources else ''
                    item['state'] = 'completed'
                    item['citation_ids_validated'] = bool(item['answer'])
                    item['abstained'] = not bool(item['answer'])
                except Exception as exc:
                    item.update(state='failed', error_type=type(exc).__name__)
                item['elapsed_ms'] = (time.perf_counter()-start)*1000
                trace_path = output / 'traces' / (q['id'] + '.json')
                trace_path.write_text(json.dumps(item, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                report['cases'].append(dict(id=q['id'], state=item['state'], trace_file=str(trace_path.resolve()), trace_sha256=digest(trace_path),
                    elapsed_ms=item['elapsed_ms'], expected_answerable_development=q['expected_answerable'], abstained=item.get('abstained')))
                (output / 'run.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
                print(json.dumps({k:item.get(k) for k in ['id','state','abstained','elapsed_ms']}), flush=True)
        completed = [r for r in report['cases'] if r['state'] == 'completed']
        negatives = [r for r in completed if not r['expected_answerable_development']]
        positives = [r for r in completed if r['expected_answerable_development']]
        report['summary'] = dict(completed=len(completed), failed=len(cases)-len(completed),
            latency_ms_median=statistics.median(r['elapsed_ms'] for r in completed) if completed else None,
            latency_ms_p95=sorted(r['elapsed_ms'] for r in completed)[max(0, __import__('math').ceil(len(completed)*.95)-1)] if completed else None,
            unanswerable_development_abstention_rate=sum(r['abstained'] for r in negatives)/len(negatives) if negatives else None,
            answerable_development_answer_rate=sum(not r['abstained'] for r in positives)/len(positives) if positives else None,
            note='Rates use AI-authored expectations only; answer presence and valid citation IDs do not establish factual correctness.')
        (output / 'run.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        fields = ['id','trace_sha256','question','answer','sources','reviewer','correctness','groundedness','citation','refusal','note']
        with (output / 'human-review.csv').open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in report['cases']:
                trace = json.loads(Path(row['trace_file']).read_text(encoding='utf-8'))
                writer.writerow(dict(id=row['id'], trace_sha256=row['trace_sha256'], question=trace['question'], answer=trace['answer'] or '',
                    sources='\n'.join(s['url'] for s in trace['sources']), **{key:'' for key in fields[5:]}))
        return report
    finally:
        engine.dispose()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--corpus', nargs='+', required=True)
    p.add_argument('--cases', default='pipelines/knowledge/rag-development-v2.jsonl')
    p.add_argument('--output', required=True)
    p.add_argument('--strategy', choices=['lexical','bm25','dense','hybrid','rerank'], default='rerank')
    p.add_argument('--embedding-url', default='http://127.0.0.1:8012')
    p.add_argument('--reranker-url', default='http://127.0.0.1:8012')
    args=p.parse_args()
    print(json.dumps(run(args.corpus,args.cases,args.output,args.strategy,args.embedding_url,args.reranker_url)['summary'],indent=2))


if __name__ == '__main__':
    main()
