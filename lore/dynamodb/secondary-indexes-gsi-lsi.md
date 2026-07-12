# Amazon DynamoDB — Secondary indexes (GSI & LSI)

Managed serverless; no engine version. An index is a maintained projection of the base table under an *alternate* key — `Query`/`Scan` it (never `GetItem`/`BatchGetItem`), never write to it directly. Indexes back access patterns the PK can't answer; without one you'd `Scan`. Defaults: up to **20 GSIs** (soft quota, raisable) and **5 LSIs** per table.

## GSI vs LSI — pick GSI unless you need strong reads
| | GSI | LSI |
|---|---|---|
| Key | any PK (+ optional SK) | **same PK as base**, different SK |
| Reads | **eventual only** | eventual OR strong (`ConsistentRead`) |
| Capacity | **own RCU/WCU** (provisioned) or inherits on-demand | draws from **base table** capacity |
| Lifecycle | add/drop anytime, online | **create-time only**, cannot add/drop later |
| Size cap | none | item collection (table+all LSIs, one PK) ≤ **10 GB** |
| Non-projected attrs | not fetchable | auto-fetched from base (extra RCU) |

Reach for GSI first; pick an LSI only when you truly need strongly-consistent reads on an alternate sort key within one partition — accepting the permanent 10 GB-per-PK ceiling and create-time lock-in.

## Projection — the cost/latency dial
`KEYS_ONLY` (index+table keys), `INCLUDE` (+ named attrs), or `ALL`. Project exactly what the query returns.
- GSI queries **cannot** fetch non-projected attrs — a missing attr forces a second round-trip to the base table in your code. LSI auto-fetches (transparent, but costs a full base-item read each).
- `ALL` removes fetches but ~doubles storage + write cost. `KEYS_ONLY` is cheapest for write-heavy, rarely-queried tables.
- Index entries round to 1 KB for WCU: while <1 KB, adding attributes is free — don't over-trim tiny indexes.

## Sparse indexes — a feature, not a side effect
An item is projected **only if it has both index key attributes defined**. Set the GSI key attr only on rows you want indexed (e.g. `gsi1pk` only on `status=OPEN` orders) → the index holds just those, and a `Query` replaces a `Scan`+filter. Deleting the attr removes the item from the index (1 WCU).

## Index (GSI) overloading — many patterns, few indexes
Give generic key attrs (`GSI1PK`/`GSI1SK`) different meanings per item type in one shared GSI, so 2-3 indexes serve many patterns — the single-table idiom (see data-modeling-single-table.md). Multi-attribute keys (PK/SK from up to 4 attrs each) replace hand-concatenated `TYPE#id#...` synthetic keys; query SK attrs left-to-right, inequality last.

## Write-amplification & throttling gotchas
- Every base write fans out to affected indexes. Changing an **indexed key** = 2 index writes (delete old + put new); a projected non-key attr = 1; an unindexed attr = 0. More indexes = higher write cost.
- A GSI carries **its own** capacity: an under-provisioned GSI **throttles writes on the BASE table**. Keep GSI WCU ≥ base WCU; on-demand GSIs inherit the mode and avoid this.
- A low-cardinality GSI key makes a hot GSI partition even when the table is well-distributed — same 3000 RCU/1000 WCU wall; write-shard it (see partition-keys-and-capacity.md).
- GSIs are **eventually consistent** by design (async, sub-second normally): never read-after-write from a GSI expecting your just-written value.
- Backfilling a new GSI is online but spends GSI write capacity; watch `OnlineIndexPercentageProgress`, and guard key-type mismatches (`ValidationException`).

See performance.md for the full fast-path/anti-pattern playbook.

## Sources
- docs.aws.amazon.com/amazondynamodb/latest/developerguide/SecondaryIndexes.html (GSI vs LSI, 20/5 quotas)
- .../GSI.html (projections, eventual reads, write-cost cases, multi-attribute keys)
- .../LSI.html (10 GB item-collection cap, strong reads, fetches)
- .../bp-indexes-general.html (keep indexes minimal, projection tradeoffs)
