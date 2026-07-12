# Elasticsearch — Mapping & Indexing

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

Time-series note: for metrics use data streams + ILM and TSDB mode (`index.mode:time_series`), marking dimension `keyword`s and metric numerics — but keep dimension cardinality bounded (see performance.md).

See also lore/elasticsearch/{query-vs-filter-and-search,aggregations-and-scale,performance}.md and lore/databases.md.

## Sources
elastic.co/guide/en/elasticsearch/reference/current/mapping.html · .../text.html · .../nested.html · docs.opensearch.org/latest/field-types
