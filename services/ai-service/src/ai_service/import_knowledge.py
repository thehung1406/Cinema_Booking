"""Owner-side replacement for Backend/ml/import_knowledge.py after cutover."""

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlmodel import Session

from .config import Settings
from .rag import upsert_document
from .schemas import DocumentWrite


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Reviewed JSON list; approved entries require a named reviewer")
    args = parser.parse_args()
    settings = Settings()
    if not settings.writes_enabled:
        raise RuntimeError("AI writes are frozen")
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    prepared = []
    for row in rows:
        data = dict(row)
        approved, reviewer = data.pop("approved", False), data.pop("reviewer", "")
        if approved and not str(reviewer).strip():
            raise ValueError("Approved documents require a responsible reviewer")
        validated = DocumentWrite.model_validate(data).model_dump(exclude={"expected_updated_at"})
        prepared.append(validated | {"approved": bool(approved)})
    with Session(create_engine(settings.database_url)) as db:
        for data in prepared:
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:source,0))"), {"source": data["source_id"]})
            upsert_document(db, data)
    print(f"Imported {len(prepared)} knowledge documents into the AI-owned store.")


if __name__ == "__main__":
    main()
