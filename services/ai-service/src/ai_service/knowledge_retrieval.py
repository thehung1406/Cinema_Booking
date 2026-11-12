"""Retrieve evidence for the whole turn within a shared top-k budget."""
import re

from neo4j.exceptions import DriverError, Neo4jError

from .graph import graph_evidence, merge_evidence
from .grounding import explicit_questions
from .rag import current_evidence, folded, retrieve


# Bilingual domain vocabulary used for ranking only. The original question and
# approved text are the only inputs to the answer verifier.
FILM_TERMS = (
    ("lia may", "pan"),
    ("tai cho", "stationary same location"),
    ("e[- ]kip", "crew crews"),
    ("nguoi phu trach hinh anh", "director of photography cinematographer"),
    ("goc may", "camera angle angles"),
    ("goc quay", "camera angle angles"),
    ("co canh", "shot"),
    ("nhan vat", "character"),
    ("nho be", "small"),
    ("yeu the", "weak"),
    ("tu dau den chan", "head to toe"),
    ("phim xem them", "further viewing"),
    ("phuong tien ghi hinh", "capture recording tạo hình ảnh chuyển động"),
    ("framing", "khung hinh"),
    ("filters?", "bo loc"),
)
BLOCKED_GRAPH_STATES = ("conflict", "ambiguous", "uncertain")


def text_query(question, scope):
    if scope != "film_education":
        return question
    normalized = folded(question)
    additions = [translation for pattern, translation in FILM_TERMS
                 if re.search(rf"\b{pattern}\b", normalized)]
    return " ".join([question, *additions])


def requested_source(question, sources):
    """Narrow a film question that explicitly asks about a book or summary."""
    normalized = folded(question)
    if re.search(r"\b(?:ban tom tat|(?:vietnamese|the) (?:\w+ ){0,3}summary)\b", normalized):
        return [source for source in sources if re.search(r"\b(?:tom tat|summary)\b", folded(source.get("title", "")))]
    if re.search(r"\b(?:theo sach|sach (?:co|noi|dung|lay)|in the book|according to the book)\b", normalized):
        return [source for source in sources if source.get("provenance", {}).get("source_type") == "pdf"
                or re.search(r"\b(?:book|textbook|sach)\b", folded(source.get("title", "")))]
    return sources


def retrieve_knowledge(db, question, scope, *, graph=None, limit=3, split=True, **options):
    parts = explicit_questions(question) if split else (question,)
    candidates, states, queries = [], [], []
    for part in parts:
        query = text_query(part, scope)
        queries.append(query)
        sources = retrieve(db, query, limit=limit, scope=scope, **options)
        if graph is not None:
            try:
                graph_sources, state = graph_evidence(db, graph, part, scope, limit=limit)
            except (DriverError, Neo4jError, ValueError):
                graph_sources, state = [], "unavailable"
            sources = merge_evidence(sources, graph_sources, state, limit)
            states.append(state)
        candidates.append(iter(sources))

    for state in BLOCKED_GRAPH_STATES:
        if state in states:
            return [], state, queries
    state = next((state for state in ("matched", "unavailable", "no_match") if state in states), "disabled")
    merged = {}
    while len(merged) < limit:
        previous_count = len(merged)
        for ranked in candidates:
            source = next((source for source in ranked if source["id"] not in merged), None)
            if source is not None:
                merged[source["id"]] = source
            if len(merged) == limit:
                break
        if len(merged) == previous_count:
            break
    sources = list(merged.values())[:limit]
    return current_evidence(db, sources, scope) if graph is not None else sources, state, queries
