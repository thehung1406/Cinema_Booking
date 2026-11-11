"""Resolve public model metadata to immutable revisions without downloading weights."""
import argparse
import json
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="pipelines/configs/ai_research.json")
    parser.add_argument("--output", default="pipelines/configs/ai_research.lock.json")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for model in config["models"]:
            if model.get("backend") == "sklearn":
                continue
            response = client.get("https://huggingface.co/api/models/"+model["checkpoint"])
            response.raise_for_status()
            metadata = response.json()
            model["revision"] = metadata["sha"]
            model["declared_task"] = metadata.get("pipeline_tag")
            model["declared_license"] = metadata.get("cardData", {}).get("license", "not-declared")
    target = Path(args.output)
    if target.exists():
        raise SystemExit("Lock exists; choose a new version instead of silently changing revisions")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({model["id"]: model.get("revision") for model in config["models"]}))


if __name__ == "__main__":
    main()
