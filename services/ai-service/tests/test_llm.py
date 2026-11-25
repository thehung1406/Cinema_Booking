import json

import httpx
import pytest
from pydantic import ValidationError

from ai_service.config import Settings
from ai_service.llm import structured
from ai_service.schemas import GroundedAnswer
from ai_service.schemas import AssistantPlan


@pytest.mark.parametrize('value', ['', None])
def test_planner_unspecified_scopes_use_defaults(value):
    result = AssistantPlan.model_validate({'intent': 'recommend', 'context': {
        'knowledge_scope': value, 'budget_scope': value}})
    assert result.context.knowledge_scope == 'policy'
    assert result.context.budget_scope == 'unknown'


def test_planner_rejects_unknown_scope():
    with pytest.raises(ValidationError):
        AssistantPlan.model_validate({'intent': 'recommend', 'context': {'knowledge_scope': 'invented'}})


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
            assert body["temperature"] == 0
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


@pytest.mark.parametrize("intent", ["get_showing_films", "get_upcoming_films", "get_my_booking"])
def test_assistant_plan_supports_listing_and_personal_booking_intents(intent):
    plan = AssistantPlan.model_validate({"intent": intent})
    assert plan.intent == intent


def test_plan_forwards_dialogue_state_to_structured(monkeypatch):
    from datetime import date
    from ai_service import llm
    from ai_service.schemas import ToolContext

    captured = {}

    def fake_structured(settings, schema, system, payload, **kwargs):
        captured["payload"] = payload
        return AssistantPlan(intent="recommend")

    monkeypatch.setattr(llm, "structured", fake_structured)
    settings = Settings(database_url="sqlite://", redis_url="redis://localhost/0",
                        llm_provider="openai", openai_api_key="test-key")
    result = llm.plan(settings, "Đổi sang 3 người", ToolContext(), date(2026, 11, 25),
                      pending_tool="recommend", active_recommendation=True)
    assert result.intent == "recommend"
    assert captured["payload"]["pending_tool"] == "recommend"
    assert captured["payload"]["active_recommendation"] is True
