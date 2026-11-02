"""Compare base/adapter on identical frozen retrieved evidence and tool snapshots.

This measures evidence selection, not a substitute for human answer/tool scoring.
"""
import argparse
import json
import time
from pathlib import Path
import numpy as np
from ml.data import load_splits, fingerprint
from ml.serve_chat import load_model, generate


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True); p.add_argument("--model", default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--revision", required=True); p.add_argument("--adapter", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    rows = load_splits(args.data)["test"]
    report = {"data_sha256": fingerprint(args.data), "base_model": args.model, "revision": args.revision, "runs": []}
    metadata = json.loads(Path(args.adapter, "metadata.json").read_text(encoding="utf-8"))
    if metadata["data_sha256"] != report["data_sha256"]:
        raise ValueError("Adapter training/evaluation data fingerprints differ")
    for name, adapter in (("base", None), ("lora", args.adapter)):
        model, tokenizer = load_model(args.model, args.revision, adapter)
        results, latencies = [], []
        for row in rows:
            start = time.perf_counter()
            try:
                result = generate(model, tokenizer, row["question"], row["evidence"])
                correct = set(result["evidence_ids"]) == set(row["evidence_ids"])
                valid = True
            except Exception:
                result, correct, valid = {"evidence_ids": []}, False, False
            latency = (time.perf_counter()-start)*1000; latencies.append(latency)
            # Store sample IDs and selected evidence only; no prompts, credentials or payment details.
            results.append(dict(id=row["id"], selected=result["evidence_ids"], correct=correct, valid=valid, latency_ms=latency))
        report["runs"].append(dict(name=name, exact_evidence_accuracy=sum(r["correct"] for r in results)/len(results),
            valid_output_rate=sum(r["valid"] for r in results)/len(results),
            latency_ms_p50=float(np.percentile(latencies, 50)), latency_ms_p95=float(np.percentile(latencies, 95)), cases=results))
        del model, tokenizer
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
