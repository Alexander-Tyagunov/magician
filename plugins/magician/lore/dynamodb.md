# Amazon DynamoDB — core digest
Version: serverless key-value/doc store; no version. On-demand (pay-per-request, default) or provisioned (RCU/WCU, auto-scaling, adaptive). 1 RCU=1 strong read/s ≤4KB (eventual 2/RCU); 1 WCU=1 write/s ≤1KB; txn=2×. Item ≤400KB.

DO model access patterns first: high-cardinality partition key, sort key for 1:N + range; single-table; denormalize/embed (no joins).
DO Query, never Scan, on PK/SK or index; page via LastEvaluatedKey; project needed attrs.
DO batch (BatchWriteItem 25, BatchGetItem, PartiQL); not per-item.
DO add ≤20 GSIs (own keys, eventual reads); ≤5 LSIs (share PK, create-time only).
DO enable TTL (bg delete, no WCU) and Streams (24h, NEW_AND_OLD_IMAGES) for CDC.
DO group atomic writes via TransactWriteItems (≤100 items/4MB, ACID per-Region, idempotent token).

DON'T Scan hot paths or skip/offset — cursor-paginate.
DON'T pick low-cardinality/monotonic partition keys — hot partitions throttle.
DON'T assume strong reads: eventual unless ConsistentRead=true (2× cost, single-Region); GSI always eventual.

Deep dive (non-trivial) — read lore/dynamodb/{data-modeling-single-table,partition-keys-and-capacity,secondary-indexes-gsi-lsi,streams-and-transactions,performance}.md

## Sources
docs.aws.amazon.com/amazondynamodb/latest/developerguide — capacity modes · NoSQL design · transaction-apis · Streams
