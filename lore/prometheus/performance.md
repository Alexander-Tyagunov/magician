# Prometheus — Performance

Fix the biggest lever first, measure every change. Verified 3.x (3.13/3.5 LTS); PromQL + pull/scrape TSDB.

## 0. Measure first — cardinality & ingest
- DO diagnose cardinality via `/api/v1/status/tsdb`: `seriesCountByMetricName`, `labelValueCountByLabelName`, `seriesCountByLabelValuePair`, `headStats.numSeries`. Live: `prometheus_tsdb_head_series`, `rate(prometheus_tsdb_head_samples_appended_total[5m])`, `scrape_duration_seconds` per target.
- DO watch `prometheus_engine_query_duration_seconds` and `prometheus_tsdb_compaction_duration_seconds`. See lore/databases/resilience-and-observability.md.

## 1. Cardinality — THE #1 lever
Each distinct label-set is a new series with RAM/CPU/disk cost; cutting series beats slowing scrapes.
- DO bound labels to low-cardinality dims (method, status class, route template); if combos near 100+, drop dimensions. lore/prometheus/data-model-and-scraping.md.
- DO drop noisy series at ingest — cheapest control: `metric_relabel_configs` `action: drop` on `__name__`; cap exporters with `sample_limit` / `label_limit` / `target_limit`.
- DON'T put user/request/trace IDs, UUIDs, emails, or full URLs in labels — series explosion → OOM.

## 2. Downsample + retention (long-term lives elsewhere)
- DO precompute costly dashboard/alert PromQL as recording rules (`level:metric:operations`). lore/prometheus/promql-and-rules.md.
- DO `remote_write` to Thanos / Mimir / Cortex / VictoriaMetrics for long-term, HA, downsampling, global query — local TSDB is single-node, not durable (NFS/EFS unsupported).
- DO cap retention via prometheus.yml `storage.tsdb.retention.time`/`.size` (default 15d, size ~80-85% of disk); equivalent CLI flags `--storage.tsdb.retention.*` are deprecated. Sizing ≈ `retention_s × samples_per_s × 1-2 bytes`.

## 3. Query performance
- DO query bounded ranges; keep `rate()` windows ≥4× scrape interval. Serve dashboards from recording rules, not raw aggregates.
- DO cap blast radius: `--query.max-samples` (50M), `--query.max-concurrency` (20), `--query.timeout` (2m), `--query.lookback-delta` (5m).
- DON'T run wide regex matchers or unbounded `{__name__=~".+"}` scans on the hot path.

## 4. Ingest & histograms
- DO prefer native histograms (3.x) — one composite sample vs classic's N `_bucket` series. lore/prometheus/data-model-and-scraping.md.
- DO widen `scrape_interval` before adding scrapers; `memory-snapshot-on-shutdown` cuts WAL-replay restart time, `delayed-compaction` staggers compaction spikes.

## 5. remote_write tuning
- DO watch `prometheus_remote_storage_samples_pending` — growing ⇒ falling behind. Autoscaling reshards up to `max_shards`; raise `min_shards` for startup lag.
- DO keep `capacity` ≈ 3-10× `max_samples_per_send` (2000). Memory ∝ `shards × (capacity + max_samples_per_send)` — when raising batch size, lower `max_shards`. Endpoint down >2h ⇒ WAL compacted, unsent data lost.

## Sources
- https://prometheus.io/docs/prometheus/latest/storage/
- https://prometheus.io/docs/practices/remote_write/
- https://prometheus.io/docs/prometheus/latest/querying/api/
- https://prometheus.io/docs/practices/instrumentation/
