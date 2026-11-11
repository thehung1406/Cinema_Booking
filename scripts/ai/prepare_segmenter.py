"""Prepare pinned VnCoreNLP files and optional portable Windows JRE with SHA checks."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

import httpx


def verified_download(client, url, digest):
    response = client.get(url)
    response.raise_for_status()
    if hashlib.sha256(response.content).hexdigest() != digest:
        raise ValueError("Download checksum differs from segmentation lock")
    return response.content


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", default="pipelines/configs/segmentation.lock.json")
    parser.add_argument("--output", default=".local/vncorenlp")
    parser.add_argument("--include-java", action="store_true")
    parser.add_argument("--java-output", default=".local/java")
    args = parser.parse_args()
    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    target = Path(args.output).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        for name, item in lock["files"].items():
            path = (target/name).resolve()
            if not path.is_relative_to(target):
                raise ValueError("Unsafe segmenter path")
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError("Existing segmenter differs; use a new output directory")
                continue
            raw = verified_download(client, item["url"], item["sha256"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        if args.include_java:
            if os.name != "nt":
                raise ValueError("Pinned portable JRE is Windows x64; configure your platform's Java separately")
            package = lock["java"]
            archive = zipfile.ZipFile(io.BytesIO(verified_download(client, package["link"], package["checksum"])))
            destination = Path(args.java_output).resolve()
            for member in archive.infolist():
                path = (destination/member.filename).resolve()
                if not path.is_relative_to(destination):
                    raise ValueError("Unsafe Java archive member")
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                raw = archive.read(member)
                if path.exists() and path.read_bytes() != raw:
                    raise ValueError("Existing Java differs; use a new Java output directory")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
    (target/"download-manifest.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
    print(json.dumps({"segmenter": str(target), "revision": lock["revision"], "java_prepared": args.include_java}))


if __name__ == "__main__":
    main()
