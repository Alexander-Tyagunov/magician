# Google BigQuery — Loading and Streaming

Serverless managed DW: no user version. Cost model evolves — GoogleSQL dialect; on-demand billing charges bytes scanned on read, capacity/editions (slots) charge compute-time. Ingestion has its own pricing lane (below). Verify current terms before quoting numbers.

## Choose the path by latency, not habit
- **Batch load (free)** — infrequently changing data, hourly/nightly. Load jobs from Cloud Storage (or local files), or the `LOAD DATA` SQL statement. Runs on the shared slot pool at **no charge** (cross-region reads may incur transfer). Loads are **atomic**: all rows or none.
- **Storage Write API** — the unified, recommended path for real-time and high-throughput batch. gRPC, protobuf/Arrow, first **2 TiB/month free**, then billed — but far cheaper than legacy insertAll.
- **Managed pipes** — Pub/Sub BigQuery subscription (high-throughput streaming loads), Datastream (CDC replication), Dataflow (preprocess then stream), Data Transfer Service (scheduled batch). Federated/external tables query GCS/Drive in place — that is not ingestion.

## Batch load — DO / DON'T
- DO prefer **Avro or Parquet**: self-describing (no schema needed) and read in parallel *even when compressed*. ORC also parallel. For CSV/JSON, **uncompressed loads faster** (parallel splits); `gzip` is the only supported compression and is slower.
- DO set write disposition deliberately: `WRITE_APPEND` (default), `WRITE_TRUNCATE` (replace + overwrite schema), `WRITE_EMPTY`. Combine `WRITE_TRUNCATE` with **partition decorators** (`table$YYYYMMDD`) for idempotent per-partition reloads and safe retries with backoff.
- DO load straight into **partitioned + clustered** tables so downstream reads prune. Use hive-partitioned layouts in GCS with `--autodetect` for schema on CSV/JSON.
- DON'T micro-batch load jobs: the default quota is **~1,500 loads per table per day**. Frequent tiny jobs exhaust it — switch to the Storage Write API for near-real-time.
- DON'T dump thousands of tiny files; consolidate so parallel readers stay busy.

## Storage Write API — stream types
- **Default stream** — at-least-once, immediate query visibility, no explicit stream to create, highest throughput. Use when duplicates are tolerable.
- **Committed** — exactly-once via client-supplied **offsets** (the API never writes the same offset twice); rows readable immediately. `CreateWriteStream → AppendRows(loop) → FinalizeWriteStream(optional)`.
- **Pending** — rows buffered until an atomic `BatchCommitWriteStreams`; a batch alternative to load jobs. `Create → AppendRows → Finalize → BatchCommit`.
- **Buffered** — advanced, Apache Beam connector only; otherwise avoid.
- Batch rows per `AppendRows` call; don't send one row per RPC.

## Gotchas
- Legacy `tabledata.insertAll` (REST) is the old streaming path: higher cost, streaming-buffer restrictions (recently streamed rows resist UPDATE/DELETE/export until flushed). Prefer the Storage Write API.
- Streaming is billed; batch load is free — don't stream data that could be nightly-batched.
- Upserts are **MERGE**, not row-by-row UPDATE. OLTP-style single-row DML at volume is an anti-pattern.
- Don't `SELECT *` to sanity-check a load — on-demand you pay per byte scanned; count/inspect specific columns.

## Sources
- docs.cloud.google.com/bigquery/docs/loading-data
- docs.cloud.google.com/bigquery/docs/batch-loading-data
- docs.cloud.google.com/bigquery/docs/write-api
