# Elasticsearch — deep dive

> On-demand companion to `lore/elasticsearch.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Mapping & Indexing](#mapping-and-indexing) · [Query vs Filter & Search](#query-vs-filter-and-search) · [Aggregations & Scale](#aggregations-and-scale) · [Performance](#performance)

## Mapping & Indexing <a id="mapping-and-indexing"></a>

Version: ES 9.x current stable (9.0, Apr 2025); 8.x still supported — semantics below apply to both. OpenSearch = Apache-2.0 fork of ES 7.10.2, current 3.x (2.x widespread): same text/keyword/nested model, but no ES|QL — it uses PPL + the SQL plugin, and the security/licensing stack differ.

Mapping is decided at INDEX TIME on an inverted index. You can ADD fields, but can't change an existing field's type/analyzer — that needs a reindex into a new index. Plan the schema before bulk-loading.

DO set explicit mappings in production; treat dynamic mapping as a prototyping crutch. `PUT /orders {"mappings":{"properties":{"sku":{"type":"keyword"},"body":{"type":"text"}}}}`.
DO pick text vs keyword deliberately: `text` is analyzed (standard analyzer → terms) for full-text scoring, rarely sortable/aggregatable; `keyword` is unanalyzed for exact match, terms aggs, and sort. IDs, status codes, tags → keyword.
DO use a multi-field for both: `{"type":"text","fields":{"raw":{"type":"keyword","ignore_above":256}}}` — search `body`, aggregate/sort `body.raw`. `ignore_above` skips over-long keyword values instead of erroring.
DO use `nested` (not plain `object`) for arrays of objects whose sub-fields must stay correlated — `object` flattens arrays and loses correlation, so `alice AND smith` cross-matches. Query it via a `nested` query + `path`.
DO bound field count: dynamic + varied JSON keys → mapping explosion → OOM. Keep `index.mapping.total_fields.limit` (default 1000) sane; for arbitrary key/value bags use `flattened` (one field, no per-key mapping).
DO tune indexing: use `_bulk`, and for large loads set `refresh_interval:-1` (or `"30s"`) then restore `"1s"` before docs must be searchable.
DO set `doc_values:false` on large fields never sorted/aggregated/scripted, `index:false` on store-only fields, and disable `norms` on unscored fields — each saves disk/heap.
DO reindex behind an ALIAS: create `orders-v2` with the fixed mapping, `_reindex` from v1, atomically repoint the alias; apps read the alias, never the concrete index.

DON'T rely on `"dynamic":true`; use `"strict"` (reject unknown fields) or `"runtime"` (queryable, unindexed, from `_source`) to catch drift. `false` silently drops fields from the index.
DON'T over-shard: `number_of_shards` is fixed at creation; target ~10–50GB per shard. Many tiny shards = cluster overhead.
DON'T set `fielddata:true` on text to aggregate/sort — it loads terms into heap and spikes latency; add a `keyword` sub-field instead.
DON'T abuse `nested`: each nested object is a separate hidden Lucene doc (1 parent + N children), so it's costly; mind `index.mapping.nested_fields.limit` (100) and `nested_objects.limit` (10000).
DON'T expect old docs to gain values when you add a multi-field — only docs (re)indexed after the change get populated.

Time-series note: for metrics use data streams + ILM and TSDB mode (`index.mode:time_series`), marking dimension `keyword`s and metric numerics — but keep dimension cardinality bounded (see lore/deep/elasticsearch.md#performance).

See also lore/deep/elasticsearch.md#{query-vs-filter-and-search,aggregations-and-scale,performance} and lore/databases.md.

### Sources
elastic.co/guide/en/elasticsearch/reference/current/mapping.html · .../text.html · .../nested.html · docs.opensearch.org/latest/field-types

## Query vs Filter & Search <a id="query-vs-filter-and-search"></a>

Version: Elasticsearch 9.x stable, 8.x supported (Elastic License 2.0 / SSPL, AGPLv3 since 8.16). OpenSearch is the Apache-2.0 fork of ES 7.10.2 — 3.x current, 2.x LTS; same Query DSL (JSON) over `_search`, but diverges: own security/ILM APIs, and **PPL + SQL** where ES has **ES|QL** (GA 8.14). Mapping is fixed at index time — analysis decides which queries work; no retype without reindex.

### Two contexts, one _search
Each clause runs in **query context** (computes relevance `_score`) or **filter context** (yes/no, no score, cacheable). Filter context: `filter`/`must_not` in `bool`, `filter` in `constant_score`, filter aggregations.

DO push exact/structural predicates (`term`, `terms`, `range` on dates/enums/status, geo) into `filter` — skips scoring, less CPU, and ES auto-caches hot filters per segment.
DO reserve `must`/`should` for the free-text part that should drive ranking.

```json
{ "query": { "bool": {
  "must":   [ { "match": { "title": "wireless earbuds" } } ],
  "filter": [ { "term":  { "status": "published" } },
              { "range": { "price": { "lte": 100 } } } ] } } }
```

DON'T wrap yes/no criteria in `must` — you pay for scoring you discard and lose filter caching.

### bool occurrences
`must`=AND (scored); `should`=OR (scored, boosts); `filter`=AND (no score); `must_not`=NOT (filter context, score 0). Gotcha: with `should` and no `must`/`filter`, `minimum_should_match` defaults to 1 (≥1 must match); add a `must`/`filter` and it defaults to 0, so `should` is pure boost. Set it explicitly.

### Analyzed vs exact — match vs term
`match`/`multi_match`/`match_phrase` are **analyzed** (query runs through the field analyzer) → use on `text`. `term`/`terms` are **not analyzed** → use on `keyword`. Classic bug: `term` on a `text` field returns nothing (indexed as tokens `quick`,`brown`; the raw string never matches). Index a multi-field (`text`+`keyword`): `match` for search, `term`/aggregate/sort on `.keyword`.

### Pagination — never deep from/size
`from`/`size` default 0/10, capped by `index.max_result_window` (10000): every shard loads from+size hits, so deep pages blow up heap/CPU. DO page with `search_after` + a **PIT** (point-in-time): sort with a unique tiebreaker (`_shard_doc` is implicit under a PIT), feed the last hit's `sort` into `search_after`, keep `from:0`, set `track_total_hits:false`, close PIT when done. Scroll API is no longer recommended for user-facing paging (batch/reindex only).

### ES|QL / PPL (analytics pipe)
ES **ES|QL** (GA 8.14): piped filter/transform/aggregate, own row `LIMIT` (default 1000):
```esql
FROM logs-* | WHERE status >= 500 | STATS errors = COUNT(*) BY host | SORT errors DESC | LIMIT 10
```
OpenSearch has **PPL** (`source=logs | where status>=500 | stats count() by host`) and SQL instead — not interchangeable. Use pipes for analytics; Query DSL for scored search + `search_after`.

DON'T sort/aggregate/`term` on a `text` field (needs `fielddata`, huge heap) — use `keyword`/`doc_values`.
DON'T read `_score` from filter-only queries (all 0/constant); add an explicit `sort`.

See lore/deep/elasticsearch.md#mapping-and-indexing, lore/deep/elasticsearch.md#aggregations-and-scale, lore/deep/elasticsearch.md#performance, lore/databases.md.

### Sources
elastic.co/guide: query-filter-context, query-dsl-bool-query, full-text-queries, paginate-search-results, esql · docs.opensearch.org: query-dsl/full-text, sql-and-ppl

## Aggregations & Scale <a id="aggregations-and-scale"></a>

Version: ES 9.x stable (Elastic License 2.0/SSPL/AGPL-3.0). OpenSearch 2.x/3.x is the Apache-2.0 fork of ES 7.10 — same aggregation JSON, its own security plugin, and PPL (`stats ... by`) not ES|QL (`STATS ... BY`). Mapping is fixed at index time: aggregate only on doc_values fields (keyword/numeric/date) — analyzed `text` needs fielddata (avoid), so add a `.keyword` sub-field. Run aggs with `size:0` in filter context; pipeline aggs run in the reduce phase and can't page.

### terms is approximate — read the error fields
Counts on a sharded index are estimates: each shard returns its top `shard_size` (default `size*1.5+10`; `size` 10), then the coordinator merges. `sum_other_doc_count` = docs beyond top N; `show_term_doc_count_error:true` exposes `doc_count_error_upper_bound`. Raise `shard_size` (not `size`) to tighten accuracy. DON'T order by ascending `_count` (unbounded, unreportable error — only `_count` desc is); use `rare_terms` instead. `breadth_first` collect_mode (default when cardinality > size) prunes parents before child aggs, avoiding bucket blow-up.

### Distinct counts are approximate too
`cardinality` uses HyperLogLog++: fixed memory, ~1-6% error. `precision_threshold` (higher = more accurate, ~`threshold*8` bytes) trades memory for accuracy, near-exact below it. ES|QL `COUNT_DISTINCT` is the same estimator — no exact distinct counts at scale.

### Paginate with composite, not size:N
Enumerate ALL buckets with `composite`: small `size`, feed each response's `after_key` into `after` (flat: size == buckets). Limits: natural-order sort only (no sort-by-metric), no pipeline aggs; highest-cardinality source first, multi-valued last, `track_total_hits:false`. Don't fake it with a huge `terms` `size`.

### Bucket explosion & memory
`search.max_buckets` defaults to 65536 — exceeding it fails the request. Nested date_histogram × terms multiplies fast — bound time range and interval. keyword bucket aggs build per-shard global ordinals (rebuilt each refresh/new segment, lazy by default); set `eager_global_ordinals:true` on hot high-cardinality agg fields to move that cost to refresh. These live in heap and can trip the fielddata circuit breaker.

### date_histogram: calendar vs fixed
`calendar_interval` is DST/month/leap aware, single-unit only (`1d`,`1M`,`1q`,`1y`); `fixed_interval` is exact SI multiples (`30d`,`90m`) but has no months. Set `time_zone` for local buckets (DST skews edge buckets); the old `interval` param is gone.

### Scaling (search + TSDB)
- Aim 10-50GB and <200M docs/shard; few large shards beat many tiny ones (segment overhead, oversharding); stay under ~1000 non-frozen shards/node.
- Time-series: data streams + ILM rollover (`max_primary_shard_size:50gb`); downsample old data and query bounded ranges, not raw re-aggregation. DON'T aggregate unbounded high-cardinality keyword fields (user/request IDs, UUIDs) — it inflates global ordinals and heap.
- ES|QL `STATS ... BY` (GA 9.x) suits exploratory aggs; OpenSearch uses PPL or Query DSL.

Cross-refs: lore/deep/elasticsearch.md#mapping-and-indexing, lore/deep/elasticsearch.md#query-vs-filter-and-search, lore/deep/elasticsearch.md#performance.

### Sources
elastic.co/guide (current): terms/composite/cardinality/date_histogram aggs, eager-global-ordinals, size-your-shards, search-settings, esql · docs.opensearch.org/latest/aggregations

## Performance <a id="performance"></a>

Ordered playbook: fix the biggest lever first, measure each change. Current stable 9.x (8.x still supported). **OpenSearch** = the Apache-2.0 fork (2.x/3.x): same shard/segment engine so every lever applies; ships built-in Security and uses **PPL + SQL**, not ES|QL.

### 0. Measure first
- DO read `_cat/shards?v` / `_cat/indices?v` for size skew and `_nodes/stats` for heap, caches, `breakers`; profile a slow query with `"profile": true` or the search slow log.
- DO treat `429 TOO_MANY_REQUESTS` (queue full) and `CircuitBreakingException` (heap) as capacity signals, not blind-retry bugs. Retry/telemetry: lore/deep/databases.md#resilience-and-observability.

### 1. Shard sizing — dominant lever
- DO aim **10–50 GB and <200M docs per shard**; few large shards beat many small. Cap ~**1000 non-frozen shards/node**; **<3000 indices per GB master heap**.
- DO roll over via ILM on `max_primary_shard_size: 50gb` (+ `max_age`); **force-merge read-only** indices toward 1 segment (never one still written). Fix oversized shards with Split/Reindex — shards are immutable.
- DON'T make daily indices for low-volume streams or over-shard "for growth."

### 2. Mapping is fixed at index time
- DO choose `text` (analyzed) vs `keyword` (exact, aggs/sort) up front — type changes need a reindex. Bound fields with `dynamic: strict` or **runtime fields**; unbounded dynamic JSON → **mapping explosion**.
- DON'T set `fielddata: true` on `text` (→ breaker trip); aggregate/sort on the `keyword` multi-field. Detail: lore/deep/elasticsearch.md#mapping-and-indexing.

### 3. Query shape — filter beats query
- DO put non-scoring predicates in **filter context** (`bool.filter`) — cached, unscored. Round date ranges (`now-1h/m`) so the query cache hits.
- DON'T run leading-wildcard/`regexp`/`script` queries hot; search fewer fields via `copy_to`. Detail: lore/deep/elasticsearch.md#query-vs-filter-and-search.

### 4. Aggregation memory
- DO expect high-cardinality `terms` aggs to dominate the **request breaker** (default 60% heap). Set `eager_global_ordinals` on hot keyword fields, pre-compute buckets, page with `composite`. Detail: lore/deep/elasticsearch.md#aggregations-and-scale.

### 5. Bulk indexing
- DO write via **`_bulk`**, batch from ~100 docs, doubled until throughput plateaus (~tens of MB); use **multiple workers**; back off on `429`.
- DO for big loads: `refresh_interval: -1` (default `1s`) and `number_of_replicas: 0`, then restore + force-merge. Prefer **auto-generated IDs** (skips a per-shard dup check).

### 6. Pagination
- DON'T deep-page with `from`/`size` (capped at `index.max_result_window` 10000; shards buffer all prior pages). DO use **`search_after` + a PIT** with a tiebreaker sort; `track_total_hits: false` if the count is unneeded. Scroll is deprecated for real-time paging.

### 7. Retention, downsampling, hardware
- DO tier with **ILM** hot→warm→cold→frozen + delete; **downsample** TSDS to coarser intervals and shrink in warm.
- DO give **≥ half of RAM to the filesystem cache**; heap ≤ 50% RAM and **under ~32 GB** (compressed oops); SSDs. Client reuse: lore/deep/databases.md#connection-pooling.

### Sources
- elastic.co/guide/en/elasticsearch/reference/current/{size-your-shards,tune-for-indexing-speed,tune-for-search-speed,paginate-search-results}.html
- docs.opensearch.org/latest
