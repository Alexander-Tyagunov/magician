# Memcached — Scaling & hashing

Verified against memcached 1.6.45 (stable, 2026-07-09). Memcached has **no server-side clustering**: each node is an independent cache unaware of its peers. A "cluster" is a client-side illusion — the client hashes each key to one node. Data is disposable (no persistence, no replication); a lost node is lost cache, not lost data — always be able to rebuild from source.

## Shard client-side with consistent hashing — DO
Every client shards by hashing the key to pick one server from a fixed list. **Use consistent hashing (ketama), not naive modulo.** With modulo (`hash(key) % N`), changing `N` remaps most keys — docs note an 11th server "may cause 40%+ of your keys to suddenly point to different servers." Consistent hashing keeps that "under 10%": only keys near the changed node move. libmemcached-based clients share ketama, so PHP and Perl clients resolve keys identically; hand-rolled hashing does **not** interoperate.
- **The server list must be byte-identical and identically ordered across every client** — same host:port strings (never `localhost`), same order (some clients sort, some don't). A mismatch silently splits your keyspace.
- Weight nodes by RAM if capacities differ; ketama supports weighting.

## Handle dead nodes as misses, not failover — DO
Prefer **Failure** mode: treat an unreachable node as a cache miss (fall through to the DB), leaving the ring intact. **Avoid auto-failover / auto-removal** — dropping a node rehashes its share onto neighbors (remapping far more keys than intended), and a node that flaps back serves stale values. Set short connect/read timeouts and pool connections (see lore/databases/connection-pooling.md); reconnecting per request leaks connections.

## Spread multiget, watch the fan-out — DO
A multiget (`get k1 k2 …` / meta `mg`) is split per destination node and issued in parallel — the round-trip win. But at scale every multiget touches *every* node (all-to-all fan-out), so p99 tracks the slowest node and one slow node stalls the batch. Keep batches bounded; co-locate related keys on one node via a shared hash prefix if your client supports key-group hashing.

## Size RAM around the slab allocator — DO
`-m` (MB, default 64) is carved into 1MB pages; each page joins a **slab class** of fixed chunks (growth factor `-f`, default 1.25). An item lands in the nearest-fitting class, wasting the slack. **Max item size is ~1MB** (`-I`, raise cautiously). Overhead is ~48–56 bytes/item plus full key length, so many tiny keys cost more than the values suggest.
- **Once a page joins a class it never moves** → *calcification*: an early skew toward one size starves other classes despite free-looking memory. Modern builds auto-repair via the slab rebalancer / `slab_automove` and segmented LRU (see lore/memcached/usage-and-slabs.md).

## DON'T
- DON'T change node count casually on a naive-hash client — you effectively cold-flush the cache (stampede risk; see lore/memcached/performance.md).
- DON'T run one giant node past one box's working set — shard across several; per-node RAM and a single event loop bound throughput.
- DON'T let one hot key/node dominate — replicate that key across nodes or add a client-local tier.

See lore/memcached/performance.md and lore/databases/resilience-and-observability.md for timeout/retry discipline.

## Sources
github.com/memcached/memcached/wiki/ConfiguringClient · wiki/ConfiguringServer · wiki/ReleaseNotes1645
