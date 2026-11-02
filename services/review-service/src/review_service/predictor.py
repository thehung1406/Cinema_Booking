"""Lazy-loaded, trusted local models; the application never invents a prediction."""
import json
import math
from functools import lru_cache
from pathlib import Path

from sqlmodel import select




from .text import normalize_text

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
