# Couchbase — deep dive

> On-demand companion to `lore/couchbase.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Data model & collections](#data-model-and-collections) · [SQL++ query & indexes](#sqlpp-query-and-indexes) · [Durability & Consistency](#durability-and-consistency) · [Performance](#performance)

## Data model & collections <a id="data-model-and-collections"></a>

Server 8.0 (scopes/collections since 7.0; `_system` scope since 7.6). JSON store: each doc is a key + JSON value, distributed by CRC32-hashing the key into a vBucket (8.0: Magma engine, 128 vBuckets; Couchstore had 1024). Model QUERY-FIRST — SQL++ can JOIN, but joins fan out and cost round-trips, so access patterns drive embed-vs-reference.

### Keyspace hierarchy — the organization lever
`Bucket → Scope → Collection → Document`. A collection groups docs of one type; a scope groups collections (tenant, domain, env). Namespaces are per-level: same collection name in different scopes, same key in different collections.
- Every bucket has a `_default` scope + collection (pre-7.0 data lands here). Default scope can't be dropped; default collection drops but can't be recreated.
- The 7.6 `_system` scope (e.g. `_query`, `_mobile`) is Couchbase-owned; don't drop or read it.
- Limits: **1000 scopes + 1000 collections per cluster**. Names 1–251 chars of `A-Za-z0-9_-%`, case-sensitive, can't start with `_`/`%`, no rename.
- Collections segregate types (cheaper than a `type` field + filter); scopes for tenant isolation + RBAC blast-radius.

### Model query-first: embed vs reference
- EMBED data read/written together into one document so a KV `get`/SQL++ row returns the whole aggregate. Single-doc mutation is atomic; no multi-doc ACID outside explicit transactions.
- REFERENCE (store the key, fetch/JOIN separately) when the child is large, unbounded, high-churn, or accessed alone. Unbounded embedded arrays are the trap: they march toward the **20 MiB** doc ceiling, rewriting the whole doc on every append.
- Denormalize read-hot fields onto the parent; sync on write.

### Document keys — distribution + access
The key is identity + shard selector: Couchbase CRC32-hashes it into a vBucket, so load spreads evenly regardless of key PATTERN — even sequential/monotonic ids scatter, they don't hot-spot. Make keys deterministic, derivable from the natural id (`user:123`, `order:2026:456`) so KV `get`/`USE KEYS` hits one node with no index. Keep keys short (byte-capped: ≤246 B, 250 in `_default`) and meaningful.

### Addressing data in SQL++
Full keyspace path ``namespace:bucket`.`scope`.`collection` `` (only the `default` namespace; backtick hyphenated names). Set a **query context** for a bare collection name (partial keyspace); unset for a full path. `USE KEYS` is a direct KV lookup (no index). Prefer ANSI `JOIN`/`NEST`/`UNNEST`; `UNNEST` flattens embedded arrays into rows, join key needs a backing index.

### Collections: TTL, indexing, consistency
- Per-collection `maxTTL` sets a default expiry; precedence document > collection > bucket — but a doc TTL can't exceed a non-zero `maxTTL`, `maxTTL=0` INHERITS the bucket, `maxTTL=-1` opts OUT (never expire). Expired docs purge lazily then tombstone.
- Collections are the unit of GSI indexing, RBAC grants, and XDCR filtering; scopes replicate but can't be indexed.
- Durable writes (`majority`/`majorityAndPersistActive`/`persistToMajority`) are synchronous per op, up to 2 replicas — see durability-and-consistency & performance deep-dives + lore/deep/databases.md#indexing-and-query-plans.

### Sources
- docs.couchbase.com/server/current/learn/data/scopes-and-collections.html; .../buckets-memory-and-storage/vbuckets.html (CRC32 key→vBucket, even spread)
- .../learn/data/document-data-model.html + data/data.html + data/expiration.html (embed/reference, ≤246 B key, maxTTL/-1)
- .../n1ql/n1ql-language-reference/from.html; .../introduction/whats-new.html (8.0 Magma/128 vBuckets)

## SQL++ query & indexes <a id="sqlpp-query-and-indexes"></a>

Server 8.0 GA (Oct 2025; latest 8.0.2, Jun 2026); 7.x still common. SQL++ (formerly **N1QL**) is a JSON-native superset of SQL over documents, not rows. Verify gates against the target cluster.

### Address data by keyspace, not table
A keyspace is `` `bucket`.`scope`.`collection` `` (default `_default`); ≤1000 scopes+collections/cluster. The doc key is `meta().id`.
- **Reach known docs by key, never by scan.** `SELECT … FROM hotel USE KEYS ["h1","h2"]` bypasses indexes (sub-ms); reserve SQL++ predicates for *unknown*-key lookups. For one field, KV subdoc beats a query.
- Nested JSON is first-class: dotted paths (`geo.lat`), collection predicates (`ANY`/`EVERY`/`ARRAY … FOR`), object construction in projections.

### Every predicate needs a GSI — index the query
Global Secondary Indexes are async/eventually consistent, on a separate Index service. `CREATE INDEX idx ON hotel(state, city) USING GSI`.
- **The leading key must appear in `WHERE`** or the index isn't selected. Composite `(a,b)` serves predicates anchored on `a`; not `WHERE b = …` alone.
- `MISSING` values aren't indexed — covering/partial indexes qualify only when the query excludes them (`WHERE a IS NOT MISSING`, or a leading-key predicate implying it).
- Batch DDL: create many `WITH {"defer_build":true}`, then one `BUILD INDEX` — a single scan, not one per index.
- Scale/HA: `PARTITION BY HASH(a)` (`num_partition` default 8) spreads a big index across nodes; `num_replica` adds redundancy + scan parallelism. Keep partition keys immutable.
- **Never rely on the primary index in prod.** `CREATE PRIMARY INDEX` allows ad-hoc unindexed queries but every scan walks the whole keyspace (`PrimaryScan`, never covered). Drop it once real indexes exist.

### Covering indexes — the biggest read win
When the index holds every field a query touches, the engine skips the KV fetch — `EXPLAIN` shows an `IndexScan3` with a `covers` array (no `covers` ⇒ a fetch). `covers` always includes `meta().id`, so index keys **plus** `meta().id` must account for every referenced field. You **cannot** stitch coverage across two indexes — build one composite index.

### Arrays, UNNEST & JOINs
Index array elements: `CREATE INDEX ix ON route(DISTINCT ARRAY s.utc FOR s IN schedule END)`, then filter via `UNNEST route.schedule AS s`. Adaptive indexes cover arbitrary fields — handy for sparse ad-hoc filters but larger/slower. JOINs exist (`USE KEYS` lookup, ANSI `JOIN … ON`) but the right side **must** be indexed (or an EE `USE HASH` hint); no cheap cross-node joins — denormalize/embed read-together data instead.

### Query↔index consistency (`scan_consistency`)
- `not_bounded` (**default**): fastest; reads whatever the GSI has indexed — may lag writes.
- `request_plus`: strong per request; waits for the index to reach the current mutation vector ⇒ read-your-own-writes.
- `at_plus`: RYOW for *specific* mutations via a `scan_vector` — cheaper than `request_plus`.
- `statement_plus`: strong per statement. Pick the weakest level tolerable; strong levels wait on index catch-up.

### Pagination, parameters, plans
- `OFFSET` scans then discards skipped rows — **keyset-paginate** on an indexed key (`WHERE id>$last ORDER BY id LIMIT n`).
- Parameterize: named `$name` / positional `$1`/`?` (via `args`); mask a secret by starting and ending its parameter name with an underscore (7.6.8+). Never string-concat user input.
- `PREPARE`/`EXECUTE` caches the plan; pair with parameters so hot queries skip re-planning.

### Sources
docs.couchbase.com/server/current/n1ql/n1ql-language-reference/{index,covering-indexes}.html · docs.couchbase.com/server/current/settings/query-settings.html · docs.couchbase.com/server/current/learn/services-and-indexes/indexes/global-secondary-indexes.html

## Durability & Consistency <a id="durability-and-consistency"></a>

Version: Server 8.0 GA (durable writes since 6.5; SQL++ `BEGIN TRANSACTION` since 7.0). Capella applies the same levels. With the **default 1 replica** majority = 2 nodes, so a single-node dev cluster can't meet it → `DurabilityImpossibleException`; **0 replicas** needs only 1 node (majority met).

### The write path: vBuckets, active/replica, CAS
Each key hashes (CRC32) to a vBucket (1024 on Couchstore; 128/1024 on Magma). Each vBucket has one **active** plus up to 3 **replicas**; writes hit the active, then stream to replicas via DCP. KV `get` reads the active, so a plain get is always RYOW — the eventual-consistency gap is the **index/query** side, not KV.
- Each doc carries a **CAS** that changes per mutation. Pass it back on `replace`/subdoc for optimistic locking; a stale CAS raises `CasMismatchException` — retry the get-modify-write with bounded backoff. Use `getAndLock` for short pessimistic locks on hot docs.

### Durability levels (per-write, tunable)
Default write is **async**: acked once in the active's memory — lost if that node dies before replication. Opt into synchronous **durable writes**:
- `MAJORITY` — a majority of Data nodes hold it in memory (only level for Ephemeral buckets).
- `MAJORITY_AND_PERSIST_TO_ACTIVE` — majority in memory + fsync on the active.
- `PERSIST_TO_MAJORITY` — fsync on a majority; strongest, slowest.

Majority math: **2 replicas→2 nodes; 3 replicas can't use durability** (`EDurabilityImpossible`). Default SDK timeout 10 s; a second durable write to the same in-flight key returns `SYNC_WRITE_IN_PROGRESS`. Use legacy `PersistTo`/`ReplicateTo` (observe API) only pre-6.5.

DON'T assume writes survive node loss without a level. DON'T set `durabilityImpossibleFallback=true` — it silently degrades durable writes to async. On auto-failover, majority loss before propagation can lose a "successful" durable write; cap `maxCount` below majority or enable `failoverPreserveDurabilityMajority` (EE).

### Query/index consistency (`scan_consistency`)
GSI maintenance is **async** to the write, so SQL++ over an index is eventually consistent. Choose per query:
- `NOT_BOUNDED` — default; whatever is indexed now. Lowest latency, no RYOW.
- `REQUEST_PLUS` — index caught up to all mutations first; full RYOW, highest latency.
- `AT_PLUS` via `consistentWith(MutationState)` — waits only on *your* mutation tokens; RYOW cheaper than `REQUEST_PLUS`.

DON'T default read-after-write flows to `NOT_BOUNDED`; use `AT_PLUS` with the write's mutation token, not the blunt `REQUEST_PLUS`.

### Multi-document ACID transactions
Distributed transactions span docs across collections/scopes/buckets. Isolation is **Read Committed** with a Monotonic Atomic View — a commit is never partially observed; lost updates are blocked via CAS. Statement-level atomicity: a failed SQL++ statement rolls back alone, the txn continues. Queries in a txn default to `request_plus` to see its own writes. Keep docs <10 MB, txns short (default expiry ~15 s), require NTP-synced clocks, and never mix non-transactional writes into docs a txn is mutating.

### Sources
- Server 8.0 — Durability: https://docs.couchbase.com/server/current/learn/data/durability.html
- Server 8.0 — Distributed ACID Transactions: https://docs.couchbase.com/server/current/learn/data/transactions.html
- Java SDK — KV & N1QL scan consistency: https://docs.couchbase.com/java-sdk/current/howtos/kv-operations.html

## Performance <a id="performance"></a>

Playbook for Server **8.0** (Magma default: 128 vBuckets, 100 MiB min quota, 1% mem-to-data; Couchstore 10%) and **7.x**; Capella runs the same engine. No release rescues a `PrimaryScan`, a cold working set, or a fat doc. **Measure first.**

### Prioritized levers (highest impact first)

1. **Reach data by key, not by query.** A KV `get`/subdoc op or SQL++ `USE KEYS` hits the Data service directly (sub-ms), skipping the Query→Index→Fetch path. Never scan for a point read. See `lore/deep/couchbase.md#data-model-and-collections`.
2. **Keep the working set resident.** Data serves from RAM; a low resident ratio turns reads into disk fetches. Magma (1% mem:data) is disk-centric for large sets; Couchstore (10%) suits in-RAM sets. Scale before the miss ratio climbs.
3. **Back every predicate with a GSI; aim for covered scans.** One composite index per query shape, leading keys = the equality predicates. Covered = `IndexScan3` carries a `covers` array and **no `Fetch`**; two GSIs can't cover a query, so build one composite. See `lore/deep/couchbase.md#sqlpp-query-and-indexes`, `lore/deep/databases.md#indexing-and-query-plans`.
4. **Model for the query.** Embed data read together; reference to bound doc size (20 MiB value ceiling; stay well under). No cheap server-side JOIN — an ANSI JOIN needs a GSI on the `ON` keys or it degrades to a nested-loop scan.
5. **Tune `scan_consistency` per query.** `not_bounded` (default) is fastest but may read a stale index; `request_plus` gives read-your-writes but blocks until the index catches up. See `lore/deep/couchbase.md#durability-and-consistency`.
6. **Right-size durability.** Default `none` (fastest); `majority` → `majorityAndPersistActive` → `persistToMajority` each add latency; up to 3 replicas but durable writes need ≤2 (impossible at 3); Ephemeral allows only `majority`.
7. **Scale services independently (MDS).** Put Query and Index on separate nodes so execution doesn't fight index maintenance; add index replicas for HA and hash-partition a hot GSI.
8. **Batch, don't chatter.** Bulk KV ops and subdoc mutations (one field, not the whole doc) beat per-doc round trips.

### How to measure

- **`EXPLAIN`** — want `IndexScan3` (ideally with `covers`); avoid `PrimaryScan`; a `Filter` after the scan = a predicate not pushed down.
- **Profile** — `profile=timings` gives `phaseTimes`/`phaseCounts` per operator to find the slow stage.
- **Query catalogs** — `system:completed_requests` (tune `completed-threshold`/`completed-limit`) is the slow-query log; `system:active_requests` for in-flight.
- **Index Advisor** — `ADVISE <query>` (EE) suggests missing indexes.
- **Cluster stats** — resident ratio + KV cache-miss ratio, index mutation-queue/drain rate + fragmentation, disk write queue.
- Pooling + spans: `lore/deep/databases.md#{connection-pooling,resilience-and-observability}`.

### Top anti-patterns

- **`PrimaryScan` / unindexed predicate** — full keyspace scan; never keep the primary index in prod.
- **`OFFSET` pagination** on large sets — scans and discards; keyset-page on an indexed key.
- **`request_plus` everywhere** — serializes queries behind index lag; reserve it.
- **Fat docs / unbounded arrays** near the 20 MiB cap — churn and slow fetches; split or cap.
- **Over-indexing** — every mutation maintains all matching GSIs; drop unused ones.
- **SQL++ for known keys** — use KV/`USE KEYS`.

### Sources
- https://docs.couchbase.com/server/current/learn/buckets-memory-and-storage/storage-engines.html
- https://docs.couchbase.com/server/current/n1ql/n1ql-language-reference/covering-indexes.html
- https://docs.couchbase.com/server/current/learn/data/durability.html
- https://docs.couchbase.com/server/current/learn/services-and-indexes/services/services.html
