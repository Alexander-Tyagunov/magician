# Weaviate — Query & Hybrid Search

Version: Weaviate DB v1.38 stable (Jun 2026); clients Python v4.16+, JS/TS v3.8+. Vector (`nearVector`/`nearText`), keyword (`bm25`), and `hybrid` all accept `filters`, `limit`/`offset`, `groupBy`, and `targetVector`/`target_vector` (REQUIRED on named-vector collections).

DO tune recall↔latency at QUERY time via HNSW `ef` (per-query, overrides collection `ef`; `-1` = dynamic from limit): a wider beam raises recall AND latency. See lore/weaviate/indexing-hnsw-and-compression.md.
DO bound similarity with EITHER `distance` OR `certainty` (mutually exclusive); `certainty` (0–1) is meaningful only for `cosine`. In hybrid, cap the vector leg with `maxVectorDistance`.
DO run `hybrid(query=, alpha=)`: `alpha` default 0.75 (1.0 = pure vector, 0.0 = pure BM25, 0.5 = even). Fusion `relativeScoreFusion` is default since v1.24 (normalize then add scores) vs `rankedFusion` (sum of 1/rank). Prefer relative-score; it is REQUIRED for autocut.
DO scope the keyword leg with `queryProperties`/`properties` + caret boosts (`["title^2","body"]`); this affects BM25 ONLY, not the vector leg. Pass your own `vector=` to override the embedded query.
DO tighten BM25 with the search operator (v1.31): `Or` + `minimum_match`/`minimumOrTokensMatch` (default `Or`), or `And` (all tokens within one property). BM25F scores `word`-tokenized text; use `trigram` tokenization for typo tolerance, else `lowercase`/`whitespace`/`field`. Stopwords are filtered at query time (v1.37, no reindex).
DO PRE-FILTER: pass `filters=` — Weaviate builds an inverted-index allow-list (uint64 ids) THEN walks HNSW, so filtered recall ≈ unfiltered (no brute-force scan). Needs `indexFilterable` (roaring bitmaps, default) / `indexRangeFilters` (int/number/date) / `indexSearchable` for BM25. Use `containsAny`/`containsAll`/`Not`, `by_ref` for cross-refs (slower).
DO leave `filterStrategy: acorn` (default v1.34): multi-hop traversal + extra matching entrypoints — much faster for RESTRICTIVE, low-correlation filters; `sweeping` is the older linear scan. Very selective filters (~<15% of data) auto-fall back to brute force over the matched subset.
DO two-stage retrieve→rerank: configure a reranker module, then `rerank(prop=, query=)` reorders the top `limit` hits with a heavier cross-encoder — keep `limit` small (cost is per-candidate). `autocut`/`auto_limit` trims to score cliffs; `return_metadata(score, explain_score)` / `explainScore` breaks out bm25/vector/hybrid contributions.

DON'T post-filter in app code — you lose recall guarantees and waste retrieved candidates; always push predicates via `filters=`.
DON'T pair `autocut` with `rankedFusion` (ranks have no score gaps to cut on) — use `relativeScoreFusion`.
DON'T omit `targetVector` on named-vector collections, or query raw `dot` on un-normalized vectors (unbounded, wrong ordering).
DON'T deep-paginate with a large `offset` (re-scans from 0) — narrow with filters + small `limit`, or cursor over ids.
DON'T set query `ef` too low to save latency — recall drops silently; measure recall per query set.

Tuning playbook: lore/weaviate/performance.md. Schema/vectorizer/metric setup: lore/weaviate/schema-and-vectorizers.md. Timeouts/retries/observability: lore/databases/resilience-and-observability.md.

## Sources
docs.weaviate.io/weaviate/search/{hybrid,bm25,filters,rerank} · /weaviate/concepts/filtering · /weaviate/api/graphql/search-operators
