from datetime import timezone
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from .models import KnowledgeDocument, KnowledgeChunk, KnowledgeRevision, utcnow
from .rag import upsert_document, EMBEDDING_VERSION

def get(db, model, key, *, lock=False):
    stmt = select(model).where(model.id == key)
    if lock:
        stmt = stmt.with_for_update(of=model)
    item = db.exec(stmt).first()
    if item is None or getattr(item, "deleted_at", None):
        raise HTTPException(404, "Không tìm thấy dữ liệu")
    return item


def save(db, item):
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Dữ liệu bị trùng hoặc đang được sử dụng. Vui lòng tải lại.")
    return item


def remove(db, item):
    try:
        db.delete(item)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Dữ liệu đang được sử dụng, không thể xóa")
    return {"message": "Đã xóa thành công"}


def document_detail(db, document_id):
    doc = get(db, KnowledgeDocument, document_id)
    chunks = db.exec(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)
        .order_by(KnowledgeChunk.id)).all()
    return {**doc.model_dump(), "chunks": [dict(id=c.id, content=c.content,
        embedding_version=c.embedding_version, provenance=c.provenance) for c in chunks]}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def lock_document_source(db, source_id):
    # PostgreSQL advisory lock also serializes creation when the source does not exist yet.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:source, 0))"), {"source": source_id})
    return db.exec(select(KnowledgeDocument).where(KnowledgeDocument.source_id == source_id)
                   .with_for_update()).first()


def require_new_version(db, document, version):
    if version == document.version or db.exec(select(KnowledgeRevision.id).where(
        KnowledgeRevision.document_id == document.id, KnowledgeRevision.version == version,
    )).first() is not None:
        raise HTTPException(409, "Mỗi phiên bản cần một mã riêng")


def pin_graph_release(provenance, default_graph_release):
    if default_graph_release and provenance.get("checksum") and "graph_release_id" not in provenance:
        return provenance | {"graph_release_id": default_graph_release, "graph_release_inherited": True}
    return provenance


def archive_current(db, current, default_graph_release):
    archived = db.exec(select(KnowledgeRevision).where(
        KnowledgeRevision.document_id == current.id, KnowledgeRevision.version == current.version)).first()
    if archived:
        provenance = pin_graph_release(
            archived.payload["provenance"], current.provenance.get("graph_release_id", default_graph_release),
        )
        archived.payload = archived.payload | {"provenance": provenance}
        return
    rows = db.exec(select(KnowledgeChunk).where(KnowledgeChunk.document_id == current.id)
                   .order_by(KnowledgeChunk.id)).all()
    blocks = {}
    for chunk in rows:
        locator = chunk.provenance
        key = locator.get("block_index")
        if key is None:
            key = ("legacy", chunk.id)
        block = blocks.setdefault(key, {"text": "", "page_start": locator.get("page_start"),
                                        "page_end": locator.get("page_end"), "section": locator.get("section", "")})
        overlap = max(0, len(block["text"]) - locator.get("character_start", len(block["text"])))
        block["text"] += chunk.content[overlap:]
    payload = jsonable_encoder({field: getattr(current, field) for field in (
        "source_id", "title", "version", "source_url", "effective_at",
    )}) | {"blocks": list(blocks.values()), "content": "",
          "provenance": pin_graph_release(current.provenance, default_graph_release)}
    db.add(KnowledgeRevision(document_id=current.id, version=current.version,
                             payload=payload,
                             base_updated_at=current.updated_at, created_at=current.updated_at,
                             published_at=current.updated_at if current.approved else None))


def replace_document(db, doc, data, default_graph_release=""):
    if doc is not None:
        require_new_version(db, doc, data["version"])
        archive_current(db, doc, default_graph_release)
    return upsert_document(db, data)


def document_write(db, body, default_graph_release=""):
    doc = lock_document_source(db, body.source_id)
    if doc and (body.expected_updated_at is None or utc(doc.updated_at) != utc(body.expected_updated_at)):
        raise HTTPException(409, "Tài liệu đã thay đổi; tải lại trước khi cập nhật")
    data = body.model_dump(exclude={"expected_updated_at"})
    data["approved"] = False
    try:
        doc = replace_document(db, doc, data, default_graph_release)
        db.refresh(doc)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Nguồn tài liệu đã được cập nhật bởi người khác")
    except Exception:
        db.rollback()
        raise
    return doc


def document_approve(db, document_id, body, default_graph_release=""):
    doc = get(db, KnowledgeDocument, document_id, lock=True)
    if doc.version != body.version or utc(doc.updated_at) != utc(body.expected_updated_at):
        raise HTTPException(409, "Phiên bản tài liệu đã thay đổi; cần xem và duyệt lại")
    chunks = db.exec(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)).all()
    if body.approved and (not chunks or any(c.embedding_version != EMBEDDING_VERSION or not c.embedding for c in chunks)):
        raise HTTPException(409, "Tài liệu chưa xử lý xong")
    if body.approved:
        doc.provenance = pin_graph_release(doc.provenance, default_graph_release)
    doc.approved, doc.updated_at = body.approved, utcnow()
    return save(db, doc)


def document_delete(db, document_id):
    doc = get(db, KnowledgeDocument, document_id, lock=True)
    db.exec(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    return remove(db, doc)
