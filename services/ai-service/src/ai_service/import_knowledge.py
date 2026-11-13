"""Owner-side operator import of reviewed knowledge documents."""

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import Session

from .config import Settings
from .documents import lock_document_source, pin_graph_release, replace_document
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
    default_graph_release = settings.graph_release_id if settings.graph_uri else ""
    with Session(create_engine(settings.database_url)) as db:
        for data in prepared:
            doc = lock_document_source(db, data["source_id"])
            if data["approved"]:
                data["provenance"] = pin_graph_release(data["provenance"], default_graph_release)
            replace_document(db, doc, data, default_graph_release)
    print(f"Imported {len(prepared)} knowledge documents into the AI-owned store.")


if __name__ == "__main__":
    main()
