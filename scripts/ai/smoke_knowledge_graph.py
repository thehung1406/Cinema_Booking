"""Replay admin approval and chat against a real Neo4j release and a disposable AI DB."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx
from sqlalchemy import create_engine

from ai_service.config import Settings
from ai_service.graph import cypher, normalize_alias
from ai_service.main import create_app
from ai_service.models import Base
from ai_service.schemas import DocumentWrite
from build_knowledge_graph import compile_release, load_release


class ReplayCache:
    def eval(self, *_):
        return 1

    def setex(self, *_):
        pass


def identity(_):
    return httpx.Response(200, json={
        "user_id": 1, "role": "ADMIN", "permissions": ["knowledge.manage"], "is_active": True,
    })


def no_owner_reads(request):
    raise AssertionError(f"Knowledge replay unexpectedly called {request.url.path}")


def prepare_update(curation, documents, settings):
    original = next(doc for doc in documents if doc["source_id"] == "wikibooks-cinematography-summary")
    updated = json.loads(json.dumps(original))
    updated["version"] = "demo-edition-2"
    excerpt = "Cinematography là nghệ thuật ghi hình chuyển động bằng phim hoặc kỹ thuật số."
    updated["blocks"][1]["text"] = excerpt + " " + updated["blocks"][1]["text"]
    updated["provenance"]["checksum"] = hashlib.sha256(updated["blocks"][1]["text"].encode("utf-8")).hexdigest()
    entries = [claim | {"version": updated["version"]} for claim in curation["claims"]
               if claim["source_id"] == updated["source_id"]]
    entries[0]["excerpt"] = excerpt
    release, rows = compile_release(curation | {"claims": entries}, [DocumentWrite.model_validate(updated)])
    load_release(settings.graph_uri, settings.graph_username, settings.graph_password.get_secret_value(),
                 settings.graph_database, release, rows)
    return updated, release


def replay(client, documents, update, generation_settings=None):
    headers = {"Authorization": "Bearer isolated-graph-replay"}

    def request(method, path, payload):
        start = perf_counter()
        response = client.request(method, path, headers=headers, json=payload)
        response.raise_for_status()
        return response.json(), round((perf_counter() - start) * 1000, 2)

    def ask(message, scope=None):
        question = {"message": message}
        if scope:
            question["context"] = {"knowledge_scope": scope}
        result, latency = request("POST", "/ai/chat", question)
        return dict(question=question, response=result, latency_ms=latency)

    def set_approval(document, approved):
        result, _ = request("PUT", f"/admin/documents/{document['id']}/approval", {
            "approved": approved, "version": document["version"], "expected_updated_at": document["updated_at"],
        })
        return result

    def timestamp(document):
        value = datetime.fromisoformat(document["updated_at"])
        return {"expected_updated_at": (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()}

    saved = [request("POST", "/admin/documents", document)[0] for document in documents]
    question = "Chuyển động máy quay có tác dụng gì trong cinematography?"
    draft = ask(question)
    assert draft["response"]["status"] == "no_evidence"
    approved = {doc["source_id"]: set_approval(doc, True) for doc in saved}
    combined = ask(question)
    graph_sources = {source["source_id"] for source in combined["response"]["sources"]
                     if source["provenance"].get("graph_release")}
    expected = {"open-suny-film-construction", "wikibooks-cinematography-summary"}
    assert graph_sources == expected, combined
    english = ask("What is cinematography?")
    assert english["response"]["graph_retrieval"] == "matched"
    typo = ask("What is cinematograhpy?", "film_education")
    assert any(source["provenance"].get("alias_method") == "near" for source in typo["response"]["sources"])
    unsupported = ask("Cinematography được phát minh năm 2049 phải không?")
    assert unsupported["response"]["status"] == "no_evidence"
    generated = {}
    if generation_settings is not None:
        from ai_service import llm
        from ai_service.grounding import explicit_questions
        generation_trace = {}
        generation_errors = []
        generate = llm.grounded_reply
        generation_question = (
            "Theo sách Open SUNY, dolly có tác dụng gì? "
            "Theo bản tóm tắt Wikibooks, chuyển động máy quay có thể góp phần thể hiện điều gì?"
        )

        def capture(settings, question, sources, **kwargs):
            kwargs.setdefault("trace", generation_trace)
            try:
                return generate(settings, question, sources, **kwargs)
            except Exception as error:
                generation_errors.append(repr(error))
                raise

        generation_settings.llm_provider = "ollama"
        try:
            with patch.object(llm, "grounded_reply", side_effect=capture):
                case = ask(generation_question)
        finally:
            generation_settings.llm_provider = "disabled"
        assert case["response"]["mode"] == "grounded_generation", (
            case, generation_errors, [part.get("response_content") for part in generation_trace.get("parts", [])]
        )
        assert case["response"]["graph_retrieval"] == "matched"
        cited_ids = {span["source_id"] for span in generation_trace["supporting_spans"]}
        assert {source["source_id"] for source in case["response"]["sources"] if source["id"] in cited_ids} == expected, case
        case["model_trace"] = generation_trace
        case["cypher"] = cypher("retrieve.cypher")
        case["cypher_parameters"] = [{
            "release_ids": [generation_settings.graph_release_id],
            "scope": "film_education",
            "phrase": f" {normalize_alias(part)} ",
            "near_aliases": [],
        } for part in explicit_questions(generation_question)]
        generated["generated"] = case
    updates = {}
    if update is not None:
        new_document, release = update
        current = approved[new_document["source_id"]]
        revisions = f"/admin/documents/{current['id']}/revisions"
        version_stamp = timestamp(current)
        staged, _ = request("POST", revisions, {"document": new_document | version_stamp, "graph_release_id": release})
        pending = ask("What is cinematography?")
        assert any(source["version"] == current["version"] for source in pending["response"]["sources"])
        assert all(source["version"] != new_document["version"] for source in pending["response"]["sources"])
        invalid, _ = request("POST", revisions, {
            "document": new_document | version_stamp | {"version": "demo-invalid-release"}, "graph_release_id": "0" * 64,
        })
        failed = client.put(f"{revisions}/{invalid['id']}/publication", headers=headers, json=version_stamp)
        assert failed.status_code == 409
        after_failure = ask("What is cinematography?")
        assert any(source["version"] == current["version"] for source in after_failure["response"]["sources"])
        active, _ = request("PUT", f"{revisions}/{staged['id']}/publication", version_stamp)
        assert active["version"] == new_document["version"]
        published = ask("What is cinematography?")
        assert any(source["version"] == new_document["version"] and source["provenance"].get("graph_release") == release
                   for source in published["response"]["sources"]), published
        assert all(source["version"] != current["version"] for source in published["response"]["sources"])
        history, _ = request("GET", revisions, None)
        previous = next(item for item in history if item["version"] == current["version"])
        request("PUT", f"{revisions}/{previous['id']}/publication", timestamp(active))
        rollback = ask("What is cinematography?")
        assert any(source["version"] == current["version"] for source in rollback["response"]["sources"])
        assert all(source["version"] != new_document["version"] for source in rollback["response"]["sources"])
        updates = {"pending": pending, "failed_publication": after_failure, "published": published, "rollback": rollback}
    set_approval(approved["open-suny-film-construction"], False)
    revoked = ask(question)
    assert all(source["source_id"] != "open-suny-film-construction" for source in revoked["response"]["sources"])
    assert any(source["source_id"] == "wikibooks-cinematography-summary" for source in revoked["response"]["sources"])
    return {"draft": draft, "combined": combined, "english": english, "typo": typo,
            "unsupported": unsupported, "revoked": revoked} | updates | generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--curation", type=Path, help="Load and replay a simulated update in the isolated graph")
    parser.add_argument("--generate", action="store_true", help="Also capture a real Ollama generation using graph evidence")
    args = parser.parse_args()
    documents = [
        {key: value for key, value in item.items() if key != "approved"}
        for path in args.document for item in json.loads(path.read_text(encoding="utf-8"))
    ]
    with TemporaryDirectory(prefix="cinema-graph-replay-") as temp:
        engine = create_engine(f"sqlite:///{Path(temp, 'ai.sqlite3').as_posix()}")
        try:
            Base.metadata.create_all(engine)
            settings = Settings(
                database_url=str(engine.url), redis_url="redis://localhost/0", writes_enabled=True,
                service_key="isolated-graph-replay-service-key", llm_provider="disabled",
            )
            if not settings.graph_uri:
                parser.error("Set AI_GRAPH_URI, AI_GRAPH_PASSWORD and AI_GRAPH_RELEASE_ID")
            update = prepare_update(json.loads(args.curation.read_text(encoding="utf-8")), documents, settings) if args.curation else None
            app = create_app(settings, engine=engine, cache=ReplayCache(),
                             auth_transport=httpx.MockTransport(identity),
                             read_transport=httpx.MockTransport(no_owner_reads))
            with TestClient(app) as client:
                cases = replay(client, documents, update, settings if args.generate else None)
        finally:
            engine.dispose()
    artifact = {"scope": "development replay", "neo4j": "real", "owner_store": "disposable SQLite",
                "identity_cache": "test adapters", "generation": "ollama" if args.generate else "disabled",
                "simulated_update": bool(args.curation),
                "cases": cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Passed {len(cases)} API replay cases. Evidence: {args.output}")


if __name__ == "__main__":
    main()
