"""Plots from completed run outputs only. Never substitute zero for missing runs."""
import argparse
import json
from pathlib import Path


def figures(root, output, config=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for path in root.glob("*/*/*/validation.json"):
        dataset, model, seed = path.parent.parts[-3:]
        reports.append((dataset, model, seed, json.loads(path.read_text(encoding="utf-8"))))
    if not reports:
        raise ValueError("No completed validation runs; no result figures generated")
    datasets = [row["id"] for row in config["datasets"]] if config else sorted({row[0] for row in reports})
    models = [row["id"] for row in config["models"]] if config else sorted({row[1] for row in reports})
    scores = np.full((len(models), len(datasets)), np.nan)
    for i, model in enumerate(models):
        for j, dataset in enumerate(datasets):
            values = [row[3]["macro_f1"] for row in reports if row[:2] == (dataset, model)]
            if values:
                scores[i, j] = np.mean(values)
    fig, axis = plt.subplots(figsize=(max(5, len(datasets)*2), max(3, len(models)*.7)))
    chart = axis.imshow(np.ma.masked_invalid(scores), vmin=0, vmax=1, cmap="YlGnBu", aspect="auto")
    axis.set_xticks(range(len(datasets)), datasets)
    axis.set_yticks(range(len(models)), models)
    for i in range(len(models)):
        for j in range(len(datasets)):
            axis.text(j, i, "not run" if np.isnan(scores[i,j]) else f"{scores[i,j]:.3f}", ha="center", va="center")
    axis.set_title("Validation Macro-F1 — completed runs only")
    fig.colorbar(chart, ax=axis)
    fig.tight_layout()
    fig.savefig(output/"validation-matrix.png", dpi=160)
    plt.close(fig)
    # Show per-class quality: accuracy can hide the minority neutral class.
    for dataset in sorted({row[0] for row in reports}):
        observed = [m for m in models if any(r[0] == dataset and r[1] == m for r in reports)]
        fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.4))
        for index, label in enumerate(("negative", "neutral", "positive")):
            values = [np.mean([r[3]["per_class"][label]["f1-score"] for r in reports if r[:2] == (dataset, m)]) for m in observed]
            axes[0].bar(np.arange(len(observed)) + (index-1)*.24, values, .24, label=label)
        axes[0].set_xticks(range(len(observed)), observed, rotation=35)
        axes[0].set_ylim(0, 1); axes[0].set_ylabel("Validation F1"); axes[0].legend(fontsize=9)
        for model in observed:
            epochs = {}
            seeds = 0
            for history in root.glob(f"{dataset}/{model}/*/training_history.json"):
                rows = json.loads(history.read_text(encoding="utf-8"))
                values = [r for r in rows if "eval_macro_f1" in r]
                if values:
                    seeds += 1
                    for row in values:
                        epochs.setdefault(row["epoch"], []).append(row["eval_macro_f1"])
            if epochs:
                xs = sorted(epochs)
                means = np.array([np.mean(epochs[x]) for x in xs])
                stds = np.array([np.std(epochs[x], ddof=1) if len(epochs[x]) > 1 else 0 for x in xs])
                line, = axes[1].plot(xs, means, marker="o", label=f"{model} n={seeds}")
                if seeds > 1:
                    axes[1].fill_between(xs, np.maximum(0, means-stds), np.minimum(1, means+stds), color=line.get_color(), alpha=.12)
        axes[1].set_xlabel("Epoch"); axes[1].set_ylabel("Validation Macro-F1"); axes[1].set_ylim(0, 1)
        if axes[1].lines:
            axes[1].legend(fontsize=8, ncol=2)
            axes[1].set_xticks(sorted({row["epoch"] for model in observed for h in root.glob(f"{dataset}/{model}/*/training_history.json")
                for row in json.loads(h.read_text(encoding="utf-8")) if "eval_macro_f1" in row}))
        else:
            axes[1].text(.5, .5, "No completed transformer histories", ha="center", transform=axes[1].transAxes)
        fig.suptitle(f"{dataset} — observed class quality and learning curves")
        fig.tight_layout(); fig.savefig(output/f"class-and-learning-{dataset}.png", dpi=160); plt.close(fig)
    for dataset, model, seed, report in reports:
        fig, axis = plt.subplots(figsize=(5, 4))
        counts = np.array(report["confusion_matrix"])
        axis.imshow(counts, cmap="Blues")
        labels = report["label_order"]
        axis.set_xticks(range(len(labels)), labels, rotation=20)
        axis.set_yticks(range(len(labels)), labels)
        axis.set_xlabel("Predicted")
        axis.set_ylabel("Human/publisher label")
        for i in range(len(labels)):
            for j in range(len(labels)):
                axis.text(j, i, str(counts[i,j]), ha="center", va="center")
        axis.set_title(f"{dataset}/{model}/seed-{seed} — validation")
        fig.tight_layout()
        fig.savefig(output/f"confusion-{dataset}-{model}-{seed}.png", dpi=160)
        plt.close(fig)
    return {"stage": "validation", "runs": len(reports),
        "datasets_observed": sorted({r[0] for r in reports}), "models_observed": sorted({r[1] for r in reports}),
        "matrix_datasets": datasets, "matrix_models": models}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", help="Display all planned matrix cells, keeping missing runs as not run")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else None
    print(json.dumps(figures(args.root, args.output, config)))


if __name__ == "__main__":
    main()
