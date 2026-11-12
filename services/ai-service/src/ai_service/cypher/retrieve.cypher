MATCH (release:KnowledgeRelease)-[:INCLUDES_ALIAS]->(alias:Alias)-[:NAMES]->(concept:Concept)
WHERE release.id IN $release_ids AND ($phrase CONTAINS (' ' + alias.normalized + ' ') OR alias.normalized IN $near_aliases)
WITH release, concept, collect(DISTINCT alias.normalized) AS matched_aliases
MATCH (release)-[:INCLUDES]->(claim:Claim)-[:ABOUT]->(concept)
WHERE claim.scope = $scope
MATCH (claim)-[:SUPPORTED_BY]->(chunk:Chunk)<-[:HAS_CHUNK]-(version:SourceVersion)<-[:HAS_VERSION]-(source:Source)
RETURN release.id AS graph_release, concept.id AS concept_id, matched_aliases, claim.id AS claim_id, claim.predicate AS predicate,
       claim.qualifier AS qualifier, claim.value AS value, claim.status AS status,
       source.id AS source_id, version.version AS version, version.checksum AS checksum,
       chunk.block_index AS block_index, chunk.page AS page, chunk.excerpt AS excerpt
ORDER BY concept_id, predicate, qualifier, source_id, page, claim_id
LIMIT 501
