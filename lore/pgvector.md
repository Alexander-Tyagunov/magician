# pgvector — core digest
Version: 0.8.x stable (0.8.5); a PostgreSQL EXTENSION (PG 13+) — inherits lore/postgres. Types: vector (index ≤2000 dims), halfvec (≤4000), sparsevec (≤1000 nnz), bit. Indexes: HNSW, IVFFlat. Ops: `<->` L2, `<#>` inner-prod, `<=>` cosine, `<+>` L1.

DO pick the operator + opclass matching how the model was trained; `l2_normalize()` for unit vectors.
DO prefer HNSW (m=16, ef_construction=64) for recall/latency; raise `hnsw.ef_search` (default 40) per query to buy recall.
DO use IVFFlat only for fast builds / low memory; lists ≈ rows/1000 (≤1M), `ivfflat.probes` ≈ sqrt(lists).
DO cut memory with halfvec (2B/dim) or `binary_quantize()`+bit index, then re-rank by original vector.
DO batch load (COPY / multi-row) then build the index; bump maintenance_work_mem + max_parallel_maintenance_workers.
DO keep filter columns as ordinary Postgres columns (b-tree/GIN) + `hnsw.iterative_scan` (0.8) for filtered ANN.

DON'T index a vector >2000 dims — reduce (matryoshka/`subvector`) or use halfvec.
DON'T insert one vector per request or rebuild the index each write.
DON'T post-filter HNSW without `iterative_scan` (strict/relaxed_order): over-filtering collapses recall.
DON'T assume zero/NULL vectors are indexed (cosine skips zeros).

Deep dive when writing non-trivial pgvector — read lore/pgvector/{index-types-and-build,query-and-tuning,performance}.md

## Sources
github.com/pgvector/pgvector (0.8.5 README) · postgresql.org/docs
