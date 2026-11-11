"""Plan/run the actual model x dataset x seed matrix, with explicit test access."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys

from ml.dataset_audit import audit


def read_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if len({m["id"] for m in config["models"]}) != len(config["models"]):
        raise ValueError("Duplicate model IDs")
    if len({d["id"] for d in config["datasets"]}) != len(config["datasets"]):
        raise ValueError("Duplicate dataset IDs")
    for row in config["models"] + config["datasets"]:
        if not re.fullmatch(r"[a-z0-9-]+", row["id"]):
            raise ValueError("Unsafe experiment ID")
    return config


def matrix(config, root):
    admitted = {}
    for dataset in config["datasets"]:
        path = root / dataset["path"]
        admitted[dataset["id"]] = audit(path) if path.is_dir() else {"admissible": False, "problems": [dataset["status"]]}
    rows = []
    for dataset in config["datasets"]:
        for model in config["models"]:
            for seed in config["seeds"]:
                issues = admitted[dataset["id"]]["problems"].copy()
                if model.get("backend") != "sklearn" and not re.fullmatch(r"[a-f0-9]{40}", model.get("revision") or ""):
                    issues.append("Model revision must be pinned to an immutable commit SHA")
                rows.append({"dataset": dataset["id"], "model": model["id"], "seed": seed,
                             "state": "blocked" if issues else "ready", "issues": issues})
    return rows


def summarize(root, output):
    """Only completed run files contribute. Missing cells stay missing, not zero."""
    groups = {}
    for path in Path(root).glob("*/*/*/validation.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        dataset, model, seed = path.parent.parts[-3:]
        groups.setdefault((dataset, model), []).append((seed, report["macro_f1"]))
    rows = [{"dataset": dataset, "model": model, "seeds_completed": len(scores),
             "macro_f1_mean": statistics.mean(score for _, score in scores),
             "macro_f1_std": statistics.stdev(score for _, score in scores) if len(scores) > 1 else None}
            for (dataset, model), scores in sorted(groups.items())]
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"stage": "validation", "results": rows}, indent=2), encoding="utf-8")
    with target.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["dataset", "model", "seeds_completed", "macro_f1_mean", "macro_f1_std"])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def training_command(config, model, dataset_path, destination, seed, segmenter_path=None):
    training = config["training"]
    command = [sys.executable, "-m", "ml.train_sentiment", "--data", str(dataset_path),
        "--output", str(destination), "--seed", str(seed), "--backend", model.get("backend", "transformers")]
    if model.get("backend") != "sklearn":
        command += ["--model", model["checkpoint"], "--revision", model["revision"],
            "--preprocessing", model["preprocessing"], "--epochs", str(training["epochs"]),
            "--learning-rate", str(training["learning_rate"]), "--weight-decay", str(training.get("weight_decay", 0.0)),
            "--max-length", str(training["max_length"]), "--batch-size", str(training["batch_size"]),
            "--gradient-accumulation-steps", str(training["gradient_accumulation_steps"])]
        if training.get("class_weight", "none") != "none":
            command += ["--class-weight", training["class_weight"]]
        if model["preprocessing"] == "vncorenlp":
            if not segmenter_path:
                raise ValueError("PhoBERT requires --segmenter-path")
            command += ["--segmenter-path", segmenter_path]
    return command


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "train", "evaluate", "summary"])
    parser.add_argument("--config", default="configs/ai_research.json")
    parser.add_argument("--output", default="ml/runs/matrix")
    parser.add_argument("--dataset")
    parser.add_argument("--model")
    parser.add_argument("--segmenter-path")
    parser.add_argument("--final-test", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config_path = Path(args.config)
    config = read_config(config_path)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.action == "summary":
        print(json.dumps(summarize(output, output / "summary.json"), indent=2))
        return
    rows = matrix(config, root)
    (output / "matrix.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(), "runs": rows}, indent=2), encoding="utf-8")
    if args.action == "plan":
        print(json.dumps({"total": len(rows), "ready": sum(r["state"] == "ready" for r in rows),
                          "blocked": sum(r["state"] == "blocked" for r in rows)}, indent=2))
        return
    if args.action == "evaluate" and not args.final_test:
        raise SystemExit("Final test locked. Freeze validation selection, then pass --final-test.")
    for row in rows:
        if (args.dataset and row["dataset"] != args.dataset) or (args.model and row["model"] != args.model):
            continue
        if row["state"] != "ready":
            print(json.dumps(row, ensure_ascii=False))
            continue
        dataset = next(d for d in config["datasets"] if d["id"] == row["dataset"])
        model = next(m for m in config["models"] if m["id"] == row["model"])
        destination = output / dataset["id"] / model["id"] / str(row["seed"])
        if args.action == "evaluate":
            command = [sys.executable, "-m", "ml.evaluate_sentiment", "--data", str(root / dataset["path"]),
                       "--models", str(destination), "--output", str(destination / "test.json"), "--final-test"]
        else:
            if (destination / "metadata.json").is_file():
                print(f"Already completed: {destination}")
                continue
            try:
                command = training_command(config, model, root / dataset["path"], destination, row["seed"], args.segmenter_path)
            except ValueError as exc:
                print(str(exc))
                continue
        subprocess.run(command, cwd=root, check=True)


if __name__ == "__main__":
    main()
