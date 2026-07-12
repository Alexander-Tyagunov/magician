# Chroma — core digest
Version: chromadb 1.x stable (1.5.x GA) · Apache-2.0 · Py>=3.9. Modes: embedded, client-server (`chroma run`, Http/AsyncHttp), Cloud. Index: HNSW single-node; SPANN on Cloud, server-fixed.

DO match space to the embedding metric — default `l2`; `cosine` for normalized text, `ip` for dot; set configuration={"hnsw":{"space":…}} at create.
DO pin ONE embedding_function per collection (stored in config, reused by add+query); one model only.
DO batch add/upsert (100s-1000s); honor get_max_batch_size(); never one per doc.
DO get_or_create_collection for idempotent setup; `ids` = upsert key.
DO tune recall↔latency: raise ef_search (mutable) per query; raise ef_construction + max_neighbors(=M) at create (immutable).
DO filter via where (metadata) + where_document ($contains); ops $eq/$ne/$gt(e)/$lt(e)/$in/$nin/$and/$or.
DO read distances smaller=closer (cosine/ip = 1−sim).

DON'T change space/ef_construction/max_neighbors after creation — recreate + re-add.
DON'T over-filter: a selective where starves HNSW recall.
DON'T ship the default MiniLM embedder unchecked.
DON'T treat Cloud SPANN params as tunable — server drops them.

Deep dive when writing non-trivial Chroma — read lore/chroma/{collections-and-usage,query-and-filtering,performance}.md

## Sources
docs.trychroma.com (configure · client-server · metadata-filtering) · pypi.org/project/chromadb
