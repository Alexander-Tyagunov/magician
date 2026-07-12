# Amazon DynamoDB — Partition keys & capacity

Managed serverless key-value/document store; no engine version. Throughput mode is per-table: **on-demand** (pay-per-request, default & recommended) or **provisioned** (RCU/WCU you set, optionally auto-scaled) — both with free adaptive capacity. DynamoDB shards by the partition key's hash across partitions you never manage.

## The capacity-unit math
- **1 RCU** = 1 strongly-consistent read/s of an item ≤4 KB, OR 2 eventually-consistent reads/s. **1 WCU** = 1 write/s ≤1 KB. Size rounds UP per 4 KB / 1 KB block: a 5 KB strong read = 2 RCU, a 1.5 KB write = 2 WCU.
- **Transactional** reads/writes cost **2×** (prepare+commit) — billed even when a `ConditionCheck` cancels it, and again on SDK retries.
- Writes and `GetItem` bill the FULL item; `Query`/`Scan` bill bytes read BEFORE `FilterExpression`, so a filter still charges every item examined. `ProjectionExpression` trims payload, NOT RCU — the whole item is read and billed.

## Per-partition ceiling — the real wall
Every physical partition maxes at **~3000 RCU/s and 1000 WCU/s**, regardless of mode or capacity bought. A single hot partition-key value throttles at that ceiling while others sit idle. Item size multiplies it: a 20 KB item = 5 RCU/read, so ≤600 consistent reads/s on that key before the wall.

## Adaptive & burst capacity
- **Adaptive capacity** (automatic, free, on-demand + provisioned): instantly lifts a hot partition toward the 3000/1000 ceiling by borrowing unused table capacity, and rebalances so frequently-accessed items land on their own partition — a single scorching key can claim a whole one. It will NOT split an item collection across partitions when an **LSI** exists.
- **Burst capacity**: up to **300 s (5 min)** of unused throughput is banked for spikes (also spent silently on maintenance). Real, but don't design to depend on it.

## Partition key = the throughput lever
- Pick a **high-cardinality** key (userId, deviceId, a composite) so requests fan out evenly. Low-cardinality keys (`status`, a bare date, a dominant tenant) create hot partitions no hardware fixes.
- **Write-shard** an unavoidably hot key with a suffix — `EVENT#<date>#<0..N>` — then scatter-gather the N shards on read (calculated suffix for deterministic reads, random for pure spread).
- Avoid **monotonic** keys (sequential ids, raw timestamps): they hammer one partition then move on, stranding the rest.

## Scaling & mode choice
- **On-demand** scales instantly to **2× your previous peak**; a new table sustains ~4000 WPS / 12000 RPS at once. Exceeding 2× peak within 30 min can throttle — **pre-warm** via *warm throughput* before a known surge (launch, migration, load test).
- Default guardrail: **40,000 read + 40,000 write units per table** (raise via quota). Set a per-table **maximum throughput** to bound runaway cost.
- **Provisioned** suits steady, forecastable load; pair with **auto scaling** (target-utilization %). You pay for provisioned, not consumed.
- Switching: provisioned→on-demand **up to 4× per 24 h rolling window**; on-demand→provisioned anytime.

## Measure it
Watch CloudWatch `Consumed`/`ProvisionedThroughput`, `Read`/`WriteThrottleEvents`. Throttling with table headroom left = a **hot partition**, not a shortage — fix the key, not the RCUs. TTL deletes are **free** (no WCU). A GSI has its OWN capacity: an under-provisioned GSI throttles WRITES on the base table.

## Sources
- docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadWriteCapacityMode.html
- .../bp-partition-key-design.html + burst-adaptive-capacity.html (3000 RCU / 1000 WCU)
- .../on-demand-capacity-mode.html (2× peak, 4000/12000 initial, 40k quota)
- .../transaction-apis.html (2× capacity, billed on cancel)
