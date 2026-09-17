"""The model selects evidence IDs; exact evidence text is rendered as the answer.

No model-generated action, URL, policy, price or SQL is executed or accepted.
Redis retains only user-scoped context, with a TTL, never raw conversation text.
"""
import json
import re
from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlmodel import select
from app.core.config import settings
from app.core.redis import redis_client
from app.models import Film, Theater
from app.models.ai import utcnow
from app.schemas.ai import ToolCall, ToolContext
from app.services.ai_tools import validate_context, missing_fields, run_tool
from app.services.rag_service import folded, retrieve

LABELS = {"film_id": "phim", "theater_id": "rạp", "show_date": "ngày xem", "showtime_id": "mã suất chiếu"}
RATE_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return n
"""


def detect_intent(message):
    text = folded(message)
    if any(w in text for w in ("dat ho", "giu ho", "thanh toan ho", "xac nhan thanh toan", "don hang cua", "don hang toi")):
        return "out_of_scope"
    if any(w in text for w in ("khen", "tich cuc", "de xuat phim", "goi y phim")):
        return "get_positive_films"
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


def infer_context(db, message, context):
    text = folded(message)
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    if "ngay mai" in text:
        context.show_date = today + timedelta(days=1)
    elif "hom nay" in text or "toi nay" in text:
        context.show_date = today
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if date_match:
        try:
            context.show_date = datetime.strptime(date_match.group(), "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(422, "Ngày không hợp lệ")
    for field, model, attribute in (("film_id", Film, "title"), ("theater_id", Theater, "name")):
        matches = [row for row in db.exec(select(model)).all() if len(folded(getattr(row, attribute))) > 2 and folded(getattr(row, attribute)) in text]
        if len(matches) == 1:
            setattr(context, field, matches[0].id)
    match = re.search(r"(?:ma suat|suat chieu so)\s*(\d+)", text)
    if match:
        context.showtime_id = int(match[1])
    return context


def select_evidence(question, evidence):
    if not settings.AI_MODEL_URL or not evidence:
        return evidence, "retrieval_only"
    import httpx
    try:
        with httpx.Client(timeout=settings.AI_MODEL_TIMEOUT_SECONDS, trust_env=False) as client:
            response = client.post(settings.AI_MODEL_URL.rstrip("/") + "/select", json={"question": question, "evidence": evidence})
            response.raise_for_status()
            payload = response.json()
        ids = payload["evidence_ids"]
        allowed = {item["id"]: item for item in evidence}
        if not isinstance(ids, list) or len(ids) > len(allowed) or any(not isinstance(i, str) or i not in allowed for i in ids):
            raise ValueError("Invalid citation")
        return [allowed[i] for i in dict.fromkeys(ids)], "model_assisted"
    except Exception:
        return evidence, "model_unavailable"


def chat(db, user_id, request, redis=None):
    redis = redis if redis is not None else redis_client
    try:
        count = redis.eval(RATE_SCRIPT, 1, f"ai:rate:{user_id}")
        if count > settings.AI_REQUESTS_PER_MINUTE:
            raise HTTPException(429, "Bạn gửi quá nhiều câu hỏi. Vui lòng thử lại sau một phút.")
        conversation_id = str(request.conversation_id or uuid4())
        key = f"ai:context:{user_id}:{conversation_id}"
        previous_raw = redis.get(key) if request.conversation_id else None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Trợ lý tạm thời không khả dụng. Bạn vẫn có thể đặt vé trực tiếp.")
    if request.conversation_id and previous_raw is None:
        raise HTTPException(404, "Hội thoại đã hết hạn; hãy bắt đầu cuộc trò chuyện mới.")
    previous = json.loads(previous_raw) if previous_raw else {}
    values = previous.get("context", {}) | request.context.model_dump(mode="json", exclude_unset=True)
    context = infer_context(db, request.message, ToolContext.model_validate(values))
    validate_context(db, context)
    intent = detect_intent(request.message)
    explicit_topic = any(w in folded(request.message) for w in ("cach", "chinh sach", "huong dan", "hoan", "huy", "thanh toan"))
    if intent == "knowledge" and not explicit_topic and previous.get("pending_tool") and len(request.message.split()) <= 8:
        intent = previous["pending_tool"]
    evening = "toi nay" in folded(request.message) or (previous.get("evening", False) and intent == previous.get("pending_tool"))
    sources, missing = [], []
    status, mode = "ok", "retrieval_only"
    if intent == "out_of_scope":
        answer = "Mình hỗ trợ tra cứu phim và hướng dẫn đặt vé. Bạn cần tự chọn ghế, tạo đơn và thanh toán trên giao diện; trợ lý chưa hỗ trợ tra đơn cá nhân."
        status = "out_of_scope"
    elif intent == "knowledge":
        sources = retrieve(db, request.message)
        db.rollback()  # Do not occupy a database connection while waiting for the model.
        sources, mode = select_evidence(request.message, sources)
        answer = "\n\n".join(s["text"] for s in sources) if sources else "Chưa có tài liệu đã duyệt đủ căn cứ cho câu hỏi này. Bạn có thể xem hướng dẫn trên giao diện hoặc liên hệ rạp."
        status = "ok" if sources else "no_evidence"
    else:
        call = ToolCall(name=intent, context=context)
        missing = ["film_id"] if intent == "search_films" and not context.film_id else missing_fields(call)
        if missing:
            answer = "Bạn vui lòng chọn hoặc cung cấp " + ", ".join(LABELS[f] for f in missing) + " để mình tra cứu chính xác."
            status = "needs_clarification"
        else:
            try:
                sources = run_tool(db, call, evening)
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
    state = dict(context=context.model_dump(mode="json"), pending_tool=intent if missing else None, evening=evening)
    try:
        redis.setex(key, settings.AI_CONTEXT_TTL_SECONDS, json.dumps(state))
    except Exception:
        raise HTTPException(503, "Không thể lưu ngữ cảnh; hãy thử lại hoặc đặt vé trực tiếp.")
    return dict(conversation_id=conversation_id, answer=answer, sources=sources, links=links,
                status=status, mode=mode, missing_fields=missing, context=context.model_dump(mode="json"),
                as_of=utcnow(), tool=intent if intent.startswith(("get_", "search_")) else None)
