# Redis — Performance

Ordered playbook: fix the biggest lever first, measure every change. Command execution is **single-threaded** (I/O threading aside) — one slow command stalls *every* client. Redis 8.x is current (8.0 added AGPLv3; 7.4 moved BSD→RSALv2/SSPLv1); Valkey is the BSD-3-Clause Linux Foundation fork (9.x) — verify version/fork. Depth is in the deep-dives; this is the checklist.

## 0. Measure first — you can't tune what you can't see
- DO baseline with `redis-cli --latency`, and `--intrinsic-latency 100` **on the server** to bound what the kernel/hypervisor allows. Enable `LATENCY MONITOR`/`LATENCY DOCTOR`; watch `INFO` for `latest_fork_usec`, `mem_fragmentation_ratio`, `evicted_keys`, `keyspace_hits`/`misses`.
- DO find offenders with `SLOWLOG GET`; hit ratio = `keyspace_hits/(hits+misses)`. Bench with `redis-benchmark -P <n>` at your app's pipeline depth — default P=1 is worst case.
- DON'T profile with `MONITOR` in production — it taxes throughput; sample `INFO`/`SLOWLOG`.

## 1. Kill O(N) commands on the hot path (top single-thread risk)
- DO iterate with `SCAN`/`HSCAN`/`SSCAN`/`ZSCAN` (cursor, small work per call) — NEVER `KEYS`; avoid `SMEMBERS`/`HGETALL`/`LRANGE 0 -1`/big `SORT` on large values. Complexity is documented per command — check it.
- DO push unavoidable heavy reads to a replica. See lore/redis/data-structures-and-patterns.md.

## 2. Cut round-trips
- DO pipeline, use multi-key `MGET`/`MSET`, `MULTI`/`EXEC`, or a Lua script to collapse RTTs — network round-trip dwarfs sub-µs command time. Keep long-lived pooled connections; Unix sockets beat TCP loopback for co-located clients. lore/databases/connection-pooling.md.
- DON'T connect/disconnect per op, or send unbounded pipelines that balloon the reply buffer.

## 3. Cap RAM: maxmemory + eviction (RAM is THE constraint)
- DO set `maxmemory` (leave headroom for replication/AOF buffers) plus a `maxmemory-policy` — default `noeviction` errors on writes; use `allkeys-lru`/`allkeys-lfu` for a pure cache. Prefer TTLs. Policies + `maxmemory-samples`: lore/redis/persistence-and-eviction.md.
- DO shrink items: small hashes/sets/zsets stay listpack/intset-encoded under `hash-max-listpack-entries` (etc.) — up to ~10× savings; overflow converts to a full table. lore/redis/data-structures-and-patterns.md.
- DON'T let one big or hot key concentrate memory and CPU on a single shard.

## 4. Tame persistence & fork latency
- DO expect a spike on RDB/AOF `fork` (page-table copy scales with RSS); disable Transparent Huge Pages; keep RSS well under RAM so copy-on-write + `BGSAVE` fit. `appendfsync everysec` balances durability/latency. lore/redis/persistence-and-eviction.md.
- DON'T use `appendfsync always` unless required; never let the box swap — paged-out keys destroy tail latency; RSS reflects *peak*.

## 5. Scale past the single-thread ceiling
- DO scale reads with replicas; scale writes/RAM with Redis Cluster (16384 hash slots) — keep multi-key ops in one slot via a `{hashtag}` (cross-slot ops error). lore/redis/clustering-and-ha.md.
- DON'T expect more cores to speed one instance — run multiple shards/instances. Failover, timeouts, retries: lore/databases/resilience-and-observability.md.

## Sources
- redis.io/docs/latest/operate/oss_and_stack/management/optimization/{latency,memory-optimization,benchmarks}/
- redis.io/docs/latest/develop/reference/eviction/
- redis.io licensing (RSALv2/SSPLv1/AGPLv3) · valkey.io (BSD-3-Clause, LF)
