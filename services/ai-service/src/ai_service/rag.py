"""Versioned lexical vector baseline. Do not ingest prices, seats or user reviews."""
import hashlib
import math
from time import monotonic
import re
import unicodedata
from collections import Counter
from types import SimpleNamespace
from sqlalchemy import delete
from sqlmodel import select
from .models import KnowledgeDocument, KnowledgeChunk
from .models import utcnow

EMBEDDING_VERSION = "lexical-hash-256-v2"
# Chunks are at most 4,000 characters; 500 fit both inference request limits.
DENSE_BATCH_SIZE = 500
STOPWORDS = {"toi", "ban", "la", "va", "co", "khong", "cua", "cho", "mot", "nhung", "cac", "duoc", "the", "nao", "gi", "ve", "muon", "hoi"}


def folded(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tokens(text):
    normalized = folded(text)
    terms = set(re.findall(r"[a-z0-9]+", normalized)) - STOPWORDS
    # Preserve domain phrases that would lose meaning after stop-word removal.
    for phrase in ("dat ve", "giu ghe", "gia ve", "lich chieu", "suat chieu", "thanh toan", "danh gia", "hoan tien", "doi ve", "huy ve"):
        if phrase in normalized:
            terms.add(phrase.replace(" ", "_"))
    return terms


def embed(text):
    vector = [0.0] * 256
    for token in tokens(text):
        index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % len(vector)
        vector[index] += 1
    norm = math.sqrt(sum(v*v for v in vector)) or 1
    return [v/norm for v in vector]


def safe_source_url(url):
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if (url.startswith("/") and not url.startswith("//") and "\\" not in url) or (parsed.scheme == "https" and parsed.netloc and not parsed.username):
        return url
    raise ValueError("Source URL must be an internal path or HTTPS URL")


def upsert_document(db, data, *, chunk_size=1200, chunk_overlap=0):
    """Replace chunks atomically when a document is updated or revoked."""
    if not isinstance(chunk_size, int) or not isinstance(chunk_overlap, int) or not 200 <= chunk_size <= 4000 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Invalid character chunk size or overlap")
    source_url = safe_source_url(data["source_url"])
    doc = db.exec(select(KnowledgeDocument).where(KnowledgeDocument.source_id == data["source_id"]).with_for_update()).first()
    if doc is None:
        doc = KnowledgeDocument(source_id=data["source_id"], title=data["title"], version=data["version"], source_url=source_url, effective_at=data["effective_at"])
    doc.title, doc.version, doc.source_url = data["title"], data["version"], source_url
    doc.approved, doc.effective_at, doc.updated_at = data.get("approved", False), data["effective_at"], utcnow()
    doc.provenance = data.get("provenance", {})
    db.add(doc)
    db.flush()
    db.exec(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    blocks = data.get("blocks") or [dict(text=p) for p in data.get("content", "").split("\n\n") if p.strip()]
    for block_index, block in enumerate(blocks):
        paragraph = block["text"].strip()
        for offset in range(0, len(paragraph), chunk_size - chunk_overlap):
            chunk = paragraph[offset:offset+chunk_size]
            if chunk:
                provenance = {k: v for k, v in block.items() if k != "text"}
                provenance.update(block_index=block_index, character_start=offset,
                                  character_end=offset+len(chunk), chunking="characters-1200-v1" if (chunk_size, chunk_overlap) == (1200, 0)
                                  else f"characters-{chunk_size}-overlap-{chunk_overlap}-v1")
                db.add(KnowledgeChunk(document_id=doc.id, content=chunk, embedding=embed(doc.title + " " + chunk),
                    embedding_version=EMBEDDING_VERSION, provenance=provenance))
            if offset + chunk_size >= len(paragraph):
                break
    db.commit()
    return doc


def retrieve(db, question, limit=3, *, strategy="lexical", scope=None, embedding_url="", reranker_url="", deadline=None):
    query_tokens, query_vector = tokens(question), embed(question)
    rows = db.exec(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
        KnowledgeDocument.approved == True, KnowledgeDocument.effective_at <= utcnow(),
        KnowledgeChunk.embedding_version == EMBEDDING_VERSION)).all()
    rows = [(SimpleNamespace(id=chunk.id, content=chunk.content, embedding=chunk.embedding, provenance=chunk.provenance),
             SimpleNamespace(id=doc.id, source_id=doc.source_id, title=doc.title, source_url=doc.source_url, version=doc.version, provenance=doc.provenance))
            for chunk, doc in rows if not scope or doc.provenance.get("scope", "policy") == scope]
    db.rollback()  # Primitive snapshots only; release the pool connection before remote inference.
    if strategy not in {"lexical", "bm25", "dense", "hybrid", "rerank"}:
        raise ValueError("Unsupported retrieval strategy")
    ranked = []
    bm25 = bm25_scores(question, [doc.title + " " + chunk.content for chunk, doc in rows]) if strategy != "lexical" else []
    semantic = []
    if strategy in {"dense", "hybrid", "rerank"} and rows:
        semantic = dense_scores(question, [chunk.content for chunk, _ in rows], embedding_url, deadline=deadline)
    lexical_order = sorted(range(len(rows)), key=lambda i: (-bm25[i], rows[i][0].id)) if bm25 else []
    dense_order = sorted(range(len(rows)), key=lambda i: (-semantic[i], rows[i][0].id)) if semantic else []
    fusion = {}
    for order in (lexical_order, dense_order):
        for rank, index in enumerate(order):
            fusion[index] = fusion.get(index, 0) + 1 / (60 + rank + 1)
    for index, (chunk, doc) in enumerate(rows):
        if strategy == "lexical":
            if len(query_tokens & tokens(doc.title + " " + chunk.content)) < 2:
                continue
            score = sum(a*b for a, b in zip(query_vector, chunk.embedding))
            eligible = score >= .15
        elif strategy == "bm25":
            score, eligible = bm25[index], bm25[index] > 0
        elif strategy == "dense":
            score, eligible = semantic[index], semantic[index] > 0
        else:
            score, eligible = fusion[index], bm25[index] > 0 or semantic[index] > 0
        if eligible:
            ranked.append((score, chunk, doc))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    if strategy == "rerank" and ranked:
        candidates = ranked[:20]
        scores = remote_scores(reranker_url, "/rerank",
            {"query": question, "texts": [c.content for _, c, _ in candidates]}, len(candidates), deadline=deadline)
        ranked = sorted([(scores[i], c, d) for i, (_, c, d) in enumerate(candidates)], key=lambda row: (-row[0], row[1].id))
    result = []
    for score, chunk, doc in ranked[:limit]:
        page = chunk.provenance.get("page_start")
        source_url = safe_source_url(doc.source_url)
        url = source_url.split("#")[0] + f"#page={page}" if page else source_url
        result.append(dict(id=f"doc:{chunk.id}", title=doc.title, text=chunk.content,
            url=url, version=doc.version, kind="document", score=score,
            provenance=doc.provenance | chunk.provenance, document_id=doc.id, source_id=doc.source_id))
    return result


def bm25_scores(question, documents, k1=1.5, b=.75):
    """Explicit reproducible BM25 baseline using the same Vietnamese folding."""
    query = tokens(question)
    words = [re.findall(r"[a-z0-9]+", folded(doc)) for doc in documents]
    average = sum(map(len, words)) / max(1, len(words)) or 1
    counters = [Counter(doc) for doc in words]
    frequency = {term: sum(term in doc for doc in counters) for term in query}
    scores = []
    for terms, counts in zip(words, counters):
        score = 0.
        for term in query:
            f = counts[term]
            inverse = math.log(1 + (len(words) - frequency[term] + .5) / (frequency[term] + .5))
            score += inverse * f * (k1 + 1) / (f + k1 * (1 - b + b * len(terms) / average))
        scores.append(score)
    return scores


def remote_scores(origin, path, payload, expected, *, deadline=None):
    import httpx
    if not origin:
        raise RuntimeError("Inference service is not configured")
    timeout = 8 if deadline is None else min(8, deadline - monotonic())
    if timeout <= 0:
        raise TimeoutError("Retrieval inference budget exhausted")
    with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
        response = client.post(origin.rstrip("/") + path, json=payload)
        response.raise_for_status()
        scores = response.json()["scores"]
    if not isinstance(scores, list) or len(scores) != expected or any(
            not isinstance(v, (float, int)) or not math.isfinite(v) for v in scores):
        raise ValueError("Invalid inference scores")
    return scores


def dense_scores(question, documents, origin, *, deadline=None):
    scores = []
    for offset in range(0, len(documents), DENSE_BATCH_SIZE):
        batch = documents[offset:offset + DENSE_BATCH_SIZE]
        scores.extend(remote_scores(origin, "/similarity", {"query": question, "texts": batch},
                                    len(batch), deadline=deadline))
    return scores
