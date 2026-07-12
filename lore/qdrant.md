# Qdrant — core digest
Version: 1.18.x stable (self-hosted/Cloud). Gates: sparse 1.7; tenant/uuid payload idx 1.11; ACORN filter 1.16; TurboQuant 1.18. HNSW = only dense ANN index.

DO match Distance to the embedding metric (Cosine/Dot/Euclid/Manhattan); Cosine=Dot on normalized vecs.
DO batch upserts (100s-1000s/req), never one-by-one.
DO index every filtered payload field (keyword/int/float/bool/geo/datetime/text/uuid); else full scan.
DO tune HNSW: raise m + ef_construct for recall (build cost), set ef per query for latency/recall.
DO cut RAM via quantization (scalar 4x, binary/TurboQuant 32x, PQ 64x) + oversampling/rescore; offload cold data on_disk.
DO multi-tenant in ONE collection via partition-key payload + tenant index, not per-tenant collections.
DO run hybrid (dense + named sparse) via Query API prefetch/fusion + rerank.

DON'T over-filter: a tight filter starves HNSW recall; below full_scan_threshold it full-scans — verify recall.
DON'T change a vector's size/distance after creation; recreate instead.
DON'T enable memmap/quantization without measuring recall.
DON'T trust defaults (m=16, ef_construct=100) at scale or high recall.

Deep dive for non-trivial Qdrant — read lore/qdrant/{collections-and-indexing,filtering-and-payloads,search-and-quantization,performance}.md

## Sources
qdrant.tech/docs (indexing · quantization · collections) · github.com/qdrant/qdrant/releases
