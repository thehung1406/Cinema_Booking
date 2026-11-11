"""Reproducible report tables. Planned settings and completed runs stay separate."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from ml.benchmark import matrix, read_config, summarize


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def export(config_path, runs, output, resolve_configs=False):
    config = read_config(config_path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    planned = []
    for model in config["models"]:
        row = dict(model_id=model["id"], stage="planned-configuration-not-run-evidence", checkpoint=model.get("checkpoint"),
            revision=model.get("revision"), preprocessing=model["preprocessing"],
            declared_license=model.get("declared_license"), architecture=None, encoder_layers=None,
            total_parameters=None, features="TF-IDF char 2–5 grams" if model.get("backend") == "sklearn" else "token IDs + attention mask",
            **{k: None if model.get("backend") == "sklearn" else v for k, v in config["training"].items()})
        row["optimizer"] = "lbfgs; C selected on validation" if model.get("backend") == "sklearn" else "adamw_torch"
        if model.get("backend") == "sklearn":
            row.update(architecture="TF-IDF + multinomial LogisticRegression", parameter_count_basis="depends on fitted vocabulary")
        elif resolve_configs:
            from accelerate import init_empty_weights
            from huggingface_hub import hf_hub_download
            from transformers import AutoConfig, AutoModelForSequenceClassification
            cfg = AutoConfig.from_pretrained(model["checkpoint"], revision=model["revision"], trust_remote_code=False)
            cfg.num_labels = 3
            # Meta tensors count the configured classifier without downloading weights.
            with init_empty_weights():
                instance = AutoModelForSequenceClassification.from_config(cfg, trust_remote_code=False)
            row.update(architecture=type(instance).__name__, encoder_layers=getattr(cfg, "num_hidden_layers", None),
                hidden_size=getattr(cfg, "hidden_size", None), attention_heads=getattr(cfg, "num_attention_heads", None),
                total_parameters=sum(p.numel() for p in instance.parameters()),
                parameter_count_basis="configured 3-class classifier; meta tensors; not loaded/trained weights")
            raw = cfg.to_json_string()
            (output / f"config-{model['id']}.json").write_text(raw, encoding="utf-8")
            row["config_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
            checkpoint_file=Path(hf_hub_download(model["checkpoint"], "config.json", revision=model["revision"]))
            row["checkpoint_config_sha256"] = hashlib.sha256(checkpoint_file.read_bytes()).hexdigest()
            row["config_hash_note"] = "config_sha256 hashes the configured 3-class classifier; checkpoint_config_sha256 hashes publisher bytes"
            (output/f"checkpoint-config-{model['id']}.json").write_bytes(checkpoint_file.read_bytes())
            row["config_source"] = f"https://huggingface.co/{model['checkpoint']}/blob/{model['revision']}/config.json"
            del instance
        planned.append(row)
    actual = []
    for path in sorted(Path(runs).glob("*/*/*/metadata.json")):
        metadata = json.loads(path.read_text(encoding="utf-8"))
        validation = path.with_name("validation.json")
        if not validation.exists():
            continue
        dataset, model, seed = path.parent.parts[-3:]
        result = json.loads(validation.read_text(encoding="utf-8"))
        actual.append(dict(dataset=dataset, model_id=model, seed=int(seed), stage="completed-validation",
            evidence_path=str(path), metadata_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            architecture=metadata.get("architecture"), training=metadata.get("training"),
            metadata_schema=metadata.get("schema_version", 1), macro_f1=result["macro_f1"],
            accuracy=result["per_class"]["accuracy"], per_class=result["per_class"],
            error_count=len(result.get("errors", [])), errors_exported="errors" in result,
            elapsed_seconds=result["elapsed_seconds"], data_sha256=metadata["data_sha256"],
            code_commit=metadata["code_commit"], pipeline_sha256=metadata.get("pipeline_sha256")))
    report = dict(created_at=datetime.now(timezone.utc).isoformat(),
        config_sha256=hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
        planned_models=planned, completed_runs=actual,
        matrix=matrix(config, Path(__file__).resolve().parents[1]),
        validation_summary=summarize(runs, output / "validation-summary.json"),
        final_test_opened=any(Path(runs).glob("*/*/*/test.json")))
    completed = {(row["dataset"], row["model_id"], row["seed"]) for row in actual}
    for row in report["matrix"]:
        row["evidence_state"] = "completed-validation" if (row["dataset"], row["model"], row["seed"]) in completed else row["state"]
    report["completion"] = dict(planned_runs=len(report["matrix"]), completed_validation_runs=len(actual),
        completed_datasets=sorted({row["dataset"] for row in actual}),
        note="Readiness is not completion; blocked/missing runs do not contribute a score.")
    write_json(output / "research-evidence.json", report)
    columns = ["model_id", "stage", "checkpoint", "features", "preprocessing", "architecture", "encoder_layers",
        "total_parameters", "learning_rate", "epochs", "batch_size", "gradient_accumulation_steps", "max_length", "optimizer"]
    with (output / "model-table-planned.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(planned)
    lines = ["# Bảng cấu hình mô hình dự kiến", "", "Các kiến trúc dưới đây lấy từ checkpoint đã pin. Tham số được đếm trên cấu hình classifier 3 lớp, không phải bằng chứng đã train.", "",
        "| Mô hình | Đặc trưng | Kiến trúc | Layer encoder | Tham số | LR | Epoch dự kiến | Batch × tích lũy | Optimizer |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |"]
    def show(value): return "N/A" if value is None else str(value)
    for row in planned:
        lines.append("| " + " | ".join(show(v) for v in [row["model_id"], row["features"], row["architecture"],
            row["encoder_layers"], row["total_parameters"], row["learning_rate"], row["epochs"],
            f"{row['batch_size']} × {row['gradient_accumulation_steps']}" if row["batch_size"] else None, row["optimizer"]]) + " |")
    lines += ["", f"Có {len(actual)} lượt validation hoàn tất trong thư mục đầu vào. Kết quả, cấu hình thực chạy và hash ở research-evidence.json.", ""]
    (output / "MODEL_TABLE.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="pipelines/configs/ai_research.lock.json")
    parser.add_argument("--runs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resolve-configs", action="store_true")
    args = parser.parse_args()
    report = export(args.config, args.runs, args.output, args.resolve_configs)
    print(json.dumps(dict(planned_models=len(report["planned_models"]), completed_runs=len(report["completed_runs"]))))


if __name__ == "__main__":
    main()
