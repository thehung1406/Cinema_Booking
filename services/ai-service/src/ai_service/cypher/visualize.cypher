MATCH (:KnowledgeRelease {id: $release_id})-[:INCLUDES]->(claim:Claim)-[about:ABOUT]->(concept:Concept {id: $concept_id})
MATCH (claim)-[support:SUPPORTED_BY]->(chunk:Chunk)<-[contains:HAS_CHUNK]-(version:SourceVersion)<-[revision:HAS_VERSION]-(source:Source)
RETURN concept, about, claim, support, chunk, contains, version, revision, source
ORDER BY source.id, chunk.page
LIMIT 50
