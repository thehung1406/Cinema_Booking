import json

import httpx

from ai_service.config import Settings
from ai_service.llm import grounded_answer


def test_trace_contains_the_actual_serialized_context_and_output(monkeypatch):
    original = httpx.Client
    requests = []
    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"model": "qwen3:4b", "done": True,
            "message": {"content": json.dumps({"decision": "answer", "clarification": "",
                "sentences": [{"text": "Genre groups films.", "source_id": "doc:7:span:0"}]})}})
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    trace = {}
    sources = [{"id": "doc:7", "text": "Genre groups films by recurring conventions."}]
    answer = grounded_answer(Settings(database_url="sqlite://", redis_url="redis://localhost/0",
        llm_provider="ollama"), "What is genre?", sources, trace=trace)
    assert trace["request_body"] == requests[0]
    citation_schema = requests[0]["format"]["$defs"]["GroundedSentence"]["properties"]["source_id"]
    assert citation_schema["enum"] == ["doc:7:span:0"]
    assert json.loads(trace["request_body"]["messages"][1]["content"])["evidence"] == [dict(id='doc:7:span:0',text=sources[0]['text'])]
    assert trace['supporting_spans'][0]['support_quote']==sources[0]['text']
    assert trace["validated_output"]["sentences"][0]["source_id"] == "doc:7:span:0"
    assert answer == "Genre groups films. [doc:7]"
