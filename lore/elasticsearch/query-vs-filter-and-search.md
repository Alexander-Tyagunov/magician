# Elasticsearch — Query vs Filter & Search

Version: Elasticsearch 9.x stable, 8.x supported (Elastic License 2.0 / SSPL, AGPLv3 since 8.16). OpenSearch is the Apache-2.0 fork of ES 7.10.2 — 3.x current, 2.x LTS; same Query DSL (JSON) over `_search`, but diverges: own security/ILM APIs, and **PPL + SQL** where ES has **ES|QL** (GA 8.14). Mapping is fixed at index time — analysis decides which queries work; no retype without reindex.

## Two contexts, one _search
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

## bool occurrences
`must`=AND (scored); `should`=OR (scored, boosts); `filter`=AND (no score); `must_not`=NOT (filter context, score 0). Gotcha: with `should` and no `must`/`filter`, `minimum_should_match` defaults to 1 (≥1 must match); add a `must`/`filter` and it defaults to 0, so `should` is pure boost. Set it explicitly.

## Analyzed vs exact — match vs term
`match`/`multi_match`/`match_phrase` are **analyzed** (query runs through the field analyzer) → use on `text`. `term`/`terms` are **not analyzed** → use on `keyword`. Classic bug: `term` on a `text` field returns nothing (indexed as tokens `quick`,`brown`; the raw string never matches). Index a multi-field (`text`+`keyword`): `match` for search, `term`/aggregate/sort on `.keyword`.

## Pagination — never deep from/size
`from`/`size` default 0/10, capped by `index.max_result_window` (10000): every shard loads from+size hits, so deep pages blow up heap/CPU. DO page with `search_after` + a **PIT** (point-in-time): sort with a unique tiebreaker (`_shard_doc` is implicit under a PIT), feed the last hit's `sort` into `search_after`, keep `from:0`, set `track_total_hits:false`, close PIT when done. Scroll API is no longer recommended for user-facing paging (batch/reindex only).

## ES|QL / PPL (analytics pipe)
ES **ES|QL** (GA 8.14): piped filter/transform/aggregate, own row `LIMIT` (default 1000):
```esql
FROM logs-* | WHERE status >= 500 | STATS errors = COUNT(*) BY host | SORT errors DESC | LIMIT 10
```
OpenSearch has **PPL** (`source=logs | where status>=500 | stats count() by host`) and SQL instead — not interchangeable. Use pipes for analytics; Query DSL for scored search + `search_after`.

DON'T sort/aggregate/`term` on a `text` field (needs `fielddata`, huge heap) — use `keyword`/`doc_values`.
DON'T read `_score` from filter-only queries (all 0/constant); add an explicit `sort`.

See lore/elasticsearch/mapping-and-indexing.md, lore/elasticsearch/aggregations-and-scale.md, lore/elasticsearch/performance.md, lore/databases.md.

## Sources
elastic.co/guide: query-filter-context, query-dsl-bool-query, full-text-queries, paginate-search-results, esql · docs.opensearch.org: query-dsl/full-text, sql-and-ppl
