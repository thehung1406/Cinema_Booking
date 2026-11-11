"""The model selects evidence IDs; exact evidence text is rendered as the answer.

No model-generated action, URL, policy, price or SQL is executed or accepted.
Redis retains only user-scoped context, with a TTL, never raw conversation text.
PostgreSQL persists conversations, messages and the authoritative context.
"""
import json
import re
from datetime import datetime, timedelta, time
from decimal import Decimal
from time import monotonic
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from .models import AIConversation, AIMessage
from .models import utcnow
from .schemas import ToolCall, ToolContext
from .tools import validate_context, missing_fields, run_tool
from .rag import folded, retrieve
from .history import owned_conversation

LABELS = {"film_id": "phim", "theater_id": "rạp", "show_date": "ngày xem", "showtime_id": "mã suất chiếu"}
SHOWTIME_PATTERN = r"(?:ma suat|suat chieu so)\s*(\d+)"
# Owner reads have a 20-second deadline and the browser waits 25 seconds.
PLANNER_TIMEOUT = 5
CHAT_INFERENCE_BUDGET = 16
RECOMMENDATION_FILTERS = ("show_date", "genre", "party_size", "budget_amount", "budget_scope", "start_after")
RATE_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return n
"""


def detect_intent(message):
    text = folded(message)
    if any(w in text for w in ("dat ho", "giu ho", "thanh toan ho", "xac nhan thanh toan", "don hang cua", "don hang toi")):
        return "out_of_scope"
    if "la gi" in text and any(w in text for w in ("the loai", "dien anh", "quay phim", "dung phim", "cinematography")):
        return "knowledge"
    if any(w in text for w in ("khen", "tich cuc")):
        return "get_positive_films"
    if any(w in text for w in ("de xuat phim", "goi y phim", "tu van phim", "muon xem", "ngan sach", "tim phim")):
        return "recommend"
    if any(w in text for w in ("chinh sach", "cach ", "huong dan", "hoan tien", "doi ve", "huy ve", "giu ghe bao lau", "thanh toan")):
        return "knowledge"
    if any(w in text for w in ("ghe trong", "con ghe", "ghe nao")):
        return "get_seat_availability"
    if any(w in text for w in ("gia ve", "bao nhieu tien", "gia ghe")):
        return "get_ticket_prices"
    if any(w in text for w in ("lich chieu", "suat chieu", "toi nay", "may gio")):
        return "get_showtimes"
    if any(w in text for w in ("phim", "the loai", "noi dung")):
        return "search_films"
    return "knowledge"


def infer_context(reader, message, context):
    text = folded(message)
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    if "ngay kia" in text:
        context.show_date = today + timedelta(days=2)
    elif "ngay mai" in text or "toi mai" in text:
        context.show_date = today + timedelta(days=1)
    elif "hom nay" in text or "toi nay" in text:
        context.show_date = today
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if date_match:
        try:
            context.show_date = datetime.strptime(date_match.group(), "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(422, "Ngày không hợp lệ")
    matches = reader.matches(message)
    for field in ("film_id", "theater_id"):
        rows = getattr(matches, field)
        if len(rows) == 1:
            setattr(context, field, rows[0].id)
    match = re.search(SHOWTIME_PATTERN, text)
    if match:
        context.showtime_id = int(match[1])
    return context


def infer_preferences(message, context):
    text = folded(message)
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    if "ngay kia" in text:
        context.show_date = today + timedelta(days=2)
    elif "ngay mai" in text or "toi mai" in text:
        context.show_date = today + timedelta(days=1)
    elif "hom nay" in text or "toi nay" in text:
        context.show_date = today
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if date_match:
        try:
            context.show_date = datetime.strptime(date_match[0], "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(422, "Ngày không hợp lệ")
    for phrase, genre in (("phim hai", "Hài"), ("phim kinh di", "Kinh dị"), ("phim hanh dong", "Hành động"),
                          ("phim hoat hinh", "Hoạt hình"), ("phim tinh cam", "Tình cảm")):
        if phrase in text:
            context.genre = genre
    party = re.search(r"\b(\d{1,2}|hai|ba|bon|nam)\s*(?:nguoi|ve)\b", text)
    if party:
        value = {"hai": 2, "ba": 3, "bon": 4, "nam": 5}.get(party[1])
        context.party_size = value if value is not None else int(party[1])
    amount = re.search(r"(?:duoi|ngan sach|toi da)\s*(\d+(?:[.,]\d+)?)\s*(k|nghin|ngan|trieu|tr|vnd|dong)?\b", text)
    if amount:
        raw = amount[1]
        if re.fullmatch(r"\d+[.,]\d{3}", raw):
            raw = raw.replace(".", "").replace(",", "")
        value = Decimal(raw.replace(",", "."))
        unit = amount[2] or ""
        value *= 1000000 if unit in {"trieu", "tr"} else 1000 if unit in {"k", "nghin", "ngan"} else 1
        context.budget_amount = value
        context.budget_scope = "total" if any(w in text for w in ("tong", "ca nhom")) else "per_ticket" if any(w in text for w in ("moi ve", "/ve")) else "unknown"
    elif context.budget_amount:
        if any(w in text for w in ("tong", "ca nhom")):
            context.budget_scope = "total"
        elif any(w in text for w in ("moi ve", "/ve")):
            context.budget_scope = "per_ticket"
    clock = re.search(r"(?:sau|tu)\s*(\d{1,2})(?:h|gio|:)\s*(\d{2})?", text)
    if clock:
        try:
            context.start_after = time(int(clock[1]), int(clock[2] or 0))
        except ValueError:
            raise HTTPException(422, "Giờ xem không hợp lệ")
    if any(w in text for w in ("toi nay", "toi mai")) and context.start_after is None:
        context.start_after = time(18)
    if "la gi" in text and any(w in text for w in ("the loai", "dien anh", "quay phim", "dung phim", "cinematography")):
        context.knowledge_scope = "film_education"
    elif any(w in text for w in ("chinh sach", "cach dat ve", "huong dan dat ve", "hoan tien", "huy ve", "giu ghe bao lau")):
        context.knowledge_scope = "policy"
    # Validate assignments too: Pydantic does not validate assignment by default.
    try:
        return ToolContext.model_validate(context.model_dump())
    except ValueError:
        raise HTTPException(422, "Số vé hoặc ngân sách không hợp lệ")


def resolve_intent(reader, message, context, pending_tool=None):
    intent = detect_intent(message)
    if not pending_tool or intent == "out_of_scope":
        return intent
    remainder = folded(message)
    if intent == "knowledge" and any(word in remainder for word in
            ("cach ", "chinh sach", "huong dan", "hoan tien", "huy ve", "thanh toan", "giu ghe bao lau")):
        return "knowledge"
    names = reader.names(context)
    for name, prefix in ((names.film_name, "phim"), (names.theater_name, "rap")):
        if name:
            remainder = re.sub(rf"\b(?:{prefix}\s+)?{re.escape(folded(name))}\b", " ", remainder)
    remainder = re.sub(SHOWTIME_PATTERN, " ", remainder)
    explicit_topic = any(w in remainder for w in ("cach", "chinh sach", "huong dan", "hoan", "huy", "thanh toan"))
    if detect_intent(remainder) == "knowledge" and not explicit_topic and len(remainder.split()) <= 8:
        return pending_tool
    return intent


def select_evidence(question, evidence, config, *, deadline=None):
    if not config.model_url or not evidence:
        return evidence, "retrieval_only"
    import httpx
    try:
        timeout = config.model_timeout_seconds
        if deadline is not None:
            timeout = min(timeout, deadline - monotonic())
            if timeout <= 0:
                return evidence, "model_unavailable"
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.post(config.model_url.rstrip("/") + "/select", json={"question": question, "evidence": evidence})
            response.raise_for_status()
            payload = response.json()
        ids = payload["evidence_ids"]
        allowed = {item["id"]: item for item in evidence}
        if not isinstance(ids, list) or len(ids) > len(allowed) or any(not isinstance(i, str) or i not in allowed for i in ids):
            raise ValueError("Invalid citation")
        return [allowed[i] for i in dict.fromkeys(ids)], "model_assisted"
    except Exception:
        return evidence, "model_unavailable"


def chat(db, user_id, request, redis, reader, config):
    inference_deadline = monotonic() + CHAT_INFERENCE_BUDGET
    try:
        count = redis.eval(RATE_SCRIPT, 1, f"ai:rate:{user_id}")
        if count > config.requests_per_minute:
            raise HTTPException(429, "Bạn gửi quá nhiều câu hỏi. Vui lòng thử lại sau một phút.")
        conversation_id = str(request.conversation_id or uuid4())
        key = f"ai:context:{user_id}:{conversation_id}"
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Trợ lý tạm thời không khả dụng. Bạn vẫn có thể đặt vé trực tiếp.")
    if request.conversation_id:
        conversation = owned_conversation(db, user_id, request.conversation_id)
        previous, previous_updated_at = conversation.context, conversation.updated_at
    else:
        previous, previous_updated_at = {}, None
    db.rollback()  # Release history read connection before calling another service.
    previous_context = ToolContext.model_validate(previous.get("context", {}))
    values = previous.get("context", {}) | request.context.model_dump(mode="json", exclude_unset=True)
    context = infer_preferences(request.message, ToolContext.model_validate(values))
    message_text = folded(request.message)
    deterministic = detect_intent(request.message)
    pending_tool = previous.get("pending_tool")
    explicit_knowledge = any(word in message_text for word in (
        "cach ", "chinh sach", "huong dan", "hoan tien", "doi ve", "huy ve", "thanh toan",
        "giu ghe bao lau", "la gi",
    ))
    refining_recommendation = (
        previous.get("active_recommendation") and not explicit_knowledge
        and (deterministic == "knowledge"
             or deterministic == "get_showtimes" and not any(
                 word in message_text for word in ("lich chieu", "suat chieu", "may gio")))
        and any(getattr(context, field) != getattr(previous_context, field)
                for field in RECOMMENDATION_FILTERS)
    )
    proposed_intent, planner_mode = None, "retrieval_only"
    if refining_recommendation:
        proposed_intent = "recommend"
    elif config.llm_provider != "disabled":
        try:
            from .llm import plan
            timeout = min(config.llm_timeout_seconds, PLANNER_TIMEOUT, inference_deadline - monotonic())
            if timeout <= 0:
                raise TimeoutError("Chat inference budget exhausted")
            planner_settings = config.model_copy(update={"llm_timeout_seconds": timeout})
            proposed = plan(planner_settings, request.message, context, datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date())
            patch = proposed.context.model_dump(mode="json", exclude_unset=True, exclude_none=True,
                exclude={"film_id", "theater_id", "showtime_id"})
            patch = {key: value for key, value in patch.items() if value != ""}
            for field in ("party_size", "budget_scope", "knowledge_scope"):
                default = ToolContext.model_fields[field].default
                if patch.get(field) == default and getattr(context, field) != default:
                    patch.pop(field)  # A model default must not erase a known preference.
            context = ToolContext.model_validate(context.model_dump(mode="json") | patch)
            proposed_intent, planner_mode = proposed.intent, "model_planned"
        except Exception:
            planner_mode = "model_unavailable"
    preliminary = proposed_intent or deterministic
    if deterministic in {"out_of_scope", "get_seat_availability", "get_ticket_prices", "get_positive_films"} or (
            deterministic == "recommend" and preliminary == "search_films") or (
            deterministic == "knowledge" and explicit_knowledge):
        preliminary = proposed_intent = deterministic
    read_context = preliminary not in {"knowledge", "out_of_scope"} or (
        bool(pending_tool) and preliminary == "knowledge" and not explicit_knowledge)
    # FAQ needs only the AI-owned approved KB; do not call Catalog/Cinema unnecessarily.
    if read_context:
        context = infer_context(reader, request.message, context)
    context = infer_preferences(request.message, context)
    ordinal = re.search(r"suat thu\s*(\d+|hai|ba|bon)\b", folded(request.message))
    if ordinal:
        index = {"hai": 2, "ba": 3, "bon": 4}.get(ordinal[1])
        index = index if index is not None else int(ordinal[1])
        choices = previous.get("options", [])
        if not 1 <= index <= len(choices):
            raise HTTPException(422, "Chưa có suất tương ứng trong danh sách gần nhất; hãy chọn lại suất")
        selected = choices[index-1]
        context.showtime_id, context.film_id, context.theater_id = selected["showtime_id"], selected["film_id"], selected["theater_id"]
        context.show_date = datetime.strptime(selected["show_date"], "%Y-%m-%d").date()
    selection_changed = any(getattr(context, field) != getattr(previous_context, field)
                            for field in ("film_id", "theater_id", "show_date"))
    # The UI echoes the full context, so an unchanged ID may still be stale.
    if (context.showtime_id is not None and context.showtime_id == previous_context.showtime_id
            and selection_changed and not ordinal and not re.search(SHOWTIME_PATTERN, folded(request.message))):
        context.showtime_id = None
    if read_context:
        validate_context(reader, context)
    intent = proposed_intent or (preliminary if not read_context or preliminary == "recommend" and not pending_tool
        else resolve_intent(reader, request.message, context, pending_tool))
    # A known booking context remains relevant to short answers such as "hai vé".
    if (pending_tool == "recommend" and intent in {"knowledge", "recommend", "get_showtimes"}
            and not explicit_knowledge and len(message_text.split()) <= 8
            and not any(word in message_text for word in ("lich chieu", "suat chieu"))):
        intent = "recommend"
    evening = "toi nay" in message_text or (
        previous.get("evening", False) and (intent == pending_tool or refining_recommendation)
    )
    sources, missing = [], []
    status, mode = "ok", planner_mode
    cards, has_more = [], False
    if intent == "out_of_scope":
        answer = "Mình hỗ trợ tra cứu phim và hướng dẫn đặt vé. Bạn cần tự chọn ghế, tạo đơn và thanh toán trên giao diện; trợ lý chưa hỗ trợ tra đơn cá nhân."
        status = "out_of_scope"
    elif intent == "knowledge":
        try:
            sources = retrieve(db, request.message, strategy=config.retrieval_strategy,
                scope=context.knowledge_scope, embedding_url=config.embedding_url, reranker_url=config.reranker_url,
                deadline=inference_deadline)
        except Exception:
            sources = retrieve(db, request.message, scope=context.knowledge_scope)
            mode = "retrieval_unavailable"
        db.rollback()  # Do not occupy a database connection while waiting for the model.
        from .grounding import covers_specifics
        sources = [s for s in sources if covers_specifics(request.message,s['text'])]
        sources, selection_mode = select_evidence(request.message, sources, config, deadline=inference_deadline)
        if selection_mode != "retrieval_only":
            mode = selection_mode
        answer = "\n\n".join(s["text"] for s in sources) if sources else "Chưa có tài liệu đã duyệt đủ căn cứ cho câu hỏi này. Bạn có thể xem hướng dẫn trên giao diện hoặc liên hệ rạp."
        if sources and context.knowledge_scope != "policy" and config.llm_provider != "disabled":
            try:
                from .llm import grounded_answer
                timeout = min(config.llm_timeout_seconds, inference_deadline - monotonic())
                if timeout <= 0:
                    raise TimeoutError("Chat inference budget exhausted")
                answer_settings = config.model_copy(update={"llm_timeout_seconds": timeout})
                generated = grounded_answer(answer_settings, request.message, sources)
                if generated:
                    answer, mode = generated, "grounded_generation"
                else:
                    sources, answer = [], "Chưa có đủ căn cứ trong các nguồn được duyệt để trả lời câu hỏi này."
            except Exception:
                mode = "model_unavailable"
        status = "ok" if sources else "no_evidence"
    elif intent == "recommend":
        try:
            from .recommendations import recommend
            recommendation = recommend(reader, context)
            answer, status, sources = recommendation["answer"], recommendation["status"], recommendation["sources"]
            cards, missing = recommendation["cards"], recommendation["missing_fields"]
            has_more = recommendation.get("has_more", False)
        except Exception:
            answer, status = "Không thể tra cứu suất phù hợp lúc này. Bạn có thể đặt vé trực tiếp hoặc thử lại sau.", "tool_unavailable"
    else:
        call = ToolCall(name=intent, context=context)
        missing = ["film_id"] if intent == "search_films" and not context.film_id else missing_fields(call)
        if missing:
            answer = "Bạn vui lòng chọn hoặc cung cấp " + ", ".join(LABELS[f] for f in missing) + " để mình tra cứu chính xác."
            status = "needs_clarification"
        else:
            try:
                sources = run_tool(reader, call, evening)
                empty_answers = {
                    "get_positive_films": "Chưa có phim đủ đánh giá hợp lệ và còn suất chiếu theo lựa chọn của bạn.",
                    "get_showtimes": "Không còn suất chiếu phù hợp với phim, rạp và ngày đã chọn.",
                    "get_ticket_prices": "Chưa có giá vé hoặc suất chiếu đã kết thúc/không còn hoạt động.",
                    "get_seat_availability": "Suất chiếu đã kết thúc hoặc không còn hoạt động.",
                    "search_films": "Không tìm thấy thông tin phim phù hợp.",
                }
                answer = "\n\n".join(s["text"] for s in sources) if sources else empty_answers[intent]
                status = "ok" if sources else "no_results"
            except Exception:
                answer = "Không thể tra cứu dữ liệu lúc này. Bạn có thể tiếp tục đặt vé trực tiếp hoặc thử lại sau."
                status = "tool_unavailable"
    links = [dict(title=s["title"], url=s["url"]) for s in sources if s["kind"] != "document"]
    state = dict(context=context.model_dump(mode="json"), pending_tool=intent if missing else None,
                 active_recommendation=intent == "recommend", evening=evening,
                 options=cards if intent == "recommend" or selection_changed else previous.get("options", []))
    result = dict(conversation_id=conversation_id, answer=answer, sources=sources, links=links, cards=cards, has_more=has_more,
                status=status, mode=mode, missing_fields=missing, context=context.model_dump(mode="json"),
                as_of=utcnow(), tool=intent if intent.startswith(("get_", "search_")) else None)
    now = result["as_of"]
    try:
        if request.conversation_id:
            # Do not overwrite a concurrent turn or recreate a deleted conversation.
            changed = db.execute(update(AIConversation).where(
                AIConversation.id == request.conversation_id,
                AIConversation.user_id == user_id,
                AIConversation.updated_at == previous_updated_at
            ).values(context=state, updated_at=now).execution_options(synchronize_session=False))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, "Hội thoại đã thay đổi. Vui lòng tải lại lịch sử trước khi gửi tiếp.")
        else:
            db.add(AIConversation(id=UUID(conversation_id), user_id=user_id,
                title=" ".join(request.message.split())[:200], context=state,
                created_at=now, updated_at=now))
            db.flush()
        db.add(AIMessage(conversation_id=UUID(conversation_id), role="user",
                         content=request.message, created_at=now))
        db.flush()
        metadata = jsonable_encoder({k: v for k, v in result.items() if k not in ("answer", "conversation_id")})
        db.add(AIMessage(conversation_id=UUID(conversation_id), role="assistant",
                         content=answer, details=metadata, created_at=now))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Không thể lưu hội thoại; vui lòng thử lại sau.")
    try:
        redis.setex(key, config.context_ttl_seconds, json.dumps(state))
    except Exception:
        pass  # A failed cache write must not turn a committed response into an error.
    return result
