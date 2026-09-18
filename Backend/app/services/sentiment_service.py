"""Lazy-loaded, trusted local models; the application never invents a prediction."""
import json
import math
from functools import lru_cache
from pathlib import Path

from sqlmodel import select

from app.core.config import settings
from app.models import Review, ReviewSentiment
from app.models.ai import utcnow
from app.ai_text import normalize_text

LABELS = ("negative", "neutral", "positive")


@lru_cache(maxsize=2)
def load_predictor(backend, model_path):
    path = Path(model_path)
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    if backend == "sklearn":
        import joblib
        model = joblib.load(path / "model.joblib")  # Only operator-supplied trusted artifacts.
        def predict(text):
            probabilities = model.predict_proba([normalize_text(text)])[0]
            return dict(zip(model.classes_, map(float, probabilities)))
    elif backend == "transformers":
        from transformers import pipeline
        import py_vncorenlp
        segmenter = py_vncorenlp.VnCoreNLP(save_dir=metadata["segmenter_path"], annotators=["wseg"])
        classifier = pipeline("text-classification", model=str(path), tokenizer=str(path), device=-1)
        def predict(text):
            segmented = " ".join(segmenter.word_segment(normalize_text(text)))
            return {r["label"]: r["score"] for r in classifier(segmented, top_k=None, truncation=True, max_length=256)}
    else:
        raise RuntimeError("Sentiment model is not configured")
    return predict, metadata["model_version"]


def validate_scores(scores):
    if set(scores) != set(LABELS) or any(not math.isfinite(v) or v < 0 or v > 1 for v in scores.values()):
        raise ValueError("Invalid class probabilities")
    if abs(sum(scores.values()) - 1) > 0.01:
        raise ValueError("Probabilities do not sum to one")


def process_review(db, review_id, version, predictor=None):
    review = db.get(Review, review_id)
    result = db.get(ReviewSentiment, review_id)
    if not review or review.is_deleted or review.moderation_status != "approved" or review.content_version != version:
        return "stale"
    if result and result.content_version == version and result.status in ("succeeded", "needs_review"):
        return result.status
    content = review.content
    db.rollback()  # Release read transaction during expensive inference.
    try:
        predict, model_version = predictor or load_predictor(settings.SENTIMENT_BACKEND, settings.SENTIMENT_MODEL_PATH)
        scores = predict(content)
        validate_scores(scores)
        label = max(scores, key=scores.get)
        status = "succeeded" if scores[label] >= settings.SENTIMENT_REVIEW_THRESHOLD else "needs_review"
    except Exception:
        scores, label, model_version, status = {}, None, None, "failed"
    review = db.exec(select(Review).where(Review.id == review_id).with_for_update().execution_options(populate_existing=True)).first()
    if not review or review.is_deleted or review.content_version != version or review.moderation_status != "approved":
        db.rollback()
        return "stale"
    result = db.get(ReviewSentiment, review_id, populate_existing=True)
    if result and result.status in ("succeeded", "needs_review") and result.content_version == version:
        db.rollback()
        return result.status
    result = result or ReviewSentiment(review_id=review_id, content_version=version)
    result.status, result.label, result.scores, result.model_version = status, label, scores, model_version
    result.attempts += 1
    result.updated_at = utcnow()
    db.add(result)
    db.commit()
    return status
