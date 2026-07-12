# Prometheus — Data Model & Scraping

Version 3.x (3.13 & 3.5 LTS). UTF-8 names since v3.0.0; keep to the recommended charset.

## Data model
Series = name + labels + `(ms ts, float64|native-histogram)` samples; the name is the reserved `__name__` label. Name regex (SHOULD) `[a-zA-Z_:][a-zA-Z0-9_:]*`; labels `[a-zA-Z_][a-zA-Z0-9_]*` (no colon), `__`-prefixed = internal. UTF-8-outside names need quoted PromQL.

- DO treat each distinct label-set as a NEW series — **cardinality is the #1 memory/perf killer** (see lore/prometheus/performance.md). Empty value == label absent.
- DON'T label with unbounded values (IDs, URLs, emails) — series explosion; bound to low-cardinality dims.
- DON'T use `:` in exporters — colons are ONLY for recording-rule names. Suffix counters `_total`; use base units (seconds, bytes).

## Metric types (client-side; float series except native histograms)
- **Counter** — monotonic, resets to 0 on restart; never query raw, use reset-aware `rate()`/`increase()`.
- **Gauge** — up/down value.
- **Histogram** — classic: `_bucket{le}` (cumulative) + `_sum` + `_count`. Native (v3, preferred): one sample, exponential buckets; NHCB = static buckets ingested native. Both feed `histogram_quantile()`; native adds `histogram_fraction()`.
- **Summary** — client-side quantiles `{quantile}` + `_sum`/`_count`; NOT aggregatable across instances (use histograms). v3.0+ normalizes `le`/`quantile` to canonical numbers.

## Scraping (pull model)
PULLS `/metrics` on `scrape_interval` (per-job, inherits `global`); push only via Pushgateway for batch jobs.

- DO tune `scrape_interval`/`scrape_timeout` (timeout <= interval); `rate()` windows >=4x interval.
- DO cap with `sample_limit`/`label_limit`/`target_limit` (default 0 = off); over-limit fails the scrape.
- DO drop noisy SERIES via `metric_relabel_configs` (`action: drop` on `__name__`, post-scrape); `relabel_configs` filters TARGETS pre-scrape.
- DO set deliberately: `honor_labels: false` (default) renames conflicts to `exported_*`; `honor_timestamps: true` (default) uses target timestamps, false = scrape time.
- DO negotiate `scrape_protocols` (`OpenMetricsText1.0.0` for exemplars); native histograms via `scrape_native_histograms`, capped by `native_histogram_bucket_limit`.
- DON'T over-scrape — each series x scrape costs ingest; missed scrapes insert staleness markers (return no data).
- Exemplars: trace-ID refs on samples; enable `--enable-feature=exemplar-storage` (buffer in the `storage`/`exemplars` block, also WAL).

## Local storage is single-node — plan HA elsewhere
Local TSDB: 2h blocks, WAL, retention `--storage.tsdb.retention.time` (default 15d) and/or `.retention.size`. NOT clustered/replicated/durable; NFS/EFS unsupported.
- DO ship to an HA/long-term backend via `remote_write` (Thanos, Mimir, VictoriaMetrics).
- DON'T rely on `remote_read` for scale: PromQL evaluates locally, loading all data into the querying server first.

## Sources
- https://prometheus.io/docs/concepts/{data_model,metric_types}/
- https://prometheus.io/docs/prometheus/latest/{configuration/configuration,storage,feature_flags}/
