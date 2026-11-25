"""The model selects evidence IDs; exact evidence text is rendered as the answer.

No model-generated action, URL, policy, price or SQL is executed or accepted.
Redis is used for rate limiting, never raw conversation text.
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
from .booking_tools import SAVED_LOOKUP, is_personal_order
from .models import AIConversation, AIMessage
from .models import utcnow
from .schemas import ToolCall, ToolContext
from .tools import validate_context, missing_fields, run_tool
from .rag import folded
from .knowledge_retrieval import retrieve_knowledge
from .history import owned_conversation

LABELS = {"film_id": "phim", "theater_id": "rạp", "show_date": "ngày xem", "showtime_id": "mã suất chiếu"}
# Owner reads have a 20-second deadline and the browser waits 30 seconds.
PLANNER_TIMEOUT = 5
CHAT_INFERENCE_BUDGET = 16
RECOMMENDATION_FILTERS = ("show_date", "genre", "party_size", "budget_amount", "budget_scope", "start_after")
SHOWTIME_SCOPE = ("film_id", "theater_id", "show_date")
SHOWTIME_DETAIL_TOOLS = {"get_ticket_prices", "get_seat_availability"}
SHOWTIME_PATTERN = r"(?:ma suat|suat chieu so)\s*(\d+)"
SHOWTIME_ORDINAL = re.compile(
    r"\bsuat\s+(?:(dau(?:\s+tien)?)|thu\s*(\d{1,2}|nhat|hai|ba|tu|bon|nam|sau|bay|tam|chin|muoi))\b"
)
ORDINAL_WORDS = {"nhat": 1, "hai": 2, "ba": 3, "tu": 4, "bon": 4, "nam": 5, "sau": 6, "bay": 7, "tam": 8, "chin": 9, "muoi": 10}
PARTY_PATTERN = re.compile(r"\b(\d{1,2}|hai|ba|bon|nam)\s*(?:nguoi|ve)\b")
VND_UNITS = r"k|nghin|ngan|trieu|tr|vnd|dong|d"
BUDGET_PATTERN = re.compile(
    rf"\b(?:duoi|ngan sach|toi da|tong(?=\s*\d+(?:[.,]\d+)?\s*(?:{VND_UNITS})\b))"
    rf"\s*(\d+(?:[.,]\d+)?)\s*({VND_UNITS})?\b"
)
DATE_CUE = re.compile(
    r"\b(?:thu\s+(?:hai|ba|tu|nam|sau|bay|[2-7])|chu nhat|cuoi (?:tuan|thang)|"
    r"(?:tuan|thang) (?:nay|sau|toi|ke tiep)|ngay\s+\d{1,2}|\d{1,2}[/-]\d{1,2}|"
    r"hom nay|ngay mai|ngay kia|toi nay|toi mai)\b"
)
START_AFTER_PATTERN = re.compile(r"\b(?:sau|tu)\s*(\d{1,2})(?:\s*(?:h|gio)|:)\s*(\d{2})?")
BOOKING_REQUEST = re.compile(r"\b(?:dat|mua)(?: [\w]+){0,4} ve\b")
BOOKING_ACTION = re.compile(r"\b(?:dat ho|giu ho|thanh toan ho|xac nhan thanh toan)\b")
BOOKING_POLICY = ("chinh sach", "huong dan", "cach ", "hoan tien", "doi ve", "huy ve", "giu ghe bao lau")
VENUE_HOURS_TERMS = ("mo cua", "dong cua", "gio hoat dong", "gio lam viec")
GENRE_PHRASES = {
    "phim hai": "Hài", "phim kinh di": "Kinh dị", "phim hanh dong": "Hành động",
    "phim hoat hinh": "Hoạt hình", "phim tinh cam": "Tình cảm", "khoa hoc vien tuong": "Khoa học viễn tưởng",
    "phim vien tuong": "Viễn tưởng", "phim tam ly": "Tâm lý", "phim phieu luu": "Phiêu lưu",
    "phim gia dinh": "Gia đình", "phim giat gan": "Giật gân",
}
GENRE_DISCOVERY = re.compile(rf"\b(?:{'|'.join(GENRE_PHRASES)}) (?:gi|nao)\b")
FILM_LIST_PATTERN = (
    r"\b(?:danh sach|liet ke)(?: nhung| cac)? phim\b|\bphim (?:gi|nao)\b"
    r"|^\s*(?:(?:nhung|cac) )?phim (?:hien )?(?:dang chieu|sap chieu|sap ra mat)\b"
)
CURRENT_FILM_PATTERN = r"\b(?:dang chieu|hom nay|ngay mai|ngay kia|toi nay|toi mai)\b"
UPCOMING_FILM_PATTERN = r"\b(?:sap chieu|sap ra mat|chua ra mat|chua khoi chieu|chieu sap toi)\b"
FILM_EDUCATION_TERMS = ("cinematography", "camera movement", "chuyen dong may quay", "chuyen dong cua may quay",
                        "dolly", "slider", "goc may", "goc quay", "co canh", "khung hinh", "iso", "pan ngang",
                        "lia may", "over-the-shoulder", "framing", "muc phim xem them")
RATE_SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return n
"""


def detect_intent(message):
    text = folded(message)
    policy = any(term in text for term in BOOKING_POLICY)
    booking_request = BOOKING_REQUEST.search(text)
    if booking_request and (policy or any(term in text for term in ("nhu the nao", "the nao", "lam sao"))):
        return "knowledge"
    if not policy and BOOKING_ACTION.search(text):
        return "out_of_scope"
    if not policy and is_personal_order(text):
        return "get_my_booking"
    if any(w in text for w in ("don hang cua", "don hang toi")):
        return "out_of_scope"
    if not policy and "thanh toan" not in text and booking_request:
        return "recommend"
    if "la gi" in text and is_film_education(text):
        return "knowledge"
    if any(w in text for w in ("khen", "tich cuc")):
        return "get_positive_films"
    explicit_recommend = any(w in text for w in ("de xuat phim", "goi y phim", "tu van phim", "ngan sach", "tim phim"))
    if explicit_recommend or (
        "muon xem" in text
        and not any(w in text for w in ("lich chieu", "gia ve", "gia ghe", "ghe trong", "con ghe", "ghe nao"))
    ):
        return "recommend"
    if policy or "thanh toan" in text:
        return "knowledge"
    if any(w in text for w in ("ghe trong", "con ghe", "ghe nao")):
        return "get_seat_availability"
    if any(w in text for w in ("gia ve", "bao nhieu tien", "gia ghe")):
        return "get_ticket_prices"
    if "lich chieu" in text or ("may gio" in text and not any(w in text for w in VENUE_HOURS_TERMS)):
        return "get_showtimes"
    if "suat chieu" in text and re.search(r"\b(?:luc|vao)\s*\d{1,2}(?:h|\s*gio|:)", text):
        return "get_showtimes"
    if is_filtered_film_discovery(text):
        return "recommend"
    if re.search(FILM_LIST_PATTERN, text) or re.fullmatch(r"(?:hien tai |hien )?phim dang chieu[?!.\s]*", text):
        if re.search(UPCOMING_FILM_PATTERN, text):
            return "get_upcoming_films"
        return "get_showing_films"
    if "suat chieu" in text or "toi nay" in text:
        return "get_showtimes"
    if is_film_education(text):
        return "knowledge"
    if any(w in text for w in ("phim", "the loai", "noi dung")):
        return "search_films"
    return "knowledge"


def is_filtered_film_discovery(text):
    if re.search(UPCOMING_FILM_PATTERN, text):
        return False
    genre = GENRE_DISCOVERY.search(text)
    if (re.search(FILM_LIST_PATTERN, text) or genre) and (PARTY_PATTERN.search(text) or BUDGET_PATTERN.search(text) or START_AFTER_PATTERN.search(text)):
        return True
    return bool(genre and re.search(CURRENT_FILM_PATTERN, text))


def is_film_education(text):
    return any(re.search(rf"\b{term}\b", text) for term in FILM_EDUCATION_TERMS) or (
        "la gi" in text and any(w in text for w in ("the loai", "dien anh", "quay phim", "dung phim"))
    )


def infer_context(reader, message, context, _matched=None, _ambiguous=None):
    text = folded(message)
    today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
    if "ngay kia" in text:
        context.show_date = today + timedelta(days=2)
        if _matched is not None:
            _matched.add("show_date")
    elif "ngay mai" in text or "toi mai" in text:
        context.show_date = today + timedelta(days=1)
        if _matched is not None:
            _matched.add("show_date")
    elif "hom nay" in text or "toi nay" in text:
        context.show_date = today
        if _matched is not None:
            _matched.add("show_date")
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", message)
    if date_match:
        try:
            context.show_date = datetime.strptime(date_match.group(), "%Y-%m-%d").date()
            if _matched is not None:
                _matched.add("show_date")
        except ValueError:
            raise HTTPException(422, "Ngày không hợp lệ")
    matches = reader.matches(message)
    for field in ("film_id", "theater_id"):
        rows = getattr(matches, field)
        if len(rows) == 1:
            setattr(context, field, rows[0].id)
            if _matched is not None:
                _matched.add(field)
        elif len(rows) > 1 and _ambiguous is not None:
            _ambiguous.add(field)
    match = re.search(SHOWTIME_PATTERN, text)
    if match:
        context.showtime_id = int(match[1])
        if _matched is not None:
            _matched.add("showtime_id")
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
    for phrase, genre in GENRE_PHRASES.items():
        if phrase in text:
            context.genre = genre
    party = PARTY_PATTERN.search(text)
    if party:
        value = {"hai": 2, "ba": 3, "bon": 4, "nam": 5}.get(party[1])
        context.party_size = value if value is not None else int(party[1])
    amount = BUDGET_PATTERN.search(text)
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
    clock = START_AFTER_PATTERN.search(text)
    if clock:
        try:
            context.start_after = time(int(clock[1]), int(clock[2] or 0))
        except ValueError:
            raise HTTPException(422, "Giờ xem không hợp lệ")
    if any(w in text for w in ("toi nay", "toi mai")) and context.start_after is None:
        context.start_after = time(18)
    if any(w in text for w in ("chinh sach", "cach dat ve", "huong dan dat ve", "hoan tien", "huy ve", "giu ghe bao lau")):
        context.knowledge_scope = "policy"
    elif is_film_education(text):
        context.knowledge_scope = "film_education"
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


def showtime_choices(sources, context):
    scope = context.model_dump(mode="json", include=set(SHOWTIME_SCOPE))
    choices = {}
    for source in sources:
        match = re.fullmatch(r"showtime:([1-9]\d*)", source["id"])
        if match and source["url"] == f"/seat-selection/{match[1]}":
            showtime_id = int(match[1])
            choices[showtime_id] = dict(scope, showtime_id=showtime_id)
    return list(choices.values())


def showtime_ordinal(message_text):
    match = SHOWTIME_ORDINAL.search(message_text)
    if not match:
        return None
    if match[1]:
        return 1
    value = match[2]
    return int(value) if value.isdecimal() else ORDINAL_WORDS[value]


def lookup_ordinal_in_scope(reader, context, ordinal, evening):
    lookup = ToolCall(name="get_showtimes", context=context)
    missing = missing_fields(lookup)
    if missing:
        labels = ", ".join(LABELS[field] for field in missing)
        return [], (f"Bạn vui lòng chọn {labels} để mình tra đúng suất nhé.", "needs_clarification", missing)
    choices = showtime_choices(run_tool(reader, lookup, evening), context)
    if not 1 <= ordinal <= len(choices):
        return choices, ("Mình chưa tìm thấy suất tương ứng với phim, rạp và ngày đã chọn. Bạn thử chọn suất khác nhé.",
                         "no_results", [])
    context.showtime_id = choices[ordinal - 1]["showtime_id"]
    return choices, None


def chat(db, user_id, request, redis, reader, config, *, graph=None, booking=None):
    inference_deadline = monotonic() + CHAT_INFERENCE_BUDGET
    if hasattr(reader, "deadline"):
        reader.deadline = min(reader.deadline, inference_deadline)
    try:
        count = redis.eval(RATE_SCRIPT, 1, f"ai:rate:{user_id}")
        if count > config.requests_per_minute:
            raise HTTPException(429, "Bạn gửi quá nhiều câu hỏi. Vui lòng thử lại sau một phút.")
        conversation_id = str(request.conversation_id or uuid4())
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
    if request.reset_filters:
        previous = {}
    previous_context = ToolContext.model_validate(previous.get("context", {}))
    submitted = request.context.model_dump(mode="json", exclude_unset=True)
    values = previous.get("context", {}) | submitted
    from .grounding import clarification_needed, covers_specifics, explicit_questions
    message_text = folded(request.message)
    deterministic = detect_intent(request.message)
    personal_lookup = deterministic == "get_my_booking"
    explicit_recommendation = deterministic == "recommend" and (
        BOOKING_REQUEST.search(message_text) or is_filtered_film_discovery(message_text)
    )
    explicit_showtime = re.search(SHOWTIME_PATTERN, message_text) or (
        request.context.showtime_id is not None and request.context.showtime_id != previous_context.showtime_id
    )
    ordinal = None if explicit_showtime else showtime_ordinal(message_text)
    pending_ordinal = None if explicit_showtime else previous.get("pending_ordinal")
    pending_tool = previous.get("pending_tool")
    listing = deterministic in {"get_showing_films", "get_upcoming_films"}
    clarification = clarification_needed(request.message) if deterministic == "knowledge" else None
    if listing:
        # A list request starts a new film lookup even when the UI echoes a selected film or an old date.
        selected_date = request.context.show_date if request.context.show_date != previous_context.show_date else None
        values = {"theater_id": values.get("theater_id"), "show_date": selected_date}
        if "genre" in submitted and request.context.genre != previous_context.genre:
            values["genre"] = request.context.genre
    context = ToolContext.model_validate(values)
    if not personal_lookup:
        context = infer_preferences(request.message, context)
    explicit_knowledge = any(word in message_text for word in (
        "cach ", "chinh sach", "huong dan", "hoan tien", "doi ve", "huy ve", "thanh toan",
        "giu ghe bao lau", "la gi", *VENUE_HOURS_TERMS,
    ))
    explicit_knowledge = explicit_knowledge or clarification or is_film_education(message_text) or (
        deterministic == "knowledge" and bool(BOOKING_REQUEST.search(message_text))
    )
    refining_recommendation = (
        not listing and previous.get("active_recommendation") and not explicit_knowledge
        and (deterministic == "knowledge"
             or deterministic == "get_showtimes" and not any(
                 word in message_text for word in ("lich chieu", "suat chieu", "may gio")))
        and any(getattr(context, field) != getattr(previous_context, field)
                for field in RECOMMENDATION_FILTERS)
    )
    proposed_intent, planner_mode = None, "retrieval_only"
    planned_listing_date = None
    agent_result, agent_context_ready = None, False
    if config.react_lookup_enabled and config.llm_provider != "disabled" and not (personal_lookup or explicit_knowledge):
        from . import react_lookup

        if react_lookup.applies(message_text):
            try:
                context = infer_context(reader, request.message, context)
                needed = [name for name in SHOWTIME_SCOPE if not getattr(context, name)]
                party = react_lookup.party_size(message_text, context.party_size)
                if not 1 <= party <= 20:
                    agent_result = react_lookup.LookupResult("Bạn muốn kiểm tra từ 1 đến 20 ghế cho bao nhiêu người?", "needs_clarification", [], [])
                elif needed:
                    labels = ", ".join(LABELS[name] for name in needed)
                    agent_result = react_lookup.LookupResult(f"Hãy chọn {labels} rồi gửi lại yêu cầu kiểm tra các suất.", "needs_clarification", [], needed)
                else:
                    context.party_size = party
                    agent_context_ready = True
                    agent_result = react_lookup.run_lookup(reader, config, request.message, context,
                                                          "toi nay" in message_text, party, inference_deadline)
                    if agent_result is None and monotonic() >= inference_deadline:
                        agent_result = react_lookup.LookupResult("Chưa tra được dữ liệu trong thời gian cho phép. Bạn có thể thử lại.", "tool_unavailable", [], [])
            except HTTPException:
                agent_result = react_lookup.LookupResult("Chưa xác minh được phim, rạp hoặc ngày chiếu. Bạn có thể thử lại.", "tool_unavailable", [], [])

    if agent_result is not None:
        proposed_intent, planner_mode = "react_lookup", "react_lookup"
    elif agent_context_ready:
        proposed_intent, planner_mode = "get_showtimes", "react_fallback"
    elif deterministic == "out_of_scope" or listing or clarification or personal_lookup or explicit_recommendation:
        proposed_intent = deterministic
    elif config.llm_provider == "openai" and deterministic == "knowledge" and explicit_knowledge:
        proposed_intent = "knowledge"
    elif refining_recommendation:
        proposed_intent = "recommend"
    elif deterministic in SHOWTIME_DETAIL_TOOLS and (context.showtime_id or explicit_showtime or ordinal is not None):
        proposed_intent = deterministic
    elif config.llm_provider != "disabled":
        try:
            from .llm import plan
            planner_start = monotonic()
            planner_deadline = min(inference_deadline, planner_start + PLANNER_TIMEOUT)
            timeout = min(config.llm_timeout_seconds, planner_deadline - planner_start)
            if timeout <= 0:
                raise TimeoutError("Chat inference budget exhausted")
            planner_settings = config.model_copy(update={"llm_timeout_seconds": timeout})
            proposed = plan(
                planner_settings,
                request.message,
                context,
                datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date(),
                pending_tool,
                bool(previous.get("active_recommendation")),
                planner_deadline,
            )
            patch = proposed.context.model_dump(mode="json", exclude_unset=True, exclude_none=True,
                exclude={"film_id", "theater_id", "showtime_id"})
            patch = {key: value for key, value in patch.items() if value != ""}
            if patch.get("start_after") == "00:00:00" and not re.search(r"\b0{1,2}(?:h|\s*gio|:00)\b", message_text):
                patch.pop("start_after", None)
            for field in ("party_size", "budget_scope", "knowledge_scope"):
                default = ToolContext.model_fields[field].default
                if patch.get(field) == default and getattr(context, field) != default:
                    patch.pop(field)  # A model default must not erase a known preference.
            context = ToolContext.model_validate(context.model_dump(mode="json") | patch)
            if DATE_CUE.search(message_text):
                planned_listing_date = proposed.context.show_date
            proposed_intent, planner_mode = proposed.intent, "model_planned"
        except Exception:
            planner_mode = "model_unavailable"
    preliminary = proposed_intent or deterministic
    if not (agent_result is not None or agent_context_ready):
        if config.llm_provider == "openai" and planner_mode == "model_planned":
            if deterministic in {"out_of_scope", "get_my_booking"}:
                preliminary = proposed_intent = deterministic
        elif (deterministic in {"out_of_scope", "get_seat_availability", "get_ticket_prices", "get_positive_films"} or (
                deterministic == "recommend" and preliminary == "search_films") or (
                deterministic == "knowledge" and explicit_knowledge)):
            preliminary = proposed_intent = deterministic
    is_listing = preliminary in {"get_showing_films", "get_upcoming_films"}
    is_personal = preliminary == "get_my_booking"
    if is_listing and not listing:
        selected_date = request.context.show_date if request.context.show_date != previous_context.show_date else None
        context = context.model_copy(update={
            "film_id": None, "showtime_id": None, "show_date": planned_listing_date or selected_date,
        })
    read_context = not (is_listing or agent_result is not None or agent_context_ready) and (
        preliminary not in {"knowledge", "out_of_scope", "get_my_booking"}
        or (bool(pending_tool) and preliminary == "knowledge" and not explicit_knowledge)
    )
    matched_fields, ambiguous_fields = set(), set()
    # FAQ needs only the AI-owned approved KB; do not call Catalog/Cinema unnecessarily.
    if read_context:
        context = infer_context(reader, request.message, context, _matched=matched_fields, _ambiguous=ambiguous_fields)
    if not is_personal:
        context = infer_preferences(request.message, context)
    if (is_listing or is_personal or preliminary == "out_of_scope" or agent_result is not None or agent_context_ready
            or (preliminary == "knowledge" and explicit_knowledge)):
        ordinal = None
    detail_lookup = preliminary in SHOWTIME_DETAIL_TOOLS or pending_tool in SHOWTIME_DETAIL_TOOLS
    ambiguous_scope = bool(ambiguous_fields) and detail_lookup and (ordinal is not None or pending_ordinal is not None)
    if ambiguous_scope:
        for field in ambiguous_fields:
            setattr(context, field, None)
    scope_changed = any(
        getattr(context, field) != getattr(previous_context, field) for field in (*SHOWTIME_SCOPE, "start_after")
    )
    needs_schedule = ordinal is not None and (ambiguous_scope or scope_changed or pending_ordinal is not None)
    if needs_schedule:
        context.showtime_id = None
    elif ordinal is not None:
        choices = previous.get("options", [])
        if not 1 <= ordinal <= len(choices):
            raise HTTPException(422, "Chưa có suất tương ứng trong danh sách gần nhất; hãy chọn lại suất")
        selected = choices[ordinal - 1]
        context.showtime_id, context.film_id, context.theater_id = selected["showtime_id"], selected["film_id"], selected["theater_id"]
        if selected.get("show_date"):
            context.show_date = datetime.strptime(selected["show_date"], "%Y-%m-%d").date()
    if "showtime_id" in matched_fields and (
            preliminary in SHOWTIME_DETAIL_TOOLS or pending_tool in SHOWTIME_DETAIL_TOOLS):
        for field in SHOWTIME_SCOPE:
            submitted_changed = field in submitted and getattr(request.context, field) != getattr(previous_context, field)
            if field not in matched_fields and not submitted_changed:
                setattr(context, field, None)
    selection_changed = any(getattr(context, field) != getattr(previous_context, field)
                            for field in SHOWTIME_SCOPE)
    # The UI echoes the full context, so an unchanged ID may still be stale.
    if (context.showtime_id is not None and context.showtime_id == previous_context.showtime_id
            and selection_changed and ordinal is None and not explicit_showtime):
        context.showtime_id = None
    if read_context:
        validate_context(reader, context)
    intent = proposed_intent or (preliminary if not read_context or preliminary == "recommend" and not pending_tool
        else resolve_intent(reader, request.message, context, pending_tool))
    if pending_tool and read_context and not explicit_knowledge and not (agent_result is not None or agent_context_ready):
        resolved = resolve_intent(reader, request.message, context, pending_tool)
        if resolved == pending_tool:
            intent = pending_tool
    # A known booking context remains relevant to short answers such as "hai vé".
    if (pending_tool == "recommend" and intent in {"knowledge", "recommend", "get_showtimes"}
            and not explicit_knowledge and len(message_text.split()) <= 8
            and not any(word in message_text for word in ("lich chieu", "suat chieu"))):
        intent = "recommend"
    evening = "toi nay" in message_text or (
        previous.get("evening", False) and (intent == pending_tool or refining_recommendation)
    )
    scoped_ordinal = ordinal if needs_schedule else None
    if ordinal is None and intent == pending_tool:
        scoped_ordinal = pending_ordinal
    ordinal_choices, ordinal_notice = None, None
    if scoped_ordinal is not None and intent in SHOWTIME_DETAIL_TOOLS:
        context.showtime_id = None
        ordinal_choices, ordinal_notice = lookup_ordinal_in_scope(reader, context, scoped_ordinal, evening)
    sources, missing = [], []
    status, mode = "ok", planner_mode
    cards, has_more = [], False
    private_order = None
    if agent_result is not None:
        answer, status, sources, missing = agent_result
    elif ordinal_notice is not None:
        answer, status, missing = ordinal_notice
    elif intent == "get_my_booking":
        if booking is None:
            answer, status = "Chưa thể tra đơn lúc này. Bạn có thể thử lại sau.", "tool_unavailable"
        else:
            answer, status, private_order = booking.get_my_booking(message_text)
    elif intent == "out_of_scope":
        answer = "Mình có thể tìm suất để bạn đặt vé trong chat hoặc kiểm tra trạng thái đơn của bạn. Giữ ghế, tạo đơn và thanh toán cần bạn xác nhận trên giao diện."
        status = "out_of_scope"
    elif intent in {"get_showing_films", "get_upcoming_films"}:
        try:
            if intent == "get_upcoming_films":
                sources, truncated = reader.upcoming_films(context)
                lead, empty = "Các phim sắp chiếu", "Mình chưa tìm thấy phim sắp chiếu trong danh mục."
            else:
                if re.search(r"\brap\s+\w+", message_text):
                    theaters = reader.matches(request.message).theater_id
                    if len(theaters) == 1:
                        context.theater_id = theaters[0].id
                theater = reader.names(context).theater_name if context.theater_id else None
                if theater and context.show_date is None:
                    context.show_date = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
                sources, truncated = reader.showing_films(context)
                where = f" tại {theater}" if theater else ""
                if context.show_date:
                    when = f"ngày {context.show_date:%d/%m/%Y}"
                    lead = f"Các phim có suất chiếu sắp tới trong {when}{where}"
                    empty = f"Mình chưa tìm thấy suất chiếu sắp tới trong {when}{where}."
                else:
                    lead, empty = "Các phim đang chiếu", "Mình chưa tìm thấy phim đang chiếu trong danh mục."
            if sources:
                answer = lead + ":\n" + "\n".join(f"• {source['title']}" for source in sources)
                if truncated:
                    answer += f"\n\nĐang hiển thị {len(sources)} phim đầu tiên."
            else:
                answer, status = empty, "no_results"
        except Exception:
            answer, status = "Mình chưa tra cứu được danh sách phim lúc này. Bạn có thể xem trang Phim hoặc thử lại sau.", "tool_unavailable"
    elif intent == "knowledge" and clarification:
        graph_state = "disabled"
        answer, status = clarification, "needs_clarification"
    elif intent == "knowledge":
        split = config.llm_provider != "disabled"
        retrieval_failed = False
        try:
            sources, graph_state, _ = retrieve_knowledge(db, request.message, context.knowledge_scope,
                graph=graph, split=split, strategy=config.retrieval_strategy,
                embedding_url=config.embedding_url, reranker_url=config.reranker_url, deadline=inference_deadline)
        except Exception:
            db.rollback()
            mode = "retrieval_unavailable"
            try:
                sources, graph_state, _ = retrieve_knowledge(db, request.message, context.knowledge_scope,
                    graph=graph, split=split, deadline=inference_deadline)
            except Exception:
                db.rollback()
                sources, graph_state, retrieval_failed = [], "unavailable", True
        db.rollback()  # Do not occupy a database connection while waiting for the model.
        if retrieval_failed:
            answer, status = "Mình chưa thể tra cứu tài liệu lúc này. Bạn có thể thử lại sau.", "tool_unavailable"
        else:
            answer, status = "Mình chưa có đủ căn cứ trong các nguồn được duyệt để trả lời câu hỏi này.", "no_evidence"
            if graph_state == "conflict":
                answer = "Các nguồn đã duyệt đang có thông tin mâu thuẫn. Mình chưa thể xác nhận câu trả lời này."
                mode = "graph_conflict"
            elif graph_state == "ambiguous":
                answer = "Cụm từ này khớp với nhiều khái niệm. Bạn có thể nói rõ kỹ thuật hoặc ngữ cảnh cần tìm không?"
                status, mode = "needs_clarification", "graph_ambiguous"
            elif graph_state == "uncertain":
                answer = "Thông tin liên quan đang chờ xác minh. Mình chưa có đủ căn cứ để trả lời."
                mode = "graph_uncertain"
            else:
                questions = explicit_questions(request.message) if split else (request.message,)
                sources = [s for s in sources if any(covers_specifics(part, s["text"]) for part in questions)]
                sources, selection_mode = select_evidence(request.message, sources, config, deadline=inference_deadline)
                if selection_mode != "retrieval_only":
                    mode = selection_mode
                if sources and config.llm_provider == "disabled":
                    answer, status = "\n\n".join(s["text"] for s in sources), "ok"
                elif sources:
                    try:
                        from .llm import grounded_reply
                        policy = context.knowledge_scope == "policy"
                        reply = grounded_reply(config, request.message, sources, extractive=policy, deadline=inference_deadline)
                        status = reply.status
                        if reply.text:
                            answer = reply.text
                        if status == "ok":
                            sources = [source for source in sources if source["id"] in reply.source_ids]
                            mode = "grounded_extract" if policy else "grounded_generation"
                    except Exception:
                        answer = "Mình chưa thể kiểm tra căn cứ lúc này. Bạn có thể thử lại sau."
                        mode = "grounding_unavailable"
                if status != "ok":
                    sources = []
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
                if mode == "react_fallback" and sources:
                    answer = "\n\n".join(react_lookup.showtime_description(source) for source in sources)
                    answer += "\n\nMình mới tìm được lịch chiếu. Hãy chọn suất để kiểm tra ghế và giá."
                    status = "partial"
            except Exception:
                answer = "Không thể tra cứu dữ liệu lúc này. Bạn có thể tiếp tục đặt vé trực tiếp hoặc thử lại sau."
                status = "tool_unavailable"
    links = [dict(title=s["title"], url=s["url"]) for s in sources if s["kind"] != "document"]
    if intent in {"get_showtimes", "react_lookup"}:
        options = showtime_choices(sources, context)
    elif ordinal_choices is not None:
        options = ordinal_choices
    elif intent == "recommend" or is_listing or selection_changed or needs_schedule:
        options = cards
    else:
        options = previous.get("options", [])
    state = dict(context=context.model_dump(mode="json"), pending_tool=intent if missing and intent != "react_lookup" else None,
                 active_recommendation=intent == "recommend", evening=evening, options=options)
    if ordinal_choices is not None and missing:
        state["pending_ordinal"] = scoped_ordinal
    if intent == "get_my_booking":
        state = previous | {"context": context.model_dump(mode="json")}
    result = dict(conversation_id=conversation_id, answer=answer, sources=sources, links=links, cards=cards, has_more=has_more,
                status=status, mode=mode, missing_fields=missing, context=context.model_dump(mode="json"),
                as_of=utcnow(), tool=intent if intent.startswith(("get_", "search_")) or intent == "react_lookup" else None)
    if intent == "knowledge" and graph is not None:
        result["graph_retrieval"] = graph_state
    if intent in {"recommend", "get_showtimes", "react_lookup"} or request.reset_filters or needs_schedule or ordinal_choices is not None:
        result["showtime_options"] = True
    if private_order is not None:
        result["booking"] = private_order
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
        metadata = jsonable_encoder({k: v for k, v in result.items() if k not in ("answer", "conversation_id", "booking")})
        db.add(AIMessage(conversation_id=UUID(conversation_id), role="assistant",
                         content=SAVED_LOOKUP if intent == "get_my_booking" else answer, details=metadata, created_at=now))
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Không thể lưu hội thoại; vui lòng thử lại sau.")
    return result
