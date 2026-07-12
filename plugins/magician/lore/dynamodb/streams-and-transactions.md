# Amazon DynamoDB — Streams & transactions

Serverless; no version to pin. **Streams** = CDC; **transactions** (`TransactWriteItems`/`TransactGetItems`) = ACID within one Region+account. Both additive.

## DynamoDB Streams — CDC
- Ordered item-level change log, retained **24 h**, trimmed after. `StreamViewType`: `KEYS_ONLY`/`NEW_IMAGE`/`OLD_IMAGE`/`NEW_AND_OLD_IMAGES` — pick smallest; can't edit (recreate).
- Guarantees: each record **exactly once**; per-item records in **modification order**; NO global order cross-item/shard. No-op `PutItem`/`UpdateItem` → **no** record. Transactional writes propagate **gradually** (interleaved) — don't assume txn atomicity/order.
- **Shards** auto-split under load; parent→child lineage — drain parents first. **≤2 readers/shard** or throttle (≤2 Lambdas/stream).
- Consume via **Lambda event-source mapping** (~4×/s, sync, batched), **Kinesis Adapter/KCL** (handles shards), or low-level `DescribeStream`/`GetShardIterator`/`GetRecords`. Separate endpoint + SDK client.
- On Lambda error, **retry the batch until success or expiry** — a poison pill blocks its shard. Set `BisectBatchOnFunctionError`, `MaximumRetryAttempts`, `MaximumRecordAgeInSeconds`, an **on-failure destination** (SQS/SNS), and **event filtering**.
- Uses: materialized views/hand-built GSIs, fan-out, aggregation, audit, S3 archive. Need >24 h retention, replay, or many consumers → **Kinesis Data Streams for DynamoDB** (may be out-of-order/duplicated — dedupe on keys).

## Transactions — ACID per Region
- `TransactWriteItems`: ≤**100 distinct items**, ≤**4 MB**, multi-table in one account+Region, all-or-nothing. Actions `Put`/`Update`/`Delete`/`ConditionCheck`. Can't **hit the same item twice**; **no indexes**.
- `TransactGetItems`: ≤**100 items / 4 MB**, serializable snapshot — prefer over parallel `GetItem`.
- Isolation: **SERIALIZABLE** vs singleton `PutItem`/`UpdateItem`/`DeleteItem`/`GetItem` and other transactions; **READ-COMMITTED** for `Query`/`Scan`/`BatchGetItem`, and NOT serializable vs `BatchWriteItem` as a unit. Post-commit *eventually consistent* reads lag — use `ConsistentRead=true`.
- **Idempotency:** `ClientRequestToken` makes `TransactWriteItems` retry-safe (same token = no-op), valid **10 min**; changed params w/ same token → `IdempotentParameterMismatch`. SDKs set it automatically.
- **Cost:** each item = **2× WCU/RCU** (prepare+commit), billed **even when cancelled**, on retries.
- Errors: contention → `TransactionCanceledException` + `CancellationReasons` aligned to actions (SDKs do NOT auto-retry); singleton write vs in-flight txn → `TransactionConflictException` (`TransactionConflict` metric).

## DON'T
- DON'T transact bulk load — use `BatchWriteItem` (25 independent puts, cheaper); split large txns.
- DON'T expect cross-Region atomicity: **global tables** give ACID only in the write Region; replicas may show partial state mid-replication.
- DON'T mix reads+writes in one **PartiQL `ExecuteTransaction`** — read-only OR write-only (`EXISTS(...)` the only condition), ≤100 statements.
- DON'T subscribe >2 consumers, ignore shard lineage, or run heavy logic in a stream Lambda — offload to Step Functions.

## Sources
docs.aws.amazon.com/amazondynamodb/latest/developerguide — transaction-apis · Streams + Streams.Lambda · kds (Kinesis Data Streams for DynamoDB — out-of-order/duplicate, longer retention, more consumers) · ql-reference.multiplestatements.transactions
