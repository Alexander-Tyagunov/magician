# Weaviate — Performance Playbook

Version: Weaviate DB v1.38 stable (Jun 2026), supported v1.36–1.38; self-hosted or Weaviate Cloud. HNSW is default (flat/dynamic alternatives). ANN is approximate: every lever trades recall ↔ latency ↔ memory. Set a recall@k target first, then tune.

## Prioritized levers (highest leverage first)

1. DIMENSIONS — biggest memory lever. RAM ≈ 2 × (n_vectors × dims × 4B); the 2× covers Go GC + HNSW links (each `maxConnections` link ≈ 8–10B). 1M×1536-dim ≈ 12GB. Prefer a smaller model or matryoshka/truncated dims over more hardware.
2. QUANTIZATION (per (named) vector; undoing needs recreate). RQ recommended: 8-bit ≈ 4× smaller at 98–99% recall (v1.32); 1-bit ≈ 32× at moderate recall (v1.33). BQ ≈ 32× (coarse); PQ slightly beats 1-bit recall but encodes slower. Compressed vectors search first, then `rescoreLimit` candidates re-score on full vectors — raise it to buy recall at a latency cost. `DEFAULT_QUANTIZATION` (v1.33) sets a fleet default; flat rejects PQ/SQ.
3. HNSW query knob `ef` (mutable): raises recall AND latency. Default `-1` = dynamic (`dynamicEfMin` 100, `dynamicEfMax` 500, `dynamicEfFactor` 8). Start ~64; >512 gives diminishing recall. Use static `ef` for predictable tail latency.
4. HNSW build knobs (IMMUTABLE): `efConstruction` 128, `maxConnections` 32. Higher = better recall + more RAM/slower build. Cutting `maxConnections` saves RAM but hurts recall — offset by raising `efConstruction`/`ef`. Wrong here = drop + reindex.
5. THROUGHPUT: a single insert/search is single-threaded; concurrency + batching use all cores. Shard (even on one node) + add CPU for QPS/import speed. Replicas add read QPS + HA.

## Top anti-patterns

- One vector per request. BATCH upserts — the client parallelizes them; single inserts waste cores.
- Post-filtering / fetch-then-drop. Weaviate PRE-filters via a roaring-bitmap allow-list (no brute force); build `indexFilterable` (default) and `indexRangeFilters` (int/number/date, new props only). Over-filtering rarely tanks recall (graph links still followed); filters under `flatSearchCutoff` (default 40000 ≈ 15%) auto-fall back to brute force. Keep `filterStrategy: acorn` (default v1.34) for low-correlation restrictive filters; else `sweeping`.
- Undersized RAM → OOM during import (imports out-allocate GC). Set `LIMIT_RESOURCES=true` or `GOMEMLIMIT` (~80–90%); enable `ASYNC_INDEXING=true` for background builds.
- `vectorCacheMaxObjects` below dataset size (default 1e12): a full cache drops wholesale and disk lookups are orders slower — keep it above live count during import.
- Mismatched distance metric — silent recall loss (see schema-and-vectorizers).

## How to measure

- Recall@k vs an exact baseline (flat index or `flatSearchCutoff: 0`) on a fixed query set; raise `ef` to target, then read the latency cost.
- Track p50/p95/p99 latency + QPS under concurrency, not one query. Watch heap, import rate, cache drops via `PROMETHEUS_MONITORING_ENABLED` metrics + spans (lore/databases/resilience-and-observability.md).
- Siblings: lore/weaviate/indexing-hnsw-and-compression.md, lore/weaviate/query-and-hybrid-search.md, lore/weaviate/schema-and-vectorizers.md; pooling: lore/databases/connection-pooling.md.

## Sources
docs.weaviate.io/weaviate/concepts/resources · /config-refs/indexing/vector-index · /weaviate/configuration/compression/rq-compression · /weaviate/concepts/filtering · /deploy/configuration/env-vars
