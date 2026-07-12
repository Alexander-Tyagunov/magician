# Cloud Firestore — Performance

Managed serverless (Native mode): no server to tune — perf is **key/index/query design**, bounded by write distribution and index fanout, not CPU. No client connection pool (SDK-managed) → lore/databases/connection-pooling.md N/A. Siblings (lore/firestore/): schema → data-model-and-documents.md, operators/indexes → queries-and-indexes.md, listeners → realtime-and-security.md.

## Levers, highest impact first
1. **Spread writes across the key range.** Hotspotting = high op rates to lexicographically close docs. Auto-IDs scatter; monotonic doc IDs or a monotonic *indexed* field (a timestamp) serialize onto one range, capping the **whole collection at 500 writes/s**.
2. **Ramp new traffic 500/50/5.** ≤500 ops/s to a new collection, +50% every 5 min; skipping it trips hotspot errors.
3. **Cut index fanout — the #1 write-latency cost.** Each indexed field adds index-entry writes per write. Exempt fields you never filter/sort on (single-field exemptions; disable Descending+Array scope): large strings, high-write sequential fields (dodge the 500/s cap), the TTL field, large arrays/maps nearing **40,000 index entries/doc**.
4. **Shard hot single docs.** A single doc's update rate is workload-dependent (load-test it); a global counter contends — split into N shards, sum on read.
5. **Page with cursors, project narrow.** `startAfter(...).limit(n)`, never `offset(n)` (skipped docs are read + billed). Keep docs small; reference past the 1 MiB cap; prefer async.
6. **Push work server-side.** `count()`/`sum()`/`avg()` return one value billed by index entries. Use BulkWriter (parallel, back-pressured) for large parallel writes; an atomic WriteBatch/transaction isn't capped at 500 writes — it's bounded by the 10 MiB request size.

## Anti-patterns
- Monotonic IDs / timestamp-ordered indexed key as the write hot spot.
- Indexes on fields you never query → fanout tax on every write.
- `offset` pagination; `orderBy` with no `limit`; fetching whole docs to count them.
- Listeners on huge or fast-churning result sets; with offline persistence on, one reconnecting after **30+ min** offline is rebilled as a fresh query — without persistence, any reconnect re-bills.
- Ignoring operator caps (`in`/`array-contains-any` ≤30, `not-in` ≤10, OR ≤30 disjunctions) — restructure, don't fan out reads.

## How to measure
- **Query Explain** — default returns `indexes_used` (plan only, 1 read); `analyze` executes, returning `executionStats` with `index_entries_scanned`/`documents_scanned` vs `resultsReturned`. Scanned ≫ returned = missing/weak index. Polled queries only.
- **Cloud Monitoring** — Document Reads/Writes/Deletes, Snapshot Listeners, `api/request_latencies`; sampled ~1/min.
- **Key Visualizer** — key-access heatmap; spot hot key ranges / write skew.
- **Cost is the profile.** Billed per doc read/write/delete + index entries read (1 read / ≤1000 entries; ≤1 range field ⇒ no index-entry charge) + stored bytes (incl. every index) + cross-region egress; min 1 read even on 0 results. Slow ≈ expensive; cut reads/index-entries. Timeout/retry → lore/databases/resilience-and-observability.md.

## Sources
- https://firebase.google.com/docs/firestore/best-practices
- https://firebase.google.com/docs/firestore/query-explain
- https://firebase.google.com/docs/firestore/monitor-usage
- https://firebase.google.com/docs/firestore/quotas
- https://firebase.google.com/docs/firestore/pricing
