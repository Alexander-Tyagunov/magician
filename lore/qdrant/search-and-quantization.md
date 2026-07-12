# Qdrant — Search & Quantization

Current stable 1.x (self-hosted or Qdrant Cloud). ANN is approximate: recall ↔ latency ↔ memory — tune the index. Prefer the unified `query_points` API (v1.10+) over legacy `search`.

## Search knobs (per-request `params`)
- `hnsw_ef` is THE recall/latency dial — the HNSW candidate beam at query time. Raise it per query (e.g. 64→256) until recall plateaus. Higher = better recall, more CPU.
- `exact: true` forces brute-force full scan (100% recall, slow). Use ONLY to compute ground truth for measuring recall, never on prod hot paths.
- `indexed_only: true` skips segments still building their graph to bound tail latency.
- Build-time `m` (default 16) and `ef_construct` (default 100) cap achievable recall; `hnsw_ef` can't recover recall a too-low `m` left on the table. See lore/qdrant/collections-and-indexing.md.

## Distance metric MUST match the model
Pick `Cosine`, `Dot`, `Euclid` (L2), or `Manhattan` (L1) to match how the embedding model was trained. Cosine normalizes internally; for `Dot` you must L2-normalize or scores are meaningless. Dims are fixed at collection creation — truncate (matryoshka) before ingest, not after.

## Quantization (`quantization_config`)
Applied at index time; originals retained for rescoring. Set per collection or per named vector.
- Scalar (`int8`): ~4x smaller, SIMD-fast, error usually <1%. `quantile` (e.g. 0.99) clips outliers; `always_ram: true` pins quantized vectors in RAM. Best default.
- Binary: 1-bit = 32x; `encoding` (v1.15) `two_bits`=16x, `one_and_half_bits`=24x. Fastest; suits high-dim, roughly centered distributions (~0.98 recall@100 reachable on 1536-dim vectors with rescore + oversampling). `query_encoding` (v1.15) enables asymmetric scoring (`scalar8bits`/`scalar4bits`).
- Product: `compression` `x4`..`x64` via k-means centroids. Highest compression but NOT SIMD-friendly (slower) and lossier — use only when RAM is the hard constraint.

## Rescore & oversampling (`params.quantization`)
- `rescore: true` re-ranks the quantized shortlist with full-precision vectors. Default ON for binary; OFF for scalar/product — enable there when recall matters.
- `oversampling` (v1.3, e.g. 2.0–3.0) fetches limit×factor via quantized distance, then rescores to `limit`. This is how binary/product recover precision — pair it WITH rescore.
- `ignore: true` bypasses quantized vectors for that query.
- Tier: quantized in RAM + `on_disk: true` originals is the sweet spot; if disk is slow, dropping rescore trades recall for latency.

## Filtering & recall (over-filtering)
A selective filter can strand the HNSW walk in a disconnected region and tank recall. Qdrant mitigates with filterable HNSW (extra payload-based edges via `payload_m`) and, for hard/combined filters, ACORN (v1.16) which explores second-hop neighbors. Create payload indexes BEFORE ingest so the edges exist; see lore/qdrant/filtering-and-payloads.md.

## Hybrid & reranking
Combine dense + sparse (BM25/IDF) via `prefetch` sub-queries fused with `fusion: rrf` or `dbsf`, or rescore a dense prefetch with a reranker/late-interaction vector. Keep each prefetch `limit` modest.

Measure: compute ground truth with `exact: true`, then report recall@k while sweeping `hnsw_ef`/`oversampling`; load-test tail latency apart — see lore/qdrant/performance.md and lore/databases/resilience-and-observability.md.

## Sources
qdrant.tech/documentation/guides/quantization · /concepts/search · /concepts/indexing
