MATCH (release:KnowledgeRelease)-[:INCLUDES]->(claim:Claim)-[:ABOUT]->(concept:Concept)
WHERE release.id IN $release_ids AND claim.scope = $scope AND claim.status = 'verified'
MATCH (release)-[:INCLUDES_ALIAS]->(alias:Alias)-[:NAMES]->(concept)
RETURN DISTINCT alias.normalized AS alias
ORDER BY alias
LIMIT 501
