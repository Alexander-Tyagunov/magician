# Amazon DynamoDB — Single-table data modeling

Managed serverless key-value/document store; no version; capacity on-demand or provisioned (RCU/WCU). Single-table design packs many entity types into ONE table so a `Query` returns a full aggregate — best for known, correlated patterns, not a mandate: split independent-access entities into separate tables.

## Model the queries first, then the keys
List every access pattern BEFORE choosing keys; each must resolve to one `Query`/`GetItem` on table or GSI — never `Scan`. No joins — pre-join by co-locating related items.

## Generic keys + entity overloading
Name keys generically (`PK`/`SK`, `GSI1PK`/`GSI1SK`), encode type in value: `PK=USER#123`, `SK=PROFILE#123` or `ORDER#<date>#456`. `Query PK=USER#123 AND begins_with(SK,'ORDER#')` returns that user's orders, sorted. Keep a `type` attr per item to filter.

## Composite sort keys & item collections
A composite `SK` (`US#CA#LA`) models hierarchy + range/prefix reads via `begins_with`/`between`; items sharing a `PK` form an *item collection*, sorted by `SK`. Limits: **400 KB/item**; an LSI caps each collection at **10 GB** — GSIs don't.

## GSIs vs LSIs, inverted & sparse
- **GSI** (default 20/table): own PK/SK + throughput, **eventually consistent only** (no `ConsistentRead`), added/dropped anytime. Overload for many patterns; an **inverted index** (`PK=SK, SK=PK`) serves reverse/many-to-many.
- **LSI** (max 5/table): same `PK`, alternate `SK`, shares table throughput, strong reads — but **only creatable at table creation**, triggers the 10 GB cap.
- **Sparse index**: only items with the indexed attr appear — write selectively for queue/status filters.
- Project only what queries read; the **≤100 combined-attr cap counts only user-specified `INCLUDE` `NonKeyAttributes` across all indexes** — `KEYS_ONLY`/`ALL` don't count.

## Denormalize & many-to-many
Duplicate read-mostly fields onto children to save a fetch; sync via transaction or Streams fan-out. Model many-to-many with an **adjacency list** (edges `PK=nodeA, SK=nodeB`) + an inverted GSI for the reverse edge.

## Multi-item writes
`TransactWriteItems`/`TransactGetItems`: **100 items / 4 MB** max, all-or-nothing, **serializable**, **2× capacity** (prepare+commit, billed even on cancel); client token = idempotency (10-min). `BatchWriteItem` (25 put/deletes), `BatchGetItem` (100 gets) are non-atomic, may return `UnprocessedItems` — retry with backoff.

## Partition key = the throughput lever
Pick a **high-cardinality** `PK` for even load; a physical partition caps at ~3000 RCU / 1000 WCU. Adaptive capacity re-isolates one hot key, not a low-cardinality key (`STATUS`, date). Write-shard a hot key (suffix `#<0..N>`), scatter-gather on read. Avoid monotonic keys.

## Retrieval discipline
`Query` on a key, never `Scan`. Each page returns ≤1 MB — paginate with `LastEvaluatedKey`→`ExclusiveStartKey` (no offset/skip). `ProjectionExpression` trims payload; `FilterExpression` runs AFTER the read, still billing scanned items. TTL (epoch-seconds attr) deletes expired items best-effort within a few days, emitting Stream service-deletions. See performance.md for hot keys.

## Sources
docs.aws.amazon.com/amazondynamodb/latest/developerguide — bp-general-nosql-design · bp-modeling-nosql · bp-adjacency-graphs · ServiceQuotas (400 KB item, 20 GSI / 5 LSI, 10 GB collection, ≤100 INCLUDE attrs) · transaction-apis (100 items / 4 MB) · howitworks-ttl (delete within days)
