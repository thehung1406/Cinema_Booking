"""Versioned lexical vector baseline. Do not ingest prices, seats or user reviews."""
import hashlib
import math
import re
import unicodedata
from sqlalchemy import delete
from sqlmodel import select
from app.models import KnowledgeDocument, KnowledgeChunk
from app.models.ai import utcnow

EMBEDDING_VERSION = "lexical-hash-256-v2"
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


def upsert_document(db, data):
    """Replace chunks atomically when a document is updated or revoked."""
    source_url = safe_source_url(data["source_url"])
    doc = db.exec(select(KnowledgeDocument).where(KnowledgeDocument.source_id == data["source_id"]).with_for_update()).first()
    if doc is None:
        doc = KnowledgeDocument(source_id=data["source_id"], title=data["title"], version=data["version"], source_url=source_url, effective_at=data["effective_at"])
    doc.title, doc.version, doc.source_url = data["title"], data["version"], source_url
    doc.approved, doc.effective_at, doc.updated_at = data.get("approved", False), data["effective_at"], utcnow()
    db.add(doc)
    db.flush()
    db.exec(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    for paragraph in data["content"].split("\n\n"):
        paragraph = paragraph.strip()
        for offset in range(0, len(paragraph), 1200):
            chunk = paragraph[offset:offset+1200]
            if chunk:
                db.add(KnowledgeChunk(document_id=doc.id, content=chunk, embedding=embed(doc.title + " " + chunk), embedding_version=EMBEDDING_VERSION))
    db.commit()
    return doc


def retrieve(db, question, limit=3):
    query_tokens, query_vector = tokens(question), embed(question)
    rows = db.exec(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
        KnowledgeDocument.approved == True, KnowledgeDocument.effective_at <= utcnow(),
        KnowledgeChunk.embedding_version == EMBEDDING_VERSION)).all()
    ranked = []
    for chunk, doc in rows:
        if len(query_tokens & tokens(doc.title + " " + chunk.content)) < 2:
            continue
        score = sum(a*b for a, b in zip(query_vector, chunk.embedding))
        if score >= 0.15:
            ranked.append((score, chunk, doc))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    return [dict(id=f"doc:{chunk.id}", title=doc.title, text=chunk.content,
                 url=safe_source_url(doc.source_url), version=doc.version, kind="document")
            for _, chunk, doc in ranked[:limit]]
