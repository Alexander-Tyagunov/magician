# Amazon DynamoDB — deep dive

> On-demand companion to `lore/dynamodb.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Single-table data modeling](#data-modeling-single-table) · [Partition keys & capacity](#partition-keys-and-capacity) · [Secondary indexes (GSI & LSI)](#secondary-indexes-gsi-lsi) · [Streams & transactions](#streams-and-transactions) · [Performance](#performance)

## Single-table data modeling <a id="data-modeling-single-table"></a>

Managed serverless key-value/document store; no version; capacity on-demand or provisioned (RCU/WCU). Single-table design packs many entity types into ONE table so a `Query` returns a full aggregate — best for known, correlated patterns, not a mandate: split independent-access entities into separate tables.

### Model the queries first, then the keys
List every access pattern BEFORE choosing keys; each must resolve to one `Query`/`GetItem` on table or GSI — never `Scan`. No joins — pre-join by co-locating related items.

### Generic keys + entity overloading
Name keys generically (`PK`/`SK`, `GSI1PK`/`GSI1SK`), encode type in value: `PK=USER#123`, `SK=PROFILE#123` or `ORDER#<date>#456`. `Query PK=USER#123 AND begins_with(SK,'ORDER#')` returns that user's orders, sorted. Keep a `type` attr per item to filter.

### Composite sort keys & item collections
A composite `SK` (`US#CA#LA`) models hierarchy + range/prefix reads via `begins_with`/`between`; items sharing a `PK` form an *item collection*, sorted by `SK`. Limits: **400 KB/item**; an LSI caps each collection at **10 GB** — GSIs don't.

### GSIs vs LSIs, inverted & sparse
- **GSI** (default 20/table): own PK/SK + throughput, **eventually consistent only** (no `ConsistentRead`), added/dropped anytime. Overload for many patterns; an **inverted index** (`PK=SK, SK=PK`) serves reverse/many-to-many.
- **LSI** (max 5/table): same `PK`, alternate `SK`, shares table throughput, strong reads — but **only creatable at table creation**, triggers the 10 GB cap.
- **Sparse index**: only items with the indexed attr appear — write selectively for queue/status filters.
- Project only what queries read; the **≤100 combined-attr cap counts only user-specified `INCLUDE` `NonKeyAttributes` across all indexes** — `KEYS_ONLY`/`ALL` don't count.

### Denormalize & many-to-many
Duplicate read-mostly fields onto children to save a fetch; sync via transaction or Streams fan-out. Model many-to-many with an **adjacency list** (edges `PK=nodeA, SK=nodeB`) + an inverted GSI for the reverse edge.

### Multi-item writes
`TransactWriteItems`/`TransactGetItems`: **100 items / 4 MB** max, all-or-nothing, **serializable**, **2× capacity** (prepare+commit, billed even on cancel); client token = idempotency (10-min). `BatchWriteItem` (25 put/deletes), `BatchGetItem` (100 gets) are non-atomic, may return `UnprocessedItems` — retry with backoff.

### Partition key = the throughput lever
Pick a **high-cardinality** `PK` for even load; a physical partition caps at ~3000 RCU / 1000 WCU. Adaptive capacity re-isolates one hot key, not a low-cardinality key (`STATUS`, date). Write-shard a hot key (suffix `#<0..N>`), scatter-gather on read. Avoid monotonic keys.

### Retrieval discipline
`Query` on a key, never `Scan`. Each page returns ≤1 MB — paginate with `LastEvaluatedKey`→`ExclusiveStartKey` (no offset/skip). `ProjectionExpression` trims payload; `FilterExpression` runs AFTER the read, still billing scanned items. TTL (epoch-seconds attr) deletes expired items best-effort within a few days, emitting Stream service-deletions. See lore/deep/dynamodb.md#performance for hot keys.

### Sources
docs.aws.amazon.com/amazondynamodb/latest/developerguide — bp-general-nosql-design · bp-modeling-nosql · bp-adjacency-graphs · ServiceQuotas (400 KB item, 20 GSI / 5 LSI, 10 GB collection, ≤100 INCLUDE attrs) · transaction-apis (100 items / 4 MB) · howitworks-ttl (delete within days)

## Partition keys & capacity <a id="partition-keys-and-capacity"></a>

Managed serverless key-value/document store; no engine version. Throughput mode is per-table: **on-demand** (pay-per-request, default & recommended) or **provisioned** (RCU/WCU you set, optionally auto-scaled) — both with free adaptive capacity. DynamoDB shards by the partition key's hash across partitions you never manage.

### The capacity-unit math
- **1 RCU** = 1 strongly-consistent read/s of an item ≤4 KB, OR 2 eventually-consistent reads/s. **1 WCU** = 1 write/s ≤1 KB. Size rounds UP per 4 KB / 1 KB block: a 5 KB strong read = 2 RCU, a 1.5 KB write = 2 WCU.
- **Transactional** reads/writes cost **2×** (prepare+commit) — billed even when a `ConditionCheck` cancels it, and again on SDK retries.
- Writes and `GetItem` bill the FULL item; `Query`/`Scan` bill bytes read BEFORE `FilterExpression`, so a filter still charges every item examined. `ProjectionExpression` trims payload, NOT RCU — the whole item is read and billed.

### Per-partition ceiling — the real wall
Every physical partition maxes at **~3000 RCU/s and 1000 WCU/s**, regardless of mode or capacity bought. A single hot partition-key value throttles at that ceiling while others sit idle. Item size multiplies it: a 20 KB item = 5 RCU/read, so ≤600 consistent reads/s on that key before the wall.

### Adaptive & burst capacity
- **Adaptive capacity** (automatic, free, on-demand + provisioned): instantly lifts a hot partition toward the 3000/1000 ceiling by borrowing unused table capacity, and rebalances so frequently-accessed items land on their own partition — a single scorching key can claim a whole one. It will NOT split an item collection across partitions when an **LSI** exists.
- **Burst capacity**: up to **300 s (5 min)** of unused throughput is banked for spikes (also spent silently on maintenance). Real, but don't design to depend on it.

### Partition key = the throughput lever
- Pick a **high-cardinality** key (userId, deviceId, a composite) so requests fan out evenly. Low-cardinality keys (`status`, a bare date, a dominant tenant) create hot partitions no hardware fixes.
- **Write-shard** an unavoidably hot key with a suffix — `EVENT#<date>#<0..N>` — then scatter-gather the N shards on read (calculated suffix for deterministic reads, random for pure spread).
- Avoid **monotonic** keys (sequential ids, raw timestamps): they hammer one partition then move on, stranding the rest.

### Scaling & mode choice
- **On-demand** scales instantly to **2× your previous peak**; a new table sustains ~4000 WPS / 12000 RPS at once. Exceeding 2× peak within 30 min can throttle — **pre-warm** via *warm throughput* before a known surge (launch, migration, load test).
- Default guardrail: **40,000 read + 40,000 write units per table** (raise via quota). Set a per-table **maximum throughput** to bound runaway cost.
- **Provisioned** suits steady, forecastable load; pair with **auto scaling** (target-utilization %). You pay for provisioned, not consumed.
- Switching: provisioned→on-demand **up to 4× per 24 h rolling window**; on-demand→provisioned anytime.

### Measure it
Watch CloudWatch `Consumed`/`ProvisionedThroughput`, `Read`/`WriteThrottleEvents`. Throttling with table headroom left = a **hot partition**, not a shortage — fix the key, not the RCUs. TTL deletes are **free** (no WCU). A GSI has its OWN capacity: an under-provisioned GSI throttles WRITES on the base table.

### Sources
- docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadWriteCapacityMode.html
- .../bp-partition-key-design.html + burst-adaptive-capacity.html (3000 RCU / 1000 WCU)
- .../on-demand-capacity-mode.html (2× peak, 4000/12000 initial, 40k quota)
- .../transaction-apis.html (2× capacity, billed on cancel)

## Secondary indexes (GSI & LSI) <a id="secondary-indexes-gsi-lsi"></a>

Managed serverless; no engine version. An index is a maintained projection of the base table under an *alternate* key — `Query`/`Scan` it (never `GetItem`/`BatchGetItem`), never write to it directly. Indexes back access patterns the PK can't answer; without one you'd `Scan`. Defaults: up to **20 GSIs** (soft quota, raisable) and **5 LSIs** per table.

### GSI vs LSI — pick GSI unless you need strong reads
| | GSI | LSI |
|---|---|---|
| Key | any PK (+ optional SK) | **same PK as base**, different SK |
| Reads | **eventual only** | eventual OR strong (`ConsistentRead`) |
| Capacity | **own RCU/WCU** (provisioned) or inherits on-demand | draws from **base table** capacity |
| Lifecycle | add/drop anytime, online | **create-time only**, cannot add/drop later |
| Size cap | none | item collection (table+all LSIs, one PK) ≤ **10 GB** |
| Non-projected attrs | not fetchable | auto-fetched from base (extra RCU) |

Reach for GSI first; pick an LSI only when you truly need strongly-consistent reads on an alternate sort key within one partition — accepting the permanent 10 GB-per-PK ceiling and create-time lock-in.

### Projection — the cost/latency dial
`KEYS_ONLY` (index+table keys), `INCLUDE` (+ named attrs), or `ALL`. Project exactly what the query returns.
- GSI queries **cannot** fetch non-projected attrs — a missing attr forces a second round-trip to the base table in your code. LSI auto-fetches (transparent, but costs a full base-item read each).
- `ALL` removes fetches but ~doubles storage + write cost. `KEYS_ONLY` is cheapest for write-heavy, rarely-queried tables.
- Index entries round to 1 KB for WCU: while <1 KB, adding attributes is free — don't over-trim tiny indexes.

### Sparse indexes — a feature, not a side effect
An item is projected **only if it has both index key attributes defined**. Set the GSI key attr only on rows you want indexed (e.g. `gsi1pk` only on `status=OPEN` orders) → the index holds just those, and a `Query` replaces a `Scan`+filter. Deleting the attr removes the item from the index (1 WCU).

### Index (GSI) overloading — many patterns, few indexes
Give generic key attrs (`GSI1PK`/`GSI1SK`) different meanings per item type in one shared GSI, so 2-3 indexes serve many patterns — the single-table idiom (see lore/deep/dynamodb.md#data-modeling-single-table). Multi-attribute keys (PK/SK from up to 4 attrs each) replace hand-concatenated `TYPE#id#...` synthetic keys; query SK attrs left-to-right, inequality last.

### Write-amplification & throttling gotchas
- Every base write fans out to affected indexes. Changing an **indexed key** = 2 index writes (delete old + put new); a projected non-key attr = 1; an unindexed attr = 0. More indexes = higher write cost.
- A GSI carries **its own** capacity: an under-provisioned GSI **throttles writes on the BASE table**. Keep GSI WCU ≥ base WCU; on-demand GSIs inherit the mode and avoid this.
- A low-cardinality GSI key makes a hot GSI partition even when the table is well-distributed — same 3000 RCU/1000 WCU wall; write-shard it (see lore/deep/dynamodb.md#partition-keys-and-capacity).
- GSIs are **eventually consistent** by design (async, sub-second normally): never read-after-write from a GSI expecting your just-written value.
- Backfilling a new GSI is online but spends GSI write capacity; watch `OnlineIndexPercentageProgress`, and guard key-type mismatches (`ValidationException`).

See lore/deep/dynamodb.md#performance for the full fast-path/anti-pattern playbook.

### Sources
- docs.aws.amazon.com/amazondynamodb/latest/developerguide/SecondaryIndexes.html (GSI vs LSI, 20/5 quotas)
- .../GSI.html (projections, eventual reads, write-cost cases, multi-attribute keys)
- .../LSI.html (10 GB item-collection cap, strong reads, fetches)
- .../bp-indexes-general.html (keep indexes minimal, projection tradeoffs)

## Streams & transactions <a id="streams-and-transactions"></a>

Serverless; no version to pin. **Streams** = CDC; **transactions** (`TransactWriteItems`/`TransactGetItems`) = ACID within one Region+account. Both additive.

### DynamoDB Streams — CDC
- Ordered item-level change log, retained **24 h**, trimmed after. `StreamViewType`: `KEYS_ONLY`/`NEW_IMAGE`/`OLD_IMAGE`/`NEW_AND_OLD_IMAGES` — pick smallest; can't edit (recreate).
- Guarantees: each record **exactly once**; per-item records in **modification order**; NO global order cross-item/shard. No-op `PutItem`/`UpdateItem` → **no** record. Transactional writes propagate **gradually** (interleaved) — don't assume txn atomicity/order.
- **Shards** auto-split under load; parent→child lineage — drain parents first. **≤2 readers/shard** or throttle (≤2 Lambdas/stream).
- Consume via **Lambda event-source mapping** (~4×/s, sync, batched), **Kinesis Adapter/KCL** (handles shards), or low-level `DescribeStream`/`GetShardIterator`/`GetRecords`. Separate endpoint + SDK client.
- On Lambda error, **retry the batch until success or expiry** — a poison pill blocks its shard. Set `BisectBatchOnFunctionError`, `MaximumRetryAttempts`, `MaximumRecordAgeInSeconds`, an **on-failure destination** (SQS/SNS), and **event filtering**.
- Uses: materialized views/hand-built GSIs, fan-out, aggregation, audit, S3 archive. Need >24 h retention, replay, or many consumers → **Kinesis Data Streams for DynamoDB** (may be out-of-order/duplicated — dedupe on keys).

### Transactions — ACID per Region
- `TransactWriteItems`: ≤**100 distinct items**, ≤**4 MB**, multi-table in one account+Region, all-or-nothing. Actions `Put`/`Update`/`Delete`/`ConditionCheck`. Can't **hit the same item twice**; **no indexes**.
- `TransactGetItems`: ≤**100 items / 4 MB**, serializable snapshot — prefer over parallel `GetItem`.
- Isolation: **SERIALIZABLE** vs singleton `PutItem`/`UpdateItem`/`DeleteItem`/`GetItem` and other transactions; **READ-COMMITTED** for `Query`/`Scan`/`BatchGetItem`, and NOT serializable vs `BatchWriteItem` as a unit. Post-commit *eventually consistent* reads lag — use `ConsistentRead=true`.
- **Idempotency:** `ClientRequestToken` makes `TransactWriteItems` retry-safe (same token = no-op), valid **10 min**; changed params w/ same token → `IdempotentParameterMismatch`. SDKs set it automatically.
- **Cost:** each item = **2× WCU/RCU** (prepare+commit), billed **even when cancelled**, on retries.
- Errors: contention → `TransactionCanceledException` + `CancellationReasons` aligned to actions (SDKs do NOT auto-retry); singleton write vs in-flight txn → `TransactionConflictException` (`TransactionConflict` metric).

### DON'T
- DON'T transact bulk load — use `BatchWriteItem` (25 independent puts, cheaper); split large txns.
- DON'T expect cross-Region atomicity: **global tables** give ACID only in the write Region; replicas may show partial state mid-replication.
- DON'T mix reads+writes in one **PartiQL `ExecuteTransaction`** — read-only OR write-only (`EXISTS(...)` the only condition), ≤100 statements.
- DON'T subscribe >2 consumers, ignore shard lineage, or run heavy logic in a stream Lambda — offload to Step Functions.

### Sources
docs.aws.amazon.com/amazondynamodb/latest/developerguide — transaction-apis · Streams + Streams.Lambda · kds (Kinesis Data Streams for DynamoDB — out-of-order/duplicate, longer retention, more consumers) · ql-reference.multiplestatements.transactions

## Performance <a id="performance"></a>

Managed serverless key-value/document store; no engine version. Capacity: on-demand or provisioned (RCU/WCU + auto scaling), both with adaptive capacity. Performance is won at MODEL time (keys + access patterns), not by buying capacity — every physical partition still caps at **~3000 RCU / 1000 WCU**.

### Levers, highest-impact first
1. **Partition-key distribution** — the #1 lever. High-cardinality key so load fans out; write-shard an unavoidably hot key and scatter-gather on read. A hot key throttles at the per-partition wall while the table sits idle — capacity can't fix it. See lore/deep/dynamodb.md#partition-keys-and-capacity.
2. **`Query`/`GetItem`, never `Scan`** — resolve every access pattern to one key lookup on the table or an index; single-table + composite SKs return a whole aggregate per round-trip. See lore/deep/dynamodb.md#data-modeling-single-table.
3. **Right index + tight projection** — back each pattern with a GSI; `KEYS_ONLY`/`INCLUDE` avoids base-table fetches and cuts payload. Sparse/overloaded GSIs replace `Scan`+filter. See lore/deep/dynamodb.md#secondary-indexes-gsi-lsi and lore/deep/databases.md#indexing-and-query-plans.
4. **Batch, don't chatter** — `BatchGetItem` (100)/`BatchWriteItem` (25) and parallel requests beat per-item calls; retry `UnprocessedItems`. Big offline reads: parallel `Scan` (`TotalSegments`, ~1 seg/2 GB, table ≥20 GB) on a non-critical table.
5. **DAX for read-heavy hot keys** — write-through cache, ms → microsecond *eventual* reads, absorbs a hot key. NOT for strong reads (bypass cache) or write-heavy loads. Keep attribute *names* bounded — unbounded top-level names (timestamps/UUIDs as keys) exhaust DAX memory.
6. **Reuse connections** — enable SDK HTTP keep-alive to skip per-request TLS handshakes. See lore/deep/databases.md#connection-pooling.
7. **Pre-warm + cap** — on-demand scales to 2× prior peak; request warm throughput before a known surge; set max throughput to cap cost.

### Top anti-patterns
- `Scan` on hot paths, or `FilterExpression` to trim a large `Scan` — you're billed for every item *examined* before the filter (`ScanCount ≫ Count` = wasted RCU). `ProjectionExpression` trims payload, not RCU.
- Low-cardinality / monotonic partition keys → hot partition.
- Under-provisioned GSI → throttles WRITES on the base table.
- Strong reads by default (2× cost), or read-after-write from a GSI (always eventual).
- `skip`/offset paging — cursor via `LastEvaluatedKey`→`ExclusiveStartKey`.

### Measure it (CloudWatch, 1-min)
- `ConsumedRead/WriteCapacityUnits` (`Sum`/60 = per-sec) vs provisioned; split GSIs by `GlobalSecondaryIndexName` dim.
- `ThrottledRequests` + `Read`/`WriteThrottleEvents`. **Throttle while table headroom remains = hot partition** — `Read`/`WriteKeyRangeThroughputThrottleEvents` isolate partition-limit throttles from provisioned ones.
- `SuccessfulRequestLatency` (server-side p99, `TableName`+`Operation`); `SystemErrors` needs both dims or the alarm never fires; `TransactionConflict` for contended items.
- Per-request `ReturnConsumedCapacity=TOTAL|INDEXES` to attribute cost.
- **Contributor Insights**: *Most Accessed Items* (`ConsumedThroughputUnits`=3×WCU+RCU) surfaces hot keys; *Most Throttled Items* (`ThrottleCount`) — throttled-keys mode is cheap to leave on. Retry throttles with exponential backoff + jitter (see lore/deep/databases.md#resilience-and-observability).

### Sources
- docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-query-scan.html (Scan cost, Limit page size, parallel scan TotalSegments)
- .../DAX.html (microsecond eventual reads, not for strong/write-heavy, attribute-name memory limit)
- .../metrics-dimensions.html + contributorinsights_HowItWorks.html (throttle metrics, Most Accessed/Throttled graphs, ConsumedThroughputUnits)
