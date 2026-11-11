"""Download versioned public archives for inspection, without approving labels."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile

import httpx


SOURCES = {"shopee": "dduongdev/shopee-vietnamese-product-reviews-sentiment",
           "imdb": "lakshmi25npathi/imdb-dataset-of-50k-movie-reviews"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", choices=SOURCES)
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", type=int, help="Download a fixed publisher version rather than the current version")
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        raise SystemExit("Choose a new output folder; downloaded sources are immutable evidence")
    slug = SOURCES[args.dataset]
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        response = client.get("https://www.kaggle.com/api/v1/datasets/view/" + slug)
        response.raise_for_status()
        metadata = response.json()
        version = args.version if args.version is not None else metadata["currentVersionNumber"]
        if version < 1:
            raise ValueError('Dataset version must be positive')
        response = client.get("https://www.kaggle.com/api/v1/datasets/download/" + slug,
                              params={"datasetVersionNumber": version})
        response.raise_for_status()
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    files = []
    for entry in archive.infolist():
        # Inspect bytes inside the ZIP; never extract untrusted paths.
        if entry.file_size > 150_000_000:
            raise ValueError("Unexpected archive member size")
        raw = archive.read(entry)
        record = dict(name=entry.filename, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if entry.filename.endswith(".jsonl"):
            rows = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines() if line.strip()]
            record.update(rows=len(rows), columns=sorted(rows[0]) if rows else [],
                labels=dict(Counter(str(row.get("label")) for row in rows)),
                duplicate_ids=len(rows)-len({row.get("id") for row in rows}))
        files.append(record)
    out.mkdir(parents=True)
    (out / "source.zip").write_bytes(response.content)
    (out / "publisher-metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = dict(source=f"https://www.kaggle.com/datasets/{slug}", version=version,
        retrieved_at=datetime.now(timezone.utc).isoformat(), declared_license=metadata.get("licenseName"),
        archive_sha256=hashlib.sha256(response.content).hexdigest(), files=files,
        status="raw-source-inspected-not-admitted", human_annotation_quality_verified=False,
        note="Use original records only. Augmented/synthetic variants are not independent datasets. Binary labels do not provide neutral examples.")
    (out / "source-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
