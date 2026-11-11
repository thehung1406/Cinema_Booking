"""Predeclare and run validation-only Bank ablations; never evaluate final test."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(output):
    config = json.loads((ROOT / "pipelines/configs/ai_research.advisor-v3.json").read_text())
    model = next(m for m in config["models"] if m["id"] == "visobert")
    dataset = ROOT / "pipelines/ml/data/reviewed/uts2017-bank"
    base = ROOT / "pipelines/ml/runs/advisor-v3/uts2017-bank/visobert"
    protocol = dict(created_at=datetime.now(timezone.utc).isoformat(), stage="validation-only-ablation",
        rationale="All baseline models had zero neutral F1; validation neutral support is only three.",
        selection="ViSoBERT had highest baseline mean validation Macro F1; this is adaptive development, not an independent benchmark.",
        seeds=config["seeds"], model=model,
        variants={"lower-lr": config["training"] | {"learning_rate": 1e-5, "class_weight": "none"},
                  "sqrt-balanced": config["training"] | {"class_weight": "sqrt-balanced"}},
        baseline={str(s): sha(base / str(s) / "metadata.json") for s in config["seeds"]},
        data_sha256={s: sha(dataset / (s + ".jsonl")) for s in ("train", "validation", "test")},
        code_sha256={p: sha(ROOT / p) for p in ("pipelines/ml/train_sentiment.py", "scripts/ai/run_bank_ablation.py")},
        objective="sqrt(N/n_class), normalized to E_train[w_y]=1; mean(w_y * CE), fitted on train only.",
        primary_metric="validation Macro F1; paired seed differences are descriptive, n=3.",
        secondary_metrics=["neutral precision/recall/F1", "all-class confusion", "actual runtime"],
        final_test="Not evaluated; no final model promotion; final test is not used for ablation selection.",
        limitations=["Adaptive follow-up on the same validation set", "Only one domain", "Three neutral validation records cannot establish generalization"])
    output.mkdir(parents=True, exist_ok=True)
    path = output / "protocol.json"
    if path.exists():
        old = json.loads(path.read_text())
        if {k: v for k, v in old.items() if k != "created_at"} != {k: v for k, v in protocol.items() if k != "created_at"}:
            raise ValueError("Frozen ablation inputs changed; use a new version directory")
        return old
    path.write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    return protocol


def summarize(output, protocol):
    rows, individual = [], {}
    for name in ("baseline", *protocol["variants"]):
        base = ROOT / "pipelines/ml/runs/advisor-v3/uts2017-bank/visobert" if name == "baseline" else output / "runs" / name
        reports = []
        for seed in protocol["seeds"]:
            path = base / str(seed) / "validation.json"
            if path.exists() and (path.parent / "metadata.json").exists():
                report = json.loads(path.read_text())
                metadata = json.loads((path.parent / "metadata.json").read_text())
                reports.append(dict(seed=seed, macro_f1=report["macro_f1"], neutral=report["per_class"]["neutral"],
                    confusion_matrix=report["confusion_matrix"], training=metadata["training"], elapsed_seconds=report["elapsed_seconds"]))
        individual[name] = reports
        scores = [r["macro_f1"] for r in reports]
        paired = [r["macro_f1"] - next(b["macro_f1"] for b in individual["baseline"] if b["seed"] == r["seed"]) for r in reports]
        rows.append(dict(variant=name, completed=len(scores), planned=len(protocol["seeds"]),
            macro_f1_mean=statistics.mean(scores) if scores else None,
            macro_f1_std=statistics.stdev(scores) if len(scores) > 1 else None,
            paired_macro_f1_delta_mean=statistics.mean(paired) if paired else None,
            neutral_f1_mean=statistics.mean(r["neutral"]["f1-score"] for r in reports) if reports else None))
    result = dict(stage="validation-only-adaptive-ablation", protocol_sha256=sha(output / "protocol.json"),
        final_test_evaluated=False, model_promoted=False, summary=rows, runs=individual)
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default=str(ROOT / ".local/evidence/advisor-v4/bank-ablation"))
    p.add_argument("--run", action="store_true")
    args = p.parse_args()
    output = Path(args.output).resolve()
    protocol = prepare(output)
    if args.run:
        from ml.benchmark import training_command
        for name, training in protocol["variants"].items():
            for seed in protocol["seeds"]:
                destination = output / "runs" / name / str(seed)
                if (destination / "metadata.json").exists():
                    continue
                command = training_command({"training": training}, protocol["model"],
                    ROOT / "pipelines/ml/data/reviewed/uts2017-bank", destination, seed)
                print(json.dumps(dict(starting=name, seed=seed, command=command)), flush=True)
                subprocess.run(command, cwd=ROOT / "pipelines", check=True)
                summarize(output, protocol)
    print(json.dumps(summarize(output, protocol)["summary"], indent=2))


if __name__ == "__main__":
    main()
