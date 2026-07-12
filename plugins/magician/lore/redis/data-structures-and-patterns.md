# Redis — Data structures & patterns

Current stable 8.8.x (8.0 renamed Redis CE → Redis Open Source). License: BSD-3 through 7.2; RSALv2/SSPLv1 for the 7.4 line; tri-license RSALv2/SSPLv1/AGPLv3 since 8.0. Valkey is the BSD-3, Linux-Foundation fork (9.1.x). Single-threaded exec (I/O threading aside) — one O(N) command stalls every client, so structure choice is a latency decision.

## Pick the structure by access pattern
- String: blob / counter / JSON-as-text. `INCR`/`INCRBY` atomic; `SET k v EX 30 NX` = value + TTL + lock in one round-trip.
- Hash: fields of one entity — far cheaper than N string keys; per-field TTL via `HEXPIRE` (7.4+, O(N) fields), `HGETEX`/`HGETDEL` (8.0).
- Sorted set: leaderboards, time/rate windows, priority queues, score-indexing. `ZADD GT/LT`, `ZRANGEBYSCORE`, `ZRANGEBYLEX`; ops are O(log N).
- List: queue/stack (`LPUSH`+`BRPOP`, `LMPOP`). Stream: durable append-only log with consumer groups + acks — prefer over List/Pub-Sub for at-least-once delivery.
- Set: membership / dedupe / tags; `SINTERCARD`. Probabilistic types (Bloom, Cuckoo, HyperLogLog, Top-K, count-min) trade exactness for tiny fixed memory. Bitmap/Bitfield: dense flags/counters. Also JSON, geospatial, time series, vector sets (HNSW, cosine).

## Encodings are the memory lever
Small hashes/sets/zsets/lists use a compact `listpack`; int-only sets use `intset`; each converts to `hashtable`/`skiplist`/`quicklist` past its `*-max-listpack-entries`/`-value` threshold — then per-item overhead jumps. Verify with `OBJECT ENCODING`. Bucketing small entries into one hash beats many top-level keys. See lore/redis/performance.md.

## O(N) hazards & big keys
Never on the hot path: `KEYS` (use `SCAN` — cursor-based, non-blocking, weak guarantees mid-mutation), or full `HGETALL`/`SMEMBERS`/`LRANGE 0 -1` on large keys. A big or hot key concentrates memory and CPU on one shard — split it (sharded counters, per-bucket hashes). `DEL` of a huge key blocks; prefer `UNLINK` (async reclaim).

## Cut round-trips, keep atomicity
Pipeline independent commands; use multi-key ops (`MGET`/`MSET`/`HMGET`). `MULTI/EXEC` batches but is not rollback — a wrong-type error still runs the rest of the queue; pair with `WATCH` for optimistic CAS. For read-modify-write, a Lua script or Function runs atomically in one shot — don't split a check-then-set across round-trips.

## Cache idioms
Cache-aside: miss → load → `SET k v EX ttl`. Always set a TTL, with random jitter so keys don't expire in lockstep (thundering herd). Stampede control: a short lock (`SET lock 1 NX EX 5`) so one worker rebuilds, or logical/early expiry (store value + soft deadline, refresh ahead of hard TTL). Invalidation is hard — prefer TTL + versioned keys (`user:1:v7`) over surgical deletes; don't trust Pub/Sub alone for correctness. Use colon namespaces (`user:1000:sess`); `{tag}` hashtags force related keys into one cluster slot so multi-key ops stay legal. TTLs are absolute (persisted/replicated), 1 ms resolution. Eviction under `maxmemory` is a separate lever (lore/redis/persistence-and-eviction.md); pooling/observability in lore/databases/connection-pooling.md, lore/databases/resilience-and-observability.md.

## Sources
- https://redis.io/docs/latest/develop/data-types/
- https://redis.io/docs/latest/develop/using-commands/keyspace/
- https://redis.io/docs/latest/commands/hexpire/
- https://github.com/redis/redis (version.h, LICENSE) ; https://valkey.io/
