# InfluxDB — core digest
Version: v3 current (Core/Enterprise 3.x: columnar, SQL+InfluxQL, no Flux). v2 (Flux+InfluxQL, buckets/tasks). v1 (InfluxQL only, RPs+CQs). v1/v2/v3 differ sharply — confirm version first.

DO model line protocol: measurement, string tags (filter/group identity), typed fields, timestamp; keep field types consistent.
DO batch writes (~10k lines or 10MB, gzip) at coarsest timestamp precision viable (default ns).
DO bound tag cardinality on v1/v2 — series = unique measurement+tagset; unbounded values (UUIDs, request/user IDs) explode memory; make them fields.
DO downsample + expire: v1 CQs + RPs; v2 tasks + bucket retention; v3 per-database retention.
DO query bounded time ranges; use that version's query language.
DO in v3 order tags by query priority on FIRST write — column order is then fixed; keep schemas narrow, not sparse.

DON'T assume Flux on v1/v3 — it's v2-only.
DON'T over-widen v3 tag sets — bigger primary key = slower sort (v3 tolerates cardinality, not width).
DON'T rely on local disk alone for retention/HA; v3 targets object storage.
DON'T use InfluxDB as a general log store or query without a time filter.

Deep dive when writing non-trivial InfluxDB — read lore/influxdb/{data-model-and-line-protocol,queries-influxql-flux-sql,performance}.md

## Sources
docs.influxdata.com: influxdb3/core (line-protocol, best-practices), influxdb/v2, influxdb/v1
