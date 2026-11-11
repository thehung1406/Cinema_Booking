"""Prepare public movie text for real human review, never promote mixed LLM labels."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

import httpx

REPOSITORY = "AlyThien/ViMovieABSA-A-Vietnamese-Aspect-Based-Sentiment-Dataset-for-Movie-Reviews-with-Reliability-Decompos"
REVISION = "2ceae3b15ece8f9a6c24f7b73465d940b0f8ce18"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        raise SystemExit("Use a new directory; do not overwrite human annotations")
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/final_dataset.csv"
    response = httpx.get(url, timeout=90)
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    prepared = []
    for index, row in enumerate(rows):
        # Keep only explicitly expressed overall categories. Preserve a typo as an exclusion.
        if row["overall"] not in {"negative", "neutral", "positive"} or not row["text"].strip():
            continue
        normalized = " ".join(row["text"].lower().split())
        digest = hashlib.sha256(normalized.encode()).hexdigest()
        prepared.append(dict(id=f"vimovie:{REVISION[:12]}:row:{index}", text=row["text"],
            group_id=f"vimovie:text:{digest}", original_comment_id=row["comment_id"], original_row=index,
            platform=row["source"], source=f"https://github.com/{REPOSITORY}/blob/{REVISION}/final_dataset.csv",
            license="CC BY 4.0 (publisher README)", synthetic=False,
            text_origin="publisher reports collected social-media movie comments",
            annotation_origin="pending-independent-human-review; publisher labels are mixed LLM/human",
            label=None, reviewer=None, second_label=None, second_reviewer=None, review_status="pending",
            suggested_label=row["overall"], suggestion_source="publisher mixed LLM/human annotations; not gold",
            annotation_note="", tags=[]))
    out.mkdir(parents=True)
    (out / "source.csv").write_bytes(response.content)
    (out / "cinema-pending.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in prepared), encoding="utf-8")
    manifest = dict(repository=REPOSITORY, revision=REVISION, source_url=url,
        source_sha256=hashlib.sha256(response.content).hexdigest(), original_count=len(rows),
        publisher_overall_counts=dict(Counter(r["overall"] for r in rows)), prepared_pending_count=len(prepared),
        publisher_duplicate_comment_ids=len(rows)-len({r["comment_id"] for r in rows}),
        excluded_labels=dict(Counter(r["overall"] for r in rows if r["overall"] not in {"negative", "neutral", "positive"})),
        human_approved_count=0, note="Real text according to publisher; labels require independent human review. IDs use source row because publisher comment_id is not unique.")
    (out / "source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
