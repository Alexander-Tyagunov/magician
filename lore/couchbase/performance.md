# Couchbase — Performance

Playbook for Server **8.0** (Magma default: 128 vBuckets, 100 MiB min quota, 1% mem-to-data; Couchstore 10%) and **7.x**; Capella runs the same engine. No release rescues a `PrimaryScan`, a cold working set, or a fat doc. **Measure first.**

## Prioritized levers (highest impact first)

1. **Reach data by key, not by query.** A KV `get`/subdoc op or SQL++ `USE KEYS` hits the Data service directly (sub-ms), skipping the Query→Index→Fetch path. Never scan for a point read. See `lore/couchbase/data-model-and-collections.md`.
2. **Keep the working set resident.** Data serves from RAM; a low resident ratio turns reads into disk fetches. Magma (1% mem:data) is disk-centric for large sets; Couchstore (10%) suits in-RAM sets. Scale before the miss ratio climbs.
3. **Back every predicate with a GSI; aim for covered scans.** One composite index per query shape, leading keys = the equality predicates. Covered = `IndexScan3` carries a `covers` array and **no `Fetch`**; two GSIs can't cover a query, so build one composite. See `lore/couchbase/sqlpp-query-and-indexes.md`, `lore/databases/indexing-and-query-plans.md`.
4. **Model for the query.** Embed data read together; reference to bound doc size (20 MiB value ceiling; stay well under). No cheap server-side JOIN — an ANSI JOIN needs a GSI on the `ON` keys or it degrades to a nested-loop scan.
5. **Tune `scan_consistency` per query.** `not_bounded` (default) is fastest but may read a stale index; `request_plus` gives read-your-writes but blocks until the index catches up. See `lore/couchbase/durability-and-consistency.md`.
6. **Right-size durability.** Default `none` (fastest); `majority` → `majorityAndPersistActive` → `persistToMajority` each add latency; up to 3 replicas but durable writes need ≤2 (impossible at 3); Ephemeral allows only `majority`.
7. **Scale services independently (MDS).** Put Query and Index on separate nodes so execution doesn't fight index maintenance; add index replicas for HA and hash-partition a hot GSI.
8. **Batch, don't chatter.** Bulk KV ops and subdoc mutations (one field, not the whole doc) beat per-doc round trips.

## How to measure

- **`EXPLAIN`** — want `IndexScan3` (ideally with `covers`); avoid `PrimaryScan`; a `Filter` after the scan = a predicate not pushed down.
- **Profile** — `profile=timings` gives `phaseTimes`/`phaseCounts` per operator to find the slow stage.
- **Query catalogs** — `system:completed_requests` (tune `completed-threshold`/`completed-limit`) is the slow-query log; `system:active_requests` for in-flight.
- **Index Advisor** — `ADVISE <query>` (EE) suggests missing indexes.
- **Cluster stats** — resident ratio + KV cache-miss ratio, index mutation-queue/drain rate + fragmentation, disk write queue.
- Pooling + spans: `lore/databases/{connection-pooling,resilience-and-observability}.md`.

## Top anti-patterns

- **`PrimaryScan` / unindexed predicate** — full keyspace scan; never keep the primary index in prod.
- **`OFFSET` pagination** on large sets — scans and discards; keyset-page on an indexed key.
- **`request_plus` everywhere** — serializes queries behind index lag; reserve it.
- **Fat docs / unbounded arrays** near the 20 MiB cap — churn and slow fetches; split or cap.
- **Over-indexing** — every mutation maintains all matching GSIs; drop unused ones.
- **SQL++ for known keys** — use KV/`USE KEYS`.

## Sources
- https://docs.couchbase.com/server/current/learn/buckets-memory-and-storage/storage-engines.html
- https://docs.couchbase.com/server/current/n1ql/n1ql-language-reference/covering-indexes.html
- https://docs.couchbase.com/server/current/learn/data/durability.html
- https://docs.couchbase.com/server/current/learn/services-and-indexes/services/services.html
