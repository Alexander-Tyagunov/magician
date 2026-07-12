# Snowflake — core digest
Version: managed cloud DW — no user version; verify current docs. Editions: Standard, Enterprise (+multi-cluster, 90-day Time Travel), Business Critical, VPS; compute + storage billed separately.

DO scan less: columnar micro-partitions keep min/max metadata; project needed columns, push predicates to prune.
DO right-size warehouses (XS=1 credit/hr, doubles per size); per-second billing, 60s min/start; auto-suspend/resume on.
DO scale concurrency via multi-cluster warehouses (Enterprise), not a bigger one.
DO bulk-load COPY INTO from a stage; Snowpipe (serverless) micro-batch, Snowpipe Streaming for low-latency rows.
DO upsert via MERGE; Streams + Tasks or dynamic tables for incremental pipelines.
DO use zero-copy CLONE, Time Travel (AT/BEFORE, UNDROP), 24h result cache (no warehouse).

DON'T SELECT * on wide tables or run row-at-a-time DML — batch every write.
DON'T add a clustering key by reflex — only multi-TB tables, then rely on automatic clustering.
DON'T leave warehouses idle, or treat Fail-safe (7 days, Snowflake-only) as backup.

Deep dive — read lore/snowflake/{performance,warehouses-and-cost,storage-clustering-and-pruning,loading-and-streaming,query-features-and-time-travel}.md

## Sources
docs.snowflake.com: warehouses-overview · tables-clustering-micropartitions · data-load-overview · data-time-travel · intro-editions
