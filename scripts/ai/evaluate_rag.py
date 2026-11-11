"""Owner-side replay of a frozen KB; never touches any live database.

Kept outside ml/: training/data pipelines do not import service database models.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from ml.data import read_jsonl, reviewed


def relevance(source, expected):
    grades = []
    for target in expected:
        if source["source_id"] != target["source_id"] or source["version"] != target["version"]:
            continue
        pages = target.get("pages", [])
        if pages and source.get("provenance", {}).get("page_start") not in pages:
            continue
        if target.get("text_contains") and not all(fragment.casefold() in source.get("text", "").casefold() for fragment in target["text_contains"]):
            continue
        grades.append(int(target.get("grade", 1)))
    return max(grades, default=0)


def measure(sources, expected, k):
    # Deduplicate matches to the same gold target; multiple chunks on one page
    # cannot inflate recall or nDCG. Ranking positions are still chunk positions.
    seen, gains = set(), []
    for source in sources[:k]:
        candidates = [(i, relevance(source, [target])) for i, target in enumerate(expected) if i not in seen]
        index, grade = max(candidates, key=lambda item: item[1], default=(-1, 0))
        if grade > 0:
            seen.add(index)
        gains.append(grade)
    ideal = sorted([int(target.get("grade", 1)) for target in expected], reverse=True)[:k]
    dcg = sum((2**grade-1)/math.log2(index+2) for index, grade in enumerate(gains))
    idcg = sum((2**grade-1)/math.log2(index+2) for index, grade in enumerate(ideal))
    return {"recall_at_k": len(seen)/len(expected) if expected else None,
            "mrr_at_k": next((1/(i+1) for i, grade in enumerate(gains) if grade > 0), 0.) if expected else None,
            "ndcg_at_k": dcg/idcg if idcg else None,
            "returned_any": bool(sources), "relevant_retrieved": len(seen)}


def evaluate(corpus_files, gold_file, strategies, k, embedding_url="", reranker_url="", pilot=False, chunk_size=1200, chunk_overlap=0):
    from sqlalchemy import create_engine
    from sqlmodel import Session
    from ai_service.models import Base
    from ai_service.schemas import DocumentWrite
    from ai_service.rag import upsert_document, retrieve
    documents = [doc for path in corpus_files for doc in json.loads(Path(path).read_text(encoding="utf-8"))]
    questions = read_jsonl(gold_file)
    if not questions or len({q["id"] for q in questions}) != len(questions):
        raise ValueError("Gold questions need unique IDs and cannot be empty")
    if not pilot:
        reviewed(questions)
        if any(q.get("synthetic") or q.get("annotation_origin", "").startswith("ai") for q in questions):
            raise ValueError("AI-created questions are pilot data until independently curated")
        if any(not d.get("approved") for d in documents):
            raise ValueError("KB contains unapproved drafts; use --pilot for a development replay")
    for question in questions:
        if not question.get("question", "").strip() or question.get("scope") not in {"policy", "film_education", "reference"}:
            raise ValueError("Question and explicit scope required")
        for target in question["expected"]:
            if not target.get("source_id") or not target.get("version") or target.get("grade", 1) not in {1, 2, 3}:
                raise ValueError("Relevance needs source_id, version and grade 1–3")
            if not any(d["source_id"] == target["source_id"] and d["version"] == target["version"] for d in documents):
                raise ValueError("Gold reference not present in frozen corpus")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    runs = []
    try:
        with Session(engine) as db:
            for document in documents:
                validated = DocumentWrite.model_validate({k: v for k, v in document.items() if k != "approved"}).model_dump()
                upsert_document(db, validated | {"approved": True}, chunk_size=chunk_size, chunk_overlap=chunk_overlap)  # Isolated replay only.
            for strategy in strategies:
                # Cold model/index initialization is reported separately from warm queries.
                start = time.perf_counter()
                try:
                    retrieve(db, questions[0]["question"], limit=k, scope=questions[0]["scope"],
                             strategy=strategy, embedding_url=embedding_url, reranker_url=reranker_url)
                except Exception as exc:
                    runs.append({"strategy": strategy, "state": "unavailable", "error_type": type(exc).__name__})
                    continue
                warmup_ms = (time.perf_counter()-start)*1000
                rows = []
                for question in questions:
                    start = time.perf_counter()
                    sources = retrieve(db, question["question"], limit=k, scope=question["scope"],
                                       strategy=strategy, embedding_url=embedding_url, reranker_url=reranker_url)
                    rows.append({"id": question["id"], "question": question["question"],
                                 "latency_ms": (time.perf_counter()-start)*1000,
                                 **measure(sources, question["expected"], k), "sources": sources})
                summary = {key: statistics.mean(row[key] for row in rows if row[key] is not None)
                           for key in ("recall_at_k", "mrr_at_k", "ndcg_at_k") if any(row[key] is not None for row in rows)}
                negatives = [row for row, question in zip(rows, questions) if not question["expected"]]
                summary["unanswerable_query_count"] = len(negatives)
                summary["unanswerable_retrieval_rate"] = statistics.mean(row["returned_any"] for row in negatives) if negatives else None
                summary["latency_ms_median"] = statistics.median(row["latency_ms"] for row in rows)
                runs.append({"strategy": strategy, "state": "completed", "warmup_ms": warmup_ms, "summary": summary, "queries": rows})
    finally:
        engine.dispose()
    return {"created_at": datetime.now(timezone.utc).isoformat(), "stage": "development-pilot" if pilot else "reviewed-retrieval-evaluation",
            "k": k, "question_count": len(questions), "generation_quality_evaluated": False,
            "chunking": {"size_characters": chunk_size, "overlap_characters": chunk_overlap},
            "sha256": {str(path): hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in [*corpus_files, gold_file]}, "runs": runs}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", nargs="+", required=True)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--strategies", nargs="+", choices=["lexical", "bm25", "dense", "hybrid", "rerank"], default=["lexical", "bm25"])
    parser.add_argument("--k", type=int, choices=range(1, 21), default=3)
    parser.add_argument("--embedding-url", default="")
    parser.add_argument("--reranker-url", default="")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = evaluate(args.corpus, args.gold, args.strategies, args.k, args.embedding_url, args.reranker_url, args.pilot, args.chunk_size, args.chunk_overlap)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stage": report["stage"], "runs": [{"strategy": r["strategy"], "state": r["state"], "summary": r.get("summary")} for r in report["runs"]]}))


if __name__ == "__main__":
    main()
