# Prometheus — PromQL & Rules

Version: 3.x current. PromQL over a pull/scrape local TSDB. See also lore/prometheus/data-model-and-scraping.md.

## Types & selectors
Four types: instant vector, range vector, scalar, string. `query_range` (needs `step`) returns only scalar/instant vectors; `query` returns any. Matchers `=`,`!=`,`=~`,`!~`; regex is fully anchored (`env=~"foo"` ≡ `^foo$`), so use `.+` not `.*` and keep one non-empty matcher (`{job=~".+"}`). Range `[5m]` is left-open, right-closed. `offset`/`@ <ts>` (with `start()`/`end()`) attach to the SELECTOR, not the aggregation. Staleness lookback 5m (`--query.lookback-delta`); gone series go stale.

## Counters vs gauges — the core rule
DO `rate()`/`increase()` ONLY on counters; both adjust resets + extrapolate missed scrapes. `rate` for alerting/recording; `irate()` only for graphing fast, volatile counters.
DON'T aggregate before `rate`: `sum(rate(x[5m]))` is right — `rate(sum(...)[5m])` loses reset detection. Always `rate` first, then `sum`/`by`.
DO use `delta()`/`deriv()`/`predict_linear(v,t)` on GAUGES only (need ≥2 float samples). `rate` on a gauge is meaningless.
DO set the range ≥ 4× the scrape interval so `rate` sees enough samples.

## Histograms
Classic: `histogram_quantile(0.99, sum by (le) (rate(dur_seconds_bucket[5m])))` — needs the `le` label and a `+Inf` bucket; keep `le` through aggregation. Native histograms (one scalable series): `histogram_quantile(0.99, rate(dur_seconds[5m]))` — no `le` fanout; also `histogram_count/_sum/_avg/_fraction`. DON'T mix float and histogram samples in one range — those elements drop.

## Operators & matching
Binary vector ops drop `__name__`. `on(...)`/`ignoring(...)` pick match labels; `group_left`/`group_right` for many-to-one (that side is higher-cardinality). Comparisons filter; add `bool` for 0/1. `and`/`or`/`unless` are set ops. Aggregations `sum/avg/min/max/count/topk/quantile(φ,v)/count_values`; `min/max/quantile/stddev` ignore histograms. Prefer `without` over `by` to keep `job` and avoid conflicts.

## Rules
Load via `rule_files`; validate with `promtool check rules`; `SIGHUP` reloads. Within a GROUP rules run SEQUENTIALLY at one eval time (later rules see earlier records); groups run concurrently. If a group overruns its `interval` the eval is skipped (gap) — watch `rule_group_iterations_missed_total`; set `limit` to cap runaway series.
Recording: `record:/expr:/labels:`. Name `level:metric:operations` (e.g. `job:http_requests:rate5m`) — strip `_total` off counters, newest op first. Precompute expensive/dashboard/alert exprs; for ratios record numerator and denominator separately, then divide — never average a ratio or an average.
Alerting: `alert:/expr:/for:/keep_firing_for:/labels:/annotations:`; `for` debounces flaps; templates use `{{ $labels.x }}`/`{{ $value }}`.

## Storage reach
Local TSDB is single-node, NOT clustered/replicated → not long-term/HA. `remote_write` (tune `queue_config`) to Thanos/Mimir/Cortex/VictoriaMetrics for durable/global storage; `remote_read` still runs PromQL locally. Exemplars (OpenMetrics exposition) need `--enable-feature=exemplar-storage`, fetched via `/api/v1/query_exemplars`, NOT normal queries. See lore/prometheus/performance.md.

## Sources
prometheus.io/docs/prometheus/latest/querying/{basics,functions,operators} · configuration/recording_rules · practices/rules · storage · querying/api
