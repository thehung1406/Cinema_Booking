import json
from datetime import date, timedelta

import httpx
import pytest

from ai_service import llm
from ai_service.rag import folded
from ai_service.react_lookup import applies
from test_chat_booking import HEADERS, client_factory  # noqa: F401


def test_react_handles_the_supported_conditions_in_their_requested_order():
    assert applies(folded("Nếu suất đầu còn đủ hai ghế thì báo giá từng loại. Nếu không đủ thì kiểm tra suất tiếp theo."))
    assert not applies(folded("Nếu suất đầu không đủ hai ghế thì báo giá. Nếu đủ thì kiểm tra suất tiếp theo."))


@pytest.mark.parametrize(("available", "scenario", "last_action", "last_id"), [
    (2, "valid", "get_ticket_prices", 11),
    (1, "valid", "get_seat_availability", 12),
    (1, "unknown", "create_booking", 12),
    (1, "out_of_scope", "get_seat_availability", 998),
    (1, "repeat", "get_seat_availability", 11),
    (1, "no_next", "", 0),
    (1, "timeout", "", 0),
    (1, "unavailable", "", 0),
])
@pytest.mark.parametrize(("provider", "json_fallback"), [
    ("openai", None), ("ollama", None), ("ollama", "rejected"), ("openai", "rejected"), ("ollama", "no_call"),
    ("ollama", "late_rejection"),
])
def test_tool_observation_drives_the_next_action(client_factory, monkeypatch, available, scenario, last_action, last_id, provider, json_fallback):
    day = (date.today() + timedelta(days=3)).isoformat()
    actions = []
    native_attempts = 0

    def owner(request):
        path = request.url.path
        if path.endswith("/matches"):
            return httpx.Response(200, json={"film_id": [{"id": 1, "name": "Phim X"}], "theater_id": [{"id": 2, "name": "Rạp Y"}]})
        if path.endswith("/context"):
            return httpx.Response(200, json={"film_name": "Phim X", "theater_name": "Rạp Y"})
        if path.endswith("/available-count"):
            show_id = int(path.split("/")[-2])
            actions.append(("get_seat_availability", show_id))
            return httpx.Response(200, json={"showtime_id": show_id, "available_seats": available if show_id == 11 else 5})
        call = json.loads(request.content)["call"]
        actions.append((call["name"], call["context"]["showtime_id"]))
        if call["name"] == "get_showtimes":
            return httpx.Response(200, json=[{"id": f"showtime:{id}", "title": f"Suất {id}", "text": f"Mã suất {id}", "url": f"/seat-selection/{id}", "kind": "live"} for id in ((11,) if scenario == "no_next" else (11, 12))])
        assert call["name"] == "get_ticket_prices"
        return httpx.Response(200, json=[{"id": "price:1", "title": "Ghế thường", "text": "Ghế thường: 90,000 VND", "url": "/seat-selection/11", "kind": "live"}])

    def model(request):
        nonlocal native_attempts
        assert request.url.path == ("/v1/responses" if provider == "openai" else "/api/chat")
        body = json.loads(request.content)
        use_json = "tools" not in body
        if use_json:
            assert json_fallback
            payload = body["input"] if provider == "openai" else body["messages"][-1]["content"]
            observations = [entry["result"] for entry in json.loads(payload)["observations"]]
        else:
            native_attempts += 1
            if provider == "openai":
                assert body["store"] is False and body["parallel_tool_calls"] is False
                definitions = body["tools"]
                results = [item for item in body["input"] if item.get("type") == "function_call_output"]
                assert [item["call_id"] for item in results] == [f"call_{i}" for i in range(len(results))]
                observations = [json.loads(item["output"]) for item in results]
            else:
                assert body["stream"] is False and request.headers.get("authorization") is None
                definitions = [entry["function"] for entry in body["tools"]]
                results = [item for item in body["messages"] if item.get("role") == "tool"]
                assert [item["tool_name"] for item in results] == ["get_showtimes", "get_seat_availability"][:len(results)]
                observations = [json.loads(item["content"]) for item in results]
            assert {tool["name"] for tool in definitions} == {"get_showtimes", "get_seat_availability", "get_ticket_prices"}
            if json_fallback == "rejected" or (json_fallback == "late_rejection" and observations):
                return httpx.Response(400, json={"error": "This model does not support tools"})
            if json_fallback == "no_call":
                return httpx.Response(200, json={"done": True, "message": {"role": "assistant", "content": "No native tool call."}})
        step = len(observations)
        if step == 0:
            if scenario == "unavailable":
                return httpx.Response(503)
            name, args = "get_showtimes", {}
        elif step == 1:
            assert observations[-1]["showtimes"][0]["showtime_id"] == 11
            name, args = "get_seat_availability", {"showtime_id": 11}
        else:
            count = observations[-1]["available_seats"]
            assert count == available
            if scenario == "timeout":
                raise httpx.ReadTimeout("fixture timeout", request=request)
            name, args = last_action, {"showtime_id": last_id}
        if use_json:
            decision = json.dumps({"name": name, "showtime_id": args.get("showtime_id")})
            if provider == "openai":
                return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": decision}]}]})
            return httpx.Response(200, json={"done": True, "message": {"role": "assistant", "content": decision}})
        if provider == "openai":
            return httpx.Response(200, json={"status": "completed", "output": [{"type": "function_call", "name": name, "arguments": json.dumps(args), "call_id": f"call_{step}"}]})
        return httpx.Response(200, json={"done": True, "message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": args}}]}})

    with client_factory(owner, llm_provider=provider, openai_api_key="fixture-token", react_lookup_enabled=True) as client:
        http_client = httpx.Client
        monkeypatch.setattr(llm.httpx, "Client", lambda **kwargs: http_client(transport=httpx.MockTransport(model), **kwargs))
        response = client.post("/ai/chat", headers=HEADERS, json={"message": f"Tìm các suất của phim X tại rạp Y ngày {day}. Nếu suất đầu còn đủ hai ghế thì báo giá từng loại. Nếu không đủ thì kiểm tra suất tiếp theo."})
    assert response.status_code == 200, response.text
    if json_fallback:
        assert native_attempts == (2 if json_fallback == "late_rejection" and scenario != "unavailable" else 1)
    data = response.json()
    if scenario == "unavailable":
        assert data["mode"] == "react_fallback" and data["status"] == "partial"
        assert actions == [("get_showtimes", None)]
        return
    assert data["mode"] == "react_lookup"
    if scenario == "valid":
        assert data["status"] == "ok"
        assert ("90,000 VND" if available == 2 else "5 ghế") in data["answer"]
        assert actions == [("get_showtimes", None), ("get_seat_availability", 11), (last_action, last_id)]
    else:
        assert data["status"] == ("ok" if scenario == "no_next" else "partial")
        assert "còn 1 ghế" in data["answer"]
        assert actions == [("get_showtimes", None), ("get_seat_availability", 11)]
