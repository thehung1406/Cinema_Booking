"""Run only in the isolated Review worker image/test DB, never install this model live."""
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

from cinema_platform.events import MessagingBase, OutboxRecord
from review_service.config import Settings
from review_service.models import Base, ReviewSentiment
from review_service.service import create_review
from review_service.worker import process_one


def main():
    url = make_url(os.environ["REVIEW_DATABASE_URL"])
    if url.host != "review-db-test" or url.database != "cinema_review_test":
        raise RuntimeError("Dedicated Review test database required")
    schema = "review_inference_test_" + uuid4().hex
    root = create_engine(url)
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        MessagingBase.metadata.create_all(engine)
        with tempfile.TemporaryDirectory() as directory:
            model = make_pipeline(TfidfVectorizer(), LogisticRegression())
            model.fit(["phim hay tuyet voi", "dien xuat tuyet voi", "phim binh thuong",
                "noi dung binh thuong", "phim do te", "dien xuat te"],
                ["positive", "positive", "neutral", "neutral", "negative", "negative"])
            joblib.dump(model, Path(directory) / "model.joblib")
            (Path(directory) / "metadata.json").write_text(json.dumps({"model_version": "isolated-smoke-model"}))
            settings = Settings(database_url=url.render_as_string(hide_password=False), writes_enabled=True,
                auto_approve=True, sentiment_backend="sklearn", sentiment_model_path=directory)
            with Session(engine) as db:
                rid = create_review(db, 1, 777, "phim hay tuyet voi", settings).id
            assert process_one(engine, settings) in {"succeeded", "needs_review"}
            assert process_one(engine, settings) is False
            with Session(engine) as db:
                assert db.get(ReviewSentiment, rid).model_version == "isolated-smoke-model"
                assert db.scalar(select(func.count()).select_from(OutboxRecord)) == 2
        print("Worker image: isolated sklearn load/inference and two transactional events verified; no production artifact installed.")
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


if __name__ == "__main__":
    main()
