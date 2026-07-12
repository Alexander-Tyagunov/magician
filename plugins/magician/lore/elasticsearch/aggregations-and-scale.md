# Elasticsearch — Aggregations & Scale

Version: ES 9.x stable (Elastic License 2.0/SSPL/AGPL-3.0). OpenSearch 2.x/3.x is the Apache-2.0 fork of ES 7.10 — same aggregation JSON, its own security plugin, and PPL (`stats ... by`) not ES|QL (`STATS ... BY`). Mapping is fixed at index time: aggregate only on doc_values fields (keyword/numeric/date) — analyzed `text` needs fielddata (avoid), so add a `.keyword` sub-field. Run aggs with `size:0` in filter context; pipeline aggs run in the reduce phase and can't page.

## terms is approximate — read the error fields
Counts on a sharded index are estimates: each shard returns its top `shard_size` (default `size*1.5+10`; `size` 10), then the coordinator merges. `sum_other_doc_count` = docs beyond top N; `show_term_doc_count_error:true` exposes `doc_count_error_upper_bound`. Raise `shard_size` (not `size`) to tighten accuracy. DON'T order by ascending `_count` (unbounded, unreportable error — only `_count` desc is); use `rare_terms` instead. `breadth_first` collect_mode (default when cardinality > size) prunes parents before child aggs, avoiding bucket blow-up.

## Distinct counts are approximate too
`cardinality` uses HyperLogLog++: fixed memory, ~1-6% error. `precision_threshold` (higher = more accurate, ~`threshold*8` bytes) trades memory for accuracy, near-exact below it. ES|QL `COUNT_DISTINCT` is the same estimator — no exact distinct counts at scale.

## Paginate with composite, not size:N
Enumerate ALL buckets with `composite`: small `size`, feed each response's `after_key` into `after` (flat: size == buckets). Limits: natural-order sort only (no sort-by-metric), no pipeline aggs; highest-cardinality source first, multi-valued last, `track_total_hits:false`. Don't fake it with a huge `terms` `size`.

## Bucket explosion & memory
`search.max_buckets` defaults to 65536 — exceeding it fails the request. Nested date_histogram × terms multiplies fast — bound time range and interval. keyword bucket aggs build per-shard global ordinals (rebuilt each refresh/new segment, lazy by default); set `eager_global_ordinals:true` on hot high-cardinality agg fields to move that cost to refresh. These live in heap and can trip the fielddata circuit breaker.

## date_histogram: calendar vs fixed
`calendar_interval` is DST/month/leap aware, single-unit only (`1d`,`1M`,`1q`,`1y`); `fixed_interval` is exact SI multiples (`30d`,`90m`) but has no months. Set `time_zone` for local buckets (DST skews edge buckets); the old `interval` param is gone.

## Scaling (search + TSDB)
- Aim 10-50GB and <200M docs/shard; few large shards beat many tiny ones (segment overhead, oversharding); stay under ~1000 non-frozen shards/node.
- Time-series: data streams + ILM rollover (`max_primary_shard_size:50gb`); downsample old data and query bounded ranges, not raw re-aggregation. DON'T aggregate unbounded high-cardinality keyword fields (user/request IDs, UUIDs) — it inflates global ordinals and heap.
- ES|QL `STATS ... BY` (GA 9.x) suits exploratory aggs; OpenSearch uses PPL or Query DSL.

Cross-refs: lore/elasticsearch/mapping-and-indexing.md, lore/elasticsearch/query-vs-filter-and-search.md, lore/elasticsearch/performance.md.

## Sources
elastic.co/guide (current): terms/composite/cardinality/date_histogram aggs, eager-global-ordinals, size-your-shards, search-settings, esql · docs.opensearch.org/latest/aggregations
