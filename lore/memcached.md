# Memcached — core digest
Version: 1.6.45 (stable; BSD-3-Clause). Multithreaded in-memory cache — no persistence, no clustering (clients shard), slab+LRU, ~1MB item cap.

DO cap RAM with `-m` (default 64MB); it auto-evicts LRU as slabs fill — size to your working set.
DO cut round-trips: multiget reads, pipeline writes, pool connections (`-c` 1024 default).
DO keep keys <250 bytes and values under the 1MB cap (`-I` raises it; big/hot items waste slabs).
DO shard client-side with consistent hashing (ketama) — no clustering; a new node remaps few keys.
DO use `gets`+`cas` for atomic read-modify-write and `incr`/`decr` for counters.
DO run cache-aside with TTLs; block stampedes with an `add`-lock or soft-TTL.
DO version-prefix keys to invalidate groups; every value is disposable.

DON'T test hits by truthiness — stored 0/""/false is a valid hit; check existence, not value.
DON'T pack whole collections into one key — split it; oversized items evict and fragment slabs.
DON'T assume durability or HA — restart/eviction loses data; rebuild from source of truth.
DON'T over-thread (`-t`, default 4); very high values run slower.

Deep dive when writing non-trivial Memcached — read lore/memcached/{usage-and-slabs,scaling-and-hashing,performance}.md

## Sources
- https://docs.memcached.org/ — server guide, protocols
- https://github.com/memcached/memcached/wiki — ConfiguringServer, ProgrammingTricks
- https://memcached.org/ — releases
