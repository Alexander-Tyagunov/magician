# Milvus — core digest
Version: 2.5.x/2.6.x stable, 3.0 beta; verify. Distributed: growing/sealed segments, compaction. Gates: BM25 sparse 2.5; RaBitQ/binary quant, MINHASH_LSH, nullable vectors 2.6. Zilliz Cloud managed. One index/vector field.

DO pick index by workload: HNSW (RAM, recall/QPS), DiskANN (huge, low RAM), IVF_FLAT/SQ8/PQ, SCANN, FLAT (exact).
DO match metric_type to model: COSINE/L2/IP; normalize IP (IP=cosine).
DO tune HNSW M/efConstruction+ef, IVF nlist/nprobe (def 128/8) for recall↔latency.
DO batch insert then flush; build index after bulk load; load before search, release RAM.
DO set consistency per search: Bounded (default), Strong read-after-write, Session own writes.
DO cut RAM via SQ/PQ/RaBitQ/binary quant + refine + refine_k to restore recall.
DO index filtered scalar fields, partition by tenant/key, hybrid dense+sparse (BM25), rerank (RRF/weighted).

DON'T over-filter: restrictive filters starve ANN recall/latency — measure it.
DON'T search before collection loaded + indexed.
DON'T change dimension or metric after creation — recreate.
DON'T assume Strong reads — default Bounded staleness.

Deep dive when writing non-trivial Milvus — read lore/milvus/{collections-and-index-types,search-and-consistency,scaling-and-architecture,performance}.md

## Sources
milvus.io/docs (index · metric · consistency · release_notes) · zilliz.com/cloud
