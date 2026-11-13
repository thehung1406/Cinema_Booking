"""Capture RAG inputs and outputs and export a blank worksheet for human scores."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import time

import httpx
from sqlalchemy import create_engine
from sqlmodel import Session

from ai_service.config import Settings
from ai_service.graph import KnowledgeGraph
from ai_service.knowledge_retrieval import retrieve_knowledge
from ai_service.llm import grounded_reply
from ai_service.models import Base
from ai_service.rag import upsert_document
from ai_service.schemas import DocumentWrite
from ml.data import read_jsonl, reviewed
from scripts.ai.evaluate_rag import measure


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(corpus, cases_file, output, strategy, embedding_url, reranker_url, *, reviewed_gold=False):
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new benchmark directory; previous evidence must remain intact")
    cases = read_jsonl(cases_file)
    if not cases or len({q['id'] for q in cases}) != len(cases):
        raise ValueError("Nonempty, unique case IDs required")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", q["id"]) for q in cases):
        raise ValueError("Invalid case ID")
    documents = [draft for path in corpus for draft in json.loads(Path(path).read_text(encoding="utf-8"))]
    if reviewed_gold:
        reviewed(cases)
        if any(q.get("synthetic") or q.get("annotation_origin", "").startswith("ai") for q in cases):
            raise ValueError("Reviewed benchmark requires human-curated cases")
        if any(not document.get("approved") for document in documents):
            raise ValueError("Reviewed benchmark requires approved sources")
    elif any(q.get('annotation_origin') != 'ai-authored-development' or not q.get('synthetic') for q in cases):
        raise ValueError("Specify --reviewed-gold for a human-curated benchmark")
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', llm_provider='ollama', llm_timeout_seconds=20)
    base, _, addition = strategy.partition("+")
    if addition and not settings.graph_uri:
        raise ValueError("Graph comparison needs a configured Neo4j release")
    output.mkdir(parents=True)
    (output / 'traces').mkdir()
    dependencies = [('embedding', embedding_url)] if base in {'dense','hybrid','rerank'} else []
    if base == 'rerank':
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
    report = dict(stage='human-curated-evaluation' if reviewed_gold else 'ai-authored-development-not-independent-gold',
        created_at=datetime.now(timezone.utc).isoformat(),
        approval='Approved corpus' if reviewed_gold else 'Draft sources temporarily enabled only in SQLite RAM',
        strategy=strategy, graph_release=settings.graph_release_id if addition else None, k=3,
        runtime=runtime, input_sha256={str(p):digest(p) for p in [*corpus, cases_file]},
        code_sha256={str(p):digest(p) for p in [Path(__file__), Path('services/ai-service/src/ai_service/llm.py'),
            Path('services/ai-service/src/ai_service/rag.py'), Path('services/ai-service/src/ai_service/grounding.py'),
            Path('services/ai-service/src/ai_service/schemas.py'), Path('services/ai-service/src/ai_service/graph.py'),
            Path('services/ai-service/src/ai_service/knowledge_retrieval.py')]},
        human_evaluated=False, planned=len(cases), cases=[])
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    graph = KnowledgeGraph(settings.graph_uri, settings.graph_username, settings.graph_password.get_secret_value(),
                           settings.graph_database, settings.graph_release_id) if addition else None
    try:
        with Session(engine) as db:
            for draft in documents:
                validated = DocumentWrite.model_validate({k:v for k,v in draft.items() if k != 'approved'}).model_dump()
                upsert_document(db, validated | {'approved': True})

            def fetch(question):
                return retrieve_knowledge(db, question["question"], question["scope"], graph=graph, strategy=base,
                                          embedding_url=embedding_url, reranker_url=reranker_url)

            start = time.perf_counter()
            fetch(cases[0])
            report['retrieval_warmup_ms'] = (time.perf_counter()-start)*1000
            for q in cases:
                start = time.perf_counter()
                item = dict(id=q['id'], question=q['question'], scope=q['scope'], expected_answerable_development=q['expected_answerable'],
                    state='running', sources=[], answer=None, generation_trace={})
                try:
                    sources, item['graph_retrieval'], item['text_retrieval_queries'] = fetch(q)
                    if item['graph_retrieval'] == "unavailable":
                        raise RuntimeError("Neo4j unavailable during comparison")
                    item['retrieval_ms'] = (time.perf_counter()-start)*1000
                    item['sources'] = sources
                    item['retrieval_metrics_development'] = measure(sources, q['expected'], 3)
                    reply = grounded_reply(settings, q['question'], sources, trace=item['generation_trace'],
                                           extractive=q['scope'] == 'policy')
                    item['answer'], item['reply_status'] = reply.text, reply.status
                    item['state'] = 'completed'
                    item['citation_ids_validated'] = reply.status == 'ok'
                    item['abstained'] = reply.status != 'ok'
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
            note=('Correctness requires human scoring of the frozen answers.' if reviewed_gold else
                  'Rates use AI-authored expectations; correctness requires human scoring.'))
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
        if graph is not None:
            graph.close()
        engine.dispose()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--corpus', nargs='+', required=True)
    p.add_argument('--cases', default='pipelines/knowledge/rag-development-v2.jsonl')
    p.add_argument('--output', required=True)
    strategies = ['lexical', 'bm25', 'dense', 'hybrid', 'rerank']
    p.add_argument('--strategy', choices=strategies + [f'{name}+graph' for name in strategies], default='rerank')
    p.add_argument('--reviewed-gold', action='store_true')
    p.add_argument('--embedding-url', default='http://127.0.0.1:8012')
    p.add_argument('--reranker-url', default='http://127.0.0.1:8012')
    args=p.parse_args()
    print(json.dumps(run(args.corpus,args.cases,args.output,args.strategy,args.embedding_url,args.reranker_url,
                         reviewed_gold=args.reviewed_gold)['summary'],indent=2))


if __name__ == '__main__':
    main()
