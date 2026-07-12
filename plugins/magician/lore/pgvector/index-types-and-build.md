# pgvector — Index Types and Build

pgvector 0.8.x (0.8.5) — a PostgreSQL extension, so ANN indexes are real access methods (`hnsw`, `ivfflat`) built with `CREATE INDEX`. Approximate indexes trade recall for speed; without one, search is exact (perfect recall, full scan). Match the opclass to how the model was trained — see lore/pgvector/query-and-tuning.md for `ef_search`/`probes`.

## Choose the index type
- **HNSW** (graph): best recall/latency, slower builds, more memory. No training step — builds on an empty table and grows incrementally on insert. Default for most workloads.
- **IVFFlat** (inverted lists): faster builds, less memory, lower recall. Needs a k-means training step, so **create it only after the table holds representative data** — an empty/tiny table gives bad lists. `lists = rows/1000` (≤1M rows) or `sqrt(rows)` (>1M).

## Operator classes (metric must match the model)
Suffix by metric: `_l2_ops` (`<->`), `_ip_ops` (`<#>` dot), `_cosine_ops` (`<=>`), `_l1_ops` (`<+>`, HNSW only). Prefix by type: `vector_*`, `halfvec_*`, `sparsevec_*`, plus `bit_hamming_ops`/`bit_jaccard_ops`. IVFFlat covers L2/IP/cosine/Hamming only (no L1/Jaccard).
```sql
CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
```
HNSW build knobs: `m` (links/layer, default 16), `ef_construction` (candidate list, default 64) — higher = better recall, slower build/insert. IVFFlat sets `lists` at build; recall is bought later via `ivfflat.probes`.

## Index dimension limits (below storage)
Storage allows up to 16,000 dims/nnz, but **indexes cap lower:** `vector` ≤2000, `halfvec` ≤4000, `bit` ≤64000, `sparsevec` ≤1000 nnz. Over 2000 dims → index `halfvec`, or reduce via `subvector`/matryoshka truncation.

## Quantization via expression indexes
Cut index memory without changing the column, then re-rank by the original vector:
```sql
-- half precision: ~2 B/dim, indexes up to 4000 dims
CREATE INDEX ON items USING hnsw ((embedding::halfvec(1536)) halfvec_cosine_ops);
-- binary quantization (binary_quantize, 0.7.0+): tiny index, coarse recall
CREATE INDEX ON items USING hnsw ((binary_quantize(embedding)::bit(1536)) bit_hamming_ops);
```

## Build fast
- Bulk-load with `COPY` first, **then** create the index — cheaper than inserting through an existing HNSW graph.
- Raise `maintenance_work_mem` so the HNSW graph fits in memory (a NOTICE warns on spill); not so high the server OOMs.
- Parallelize: `max_parallel_maintenance_workers` (default 2, plus a leader); may also need `max_parallel_workers` (default 8) raised.
- Production: `CREATE INDEX CONCURRENTLY` avoids an ACCESS EXCLUSIVE lock on writes (slower; a failed build leaves an INVALID index — drop and retry).
- Progress: `SELECT phase, round(100.0*blocks_done/nullif(blocks_total,0),1) FROM pg_stat_progress_create_index;`

## DON'T
- DON'T build IVFFlat on empty/small data — the k-means lists are meaningless; drop it until you have volume.
- DON'T index >2000-dim `vector` — cast to `halfvec` or truncate.
- DON'T expect NULL (or zero, under cosine) vectors to be indexed — they're skipped.
- DON'T just `VACUUM` a churned HNSW index (slow) — `REINDEX INDEX CONCURRENTLY`, then vacuum. See lore/pgvector/performance.md and lore/databases/resilience-and-observability.md.

## Sources
github.com/pgvector/pgvector (0.8.5 README: Indexing, HNSW/IVFFlat, Reference) · postgresql.org/docs (CREATE INDEX, pg_stat_progress_create_index)
