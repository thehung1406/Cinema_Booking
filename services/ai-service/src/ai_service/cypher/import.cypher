MERGE (release:KnowledgeRelease {id: $release_id})
WITH release
UNWIND $rows AS row
MERGE (source:Source {id: row.source_id})
MERGE (version:SourceVersion {id: row.version_id})
ON CREATE SET version.version = row.version, version.checksum = row.checksum,
              version.title = row.title, version.url = row.url, version.language = row.language
MERGE (source)-[:HAS_VERSION]->(version)
MERGE (chunk:Chunk {id: row.chunk_id})
ON CREATE SET chunk.page = row.page, chunk.block_index = row.block_index, chunk.excerpt = row.excerpt
MERGE (version)-[:HAS_CHUNK]->(chunk)
MERGE (concept:Concept {id: row.concept_id})
MERGE (claim:Claim {id: row.claim_id})
ON CREATE SET claim.scope = row.scope, claim.predicate = row.predicate,
              claim.qualifier = row.qualifier, claim.value = row.value, claim.status = row.status
MERGE (claim)-[:ABOUT]->(concept)
MERGE (claim)-[:SUPPORTED_BY]->(chunk)
MERGE (release)-[:INCLUDES]->(claim)
WITH DISTINCT release, concept, row.aliases AS aliases
UNWIND aliases AS entry
MERGE (alias:Alias {id: entry.id})
ON CREATE SET alias.label = entry.label, alias.language = entry.language, alias.normalized = entry.normalized
MERGE (alias)-[:NAMES]->(concept)
MERGE (release)-[:INCLUDES_ALIAS]->(alias)
