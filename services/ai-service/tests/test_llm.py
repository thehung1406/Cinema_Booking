import json

import httpx
import pytest
from pydantic import ValidationError

from ai_service.config import Settings
from ai_service.llm import structured
from ai_service.schemas import GroundedAnswer


@pytest.mark.parametrize(("provider", "base_url", "expected_url"), [
    ("ollama", "", "http://127.0.0.1:11434/api/chat"),
    ("ollama", "http://ollama:11434/", "http://ollama:11434/api/chat"),
    ("openai", "", "https://api.openai.com/v1/responses"),
    ("openai", "https://llm.example.test/openai/v1/", "https://llm.example.test/openai/v1/responses"),
])
def test_provider_switch_preserves_the_grounding_schema(monkeypatch, provider, base_url, expected_url):
    monkeypatch.setenv("AI_LLM_PROVIDER", provider)
    monkeypatch.setenv("AI_LLM_BASE_URL", base_url)
    monkeypatch.setenv("AI_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_OPENAI_MODEL", "gpt-4.1-mini-2025-04-14")
    settings = Settings(database_url="sqlite://", redis_url="redis://localhost/0")
    schema = GroundedAnswer.model_json_schema()
    schema["$defs"]["GroundedSentence"]["properties"]["source_id"]["enum"] = ["source-1"]
    output = json.dumps({"decision": "answer", "sentences": [{"source_id": "source-1", "text": "Câu trả lời"}], "clarification": ""})

    def respond(request):
        body = json.loads(request.content)
        assert request.url == expected_url
        if provider == "openai":
            assert request.headers["Authorization"] == "Bearer test-key"
            assert body["model"] == "gpt-4.1-mini-2025-04-14" and body["store"] is False
            assert body["text"]["format"]["schema"] == schema
            assert json.loads(body["input"]) == {"question": "Câu hỏi"}
            return httpx.Response(200, json={"status": "completed", "output": [
                {"type": "message", "content": [{"type": "output_text", "text": output}]}
            ]})
        assert "Authorization" not in request.headers
        assert body["model"] == "qwen3:4b" and body["format"] == schema
        return httpx.Response(200, json={"message": {"content": output}})

    client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs))
    trace = {}
    answer = structured(settings, GroundedAnswer, "Return JSON", {"question": "Câu hỏi"}, format_schema=schema, trace=trace)
    assert answer.sentences[0].source_id == "source-1"
    assert "test-key" not in str(trace)


def test_openai_requires_an_api_key(monkeypatch):
    monkeypatch.setenv("AI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("AI_OPENAI_API_KEY", " ")
    with pytest.raises(ValidationError, match="AI_OPENAI_API_KEY is required"):
        Settings(database_url="sqlite://", redis_url="redis://localhost/0")


def test_openai_rejects_a_plain_http_endpoint(monkeypatch):
    monkeypatch.setenv("AI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("AI_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_LLM_BASE_URL", "http://llm.example.test/v1")
    with pytest.raises(ValidationError, match="OpenAI requires HTTPS"):
        Settings(database_url="sqlite://", redis_url="redis://localhost/0")
