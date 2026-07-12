# Elasticsearch — Performance

Ordered playbook: fix the biggest lever first, measure each change. Current stable 9.x (8.x still supported). **OpenSearch** = the Apache-2.0 fork (2.x/3.x): same shard/segment engine so every lever applies; ships built-in Security and uses **PPL + SQL**, not ES|QL.

## 0. Measure first
- DO read `_cat/shards?v` / `_cat/indices?v` for size skew and `_nodes/stats` for heap, caches, `breakers`; profile a slow query with `"profile": true` or the search slow log.
- DO treat `429 TOO_MANY_REQUESTS` (queue full) and `CircuitBreakingException` (heap) as capacity signals, not blind-retry bugs. Retry/telemetry: lore/databases/resilience-and-observability.md.

## 1. Shard sizing — dominant lever
- DO aim **10–50 GB and <200M docs per shard**; few large shards beat many small. Cap ~**1000 non-frozen shards/node**; **<3000 indices per GB master heap**.
- DO roll over via ILM on `max_primary_shard_size: 50gb` (+ `max_age`); **force-merge read-only** indices toward 1 segment (never one still written). Fix oversized shards with Split/Reindex — shards are immutable.
- DON'T make daily indices for low-volume streams or over-shard "for growth."

## 2. Mapping is fixed at index time
- DO choose `text` (analyzed) vs `keyword` (exact, aggs/sort) up front — type changes need a reindex. Bound fields with `dynamic: strict` or **runtime fields**; unbounded dynamic JSON → **mapping explosion**.
- DON'T set `fielddata: true` on `text` (→ breaker trip); aggregate/sort on the `keyword` multi-field. Detail: lore/elasticsearch/mapping-and-indexing.md.

## 3. Query shape — filter beats query
- DO put non-scoring predicates in **filter context** (`bool.filter`) — cached, unscored. Round date ranges (`now-1h/m`) so the query cache hits.
- DON'T run leading-wildcard/`regexp`/`script` queries hot; search fewer fields via `copy_to`. Detail: lore/elasticsearch/query-vs-filter-and-search.md.

## 4. Aggregation memory
- DO expect high-cardinality `terms` aggs to dominate the **request breaker** (default 60% heap). Set `eager_global_ordinals` on hot keyword fields, pre-compute buckets, page with `composite`. Detail: lore/elasticsearch/aggregations-and-scale.md.

## 5. Bulk indexing
- DO write via **`_bulk`**, batch from ~100 docs, doubled until throughput plateaus (~tens of MB); use **multiple workers**; back off on `429`.
- DO for big loads: `refresh_interval: -1` (default `1s`) and `number_of_replicas: 0`, then restore + force-merge. Prefer **auto-generated IDs** (skips a per-shard dup check).

## 6. Pagination
- DON'T deep-page with `from`/`size` (capped at `index.max_result_window` 10000; shards buffer all prior pages). DO use **`search_after` + a PIT** with a tiebreaker sort; `track_total_hits: false` if the count is unneeded. Scroll is deprecated for real-time paging.

## 7. Retention, downsampling, hardware
- DO tier with **ILM** hot→warm→cold→frozen + delete; **downsample** TSDS to coarser intervals and shrink in warm.
- DO give **≥ half of RAM to the filesystem cache**; heap ≤ 50% RAM and **under ~32 GB** (compressed oops); SSDs. Client reuse: lore/databases/connection-pooling.md.

## Sources
- elastic.co/guide/en/elasticsearch/reference/current/{size-your-shards,tune-for-indexing-speed,tune-for-search-speed,paginate-search-results}.html
- docs.opensearch.org/latest
