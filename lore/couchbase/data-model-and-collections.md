# Couchbase — Data model & collections

Server 8.0 (scopes/collections since 7.0; `_system` scope since 7.6). JSON store: each doc is a key + JSON value, distributed by CRC32-hashing the key into a vBucket (8.0: Magma engine, 128 vBuckets; Couchstore had 1024). Model QUERY-FIRST — SQL++ can JOIN, but joins fan out and cost round-trips, so access patterns drive embed-vs-reference.

## Keyspace hierarchy — the organization lever
`Bucket → Scope → Collection → Document`. A collection groups docs of one type; a scope groups collections (tenant, domain, env). Namespaces are per-level: same collection name in different scopes, same key in different collections.
- Every bucket has a `_default` scope + collection (pre-7.0 data lands here). Default scope can't be dropped; default collection drops but can't be recreated.
- The 7.6 `_system` scope (e.g. `_query`, `_mobile`) is Couchbase-owned; don't drop or read it.
- Limits: **1000 scopes + 1000 collections per cluster**. Names 1–251 chars of `A-Za-z0-9_-%`, case-sensitive, can't start with `_`/`%`, no rename.
- Collections segregate types (cheaper than a `type` field + filter); scopes for tenant isolation + RBAC blast-radius.

## Model query-first: embed vs reference
- EMBED data read/written together into one document so a KV `get`/SQL++ row returns the whole aggregate. Single-doc mutation is atomic; no multi-doc ACID outside explicit transactions.
- REFERENCE (store the key, fetch/JOIN separately) when the child is large, unbounded, high-churn, or accessed alone. Unbounded embedded arrays are the trap: they march toward the **20 MiB** doc ceiling, rewriting the whole doc on every append.
- Denormalize read-hot fields onto the parent; sync on write.

## Document keys — distribution + access
The key is identity + shard selector: Couchbase CRC32-hashes it into a vBucket, so load spreads evenly regardless of key PATTERN — even sequential/monotonic ids scatter, they don't hot-spot. Make keys deterministic, derivable from the natural id (`user:123`, `order:2026:456`) so KV `get`/`USE KEYS` hits one node with no index. Keep keys short (byte-capped: ≤246 B, 250 in `_default`) and meaningful.

## Addressing data in SQL++
Full keyspace path ``namespace:bucket`.`scope`.`collection` `` (only the `default` namespace; backtick hyphenated names). Set a **query context** for a bare collection name (partial keyspace); unset for a full path. `USE KEYS` is a direct KV lookup (no index). Prefer ANSI `JOIN`/`NEST`/`UNNEST`; `UNNEST` flattens embedded arrays into rows, join key needs a backing index.

## Collections: TTL, indexing, consistency
- Per-collection `maxTTL` sets a default expiry; precedence document > collection > bucket — but a doc TTL can't exceed a non-zero `maxTTL`, `maxTTL=0` INHERITS the bucket, `maxTTL=-1` opts OUT (never expire). Expired docs purge lazily then tombstone.
- Collections are the unit of GSI indexing, RBAC grants, and XDCR filtering; scopes replicate but can't be indexed.
- Durable writes (`majority`/`majorityAndPersistActive`/`persistToMajority`) are synchronous per op, up to 2 replicas — see durability-and-consistency & performance deep-dives + lore/databases/indexing-and-query-plans.md.

## Sources
- docs.couchbase.com/server/current/learn/data/scopes-and-collections.html; .../buckets-memory-and-storage/vbuckets.html (CRC32 key→vBucket, even spread)
- .../learn/data/document-data-model.html + data/data.html + data/expiration.html (embed/reference, ≤246 B key, maxTTL/-1)
- .../n1ql/n1ql-language-reference/from.html; .../introduction/whats-new.html (8.0 Magma/128 vBuckets)
