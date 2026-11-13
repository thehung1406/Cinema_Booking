"""Load trusted local models and validate their predictions."""
import json
import math
import os
from functools import lru_cache
from pathlib import Path

from .text import normalize_text

LABELS = ("negative", "neutral", "positive")


class InputTooLong(ValueError):
    pass


@lru_cache(maxsize=2)
def load_predictor(backend, model_path, *, reject_truncation=False):
    path = Path(model_path).resolve()
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    if backend == "sklearn":
        import joblib
        model = joblib.load(path / "model.joblib")  # Only operator-supplied trusted artifacts.
        def predict(text):
            probabilities = model.predict_proba([normalize_text(text)])[0]
            return dict(zip(model.classes_, map(float, probabilities)))
    elif backend == "transformers":
        from transformers import pipeline
        segmenter = None
        preprocessing = metadata.get("text_preprocessing", "vncorenlp" if metadata.get("segmenter_path") else "normalize")
        if preprocessing not in {"normalize", "vncorenlp"}:
            raise ValueError("Unsupported preprocessing")
        if preprocessing == "vncorenlp":
            import py_vncorenlp
            original = Path.cwd()
            try:
                segmenter = py_vncorenlp.VnCoreNLP(save_dir=metadata["segmenter_path"], annotators=["wseg"])
            finally:
                os.chdir(original)
        classifier = pipeline("text-classification", model=str(path), tokenizer=str(path), device=-1)
        max_length = metadata.get("max_length", 256)

        def predict(text):
            prepared = normalize_text(text)
            if segmenter:
                prepared = " ".join(segmenter.word_segment(prepared))
            if reject_truncation:
                tokens = classifier.tokenizer(prepared, truncation=False, verbose=False)["input_ids"]
                if len(tokens) > max_length:
                    raise InputTooLong
            results = classifier(prepared, top_k=None, truncation=not reject_truncation, max_length=max_length)
            return {r["label"]: r["score"] for r in results}
    else:
        raise RuntimeError("Sentiment model is not configured")
    return predict, metadata["model_version"]


def validate_scores(scores):
    if set(scores) != set(LABELS) or any(not math.isfinite(v) or v < 0 or v > 1 for v in scores.values()):
        raise ValueError("Invalid class probabilities")
    if abs(sum(scores.values()) - 1) > 0.01:
        raise ValueError("Probabilities do not sum to one")
