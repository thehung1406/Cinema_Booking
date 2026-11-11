import json
import re
import threading

import httpx

from ml.annotation_app import create_server
from ml.data import read_jsonl, write_jsonl
from scripts.ai.evaluate_rag import measure


def test_annotation_requires_session_cas_and_preserves_synthetic_origin(tmp_path):
    original, output = tmp_path/"original.jsonl", tmp_path/"confirmed.jsonl"
    write_jsonl(original, [{"id": "fixture", "text": "Synthetic test review", "synthetic": True,
                            "review_status": "pending", "suggested_label": "positive"}])
    server = create_server(original, output, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as client:
            assert client.post("/api/decision", json={}).status_code == 403
            token = re.search(r"const token='([^']+)'", client.get("/").text)[1]
            client.headers["X-Annotation-Token"] = token
            state = client.get("/api/items").json()
            body = {"id": "fixture", "revision": state["revision"], "label": "neutral", "reviewer": "test-actor"}
            assert client.post("/api/decision", json=body, headers={"Origin": "https://untrusted.example"}).status_code == 403
            assert client.post("/api/decision", json=body).status_code == 200
            assert client.post("/api/decision", json=body).status_code == 409
            row = read_jsonl(output)[0]
            assert row["synthetic"] and row["label"] == "neutral" and row["suggested_label"] == "positive"
            assert read_jsonl(original)[0]["review_status"] == "pending"
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_retrieval_metrics_do_not_reward_duplicate_chunks_or_wrong_version():
    target = [{"source_id": "book", "version": "2", "pages": [7], "grade": 3}]
    match = {"source_id": "book", "version": "2", "provenance": {"page_start": 7}}
    report = measure([match, match, match], target, 3)
    assert report["recall_at_k"] == report["ndcg_at_k"] == 1
    assert measure([match | {"version": "1"}], target, 3)["recall_at_k"] == 0
    assert measure([match], [], 3)["recall_at_k"] is None
