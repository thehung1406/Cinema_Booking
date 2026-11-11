"""Extract a licensed source into reviewable, page-addressable owner input.

This CLI never approves a document. The responsible person uses the existing
knowledge.manage review screen after inspecting extracted text and source pages.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata


def clean_text(text):
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()).strip()


def prepare(source, path):
    from ai_service.schemas import DocumentWrite
    path = Path(path)
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Source exceeds 100 MiB extraction limit")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    provenance = {key: source[key] for key in ("source_type", "scope", "author", "license", "language")}
    provenance["checksum"] = digest
    blocks, warnings = [], []
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        import pypdf
        provenance["extraction"] = f"pypdf-{pypdf.__version__}-page-text-v1"
        reader = PdfReader(path)
        if len(reader.pages) > 1000:
            raise ValueError("PDF exceeds 1000-page extraction limit")
        for index, page in enumerate(reader.pages, 1):
            contents = page.get_contents()
            if contents and len(contents.get_data()) > 8 * 1024 * 1024:
                raise ValueError(f"Page {index}: content stream too large")
            text = clean_text(page.extract_text() or "")
            if len(text) < 20:
                warnings.append({"page": index, "issue": "Sparse text; inspect blank page/image or supply reviewed OCR"})
            if text:
                blocks.append(dict(text=text, page_start=index, page_end=index, section=""))
    else:
        provenance["extraction"] = "utf8-text-v1"
        text = clean_text(path.read_text(encoding="utf-8"))
        blocks = [dict(text=paragraph) for paragraph in text.split("\n\n") if paragraph.strip()]
    if not blocks:
        raise ValueError("No text extracted; OCR is required before importing this source")
    payload = dict(source_id=source["source_id"], title=source["title"], version=source["version"],
        source_url=source["source_url"], effective_at=source.get("effective_at", datetime.now(timezone.utc).isoformat()),
        provenance=provenance, blocks=blocks)
    validated = DocumentWrite.model_validate(payload).model_dump(mode="json")
    return validated | {"approved": False}, {"source_id": source["source_id"], "sha256": digest,
        "pages_or_blocks": len(blocks), "characters": sum(len(b["text"]) for b in blocks), "warnings": warnings,
        "review_required": True, "ocr_performed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("source_id")
    parser.add_argument("input")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sources = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["sources"]
    source = next(item for item in sources if item["source_id"] == args.source_id)
    payload, report = prepare(source, args.input)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps([payload], ensure_ascii=False, indent=2), encoding="utf-8")
    target.with_suffix(".extraction.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
