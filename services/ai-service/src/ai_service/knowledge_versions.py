"""Review an immutable draft, then switch the served source and graph revision together."""
from datetime import datetime

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from neo4j.exceptions import DriverError, Neo4jError
from sqlmodel import select

from .documents import get, utc
from .graph import normalize_excerpt
from .models import KnowledgeChunk, KnowledgeDocument, KnowledgeRevision, utcnow
from .rag import chunk_segments, upsert_document


def revision_list(db, document_id):
    get(db, KnowledgeDocument, document_id)
    revisions = db.exec(select(KnowledgeRevision).where(KnowledgeRevision.document_id == document_id)
                        .order_by(KnowledgeRevision.created_at.desc())).all()
    return [describe(revision) for revision in revisions]


def describe(revision):
    return {field: getattr(revision, field) for field in (
        "id", "document_id", "version", "created_at", "created_by", "published_at", "published_by",
    )} | {"title": revision.payload["title"], "graph_release_id": revision.payload["provenance"].get("graph_release_id", "")}


def revision_detail(db, document_id, revision_id):
    revision = get(db, KnowledgeRevision, revision_id)
    if revision.document_id != document_id:
        raise HTTPException(404, "Không tìm thấy phiên bản tài liệu")
    return describe(revision) | {"document": revision.payload}


def stage(db, document_id, body, user_id):
    draft = body.document
    current = get(db, KnowledgeDocument, document_id, lock=True)
    if draft.source_id != current.source_id:
        raise HTTPException(422, "Mã nguồn tài liệu phải giữ nguyên")
    check_timestamp(current, draft.expected_updated_at)
    exists = db.exec(select(KnowledgeRevision.id).where(
        KnowledgeRevision.document_id == document_id, KnowledgeRevision.version == draft.version)).first()
    if draft.version == current.version or exists:
        raise HTTPException(409, "Mỗi phiên bản cần một mã riêng")
    payload = draft.model_dump(mode="json", exclude={"expected_updated_at"})
    if body.graph_release_id:
        if not draft.provenance.checksum:
            raise HTTPException(422, "Bản đồ thị yêu cầu checksum của nguồn")
        payload["provenance"]["graph_release_id"] = body.graph_release_id
    revision = KnowledgeRevision(document_id=document_id, version=draft.version, payload=payload,
                                 base_updated_at=current.updated_at, created_by=user_id)
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return describe(revision)


def check_timestamp(document, expected):
    if expected is None or utc(document.updated_at) != utc(expected):
        raise HTTPException(409, "Tài liệu đã thay đổi; hãy tải lại trước khi tiếp tục")


def archive_current(db, current):
    archived = db.exec(select(KnowledgeRevision).where(
        KnowledgeRevision.document_id == current.id, KnowledgeRevision.version == current.version)).first()
    if archived:
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
        "source_id", "title", "version", "source_url", "effective_at", "provenance",
    )}) | {"blocks": list(blocks.values()), "content": ""}
    db.add(KnowledgeRevision(document_id=current.id, version=current.version, payload=payload,
                             base_updated_at=current.updated_at, created_at=current.updated_at,
                             published_at=current.updated_at if current.approved else None))


def validate_graph_revision(graph, payload):
    release_id = payload["provenance"].get("graph_release_id")
    if not release_id:
        return
    if graph is None:
        raise HTTPException(409, "Chưa cấu hình đồ thị để kiểm tra bản phát hành")
    try:
        spans = graph.revision_spans(release_id, payload)
    except (DriverError, Neo4jError, ValueError) as exc:
        raise HTTPException(503, "Chưa kiểm tra được bản phát hành đồ thị") from exc
    blocks = payload.get("blocks") or [{"text": paragraph} for paragraph in payload["content"].split("\n\n") if paragraph.strip()]
    if not spans or len(spans) > 500 or any(
        not 0 <= span["block_index"] < len(blocks)
        or blocks[span["block_index"]].get("page_start") != span["page"]
        or not any(span["excerpt"] in normalize_excerpt(text)
                   for _, text in chunk_segments(blocks[span["block_index"]]["text"].strip()))
        for span in spans
    ):
        raise HTTPException(409, "Bản phát hành đồ thị chưa có bằng chứng khớp phiên bản tài liệu")


def publish(db, document_id, revision_id, body, user_id, graph):
    current = get(db, KnowledgeDocument, document_id)
    revision = get(db, KnowledgeRevision, revision_id)
    if revision.document_id != document_id:
        raise HTTPException(404, "Không tìm thấy phiên bản tài liệu")
    check_timestamp(current, body.expected_updated_at)
    payload = revision.payload
    effective_at = datetime.fromisoformat(payload["effective_at"])
    if utc(effective_at) > utcnow():
        raise HTTPException(409, "Chỉ có thể công bố sau thời điểm hiệu lực")
    db.rollback()
    validate_graph_revision(graph, payload)

    current = get(db, KnowledgeDocument, document_id, lock=True)
    revision = get(db, KnowledgeRevision, revision_id, lock=True)
    check_timestamp(current, body.expected_updated_at)
    if current.version == revision.version and current.approved:
        return current.model_dump()
    if revision.published_at is None and utc(revision.base_updated_at) != utc(current.updated_at):
        raise HTTPException(409, "Bản nháp dựa trên phiên bản cũ; hãy soạn lại từ bản đang phục vụ")
    archive_current(db, current)
    document = upsert_document(db, payload | {"effective_at": effective_at, "approved": True}, commit=False)
    revision.published_at, revision.published_by = document.updated_at, user_id
    db.commit()
    db.refresh(document)
    return document.model_dump()
