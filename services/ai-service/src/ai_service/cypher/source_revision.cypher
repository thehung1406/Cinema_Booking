MATCH (:KnowledgeRelease {id: $release_id})-[:INCLUDES]->(claim:Claim)-[:SUPPORTED_BY]->(chunk:Chunk)
      <-[:HAS_CHUNK]-(:SourceVersion {version: $version, checksum: $checksum})<-[:HAS_VERSION]-(:Source {id: $source_id})
WHERE claim.scope = $scope AND claim.status = 'verified'
RETURN DISTINCT chunk.block_index AS block_index, chunk.page AS page, chunk.excerpt AS excerpt
LIMIT 501
