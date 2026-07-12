# Elasticsearch — core digest
Version: ES 9.4.x stable (9.x; 8.x common). Licensed AGPLv3/SSPL/ELv2. OpenSearch = Apache-2.0 fork (3.7.x, 2.x); diverges on license, security, APIs, ES|QL vs PPL (don't mix).

DO set MAPPING at index time: `text`=analyzed full-text, `keyword`=exact/sort/aggregate; near-immutable (reindex to change). `dynamic: strict` stops field explosion.
DO use filter context (`bool.filter`) for yes/no criteria — cached/unscored; query context for scoring.
DO bulk-index via `_bulk`; raise `refresh_interval` (or `-1`) during loads, then restore.
DO aim ~10-50GB/shard; data streams + ILM for time-series/logs; avoid tiny shards.
DO page deep hits with `search_after`+PIT, not `from`/`size` (capped by `index.max_result_window`, default 10000).
DO bound agg cardinality; page large groups via `composite`.

DON'T use ES as system of record — it's a secondary search/analytics store.
DON'T allow unbounded dynamic fields / high-cardinality text — blowups + OOM aggs.
DON'T leave the default 1 shard on big indices, nor over-shard small ones.

Deep dive when writing non-trivial Elasticsearch — read lore/elasticsearch/{mapping-and-indexing,query-vs-filter-and-search,aggregations-and-scale,performance}.md

## Sources
- elastic.co/docs/reference/elasticsearch/mapping-reference/
- elastic.co/docs/reference/elasticsearch/index-settings/index-modules
- opensearch.org/about.html
