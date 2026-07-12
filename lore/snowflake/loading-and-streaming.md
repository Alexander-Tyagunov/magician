# Snowflake — Loading and streaming

Managed cloud DW (no user version; ingestion features/pricing evolve — verify current docs). Ingestion is **batch-first**: bulk-load staged files with `COPY INTO`, or stream with Snowpipe / Snowpipe Streaming. Row-at-a-time `INSERT ... VALUES` wastes compute and fragments micro-partitions — never build pipelines on it.

## Stages & file prep
- A **stage** holds files before load: **internal** (user `@~`, table `@%t`, named `@stg`; `PUT` uploads, auto-gzip) vs **external** (S3/GCS/Azure via a `STORAGE INTEGRATION` — prefer integrations over inline creds).
- DO size files **~100–250 MB compressed (or larger)**; aggregate tiny files, split huge ones. Avoid 100 GB+; a load running >24h may abort uncommitted. Parallelism is bounded by **file count** and warehouse size — one giant file can't parallelize.
- Prefer columnar **Parquet** for typed, compressed loads; define a reusable `FILE FORMAT` object.

## Bulk load: COPY INTO <table>
- `COPY INTO t FROM @stg` loads new files. Snowflake keeps **load metadata (~64 days)** and **skips already-loaded files** by path+checksum — so re-running is idempotent. `FORCE=TRUE` reloads all (risks duplicates); restaging a changed file makes a new checksum.
- DO set `ON_ERROR` deliberately: bulk default `ABORT_STATEMENT`; also `CONTINUE`, `SKIP_FILE`, `SKIP_FILE_<n>`/`<n>%`. Dry-run with `VALIDATION_MODE = RETURN_ERRORS`.
- Load semi-structured columns by name with `MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE` (order-independent), or transform inline: `COPY INTO t(c1) FROM (SELECT $1::int FROM @stg d)`. `PATTERN='.*\.parquet'` filters files; `PURGE=TRUE` deletes on success.

## Snowpipe (continuous, file-based)
- A **PIPE** wraps a COPY and loads files **serverlessly within minutes** of arrival. Automate with **cloud event notifications** (auto-ingest) over the polling REST endpoint; enable event filtering to cut noise/cost.
- Billed on **serverless compute Snowpipe consumes** (not your warehouse) + small per-file overhead — so file sizing still matters; stage roughly **one file per minute**. Load history lives in the pipe (~14 days); order is not guaranteed. Use bulk COPY **or** a pipe for a file set, never both (duplicates).

## Snowpipe Streaming (rows, seconds)
- Ingests **rows directly via SDK** (Java/Python/Node share a Rust core) or Kafka connector — no staged files — queryable in **seconds**. The current **high-performance architecture** centers on a server-side **PIPE**; the classic `snowflake-ingest-sdk` path is legacy/deprecating.
- **Exactly-once** via per-channel **offset tokens**; **ordered within a channel**. Billed **per uncompressed GB ingested**, not per file. Use for true low-latency event streams; if your source already writes files to blob storage, plain Snowpipe is cheaper.

## Upserts, Streams & Tasks
- DO upsert with `MERGE`, never per-row UPDATE loops.
- A **STREAM** is CDC: stores only an **offset** over a table's versioning and exposes changed rows (`METADATA$ACTION`, `METADATA$ISUPDATE`). Offset advances **only when consumed in a committed DML** (e.g. the MERGE) — querying alone doesn't. **One stream per consumer.** `APPEND_ONLY` streams are cheaper for insert-only ELT; streams go **stale** past source retention — recreate them.
- **TASKS** run scheduled/triggered SQL (gate with `WHEN SYSTEM$STREAM_HAS_DATA('s')` to fire only on change), chained into DAGs, on a warehouse or serverless.

## Dynamic tables (declarative pipelines)
- Prefer **dynamic tables** over hand-wired streams+tasks: declare a `SELECT` + `TARGET_LAG` (min **60s**, or `DOWNSTREAM`); Snowflake infers the DAG and refreshes **incrementally** when possible (`REFRESH_MODE AUTO/INCREMENTAL/FULL`). Billed as refresh warehouse compute + cloud services + storage. Not for sub-minute freshness or stored-proc/volatile logic.

## Sources
- https://docs.snowflake.com/en/user-guide/data-load-considerations-prepare
- https://docs.snowflake.com/en/sql-reference/sql/copy-into-table
- https://docs.snowflake.com/en/user-guide/data-load-snowpipe-intro
- https://docs.snowflake.com/en/user-guide/data-load-snowpipe-streaming-overview
- https://docs.snowflake.com/en/user-guide/streams-intro
- https://docs.snowflake.com/en/user-guide/dynamic-tables-about
