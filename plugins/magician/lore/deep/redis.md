# Redis — deep dive

> On-demand companion to `lore/redis.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Data structures & patterns](#data-structures-and-patterns) · [Persistence & eviction](#persistence-and-eviction) · [Clustering & HA](#clustering-and-ha) · [Performance](#performance)

## Data structures & patterns <a id="data-structures-and-patterns"></a>

Current stable 8.8.x (8.0 renamed Redis CE → Redis Open Source). License: BSD-3 through 7.2; RSALv2/SSPLv1 for the 7.4 line; tri-license RSALv2/SSPLv1/AGPLv3 since 8.0. Valkey is the BSD-3, Linux-Foundation fork (9.1.x). Single-threaded exec (I/O threading aside) — one O(N) command stalls every client, so structure choice is a latency decision.

### Pick the structure by access pattern
- String: blob / counter / JSON-as-text. `INCR`/`INCRBY` atomic; `SET k v EX 30 NX` = value + TTL + lock in one round-trip.
- Hash: fields of one entity — far cheaper than N string keys; per-field TTL via `HEXPIRE` (7.4+, O(N) fields), `HGETEX`/`HGETDEL` (8.0).
- Sorted set: leaderboards, time/rate windows, priority queues, score-indexing. `ZADD GT/LT`, `ZRANGEBYSCORE`, `ZRANGEBYLEX`; ops are O(log N).
- List: queue/stack (`LPUSH`+`BRPOP`, `LMPOP`). Stream: durable append-only log with consumer groups + acks — prefer over List/Pub-Sub for at-least-once delivery.
- Set: membership / dedupe / tags; `SINTERCARD`. Probabilistic types (Bloom, Cuckoo, HyperLogLog, Top-K, count-min) trade exactness for tiny fixed memory. Bitmap/Bitfield: dense flags/counters. Also JSON, geospatial, time series, vector sets (HNSW, cosine).

### Encodings are the memory lever
Small hashes/sets/zsets/lists use a compact `listpack`; int-only sets use `intset`; each converts to `hashtable`/`skiplist`/`quicklist` past its `*-max-listpack-entries`/`-value` threshold — then per-item overhead jumps. Verify with `OBJECT ENCODING`. Bucketing small entries into one hash beats many top-level keys. See lore/deep/redis.md#performance.

### O(N) hazards & big keys
Never on the hot path: `KEYS` (use `SCAN` — cursor-based, non-blocking, weak guarantees mid-mutation), or full `HGETALL`/`SMEMBERS`/`LRANGE 0 -1` on large keys. A big or hot key concentrates memory and CPU on one shard — split it (sharded counters, per-bucket hashes). `DEL` of a huge key blocks; prefer `UNLINK` (async reclaim).

### Cut round-trips, keep atomicity
Pipeline independent commands; use multi-key ops (`MGET`/`MSET`/`HMGET`). `MULTI/EXEC` batches but is not rollback — a wrong-type error still runs the rest of the queue; pair with `WATCH` for optimistic CAS. For read-modify-write, a Lua script or Function runs atomically in one shot — don't split a check-then-set across round-trips.

### Cache idioms
Cache-aside: miss → load → `SET k v EX ttl`. Always set a TTL, with random jitter so keys don't expire in lockstep (thundering herd). Stampede control: a short lock (`SET lock 1 NX EX 5`) so one worker rebuilds, or logical/early expiry (store value + soft deadline, refresh ahead of hard TTL). Invalidation is hard — prefer TTL + versioned keys (`user:1:v7`) over surgical deletes; don't trust Pub/Sub alone for correctness. Use colon namespaces (`user:1000:sess`); `{tag}` hashtags force related keys into one cluster slot so multi-key ops stay legal. TTLs are absolute (persisted/replicated), 1 ms resolution. Eviction under `maxmemory` is a separate lever (lore/deep/redis.md#persistence-and-eviction); pooling/observability in lore/deep/databases.md#connection-pooling, lore/deep/databases.md#resilience-and-observability.

### Sources
- https://redis.io/docs/latest/develop/data-types/
- https://redis.io/docs/latest/develop/using-commands/keyspace/
- https://redis.io/docs/latest/commands/hexpire/
- https://github.com/redis/redis (version.h, LICENSE) ; https://valkey.io/

## Persistence & eviction <a id="persistence-and-eviction"></a>

Versions: Redis 8.x current stable (LRM policy 8.6+). Commands execute **single-threaded** (I/O threads handle only socket I/O). License: BSD-3 through 7.2; dual RSALv2/SSPLv1 for the 7.4 line; **tri-license RSALv2/SSPLv1/AGPLv3 since 8.0** (AGPLv3 the sole OSI-approved option). Valkey is the BSD-3 Linux-Foundation fork (9.x).

### Two engines — DO pick per durability need
- **RDB (snapshot):** point-in-time `dump.rdb` via `save <sec> <changes>` (e.g. `save 60 1000`) or `BGSAVE`; `SAVE` blocks — never in prod. Compact, fast restarts, great for backups/DR — but **loses everything since the last snapshot**.
- **AOF (append-only):** `appendonly yes` logs each write in RESP. `appendfsync everysec` (default; ≤1s loss, background fsync), `always` (per batch, slow), or `no` (OS flushes, ~30s). Since 7.0 the AOF is **multi-part** (base + incremental files + manifest) under `appenddirname` (default `appendonlydir`).
- **RDB+AOF together:** on restart the **AOF wins** (most complete). `aof-use-rdb-preamble yes` (default) makes the base an RDB image → smaller, faster load.

### Rewrites & fork cost — DON'T ignore COW
- AOF grows unbounded; compacted by `BGREWRITEAOF`, auto-fired at `auto-aof-rewrite-percentage 100` + `auto-aof-rewrite-min-size 64mb`.
- Every snapshot/rewrite `fork()`s; the parent serves via copy-on-write. **Fork pauses the main thread** (µs–seconds on big datasets; up to ~2× RAM on full churn). Set `vm.overcommit_memory=1`, disable THP, keep RAM headroom. BGSAVE and rewrite are serialized.
- Truncated tail: `aof-load-truncated yes` (default) loads anyway; real corruption → `redis-check-aof --fix`.

### Eviction — DO set maxmemory + a policy (it's a cache)
- `maxmemory` default `0` = unlimited (64-bit; 32-bit implicit 3GB) → OOM / OS-kill risk. `maxmemory-policy` default **`noeviction`** (writes fail with an OOM error; reads serve).
- Policies: `allkeys-lru|lfu|random`, `volatile-lru|lfu|random|ttl`. `volatile-*` touch only keys with a TTL and act like `noeviction` when none have one. `allkeys-lru` is the sane default; `allkeys-lfu` for skewed hot sets; `volatile-ttl` with meaningful TTLs.
- LRU/LFU are **approximated** by sampling: `maxmemory-samples 5` (raise to 10 for near-true LRU at CPU cost). LFU tuning: `lfu-log-factor 10`, `lfu-decay-time 1`.
- Eviction runs **inline in the command path** — the single thread evicts before serving the write, so it steals throughput; a big multi-key write can transiently overshoot `maxmemory`. Repl/AOF buffers don't count toward the evict total — leave headroom.

### Expiration — DO pair TTLs with eviction
Passive (lazy) delete on access + active background sampling (~10 Hz) of volatile keys. Replicas never expire on their own — they serve a stale key until the primary propagates `DEL`/`UNLINK`. Each TTL costs a few bytes.

### Measure
`INFO persistence` (`rdb_last_bgsave_status`, `aof_last_bgrewrite_status`, `latest_fork_usec`), `INFO stats` (`evicted_keys`, `expired_keys`, `keyspace_hits/misses`), `INFO memory` (`used_memory`, `mem_not_counted_for_evict`). See lore/deep/redis.md#{performance,clustering-and-ha,data-structures-and-patterns} and lore/deep/databases.md#{resilience-and-observability,connection-pooling}.

### Sources
- https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- https://redis.io/docs/latest/develop/reference/eviction/
- https://redis.io/legal/licenses/ · https://valkey.io/

## Clustering & HA <a id="clustering-and-ha"></a>

Versions: Redis 8.8 stable — tri-license RSALv2/SSPLv1/AGPLv3 since 8.0; dual RSALv2/SSPLv1 for the 7.4 line; BSD-3 through 7.2. Valkey 9.1 is the BSD-3-Clause, Linux-Foundation fork (wire/cluster compatible). Command execution stays **single-threaded** (I/O threading aside): one slow command blocks only its own shard, but a hot slot pins that shard's load on one core.

### Two different tools — DON'T conflate
- **Redis Cluster** = automatic sharding across masters **plus** built-in failover. Use it to scale past one node's RAM/CPU.
- **Sentinel** = HA for a **single, non-sharded** master + replicas (monitoring, automatic failover, client service-discovery). No sharding. Don't put Sentinel in front of a Cluster — Cluster fails itself over.

### Cluster mechanics — DO
- Keyspace = **16384 hash slots**; slot = `CRC16(key) mod 16384`. Each master owns a slot range; slots migrate online with **no downtime** (resharding).
- Multi-key ops (MGET/MSET, MULTI/EXEC, Lua) require **all keys in one slot**, else `CROSSSLOT` error. Co-locate with a **hash tag** — only the substring in `{}` is hashed, so `user:{42}:profile` and `user:{42}:cart` share a slot. DON'T over-wrap `{}` until everything collapses onto one slot (hot shard).
- Use a **cluster-aware client** caching the slot map (`CLUSTER SHARDS`). On **`MOVED`** refresh the map (slot relocated permanently); on **`ASK`** send `ASKING` + retry that one command (slot mid-migration) — don't rebuild the whole map.
- Deploy **≥3 masters**; recommended shape is **6 nodes = 3 masters + 3 replicas** (`--cluster-replicas 1`), spread across failure domains. A master whose slots lose every live replica can fail the cluster.

### Availability & consistency — the tradeoff
- Replication is **asynchronous**: the master ACKs the client, then propagates — a crash before propagation **loses acknowledged writes**. `WAIT numreplicas timeout` blocks until N replicas ack (stronger, still not full sync).
- `cluster-node-timeout` drives failure detection/failover; a node that can't reach a **majority of masters** stops serving. Default `cluster-require-full-coverage yes` halts the whole cluster if any slot is unowned — flip `cluster-allow-reads-when-down` only if stale reads are acceptable.
- Sentinel: **run ≥3, never 2**, on independent hosts. `quorum` = sentinels needed to mark a master `ODOWN` (objectively down; a lone sentinel's view is `SDOWN`). But a failover needs a **majority** of all sentinels to elect a leader — so none happens in a minority partition. Clients resolve the master via `SENTINEL get-master-addr-by-name`.

### DON'T
- Fan `KEYS`, `FLUSHALL`, or wide `MGET` across the cluster as if it were one node — each key maps to a specific shard.
- Equate failover with zero data loss; quantify the write-loss window and gate critical writes behind `WAIT`.
- Read from replicas expecting freshness (`READONLY` is a conscious choice) — replication lag serves stale data.

Deep dive: lore/deep/redis.md#{data-structures-and-patterns,persistence-and-eviction,performance} and lore/deep/databases.md#{connection-pooling,resilience-and-observability}.

### Sources
redis.io/docs/latest/operate/oss_and_stack/management/scaling · .../management/sentinel · redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec · redis.io/legal/licenses · valkey.io/download

## Performance <a id="performance"></a>

Ordered playbook: fix the biggest lever first, measure every change. Command execution is **single-threaded** (I/O threading aside) — one slow command stalls *every* client. Redis 8.x is current (8.0 added AGPLv3; 7.4 moved BSD→RSALv2/SSPLv1); Valkey is the BSD-3-Clause Linux Foundation fork (9.x) — verify version/fork. Depth is in the deep-dives; this is the checklist.

### 0. Measure first — you can't tune what you can't see
- DO baseline with `redis-cli --latency`, and `--intrinsic-latency 100` **on the server** to bound what the kernel/hypervisor allows. Enable `LATENCY MONITOR`/`LATENCY DOCTOR`; watch `INFO` for `latest_fork_usec`, `mem_fragmentation_ratio`, `evicted_keys`, `keyspace_hits`/`misses`.
- DO find offenders with `SLOWLOG GET`; hit ratio = `keyspace_hits/(hits+misses)`. Bench with `redis-benchmark -P <n>` at your app's pipeline depth — default P=1 is worst case.
- DON'T profile with `MONITOR` in production — it taxes throughput; sample `INFO`/`SLOWLOG`.

### 1. Kill O(N) commands on the hot path (top single-thread risk)
- DO iterate with `SCAN`/`HSCAN`/`SSCAN`/`ZSCAN` (cursor, small work per call) — NEVER `KEYS`; avoid `SMEMBERS`/`HGETALL`/`LRANGE 0 -1`/big `SORT` on large values. Complexity is documented per command — check it.
- DO push unavoidable heavy reads to a replica. See lore/deep/redis.md#data-structures-and-patterns.

### 2. Cut round-trips
- DO pipeline, use multi-key `MGET`/`MSET`, `MULTI`/`EXEC`, or a Lua script to collapse RTTs — network round-trip dwarfs sub-µs command time. Keep long-lived pooled connections; Unix sockets beat TCP loopback for co-located clients. lore/deep/databases.md#connection-pooling.
- DON'T connect/disconnect per op, or send unbounded pipelines that balloon the reply buffer.

### 3. Cap RAM: maxmemory + eviction (RAM is THE constraint)
- DO set `maxmemory` (leave headroom for replication/AOF buffers) plus a `maxmemory-policy` — default `noeviction` errors on writes; use `allkeys-lru`/`allkeys-lfu` for a pure cache. Prefer TTLs. Policies + `maxmemory-samples`: lore/deep/redis.md#persistence-and-eviction.
- DO shrink items: small hashes/sets/zsets stay listpack/intset-encoded under `hash-max-listpack-entries` (etc.) — up to ~10× savings; overflow converts to a full table. lore/deep/redis.md#data-structures-and-patterns.
- DON'T let one big or hot key concentrate memory and CPU on a single shard.

### 4. Tame persistence & fork latency
- DO expect a spike on RDB/AOF `fork` (page-table copy scales with RSS); disable Transparent Huge Pages; keep RSS well under RAM so copy-on-write + `BGSAVE` fit. `appendfsync everysec` balances durability/latency. lore/deep/redis.md#persistence-and-eviction.
- DON'T use `appendfsync always` unless required; never let the box swap — paged-out keys destroy tail latency; RSS reflects *peak*.

### 5. Scale past the single-thread ceiling
- DO scale reads with replicas; scale writes/RAM with Redis Cluster (16384 hash slots) — keep multi-key ops in one slot via a `{hashtag}` (cross-slot ops error). lore/deep/redis.md#clustering-and-ha.
- DON'T expect more cores to speed one instance — run multiple shards/instances. Failover, timeouts, retries: lore/deep/databases.md#resilience-and-observability.

### Sources
- redis.io/docs/latest/operate/oss_and_stack/management/optimization/{latency,memory-optimization,benchmarks}/
- redis.io/docs/latest/develop/reference/eviction/
- redis.io licensing (RSALv2/SSPLv1/AGPLv3) · valkey.io (BSD-3-Clause, LF)
