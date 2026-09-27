# Prometheus — deep dive

> On-demand companion to `lore/prometheus.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Data Model & Scraping](#data-model-and-scraping) · [PromQL & Rules](#promql-and-rules) · [Performance](#performance)

## Data Model & Scraping <a id="data-model-and-scraping"></a>

Version 3.x (3.13 & 3.5 LTS). UTF-8 names since v3.0.0; keep to the recommended charset.

### Data model
Series = name + labels + `(ms ts, float64|native-histogram)` samples; the name is the reserved `__name__` label. Name regex (SHOULD) `[a-zA-Z_:][a-zA-Z0-9_:]*`; labels `[a-zA-Z_][a-zA-Z0-9_]*` (no colon), `__`-prefixed = internal. UTF-8-outside names need quoted PromQL.

- DO treat each distinct label-set as a NEW series — **cardinality is the #1 memory/perf killer** (see lore/deep/prometheus.md#performance). Empty value == label absent.
- DON'T label with unbounded values (IDs, URLs, emails) — series explosion; bound to low-cardinality dims.
- DON'T use `:` in exporters — colons are ONLY for recording-rule names. Suffix counters `_total`; use base units (seconds, bytes).

### Metric types (client-side; float series except native histograms)
- **Counter** — monotonic, resets to 0 on restart; never query raw, use reset-aware `rate()`/`increase()`.
- **Gauge** — up/down value.
- **Histogram** — classic: `_bucket{le}` (cumulative) + `_sum` + `_count`. Native (v3, preferred): one sample, exponential buckets; NHCB = static buckets ingested native. Both feed `histogram_quantile()`; native adds `histogram_fraction()`.
- **Summary** — client-side quantiles `{quantile}` + `_sum`/`_count`; NOT aggregatable across instances (use histograms). v3.0+ normalizes `le`/`quantile` to canonical numbers.

### Scraping (pull model)
PULLS `/metrics` on `scrape_interval` (per-job, inherits `global`); push only via Pushgateway for batch jobs.

- DO tune `scrape_interval`/`scrape_timeout` (timeout <= interval); `rate()` windows >=4x interval.
- DO cap with `sample_limit`/`label_limit`/`target_limit` (default 0 = off); over-limit fails the scrape.
- DO drop noisy SERIES via `metric_relabel_configs` (`action: drop` on `__name__`, post-scrape); `relabel_configs` filters TARGETS pre-scrape.
- DO set deliberately: `honor_labels: false` (default) renames conflicts to `exported_*`; `honor_timestamps: true` (default) uses target timestamps, false = scrape time.
- DO negotiate `scrape_protocols` (`OpenMetricsText1.0.0` for exemplars); native histograms via `scrape_native_histograms`, capped by `native_histogram_bucket_limit`.
- DON'T over-scrape — each series x scrape costs ingest; missed scrapes insert staleness markers (return no data).
- Exemplars: trace-ID refs on samples; enable `--enable-feature=exemplar-storage` (buffer in the `storage`/`exemplars` block, also WAL).

### Local storage is single-node — plan HA elsewhere
Local TSDB: 2h blocks, WAL, retention `--storage.tsdb.retention.time` (default 15d) and/or `.retention.size`. NOT clustered/replicated/durable; NFS/EFS unsupported.
- DO ship to an HA/long-term backend via `remote_write` (Thanos, Mimir, VictoriaMetrics).
- DON'T rely on `remote_read` for scale: PromQL evaluates locally, loading all data into the querying server first.

### Sources
- https://prometheus.io/docs/concepts/{data_model,metric_types}/
- https://prometheus.io/docs/prometheus/latest/{configuration/configuration,storage,feature_flags}/

## PromQL & Rules <a id="promql-and-rules"></a>

Version: 3.x current. PromQL over a pull/scrape local TSDB. See also lore/deep/prometheus.md#data-model-and-scraping.

### Types & selectors
Four types: instant vector, range vector, scalar, string. `query_range` (needs `step`) returns only scalar/instant vectors; `query` returns any. Matchers `=`,`!=`,`=~`,`!~`; regex is fully anchored (`env=~"foo"` ≡ `^foo$`), so use `.+` not `.*` and keep one non-empty matcher (`{job=~".+"}`). Range `[5m]` is left-open, right-closed. `offset`/`@ <ts>` (with `start()`/`end()`) attach to the SELECTOR, not the aggregation. Staleness lookback 5m (`--query.lookback-delta`); gone series go stale.

### Counters vs gauges — the core rule
DO `rate()`/`increase()` ONLY on counters; both adjust resets + extrapolate missed scrapes. `rate` for alerting/recording; `irate()` only for graphing fast, volatile counters.
DON'T aggregate before `rate`: `sum(rate(x[5m]))` is right — `rate(sum(...)[5m])` loses reset detection. Always `rate` first, then `sum`/`by`.
DO use `delta()`/`deriv()`/`predict_linear(v,t)` on GAUGES only (need ≥2 float samples). `rate` on a gauge is meaningless.
DO set the range ≥ 4× the scrape interval so `rate` sees enough samples.

### Histograms
Classic: `histogram_quantile(0.99, sum by (le) (rate(dur_seconds_bucket[5m])))` — needs the `le` label and a `+Inf` bucket; keep `le` through aggregation. Native histograms (one scalable series): `histogram_quantile(0.99, rate(dur_seconds[5m]))` — no `le` fanout; also `histogram_count/_sum/_avg/_fraction`. DON'T mix float and histogram samples in one range — those elements drop.

### Operators & matching
Binary vector ops drop `__name__`. `on(...)`/`ignoring(...)` pick match labels; `group_left`/`group_right` for many-to-one (that side is higher-cardinality). Comparisons filter; add `bool` for 0/1. `and`/`or`/`unless` are set ops. Aggregations `sum/avg/min/max/count/topk/quantile(φ,v)/count_values`; `min/max/quantile/stddev` ignore histograms. Prefer `without` over `by` to keep `job` and avoid conflicts.

### Rules
Load via `rule_files`; validate with `promtool check rules`; `SIGHUP` reloads. Within a GROUP rules run SEQUENTIALLY at one eval time (later rules see earlier records); groups run concurrently. If a group overruns its `interval` the eval is skipped (gap) — watch `rule_group_iterations_missed_total`; set `limit` to cap runaway series.
Recording: `record:/expr:/labels:`. Name `level:metric:operations` (e.g. `job:http_requests:rate5m`) — strip `_total` off counters, newest op first. Precompute expensive/dashboard/alert exprs; for ratios record numerator and denominator separately, then divide — never average a ratio or an average.
Alerting: `alert:/expr:/for:/keep_firing_for:/labels:/annotations:`; `for` debounces flaps; templates use `{{ $labels.x }}`/`{{ $value }}`.

### Storage reach
Local TSDB is single-node, NOT clustered/replicated → not long-term/HA. `remote_write` (tune `queue_config`) to Thanos/Mimir/Cortex/VictoriaMetrics for durable/global storage; `remote_read` still runs PromQL locally. Exemplars (OpenMetrics exposition) need `--enable-feature=exemplar-storage`, fetched via `/api/v1/query_exemplars`, NOT normal queries. See lore/deep/prometheus.md#performance.

### Sources
prometheus.io/docs/prometheus/latest/querying/{basics,functions,operators} · configuration/recording_rules · practices/rules · storage · querying/api

## Performance <a id="performance"></a>

Fix the biggest lever first, measure every change. Verified 3.x (3.13/3.5 LTS); PromQL + pull/scrape TSDB.

### 0. Measure first — cardinality & ingest
- DO diagnose cardinality via `/api/v1/status/tsdb`: `seriesCountByMetricName`, `labelValueCountByLabelName`, `seriesCountByLabelValuePair`, `headStats.numSeries`. Live: `prometheus_tsdb_head_series`, `rate(prometheus_tsdb_head_samples_appended_total[5m])`, `scrape_duration_seconds` per target.
- DO watch `prometheus_engine_query_duration_seconds` and `prometheus_tsdb_compaction_duration_seconds`. See lore/deep/databases.md#resilience-and-observability.

### 1. Cardinality — THE #1 lever
Each distinct label-set is a new series with RAM/CPU/disk cost; cutting series beats slowing scrapes.
- DO bound labels to low-cardinality dims (method, status class, route template); if combos near 100+, drop dimensions. lore/deep/prometheus.md#data-model-and-scraping.
- DO drop noisy series at ingest — cheapest control: `metric_relabel_configs` `action: drop` on `__name__`; cap exporters with `sample_limit` / `label_limit` / `target_limit`.
- DON'T put user/request/trace IDs, UUIDs, emails, or full URLs in labels — series explosion → OOM.

### 2. Downsample + retention (long-term lives elsewhere)
- DO precompute costly dashboard/alert PromQL as recording rules (`level:metric:operations`). lore/deep/prometheus.md#promql-and-rules.
- DO `remote_write` to Thanos / Mimir / Cortex / VictoriaMetrics for long-term, HA, downsampling, global query — local TSDB is single-node, not durable (NFS/EFS unsupported).
- DO cap retention via prometheus.yml `storage.tsdb.retention.time`/`.size` (default 15d, size ~80-85% of disk); equivalent CLI flags `--storage.tsdb.retention.*` are deprecated. Sizing ≈ `retention_s × samples_per_s × 1-2 bytes`.

### 3. Query performance
- DO query bounded ranges; keep `rate()` windows ≥4× scrape interval. Serve dashboards from recording rules, not raw aggregates.
- DO cap blast radius: `--query.max-samples` (50M), `--query.max-concurrency` (20), `--query.timeout` (2m), `--query.lookback-delta` (5m).
- DON'T run wide regex matchers or unbounded `{__name__=~".+"}` scans on the hot path.

### 4. Ingest & histograms
- DO prefer native histograms (3.x) — one composite sample vs classic's N `_bucket` series. lore/deep/prometheus.md#data-model-and-scraping.
- DO widen `scrape_interval` before adding scrapers; `memory-snapshot-on-shutdown` cuts WAL-replay restart time, `delayed-compaction` staggers compaction spikes.

### 5. remote_write tuning
- DO watch `prometheus_remote_storage_samples_pending` — growing ⇒ falling behind. Autoscaling reshards up to `max_shards`; raise `min_shards` for startup lag.
- DO keep `capacity` ≈ 3-10× `max_samples_per_send` (2000). Memory ∝ `shards × (capacity + max_samples_per_send)` — when raising batch size, lower `max_shards`. Endpoint down >2h ⇒ WAL compacted, unsent data lost.

### Sources
- https://prometheus.io/docs/prometheus/latest/storage/
- https://prometheus.io/docs/practices/remote_write/
- https://prometheus.io/docs/prometheus/latest/querying/api/
- https://prometheus.io/docs/practices/instrumentation/
