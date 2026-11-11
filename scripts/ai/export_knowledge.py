"""Export actual owner chunks from draft inputs using isolated RAM storage only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import Session, select
from ai_service.models import Base, KnowledgeDocument, KnowledgeChunk
from ai_service.rag import upsert_document
from ai_service.schemas import DocumentWrite


def export(manifest_path, corpus_paths, output):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    registry = {row["source_id"]: row for row in manifest["sources"]}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inventory, chunks = [], []
    try:
        with Session(engine) as db:
            for path in corpus_paths:
                for raw in json.loads(Path(path).read_text(encoding="utf-8")):
                    data = DocumentWrite.model_validate({k: v for k, v in raw.items() if k != "approved"}).model_dump()
                    # Preserve the actual source-file approval status for this export.
                    doc = upsert_document(db, data | {"approved": raw.get("approved", False)})
                    source = registry[doc.source_id]
                    raw_file = Path(source.get("local_file", source.get("input", "")))
                    raw_evidence = {}
                    if raw_file.is_file():
                        raw_digest = hashlib.sha256(raw_file.read_bytes()).hexdigest()
                        if source.get("sha256") and raw_digest != source["sha256"]:
                            raise ValueError("Raw source checksum differs from manifest")
                        raw_evidence = dict(local_file=str(raw_file), bytes=raw_file.stat().st_size, sha256=raw_digest)
                        if source["source_type"] == "pdf":
                            from pypdf import PdfReader
                            raw_evidence["pdf_pages"] = len(PdfReader(raw_file).pages)
                    rows = db.exec(select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id).order_by(KnowledgeChunk.id)).all()
                    inventory.append(dict(source=source, document_id=doc.id, approved=doc.approved,
                        corpus_path=str(path), corpus_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                        blocks=len(data.get("blocks") or []), chunks=len(rows),
                        document_provenance=doc.provenance, raw_file=raw_evidence))
                    for chunk in rows:
                        chunks.append(dict(id=f"doc:{chunk.id}", document_id=doc.id, source_id=doc.source_id,
                            title=doc.title, version=doc.version, approved=doc.approved, source_url=doc.source_url,
                            text=chunk.content, embedding_dimension=len(chunk.embedding),
                            embedding=chunk.embedding,
                            embedding_nonzero_preview=[dict(index=i, value=value) for i,value in enumerate(chunk.embedding) if value][:6],
                            embedding_version=chunk.embedding_version,
                            provenance=doc.provenance | chunk.provenance))
    finally:
        engine.dispose()
    sample = next((row for row in chunks if row["provenance"].get("page_start") == 26), chunks[0])
    report = dict(created_at=datetime.now(timezone.utc).isoformat(), stage="draft-corpus-export-not-live-kb",
        storage="ai_documents + ai_chunks; lexical hash JSON, no persistent dense vector index",
        isolation="SQLite RAM export; live DB and source files unchanged",
        inventory=inventory, document_count=len(inventory), chunk_count=len(chunks), representative_chunk=sample)
    (output / "knowledge-inventory.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output / "kb-chunks.jsonl").open("w", encoding="utf-8") as stream:
        for row in chunks:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output / "kb-page-sample.json").write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Danh mục nguồn Knowledge Base", "", "Bản xuất từ corpus draft bằng code chunking của AI Service; chưa phải KB live được duyệt.", ""]
    for row in inventory:
        source = row["source"]
        lines += [f"## {source['title']}", "", f"- Nguồn: {source['source_url']}",
            f"- Tác giả: {source['author']}", f"- Quyền sử dụng: {source['license']}",
            f"- Phiên bản: {source['version']}; approved={row['approved']}",
            f"- Corpus: {row['corpus_path']}; blocks={row['blocks']}; chunks={row['chunks']}",
            f"- SHA-256 corpus: {row['corpus_sha256']}", ""]
    (output / "KB_SOURCES.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="pipelines/knowledge/sources.json")
    parser.add_argument("--corpus", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = export(args.manifest, args.corpus, args.output)
    print(json.dumps({key: report[key] for key in ["stage", "document_count", "chunk_count"]}))


if __name__ == "__main__":
    main()
