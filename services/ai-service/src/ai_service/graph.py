"""Read a pinned knowledge release and validate its evidence against the owner DB."""
from collections import defaultdict
from difflib import SequenceMatcher
from importlib.resources import files
import re

from neo4j import GraphDatabase, Query
from sqlmodel import select

from .models import KnowledgeChunk, KnowledgeDocument, utcnow
from .rag import folded, safe_source_url


def cypher(name):
    return files("ai_service").joinpath("cypher", name).read_text(encoding="utf-8")


def normalize_alias(text):
    return " ".join(re.findall(r"[a-z0-9]+", folded(text)))


def normalize_excerpt(text):
    return " ".join(text.split())


def near_aliases(phrase, aliases):
    tokens = phrase.split()
    scores = {}
    for alias in aliases:
        if len(alias) < 8:
            continue
        width = len(alias.split())
        best = max((SequenceMatcher(None, alias, " ".join(tokens[index:index + width])).ratio()
                    for index in range(len(tokens) - width + 1)), default=0)
        if best >= 0.90:
            scores[alias] = best
    if not scores:
        return {}
    top = max(scores.values())
    return {alias: score for alias, score in scores.items() if top - score < 0.04}


class KnowledgeGraph:
    def __init__(self, uri, username, password, database, release_id):
        self.database = database
        self.release_id = release_id
        self.driver = GraphDatabase.driver(
            uri, auth=(username, password), connection_timeout=2, connection_acquisition_timeout=3
        )
        self.query = Query(cypher("retrieve.cypher"), timeout=3)
        self.alias_query = Query(cypher("aliases.cypher"), timeout=3)
        self.revision_query = Query(cypher("source_revision.cypher"), timeout=3)

    def close(self):
        self.driver.close()

    def revision_spans(self, release_id, document):
        parameters = dict(release_id=release_id, source_id=document["source_id"], version=document["version"],
                          checksum=document["provenance"].get("checksum"), scope=document["provenance"].get("scope", "policy"))
        with self.driver.session(database=self.database, default_access_mode="READ") as session:
            return session.run(self.revision_query, parameters).data()

    def find(self, question, scope, release_ids):
        phrase = f" {normalize_alias(question)} "
        scores = {}
        with self.driver.session(database=self.database, default_access_mode="READ") as session:
            parameters = dict(release_ids=release_ids, phrase=phrase, scope=scope, near_aliases=[])
            matches = session.run(self.query, parameters).data()
            if not matches:
                aliases = session.run(self.alias_query, release_ids=release_ids, scope=scope).value("alias")
                if len(aliases) > 500:
                    raise ValueError("Knowledge graph returned too many aliases")
                scores = near_aliases(phrase, aliases)
                if scores:
                    matches = session.run(self.query, parameters | {"near_aliases": list(scores)}).data()
        if len(matches) > 500:
            raise ValueError("Knowledge graph returned too many claims")
        for match in matches:
            match["alias_score"] = max(scores.get(alias, 1.0) for alias in match["matched_aliases"])
            match["alias_method"] = "near" if scores else "exact"
        return matches


def graph_evidence(db, graph, question, scope, limit=3):
    active = select(KnowledgeDocument).where(KnowledgeDocument.approved.is_(True),
                                             KnowledgeDocument.effective_at <= utcnow())
    release_ids = {doc.provenance.get("graph_release_id", graph.release_id) for doc in db.exec(active).all()
                   if doc.provenance.get("scope", "policy") == scope}
    db.rollback()
    if not release_ids:
        return [], "no_match"
    matches = graph.find(question, scope, sorted(release_ids))
    if not matches:
        return [], "no_match"
    source_ids = {match["source_id"] for match in matches}
    rows = db.exec(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
        KnowledgeDocument.source_id.in_(source_ids),
        KnowledgeDocument.approved.is_(True),
        KnowledgeDocument.effective_at <= utcnow(),
    )).all()
    chunks = defaultdict(list)
    for chunk, doc in rows:
        if doc.provenance.get("scope", "policy") != scope:
            continue
        key = (doc.provenance.get("graph_release_id", graph.release_id), doc.source_id,
               doc.version, doc.provenance.get("checksum"),
               chunk.provenance.get("block_index"), chunk.provenance.get("page_start"))
        chunks[key].append((chunk, doc))

    evidence, groups, alias_concepts = [], defaultdict(set), defaultdict(set)
    pending_groups = set()
    for match in matches:
        key = tuple(match[field] for field in ("graph_release", "source_id", "version", "checksum", "block_index", "page"))
        excerpt = match["excerpt"]
        for chunk, doc in chunks[key]:
            if not excerpt or excerpt not in normalize_excerpt(chunk.content):
                continue
            group = (match["concept_id"], match["predicate"], match["qualifier"])
            if match["status"] != "verified":
                pending_groups.add(group)
                break
            groups[group].add(match["value"])
            for alias in match["matched_aliases"]:
                alias_concepts[alias].add(match["concept_id"])
            if match["alias_method"] == "near":
                alias_concepts["near candidates"].add(match["concept_id"])
            url = safe_source_url(doc.source_url)
            if match["page"]:
                url = url.split("#", 1)[0] + f"#page={match['page']}"
            evidence.append(dict(
                id=f"doc:{chunk.id}", title=doc.title, text=excerpt, url=url, version=doc.version,
                kind="document", document_id=doc.id, source_id=doc.source_id, score=match["alias_score"],
                provenance=doc.provenance | chunk.provenance | {
                    "graph_release": match["graph_release"],
                    "concept_id": match["concept_id"],
                    "claim_id": match["claim_id"],
                    "alias_method": match["alias_method"],
                    "matched_aliases": match["matched_aliases"],
                },
            ))
            break
    db.rollback()
    if any(len(concepts) > 1 for concepts in alias_concepts.values()):
        return [], "ambiguous"
    if any(len(values) > 1 for values in groups.values()):
        return [], "conflict"
    if pending_groups.difference(groups):
        return [], "uncertain"
    # Allocate first slots to different sources so a single book cannot crowd out a second source.
    unique = {item["id"]: item for item in reversed(evidence)}
    first_by_source = {}
    for item in reversed(list(unique.values())):
        first_by_source.setdefault(item["source_id"], item)
    selected = {item["id"]: item for item in first_by_source.values()}
    return list((selected | unique).values())[:limit], "matched" if selected else "no_match"


def merge_evidence(text_sources, graph_sources, graph_state, limit):
    if graph_state in {"conflict", "ambiguous", "uncertain"}:
        return []
    by_id = {source["id"]: source for source in text_sources}
    linked = {}
    for source in graph_sources:
        text_source = by_id.get(source["id"])
        linked[source["id"]] = (text_source | {"provenance": source["provenance"] | {"graph_excerpt": source["text"]}}
                                if text_source else source)
    # The text retriever ranks the question itself. Graph matches expand coverage through related sources.
    merged = {source["id"]: linked.get(source["id"], source) for source in text_sources[:1]}
    merged.update(linked)
    for source in text_sources:
        merged.setdefault(source["id"], source)
    return list(merged.values())[:limit]
