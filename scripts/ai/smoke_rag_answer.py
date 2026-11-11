"""Actual retrieval + grounded local generation, in an explicitly isolated replay."""
import argparse
import json
from pathlib import Path
import time
import hashlib
import httpx
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlmodel import Session
from ai_service.config import Settings
from ai_service.llm import grounded_answer
from ai_service.models import Base
from ai_service.rag import retrieve, upsert_document
from ai_service.schemas import DocumentWrite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', nargs='+', default=['.local/knowledge/film-book.json'])
    parser.add_argument('--question', default='Thể loại phim là gì?')
    parser.add_argument('--embedding-url', default='http://127.0.0.1:8011')
    parser.add_argument('--strategy', choices=['lexical', 'bm25', 'dense', 'hybrid', 'rerank'], default='dense')
    parser.add_argument('--reranker-url', default='')
    parser.add_argument('--model', default='qwen3:4b')
    parser.add_argument('--output', default='.local/evidence/rag-answer-pilot.json')
    args = parser.parse_args()
    settings = Settings(database_url='sqlite://', redis_url='redis://localhost/0', llm_provider='ollama',
                        llm_model=args.model, llm_timeout_seconds=20)
    runtime = {}
    with httpx.Client(timeout=5, trust_env=False) as client:
        dependencies = [('embedding', args.embedding_url)] if args.strategy in {'dense', 'hybrid', 'rerank'} else []
        if args.strategy == 'rerank':
            dependencies.append(('reranker', args.reranker_url))
        for name, origin in dependencies:
            if origin:
                response = client.get(origin.rstrip('/')+'/health/ready')
                response.raise_for_status()
                runtime[name] = response.json()
        response = client.get(settings.llm_base_url.rstrip('/')+'/api/tags')
        response.raise_for_status()
        runtime['ollama_model'] = next(({'name':m.get('name'), 'digest':m.get('digest')}
            for m in response.json()['models'] if m.get('name') == settings.llm_model), None)
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    start = time.perf_counter()
    try:
        with Session(engine) as db:
            for path in args.corpus:
                for draft in json.loads(Path(path).read_text(encoding='utf-8')):
                    validated = DocumentWrite.model_validate({k: v for k, v in draft.items() if k != 'approved'}).model_dump()
                    upsert_document(db, validated | {'approved': True})
            retrieval_started = time.perf_counter()
            sources = retrieve(db, args.question, scope='film_education', strategy=args.strategy,
                embedding_url=args.embedding_url, reranker_url=args.reranker_url)
            retrieval_ms = (time.perf_counter()-retrieval_started)*1000
            generation_trace = {}
            answer = grounded_answer(settings, args.question, sources, trace=generation_trace) if sources else ''
        report = {'stage': 'development-pilot-not-human-evaluated', 'approval': 'temporary in RAM replay only; source files stay unapproved',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'corpus_sha256': {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in args.corpus},
            'question': args.question, 'scope': 'film_education', 'strategy': args.strategy, 'model': settings.llm_model,
            'retrieval_ms': retrieval_ms, 'elapsed_seconds': time.perf_counter()-start,
            'sources': sources, 'generation_trace': generation_trace, 'runtime': runtime, 'answer': answer,
            'citation_ids_validated': bool(sources) and bool(answer), 'semantic_groundedness_human_reviewed': False}
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'sources': len(sources), 'answer_present': bool(answer), 'seconds': report['elapsed_seconds'], 'stage': report['stage']}))
    finally:
        engine.dispose()


if __name__ == '__main__': main()
