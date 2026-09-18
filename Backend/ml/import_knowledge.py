import argparse
import json
from datetime import datetime
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", help="Reviewed JSON list; approved=false revokes a source")
    args = p.parse_args()
    from sqlmodel import Session
    from app.core.database import engine
    from app.services.rag_service import upsert_document
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    for row in rows:
        if row.get("approved") and not row.get("reviewer"):
            raise ValueError("Approved documents must name the responsible human reviewer")
        row["effective_at"] = datetime.fromisoformat(row["effective_at"])
        if row["effective_at"].tzinfo is None:
            raise ValueError("effective_at requires timezone")
    with Session(engine) as db:
        for row in rows:
            upsert_document(db, row)
    print(f"Imported {len(rows)} documents; only approved/effective sources are retrievable.")


if __name__ == "__main__":
    main()
