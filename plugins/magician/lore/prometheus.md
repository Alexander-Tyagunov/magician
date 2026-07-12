# Prometheus — core digest
Version: 3.13 LTS stable (3.5 also LTS). 3.x: UTF-8 names, remote_write 2.0, native histograms. Pull/scrape, local TSDB, PromQL.

DO name in base units + type suffixes (`_total`, `_seconds`, `_bytes`; ratios 0-1); expose OpenMetrics.
DO rate()/increase() on counters, never raw values; irate() for fast graphs.
DO histogram_quantile() over buckets; native histograms (3.x) = high-res latency, no bucket sprawl; exemplars (trace IDs) link to traces.
DO precompute costly dashboard/alert PromQL as recording rules (`level:metric:operations`); bound query ranges.
DO aggregate with by()/without(); for ratios sum numerator & denominator, then divide.
DO remote_write to Thanos/Mimir/Cortex/VictoriaMetrics for long-term/HA/global; run redundant scrapers.
DO set retention (--storage.tsdb.retention.time/.size ~80-85% disk); POSIX only, no NFS/EFS.

DON'T put unbounded high-cardinality values (user/request IDs, UUIDs) in labels — series/mem blowup.
DON'T treat local TSDB as clustered/replicated/durable — single-node DB.
DON'T use it as an event/log/trace store or for exact per-request records.
DON'T rate() over a range under ~4x scrape interval, or alert without `for:`.

Deep dive when writing non-trivial Prometheus — read lore/prometheus/{data-model-and-scraping,promql-and-rules,performance}.md

## Sources
prometheus.io/docs {storage, naming, rules, querying} · GitHub prometheus/releases
