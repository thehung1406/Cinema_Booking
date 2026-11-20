CREATE CONSTRAINT kb_release_id IF NOT EXISTS FOR (n:KnowledgeRelease) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT kb_source_id IF NOT EXISTS FOR (n:Source) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT kb_version_id IF NOT EXISTS FOR (n:SourceVersion) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT kb_chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT kb_concept_id IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT kb_alias_id IF NOT EXISTS FOR (n:Alias) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT kb_claim_id IF NOT EXISTS FOR (n:Claim) REQUIRE n.id IS UNIQUE;

MERGE (release:KnowledgeRelease {id: "2a11f6834bd478155ce4eb8b579b8853cada33280720de7b55199cfb4f102e1d"})
WITH release
UNWIND [{source_id: "cinema-booking-guide", version: "draft-2-20261120", version_id: "439fceb87e7c35c058f4cc0d8b5134c7716225ec83469d3e2ffea06444eac664", title: "Hướng dẫn đặt vé Cinema Booking", url: "/ticket-booking", checksum: "1ac353a67161e1a96e6977a111f18e175271bf63f8889ee07e4356f7f5f88049", language: "vi", scope: "policy", chunk_id: "d04ab08bb6fa1931dcc50c6914bebcbdfe2744a76447495744e78a7963d35b80", page: null, block_index: 1, excerpt: "Việc tra cứu trong trợ lý chưa giữ ghế.", concept_id: "seat-selection", claim_id: "45b4f6b982d664e68b896122914d0517a30733268ec60e23adf19b5c0201105a", predicate: "holds-seat", qualifier: "chat-assistant-search", value: "no", status: "verified", aliases: [{id: "c0b41d9ed681cdefb996a051538a1eb093ca200b64f91c7eeffff70733b0c184", label: "chọn ghế", language: "vi", normalized: "chon ghe"},
{id: "d808b8a84e12904a9b8abc32bd750b9207fd8aa1e680f2ca3f3cac0455076bda", label: "giữ ghế", language: "vi", normalized: "giu ghe"}]},
{source_id: "wikibooks-cinematography-summary", version: "oldid-3335736-summary-1", version_id: "b054e17a7bb7b4b5b047b4d96f76ba2a85d6cddcee957ff7681dcbf3be0ccd88", title: "Cinematography — tóm tắt tiếng Việt từ Wikibooks", url: "https://en.wikibooks.org/w/index.php?title=Movie_Making_Manual/Cinematography&oldid=3335736", checksum: "192c94bc9b099dffb0cca095cac2daa34fee774f55edf18ee5568955d69cc7a1", language: "vi", scope: "film_education", chunk_id: "522bfdd07b9e6d10acc4f6506520b98fb70188fb0d9980a220a8b70758b2c2d3", page: null, block_index: 1, excerpt: "Chuyển động máy quay có thể góp phần thể hiện cảm xúc.", concept_id: "camera-movement", claim_id: "967a931b4af568a4d5a8f2082e829fb8521438fc67b69f3e096c8d672f02e9b0", predicate: "example-purpose", qualifier: "general", value: "express-emotion", status: "verified", aliases: [{id: "1c8e8851b4d333ffcfdaa01c1813e61683adebf447cb1345ddc8e398e4d0ec28", label: "dolly", language: "en", normalized: "dolly"},
{id: "4ac00b8c0bc1647135cd54b6cf4ea5e89a5b7a751a9aa338a86e76100d98544c", label: "camera movements", language: "en", normalized: "camera movements"},
{id: "61577653c8fc98f710098ff85c6d6e1c96b078c7f03d9d0323215b95a67c2292", label: "chuyển động máy quay", language: "vi", normalized: "chuyen dong may quay"},
{id: "6ed3a21ea9e5805b277c710541e8ca991d321c46d020dbb63b0c26a9b2a25d42", label: "chuyển động của máy quay", language: "vi", normalized: "chuyen dong cua may quay"},
{id: "c1fd8796b06770af9c35a495262eabe4d105393cc205968af9b3c9a5018db604", label: "camera movement", language: "en", normalized: "camera movement"}]},
{source_id: "open-suny-film-construction", version: "2017", version_id: "4dbc6376ce471e97d7e10f5da60e3bfa331d53c387cfdade2bf3e1f4fa451772", title: "Exploring Movie Construction and Production", url: "https://openlibrary-repo.ecampusontario.ca/jspui/bitstream/123456789/429/1/Exploring-Movie-Construction-and-Production-1499438054.pdf", checksum: "789d951902d630beafbb81ec77253cfb2c52111595066eae97715c9e6983a258", language: "en", scope: "film_education", chunk_id: "4719a0efd59b5637f7f584e2a8c15c9aa82fba41e5449b184b34a49d0b2c70c0", page: 62, block_index: 55, excerpt: "the art or technique of motion-picture photography.", concept_id: "cinematography", claim_id: "ab82a97e0de81142f80ace0977ebd4a11732cd3d8573b82419ac294c7fc4ad82", predicate: "definition", qualifier: "", value: "motion-picture-photography", status: "verified", aliases: [{id: "9f9aee539b6dfc66559930f753d607e50d2c3c20514df01b19cb42e9b097fae7", label: "nghệ thuật quay phim", language: "vi", normalized: "nghe thuat quay phim"},
{id: "bacb3b7db9bd6fd182796de765ae6c11f273b6532621a010ecd14741c6e66365", label: "cinematography", language: "en", normalized: "cinematography"},
{id: "e1bc850549caca52e90de61b100c1f6be4131ec4836a08bd99857d302bbfc2c0", label: "quay phim", language: "vi", normalized: "quay phim"}]},
{source_id: "wikibooks-cinematography-summary", version: "oldid-3335736-summary-1", version_id: "b054e17a7bb7b4b5b047b4d96f76ba2a85d6cddcee957ff7681dcbf3be0ccd88", title: "Cinematography — tóm tắt tiếng Việt từ Wikibooks", url: "https://en.wikibooks.org/w/index.php?title=Movie_Making_Manual/Cinematography&oldid=3335736", checksum: "192c94bc9b099dffb0cca095cac2daa34fee774f55edf18ee5568955d69cc7a1", language: "vi", scope: "film_education", chunk_id: "bda14772d917ed673cb6e17fe2f69f7dd8e3bb06b66206cd80c414179a3bad71", page: null, block_index: 1, excerpt: "Cinematography là quá trình tạo hình ảnh chuyển động bằng phim hoặc kỹ thuật số.", concept_id: "cinematography", claim_id: "cbce8e83d9efbfc1daffed9a5e57bdcd1cc3d0895497e7f62d6c4c6bbeef256f", predicate: "definition", qualifier: "", value: "motion-picture-photography", status: "verified", aliases: [{id: "9f9aee539b6dfc66559930f753d607e50d2c3c20514df01b19cb42e9b097fae7", label: "nghệ thuật quay phim", language: "vi", normalized: "nghe thuat quay phim"},
{id: "bacb3b7db9bd6fd182796de765ae6c11f273b6532621a010ecd14741c6e66365", label: "cinematography", language: "en", normalized: "cinematography"},
{id: "e1bc850549caca52e90de61b100c1f6be4131ec4836a08bd99857d302bbfc2c0", label: "quay phim", language: "vi", normalized: "quay phim"}]},
{source_id: "open-suny-film-construction", version: "2017", version_id: "4dbc6376ce471e97d7e10f5da60e3bfa331d53c387cfdade2bf3e1f4fa451772", title: "Exploring Movie Construction and Production", url: "https://openlibrary-repo.ecampusontario.ca/jspui/bitstream/123456789/429/1/Exploring-Movie-Construction-and-Production-1499438054.pdf", checksum: "789d951902d630beafbb81ec77253cfb2c52111595066eae97715c9e6983a258", language: "en", scope: "film_education", chunk_id: "2a8013feaf98b37b61f5d5da6955198c097a1bdefdd5da8046496ff62958935b", page: 63, block_index: 56, excerpt: "Dolly: The camera moves side to side. This movement can be used to reveal something in a scene.", concept_id: "camera-movement", claim_id: "eda833ef09ec1cf4b2970e6bc5b3ddad8b39f7bf083c65e1e4967d0003b59c74", predicate: "example-purpose", qualifier: "dolly", value: "reveal-in-scene", status: "verified", aliases: [{id: "1c8e8851b4d333ffcfdaa01c1813e61683adebf447cb1345ddc8e398e4d0ec28", label: "dolly", language: "en", normalized: "dolly"},
{id: "4ac00b8c0bc1647135cd54b6cf4ea5e89a5b7a751a9aa338a86e76100d98544c", label: "camera movements", language: "en", normalized: "camera movements"},
{id: "61577653c8fc98f710098ff85c6d6e1c96b078c7f03d9d0323215b95a67c2292", label: "chuyển động máy quay", language: "vi", normalized: "chuyen dong may quay"},
{id: "6ed3a21ea9e5805b277c710541e8ca991d321c46d020dbb63b0c26a9b2a25d42", label: "chuyển động của máy quay", language: "vi", normalized: "chuyen dong cua may quay"},
{id: "c1fd8796b06770af9c35a495262eabe4d105393cc205968af9b3c9a5018db604", label: "camera movement", language: "en", normalized: "camera movement"}]}] AS row
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
MERGE (release)-[:INCLUDES_ALIAS]->(alias);
