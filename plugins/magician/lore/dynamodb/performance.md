# Amazon DynamoDB — Performance

Managed serverless key-value/document store; no engine version. Capacity: on-demand or provisioned (RCU/WCU + auto scaling), both with adaptive capacity. Performance is won at MODEL time (keys + access patterns), not by buying capacity — every physical partition still caps at **~3000 RCU / 1000 WCU**.

## Levers, highest-impact first
1. **Partition-key distribution** — the #1 lever. High-cardinality key so load fans out; write-shard an unavoidably hot key and scatter-gather on read. A hot key throttles at the per-partition wall while the table sits idle — capacity can't fix it. See partition-keys-and-capacity.md.
2. **`Query`/`GetItem`, never `Scan`** — resolve every access pattern to one key lookup on the table or an index; single-table + composite SKs return a whole aggregate per round-trip. See data-modeling-single-table.md.
3. **Right index + tight projection** — back each pattern with a GSI; `KEYS_ONLY`/`INCLUDE` avoids base-table fetches and cuts payload. Sparse/overloaded GSIs replace `Scan`+filter. See secondary-indexes-gsi-lsi.md and lore/databases/indexing-and-query-plans.md.
4. **Batch, don't chatter** — `BatchGetItem` (100)/`BatchWriteItem` (25) and parallel requests beat per-item calls; retry `UnprocessedItems`. Big offline reads: parallel `Scan` (`TotalSegments`, ~1 seg/2 GB, table ≥20 GB) on a non-critical table.
5. **DAX for read-heavy hot keys** — write-through cache, ms → microsecond *eventual* reads, absorbs a hot key. NOT for strong reads (bypass cache) or write-heavy loads. Keep attribute *names* bounded — unbounded top-level names (timestamps/UUIDs as keys) exhaust DAX memory.
6. **Reuse connections** — enable SDK HTTP keep-alive to skip per-request TLS handshakes. See lore/databases/connection-pooling.md.
7. **Pre-warm + cap** — on-demand scales to 2× prior peak; request warm throughput before a known surge; set max throughput to cap cost.

## Top anti-patterns
- `Scan` on hot paths, or `FilterExpression` to trim a large `Scan` — you're billed for every item *examined* before the filter (`ScanCount ≫ Count` = wasted RCU). `ProjectionExpression` trims payload, not RCU.
- Low-cardinality / monotonic partition keys → hot partition.
- Under-provisioned GSI → throttles WRITES on the base table.
- Strong reads by default (2× cost), or read-after-write from a GSI (always eventual).
- `skip`/offset paging — cursor via `LastEvaluatedKey`→`ExclusiveStartKey`.

## Measure it (CloudWatch, 1-min)
- `ConsumedRead/WriteCapacityUnits` (`Sum`/60 = per-sec) vs provisioned; split GSIs by `GlobalSecondaryIndexName` dim.
- `ThrottledRequests` + `Read`/`WriteThrottleEvents`. **Throttle while table headroom remains = hot partition** — `Read`/`WriteKeyRangeThroughputThrottleEvents` isolate partition-limit throttles from provisioned ones.
- `SuccessfulRequestLatency` (server-side p99, `TableName`+`Operation`); `SystemErrors` needs both dims or the alarm never fires; `TransactionConflict` for contended items.
- Per-request `ReturnConsumedCapacity=TOTAL|INDEXES` to attribute cost.
- **Contributor Insights**: *Most Accessed Items* (`ConsumedThroughputUnits`=3×WCU+RCU) surfaces hot keys; *Most Throttled Items* (`ThrottleCount`) — throttled-keys mode is cheap to leave on. Retry throttles with exponential backoff + jitter (see lore/databases/resilience-and-observability.md).

## Sources
- docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-query-scan.html (Scan cost, Limit page size, parallel scan TotalSegments)
- .../DAX.html (microsecond eventual reads, not for strong/write-heavy, attribute-name memory limit)
- .../metrics-dimensions.html + contributorinsights_HowItWorks.html (throttle metrics, Most Accessed/Throttled graphs, ConsumedThroughputUnits)
