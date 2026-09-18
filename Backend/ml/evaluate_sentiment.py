"""Run final held-out comparison only after fixing the deployment configuration."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
from ml.data import load_splits, fingerprint
from ml.train_sentiment import metrics


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True); p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    from app.services.sentiment_service import load_predictor
    rows = load_splits(args.data)["test"]
    report = {"data_sha256": fingerprint(args.data), "test_count": len(rows), "runs": []}
    for model_path in args.models:
        meta = json.loads(Path(model_path, "metadata.json").read_text(encoding="utf-8"))
        predict, version = load_predictor(meta["backend"], model_path)
        if meta["data_sha256"] != report["data_sha256"]:
            raise ValueError("Training/evaluation data fingerprints differ")
        predictions, latencies, errors = [], [], []
        predict(rows[0]["text"])  # Warm-up excluded from inference latency.
        for row in rows:
            start = time.perf_counter(); scores = predict(row["text"])
            latencies.append((time.perf_counter()-start)*1000)
            prediction = max(scores, key=scores.get); predictions.append(prediction)
            if prediction != row["label"]:
                errors.append({"id": row["id"], "expected": row["label"], "predicted": prediction, "tags": row.get("tags", [])})
        result = metrics([r["label"] for r in rows], predictions)
        result.update(model_version=version, latency_ms_p50=float(np.percentile(latencies, 50)), latency_ms_p95=float(np.percentile(latencies, 95)), errors=errors)
        report["runs"].append(result)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
