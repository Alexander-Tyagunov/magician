# Memcached — deep dive

> On-demand companion to `lore/memcached.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Usage & Slabs](#usage-and-slabs) · [Scaling & hashing](#scaling-and-hashing) · [Performance](#performance)

## Usage & Slabs <a id="usage-and-slabs"></a>

Version: 1.6.x current (1.6.45, mid-2026). Pure in-memory cache: NO persistence (restart loses all — data must be disposable), NO server-side clustering (client-side sharding). RAM is THE constraint.

### Protocol & connecting
- DO prefer the meta protocol (`mg`/`ms`/`md`/`ma`): flag-driven, folds get+touch+CAS+TTL with real quiet semantics. Legacy ASCII (`set`/`get`…) works; the old binary protocol is deprecated.
- DO pool + reuse connections; defaults `-c` 1024 conns, `-t` 4 threads (threaded, unlike Redis). Exhaustion → `listen_disabled_num`. See lore/deep/databases.md#connection-pooling.
- DON'T use ASCII `noreply` on mutations — errors can't align to requests; use meta quiet flags.

### Core commands (keyed, ~O(1))
- Storage: `set` (upsert), `add` (only if absent — good for locks), `replace` (only if present), `append`/`prepend` (ignore new flags/exptime), `cas` (conditional).
- Retrieval: `get`, `gets` (adds CAS token). MULTIGET — `get k1 k2 k3…` in ONE round trip: the biggest latency lever. Also `delete`, `touch`, `gat`/`gats`.
- `incr`/`decr`: atomic on 64-bit unsigned int text; key must pre-exist + be numeric; decr floors at 0, incr wraps; `set` it first.
- DON'T treat it as a datastore: no queries, scans, secondary indexes, or cross-key transactions.

### Expiration, flags, CAS
- TTL: `0`=never; `1..2592000` (≤30d)=relative seconds; larger=absolute Unix timestamp; past/negative=expire now. `now+31d` as seconds silently means "1970".
- Expiry is LAZY (on access); `lru_crawler` reclaims dead items — RAM held past TTL until then.
- `flags`: opaque 32-bit per item. CAS: `gets`→token, `cas` writes only if unchanged — optimistic concurrency; retry on mismatch.

### Slab allocator & item size
- `-m` (default 64MB) pool is cut into 1MB PAGES; each page goes to a slab CLASS diced into equal CHUNKS. Classes grow by `-f` (default 1.25): ~80B, 104B, 136B… up to 1MB.
- An item lands in the smallest class that fits — the tail is wasted (internal fragmentation). Item size = key + value + overhead (~48–80B; check the `sizes` tool). Right-size values; tune `-f`.
- Default MAX ITEM 1MB; raise with `-I` (e.g. `-I 2m`), but big items waste chunk space and churn the LRU — prefer splitting blobs.

### Calcification, eviction, rebalancing
- A PAGE IS BOUND TO ITS CLASS FOR LIFE. If item sizes shift later → slab CALCIFICATION: one class evicts hot data while another sits on free pages.
- Eviction is PER-CLASS LRU, not global — a full class evicts its own tail even with RAM free elsewhere. Watch `evictions`, `expired_unfetched`, `reclaimed` in `stats items`.
- Modern defaults fight this: slab_automove (default 1; `-o slab_automove=2` aggressive) rebalances pages to pressured classes; segmented LRU (HOT/WARM/COLD + TEMP) via `lru_maintainer` keeps hot items resident.

### Idioms
- DO cache-aside with TTLs + jitter; batch reads via multiget; check `stats slabs`/`stats items` before tuning.
- DON'T lean on `flush_all` in prod (marks all expired), assume durability, or let one giant/hot key dominate a class.
- Working set > RAM: overflow values to SSD with extstore (keys + metadata stay in RAM) — see lore/deep/memcached.md#performance and lore/deep/memcached.md#scaling-and-hashing.

### Sources
- docs.memcached.org/protocols/basic/ · /protocols/meta/ · /features/lru/ (2026-07)
- github.com/memcached/memcached/wiki/{UserInternals,ConfiguringServer,Commands,ReleaseNotes}

## Scaling & hashing <a id="scaling-and-hashing"></a>

Verified against memcached 1.6.45 (stable, 2026-07-09). Memcached has **no server-side clustering**: each node is an independent cache unaware of its peers. A "cluster" is a client-side illusion — the client hashes each key to one node. Data is disposable (no persistence, no replication); a lost node is lost cache, not lost data — always be able to rebuild from source.

### Shard client-side with consistent hashing — DO
Every client shards by hashing the key to pick one server from a fixed list. **Use consistent hashing (ketama), not naive modulo.** With modulo (`hash(key) % N`), changing `N` remaps most keys — docs note an 11th server "may cause 40%+ of your keys to suddenly point to different servers." Consistent hashing keeps that "under 10%": only keys near the changed node move. libmemcached-based clients share ketama, so PHP and Perl clients resolve keys identically; hand-rolled hashing does **not** interoperate.
- **The server list must be byte-identical and identically ordered across every client** — same host:port strings (never `localhost`), same order (some clients sort, some don't). A mismatch silently splits your keyspace.
- Weight nodes by RAM if capacities differ; ketama supports weighting.

### Handle dead nodes as misses, not failover — DO
Prefer **Failure** mode: treat an unreachable node as a cache miss (fall through to the DB), leaving the ring intact. **Avoid auto-failover / auto-removal** — dropping a node rehashes its share onto neighbors (remapping far more keys than intended), and a node that flaps back serves stale values. Set short connect/read timeouts and pool connections (see lore/deep/databases.md#connection-pooling); reconnecting per request leaks connections.

### Spread multiget, watch the fan-out — DO
A multiget (`get k1 k2 …` / meta `mg`) is split per destination node and issued in parallel — the round-trip win. But at scale every multiget touches *every* node (all-to-all fan-out), so p99 tracks the slowest node and one slow node stalls the batch. Keep batches bounded; co-locate related keys on one node via a shared hash prefix if your client supports key-group hashing.

### Size RAM around the slab allocator — DO
`-m` (MB, default 64) is carved into 1MB pages; each page joins a **slab class** of fixed chunks (growth factor `-f`, default 1.25). An item lands in the nearest-fitting class, wasting the slack. **Max item size is ~1MB** (`-I`, raise cautiously). Overhead is ~48–56 bytes/item plus full key length, so many tiny keys cost more than the values suggest.
- **Once a page joins a class it never moves** → *calcification*: an early skew toward one size starves other classes despite free-looking memory. Modern builds auto-repair via the slab rebalancer / `slab_automove` and segmented LRU (see lore/deep/memcached.md#usage-and-slabs).

### DON'T
- DON'T change node count casually on a naive-hash client — you effectively cold-flush the cache (stampede risk; see lore/deep/memcached.md#performance).
- DON'T run one giant node past one box's working set — shard across several; per-node RAM and a single event loop bound throughput.
- DON'T let one hot key/node dominate — replicate that key across nodes or add a client-local tier.

See lore/deep/memcached.md#performance and lore/deep/databases.md#resilience-and-observability for timeout/retry discipline.

### Sources
github.com/memcached/memcached/wiki/ConfiguringClient · wiki/ConfiguringServer · wiki/ReleaseNotes1645

## Performance <a id="performance"></a>

Ordered playbook: fix the biggest lever first, measure every change. Memcached IS multithreaded (scales with cores — unlike single-threaded Redis), so the ceilings are RAM, round-trips, and slab layout, not CPU. Verified 1.6.x; depth in the deep-dives.

### 0. Measure first — read `stats` before tuning
- DO baseline: `stats` (`get_hits`/`get_misses`→hit ratio, `evictions`, `expired_unfetched`, `reclaimed`), `stats settings`, `stats slabs`/`stats items` (per-class chunks, evictions, age). Connection exhaustion shows as `listen_disabled_num` — keep it ~0.
- DO load-test with `mc-crusher` at real key sizes and multiget width.
- DO use `stats sizes` for slab-class alignment (needs `-o track_sizes` at start; the old item-walking form that hung the server was removed, safe 1.4.27+). `stats cachedump` is capped, debug-only.

### 1. Cut round-trips (top latency lever)
- DO batch reads with MULTIGET, pipeline writes with meta quiet flags (not ASCII `noreply`); network RTT dwarfs the sub-µs command time. Keep long-lived pooled connections — see lore/deep/databases.md#connection-pooling.
- DON'T open/close a connection per op — the TCP handshake becomes your latency.

### 2. Cap RAM + defeat slab calcification (RAM is THE constraint)
- DO set `-m` to your working set; items evict per-class LRU as slabs fill. Keep `slab_automove` on (default 1; `=2` aggressive) so whole pages migrate to pressured classes; keep `lru_maintainer` on for segmented LRU (HOT/WARM/COLD/TEMP). Tune growth factor `-f` (default 1.25) and right-size values to the slab grid. Detail: lore/deep/memcached.md#usage-and-slabs.
- DON'T ignore rising `evictions` on one class while RAM looks free — that's calcification; rebalance or resize items.

### 3. Protect the hit ratio (TTLs, stampedes, hot keys)
- DO run cache-aside with TTLs + jitter to spread expiry; gate recompute with an `add`-lock or soft-TTL to stop thundering herds. Hit ratio = `get_hits/(get_hits+get_misses)`.
- DON'T let one big or hot key dominate a class/node — split it or add a client-local tier.

### 4. Mind the multiget hole at scale (fan-out)
- DO keep multiget batches bounded — at many nodes each fans out all-to-all, so p99 tracks the slowest node. Co-locate related keys via a shared hash prefix. See lore/deep/memcached.md#scaling-and-hashing.

### 5. Tune threads & connections
- DO leave `-t` near default 4; raise only under extreme load (80+ runs slower). Size `-c` (default 1024) with headroom; favor persistent connections over reconnect churn (watch `TIME_WAIT`).

### 6. Overflow to flash when the set outgrows RAM (extstore)
- DO enable extstore (`-o ext_path=/data:100G`, `ext_threads`): hash table, keys, and item headers stay in RAM, values go to SSD (~12 bytes/item flash pointer). Set `ext_item_size` so only worthwhile items flush.

### Anti-patterns
- DON'T `flush_all` in prod expecting freed RAM — it only marks items expired. DON'T raise `-I` above ~1MB casually; big items churn the LRU. DON'T change node count on a naive-modulo client — you cold-flush the cache; use ketama. DON'T rely on wall-clock for absolute (unix-timestamp) TTLs — a clock jump skews them; relative TTLs use memcached's monotonic clock.

Timeout/retry/observability: lore/deep/databases.md#resilience-and-observability.

### Sources
- docs.memcached.org/features/flashstorage/ · /protocols/meta/ (2026-07)
- github.com/memcached/memcached/wiki/{Performance,ConfiguringServer,ServerMaint,ReleaseNotes1645}
