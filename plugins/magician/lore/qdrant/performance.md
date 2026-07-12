# Qdrant — Performance

Version: current stable 1.18.x (self-hosted or Qdrant Cloud). HNSW vector index; scalar/product/binary + TurboQuant (1.18) quantization; per-collection optimizer/segment tuning. Verify param names/defaults against your release — they evolve.

The core tradeoff is recall ↔ latency ↔ memory. Levers below are ordered by typical payoff.

## Prioritized levers (biggest wins first)

1. Keep hot vectors in RAM, and size it. Estimate `vectors × dim × 4 bytes × 1.5` (the ×1.5 covers indexes, versions, temp segments). Rule of thumb: storing half your vectors in RAM roughly doubles search latency. If it won't fit, quantize before offloading to disk.
2. Quantize to shrink the working set. `scalar` int8 = 4x, SIMD-accelerated, ~1% error — the safe default; keep quantized vectors resident with `always_ram: true` and push originals `on_disk: true`. `binary` = up to 32x and much faster, but only for high-dim, centered embeddings; `product` up to 64x but slower (no SIMD); TurboQuant (1.18) defaults to `bits4` (8x). Restore precision with `rescore` + `oversampling` (e.g. 2.0). See lore/qdrant/search-and-quantization.md.
3. Tune HNSW to the recall target. Defaults `m: 16`, `ef_construct: 100`; raise `m`/`ef_construct` for recall (more RAM, slower build), raise query-time `ef`/`hnsw_ef` for recall at latency cost. On-disk HNSW (`on_disk: true`, e.g. `m: 64, ef_construct: 512`) trades RAM for IOPS-bound latency; `inline_storage` (1.16) cuts disk IO at ~3-4x storage. See lore/qdrant/collections-and-indexing.md.
4. Match segments to your goal via `default_segment_number` (0 = auto ≈ CPU cores). Latency: segments ≈ cores so one query fans across cores. Throughput: fewer (~2), larger segments handle more parallel requests.
5. Index the payload fields you filter on BEFORE ingest, so filterable-HNSW edges get built into the graph — otherwise you must rebuild HNSW. Over-restrictive filters fragment traversal (ACORN, 1.16, mitigates). See lore/qdrant/filtering-and-payloads.md.
6. Threshold control: `indexing_threshold_kb` (default 10000; set 0 to skip indexing during bulk load, re-enable after) and `memmap_threshold` to memory-map large segments onto disk.

## Anti-patterns
- One-vector-per-request upserts — always batch; set `wait: false` for ingest throughput.
- Payload indexes created after loading data (forces a full HNSW rebuild).
- Distance metric mismatched to how the model was trained (normalize for cosine).
- All payload pinned in RAM — put non-filtered fields `on_disk`.
- Unbounded unindexed segments under heavy writes — use `indexed_only` / `prevent_unoptimized` (1.17) so queries skip slow full scans.
- Non-POSIX storage (WSL bind mounts → corruption); too-low open-file limit (OS error 24 — raise `ulimit -n`).

## How to measure
- Recall: run search with `exact: true` for ground truth, compare ANN results across `hnsw_ef` values.
- Quantization quality: compare `ignore: true` vs `false`.
- Disk-bound builds/search: measure IOPS (fio); watch the optimizer via `/collections/{name}/optimizations` + telemetry/metrics, and `update_queue` deferred-point count.
- Track p95/p99 latency alongside throughput; see lore/databases/resilience-and-observability.md and lore/databases/connection-pooling.md.

## Sources
qdrant.tech/documentation/ops-optimization/{optimize,optimizer} · guides/quantization · concepts/indexing · capacity-planning (v1.18)
