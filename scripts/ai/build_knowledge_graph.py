"""Compile explicitly curated source spans to Cypher and optionally load an isolated release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from ai_service.graph import cypher, normalize_alias, normalize_excerpt
from ai_service.rag import chunk_segments
from ai_service.schemas import DocumentWrite


def stable_id(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def compile_release(curation, documents):
    inputs = {}
    for document in documents:
        key = (document.source_id, document.version)
        if key in inputs:
            raise ValueError(f"Duplicate source/version input: {key}")
        inputs[key] = document
    rows = []
    for claim in curation["claims"]:
        key = claim["source_id"], claim["version"]
        if key not in inputs:
            continue  # Enables reproducible runs with a subset of sources.
        document = inputs[key]
        if not document.provenance.checksum:
            raise ValueError(f"Missing source checksum: {key}")
        index = claim["block_index"]
        if not isinstance(index, int) or not 0 <= index < len(document.blocks):
            raise ValueError(f"Invalid block index: {key} {index}")
        block = document.blocks[index]
        excerpt = normalize_excerpt(claim["excerpt"])
        if (not excerpt or claim.get("page") != block.page_start or
                not any(excerpt in normalize_excerpt(text) for _, text in chunk_segments(block.text))):
            raise ValueError(f"Evidence does not match source block and page: {key} {index}")
        concept = claim["concept_id"]
        aliases = []
        for language, labels in curation["concepts"][concept].items():
            for label in labels:
                normalized = normalize_alias(label)
                if not normalized:
                    raise ValueError(f"Empty alias for {concept}")
                aliases.append(dict(id=stable_id(concept, language, label), label=label,
                                    language=language, normalized=normalized))
        version_id = stable_id(*key, document.provenance.checksum)
        chunk_id = stable_id(version_id, index, excerpt)
        qualifier = claim.get("qualifier", "")
        status = claim.get("status", "verified")
        if status not in {"verified", "needs_review"}:
            raise ValueError(f"Unknown claim status: {status}")
        claim_id = stable_id(chunk_id, concept, claim["predicate"], qualifier, claim["value"], status)
        rows.append(dict(
            source_id=document.source_id, version=document.version, version_id=version_id,
            title=document.title, url=document.source_url, checksum=document.provenance.checksum,
            language=document.provenance.language, scope=document.provenance.scope,
            chunk_id=chunk_id, page=block.page_start, block_index=index, excerpt=excerpt, concept_id=concept,
            claim_id=claim_id, predicate=claim["predicate"], qualifier=qualifier, value=claim["value"],
            status=status, aliases=sorted(aliases, key=lambda alias: alias["id"]),
        ))
    if not rows:
        raise ValueError("No curated evidence matches the supplied documents")
    rows.sort(key=lambda row: row["claim_id"])
    if len({row["claim_id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate curated claim")
    return stable_id(rows), rows


def cypher_literal(value):
    if isinstance(value, dict):
        if any(not re.fullmatch(r"[a-z_]+", key) for key in value):
            raise ValueError("Invalid Cypher map key")
        return "{" + ", ".join(f"{key}: {cypher_literal(item)}" for key, item in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",\n".join(map(cypher_literal, value)) + "]"
    return json.dumps(value, ensure_ascii=False)


def export_cypher(release, rows):
    return (cypher("schema.cypher") + "\n" +
            cypher("import.cypher").replace("$release_id", cypher_literal(release), 1)
            .replace("$rows", cypher_literal(rows), 1).rstrip() + ";\n")


def load_release(uri, username, password, database, release, rows):
    from neo4j import GraphDatabase
    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        for statement in cypher("schema.cypher").split(";"):
            if statement.strip():
                driver.execute_query(statement, database_=database)
        driver.execute_query(cypher("import.cypher"), release_id=release, rows=rows, database_=database)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curation", required=True, type=Path)
    parser.add_argument("--document", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--load", action="store_true")
    args = parser.parse_args()
    documents = [
        DocumentWrite.model_validate({key: value for key, value in document.items() if key != "approved"})
        for path in args.document for document in json.loads(path.read_text(encoding="utf-8"))
    ]
    release, rows = compile_release(json.loads(args.curation.read_text(encoding="utf-8")), documents)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(export_cypher(release, rows), encoding="utf-8")
    if args.load:
        load_release(os.environ["AI_GRAPH_URI"], os.environ.get("AI_GRAPH_USERNAME", "neo4j"),
                     os.environ["AI_GRAPH_PASSWORD"], os.environ.get("AI_GRAPH_DATABASE", "neo4j"), release, rows)
    print(json.dumps({"release_id": release, "claims": len(rows),
                      "sources": sorted({row["source_id"] for row in rows}), "loaded": args.load}))


if __name__ == "__main__":
    main()
