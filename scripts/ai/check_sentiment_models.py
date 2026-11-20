"""Verify the shared sentiment artifacts; optionally run offline CPU inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MODEL_ROOT = ROOT / "pipelines/models/sentiment-demo"
REQUIRED = {
    "lr": ("sklearn", {"metadata.json", "model.joblib"}),
    "visobert": ("transformers", {"metadata.json", "config.json", "model.safetensors",
        "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer_config.json", "tokenizer.json"}),
}


def verify(model_root):
    manifest = json.loads((model_root / "manifest.json").read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported model manifest")
    expected = {f"{model}/{name}" for model, (_, names) in REQUIRED.items() for name in names}
    entries = manifest["files"]
    if len(entries) != len(expected) or {entry["path"] for entry in entries} != expected:
        raise ValueError("Manifest must contain exactly the required inference files")
    for entry in entries:
        path = model_root / entry["path"]
        if not path.resolve().is_relative_to(model_root.resolve()):
            raise ValueError("Model file must remain inside the shared model directory")
        with path.open("rb") as stream:
            if stream.read(64).startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise ValueError(f"{entry['path']} is only a Git LFS pointer; run git lfs install and git lfs pull")
            stream.seek(0)
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if path.stat().st_size != entry["bytes"] or digest != entry["sha256"]:
            raise ValueError(f"Checksum mismatch: {entry['path']}")
    versions = {}
    for name, (backend, _) in REQUIRED.items():
        metadata = json.loads((model_root / name / "metadata.json").read_text(encoding="utf-8"))
        if (metadata["backend"] != backend or metadata["labels"] != ["negative", "neutral", "positive"]
                or metadata.get("production_promoted") is not False):
            raise ValueError(f"Unexpected metadata for {name}")
        versions[name] = metadata["model_version"]
    return {"verified_files": len(entries), "bytes": sum(entry["bytes"] for entry in entries), "models": versions}


def smoke(model_root):
    # Keep all model/tokenizer reads offline. The runtime loader reads local paths.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    sys.path.insert(0, str(ROOT / "services/review-service/src"))
    from review_service.predictor import load_predictor, validate_scores
    samples = ("Phim hay, diễn viên diễn xuất tốt.", "Phim dở, nội dung nhàm chán.", "Phim dài hai tiếng.")
    output = {}
    for name, (backend, _) in REQUIRED.items():
        predict, version = load_predictor(backend, str(model_root / name), reject_truncation=True)
        predictions = []
        for sample in samples:
            scores = predict(sample)
            validate_scores(scores)
            predictions.append(max(scores, key=scores.get))
        output[name] = {"version": version, "sample_predictions": predictions}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, default=MODEL_ROOT)
    parser.add_argument("--smoke", action="store_true", help="Also load both trusted models and infer on CPU")
    args = parser.parse_args()
    try:
        result = verify(args.models)
        if args.smoke:
            result["offline_cpu_smoke"] = smoke(args.models)
        print(json.dumps(result))
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        parser.exit(1, f"Model check failed: {error}\n")


if __name__ == "__main__":
    main()
