from datetime import timezone
from fastapi import HTTPException
from sqlalchemy import delete, func, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from .models import KnowledgeDocument, KnowledgeChunk, utcnow
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
        embedding_version=c.embedding_version) for c in chunks]}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def document_write(db, body):
    # PostgreSQL advisory lock also serializes creation when the source does not exist yet.
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:source, 0))"), {"source": body.source_id})
    doc = db.exec(select(KnowledgeDocument).where(KnowledgeDocument.source_id == body.source_id)
        .with_for_update()).first()
    if doc and (body.expected_updated_at is None or utc(doc.updated_at) != utc(body.expected_updated_at)):
        raise HTTPException(409, "Tài liệu đã thay đổi; tải lại trước khi cập nhật")
    data = body.model_dump(exclude={"expected_updated_at"})
    data["approved"] = False
    try:
        doc = upsert_document(db, data)
        db.refresh(doc)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Nguồn tài liệu đã được cập nhật bởi người khác")
    except Exception:
        db.rollback()
        raise
    return doc


def document_approve(db, document_id, body):
    doc = get(db, KnowledgeDocument, document_id, lock=True)
    if doc.version != body.version or utc(doc.updated_at) != utc(body.expected_updated_at):
        raise HTTPException(409, "Phiên bản tài liệu đã thay đổi; cần xem và duyệt lại")
    chunks = db.exec(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)).all()
    if body.approved and (not chunks or any(c.embedding_version != EMBEDDING_VERSION or not c.embedding for c in chunks)):
        raise HTTPException(409, "Tài liệu chưa xử lý xong")
    doc.approved, doc.updated_at = body.approved, utcnow()
    return save(db, doc)


def document_delete(db, document_id):
    doc = get(db, KnowledgeDocument, document_id, lock=True)
    db.exec(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    return remove(db, doc)
