"""Measure a staged 1–4-source graph replay with an explicitly simulated conflict."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

from sqlalchemy import create_engine
from sqlmodel import Session

from ai_service.graph import KnowledgeGraph, graph_evidence
from ai_service.models import Base
from ai_service.rag import upsert_document
from ai_service.schemas import DocumentWrite
from build_knowledge_graph import compile_release, load_release


def replay(curation, documents, uri, username, password, database):
    if len(documents) != 3:
        raise ValueError("Supply the three demo documents in order: film book, Vietnamese summary, booking guide")
    if [doc.source_id for doc in documents] != [
        "open-suny-film-construction", "wikibooks-cinematography-summary", "cinema-booking-guide",
    ]:
        raise ValueError("Unexpected source order")
    excerpt = "Dữ liệu mô phỏng: Cinematography chỉ dùng để mô tả ảnh tĩnh."
    alias_excerpt = "Dữ liệu mô phỏng: Dolly là tên một nhân vật."
    pending_excerpt = "Dữ liệu mô phỏng: frame rate mặc định là 36 hình mỗi giây."
    texts = [excerpt, alias_excerpt, pending_excerpt]
    simulated = DocumentWrite(
        source_id="simulated-conflicting-definition", title="Nguồn mô phỏng mâu thuẫn", version="test-1",
        source_url="/about", effective_at=documents[0].effective_at,
        provenance={"scope": "film_education", "license": "Synthetic test fixture",
                    "checksum": hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()},
        blocks=[{"text": text} for text in texts],
    )
    test_claims = [
        dict(concept_id="cinematography", predicate="definition", value="still-photography", block_index=0, excerpt=excerpt),
        dict(concept_id="simulated-character", predicate="definition", value="character", block_index=1, excerpt=alias_excerpt),
        dict(concept_id="simulated-frame-rate", predicate="default", value="36-fps", block_index=2,
             excerpt=pending_excerpt, status="needs_review"),
    ]
    curation = {
        "concepts": curation["concepts"] | {"simulated-character": {"en": ["Dolly"]},
                                             "simulated-frame-rate": {"en": ["frame rate"]}},
        "claims": curation["claims"] + [claim | {"source_id": simulated.source_id, "version": simulated.version}
                                          for claim in test_claims],
    }
    documents = [*documents, simulated]
    observations = []
    for count in range(1, len(documents) + 1):
        included = documents[:count]
        release, claims = compile_release(curation, included)
        started = perf_counter()
        load_release(uri, username, password, database, release, claims)
        elapsed = (perf_counter() - started) * 1000
        # Replay the same Cypher import to verify that there is still one edge per curated claim.
        load_release(uri, username, password, database, release, claims)
        graph = KnowledgeGraph(uri, username, password, database, release)
        engine = create_engine("sqlite://")
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                for document in included:
                    upsert_document(db, document.model_dump() | {"approved": True})
                evidence, state = graph_evidence(db, graph, "Cinematography là gì?", "film_education")
                policy, policy_state = graph_evidence(db, graph, "Trợ lý có giữ ghế không?", "policy")
                _, alias_state = graph_evidence(db, graph, "Dolly là gì?", "film_education")
                _, pending_state = graph_evidence(db, graph, "Frame rate mặc định là bao nhiêu?", "film_education")
            with graph.driver.session(database=database, default_access_mode="READ") as session:
                loaded = session.run(
                    "MATCH (:KnowledgeRelease {id: $release})-[link:INCLUDES]->(:Claim) RETURN count(link) AS count",
                    release=release,
                ).single(strict=True)["count"]
            assert loaded == len(claims)
            expected = [
                {"open-suny-film-construction"},
                {"open-suny-film-construction", "wikibooks-cinematography-summary"},
                {"open-suny-film-construction", "wikibooks-cinematography-summary"},
                set(),
            ][count - 1]
            assert {item["source_id"] for item in evidence} == expected
            assert state == ("conflict" if count == 4 else "matched")
            assert alias_state == ("ambiguous" if count == 4 else "matched")
            assert pending_state == ("uncertain" if count == 4 else "no_match")
            assert {item["source_id"] for item in policy} == ({"cinema-booking-guide"} if count >= 3 else set())
            observations.append(dict(source_count=count, sources=[doc.source_id for doc in included],
                                     simulated_source=count == 4, release_id=release, claims=loaded,
                                     import_ms=round(elapsed, 2), duplicate_claim_edges=loaded - len(claims),
                                     definition_status=state, definition_sources=sorted(expected), policy_status=policy_state,
                                     alias_status=alias_state, unverified_claim_status=pending_state))
        finally:
            graph.close()
            engine.dispose()
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curation", required=True, type=Path)
    parser.add_argument("--document", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    documents = [DocumentWrite.model_validate({key: value for key, value in item.items() if key != "approved"})
                 for path in args.document for item in json.loads(path.read_text(encoding="utf-8"))]
    curation = json.loads(args.curation.read_text(encoding="utf-8"))
    observations = replay(curation, documents, os.environ["AI_GRAPH_URI"], os.environ.get("AI_GRAPH_USERNAME", "neo4j"),
                          os.environ["AI_GRAPH_PASSWORD"], os.environ.get("AI_GRAPH_DATABASE", "neo4j"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"stage": "development replay", "observations": observations},
                                      ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Passed {len(observations)} source-count stages. Evidence: {args.output}")


if __name__ == "__main__":
    main()
