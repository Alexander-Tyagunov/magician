# Cloud Firestore — deep dive

> On-demand companion to `lore/firestore.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Data model & documents](#data-model-and-documents) · [Queries & indexes](#queries-and-indexes) · [Realtime & Security](#realtime-and-security) · [Performance](#performance)

## Data model & documents <a id="data-model-and-documents"></a>

Managed serverless document DB (Google Cloud / Firebase); no user version — quotas/pricing/features evolve, verify live. Use **Native mode** (realtime listeners, collection-group + richer queries); Datastore mode is legacy. An Enterprise edition (MongoDB-compatible) also exists.

### Documents, collections, subcollections
A **document** is a fields→values record (JSON-like plus native types), the unit of storage and atomicity. Documents live only in **collections** (which hold documents and nothing else). A **subcollection** hangs off a document: `users/{uid}/orders/{orderId}` — paths alternate collection/document. Both are created implicitly on first write and vanish when empty; no CREATE/DROP, no schema.

Subcollections aren't fetched with the parent, and deleting a parent doesn't delete them (orphans persist — delete recursively). A **collection-group query** hits the same subcollection ID across all parents (needs a collection-group index).

### Field types & sort order
Types: null, boolean, integer & double (64-bit; sorted interleaved, `NaN` < `-Infinity`), timestamp (µs), string (UTF-8; queries compare first 1,500 bytes), bytes, reference, geopoint, array, vector, map. Mixed-type sort follows that order. Arrays compare element-wise (shorter first) and can't nest arrays; maps compare key-then-value.

### Model for the query, not for normalization
No JOINs — pick per access pattern:
- **Map / nested object**: small, bounded, read + updated with the parent (address, settings); counts against its 1 MiB + index entries.
- **Array**: small `array-contains` sets (tags); unbounded arrays bloat the doc and near the 40,000-index-entry/doc cap.
- **Subcollection**: large/unbounded children queried on their own; parent stays small, children paginate independently.
- **Top-level collection + reference/duplicated key**: many-to-many or globally-queried children; use collection-group queries or denormalize the key + fan-out updates.

Range/inequality filters may span **up to 10 fields** per query, each also in `orderBy`; composite queries need composite indexes, and index-exempted fields can't be filtered or ordered.

### Document ID / key design — avoid hotspots
Prefer **auto-IDs** (scatter-distributed, no write hotspot). Never use monotonic IDs (`cust1, cust2…`) or a high-rate monotonic indexed field (raw timestamp): an ascending-indexed sequential field caps the collection near **500 writes/s**. Sustained single-document writes are limited (~1/s) — shard hot counters, reverse/shard sequential keys, and ramp new-collection or narrow-range traffic via **500/50/5** (start 500 ops/s, +50%/5 min). IDs: UTF-8 ≤ 1,500 bytes, no `/`, not `.`/`..`, not matching `__.*__`.

### Limits that shape schema
Document ≤ **1 MiB**; field nesting ≤ 20; subcollection depth ≤ 100; ≤ 40,000 index entries/doc; field name/path and indexed values cap at 1,500 bytes. A write rewrites the doc + all its index entries across a replica quorum, so wide docs and many indexes raise write latency — **exempt from indexing** large or never-filtered fields.

### Cost-aware modeling
Billed on doc reads/writes/deletes, index-entry reads, stored bytes, and egress; a query bills one read **per returned document** (min one, even for zero results). Paginate with cursors (`startAt`), never offsets (skipped docs are billed); each index adds storage + write cost — index only what you query. See lore/deep/firestore.md#performance.

### Sources
- https://firebase.google.com/docs/firestore/data-model
- https://firebase.google.com/docs/firestore/manage-data/data-types
- https://firebase.google.com/docs/firestore/quotas
- https://firebase.google.com/docs/firestore/best-practices
- https://firebase.google.com/docs/firestore/pricing

## Queries & indexes <a id="queries-and-indexes"></a>

Managed serverless document DB; no version — verify live. **Native mode** (real-time listeners, mobile/web SDKs) vs *Datastore mode* (server-only GQL API). **No server-side JOINs**; Firestore *refuses* any query it can't index (never a silent scan). Schema follows the access pattern, not normalization.

### Operators & compound-query rules
Filters: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not-in`, `array-contains`, `array-contains-any`.
- `in` / `array-contains-any`: **up to 30** values. `not-in`: **up to 10**; can't combine with `!=`, excludes docs where the field is absent, `null` never matches.
- OR queries expand to disjunctive normal form, capped at **30 disjunctions** (fixed) — `in` is itself a disjunction, so nesting multiplies the count.
- Multiple equality (`==`/`in`) AND is fine. Adding any range/inequality (`<,<=,>,>=,!=`) across fields needs a **composite index**; range/inequality is allowed on **up to 10** fields per query.
- `orderBy` picks the index (its prefix must match). **First `orderBy` = the first range/inequality field**; order by *decreasing selectivity* (tightest first) so the leftmost index range narrows the scan.

### Automatic (single-field) vs manual (composite) indexes
- **Automatic** (per field, on by default): asc+desc for scalars; asc+desc+`array-contains` for arrays; maps indexed recursively.
- **Manual composite**: sorted mapping over an *ordered* field list for multi-field queries. Not auto-created — a missing one throws `FAILED_PRECONDITION` with a **console link to the exact index**; also declared in `firestore.indexes.json` (CLI)/Terraform. Modes: ascending, descending, array-contains, vector (`FindNearest`).
- **Index merging**: Firestore zig-zag-merges single-field indexes for some equality-only multi-field queries without a composite (`in`/`==` share one). It adds latency — for `array-contains(-any)` + other clauses, build the composite.

### Exemptions & limits
Single-field **exemptions** override the DB-wide auto-index setting (`*` scopes a collection group); exempting fields you never filter/sort cuts storage and write latency.

| Limit | Value |
|---|---|
| Composite indexes / DB | 200 (no billing) · **1000** (billing) |
| Single-field configs / DB | 200 · **1000** |
| Index entries / document | **40,000** |
| One entry / entries-sum per doc | 7.5 KiB / 8 MiB |
| Indexed value size | 1500 bytes (larger → truncated, inconsistent) |
| Fields / composite · range fields / query | 100 · 10 |

### Billing & the write-side cost of indexes
Reads bill **per doc returned + per batch of ≤1000 index entries**; a query with ≤1 range field isn't charged for them. Every query bills **≥1 read even at 0 results**; `count()`/aggregations bill 1 read per 1000 entries (min 1). `offset` still *reads and bills* skipped docs — **paginate with cursors** (`startAfter`/`endBefore`). Storage bills data **+ index overhead** (automatic + composite).
Writes fan out to every affected index — more indexes = higher write latency/cost. An indexed **monotonic value** (timestamp, counter) or **sequential doc IDs** make a hot index range capping the collection near **500 writes/s** — exempt the field if unqueried, prefer auto IDs (scatter algorithm), and ramp new collections by the **500/50/5 rule** (500 ops/s, +50%/5 min). See lore/deep/firestore.md#performance.

### Sources
- cloud.google.com/firestore/native/docs/query-data/queries (operators; in/not-in 30/10; 30 disjunctions)
- .../query-data/multiple-range-fields (multi-field range ≤10; orderBy/selectivity)
- firebase.google.com/docs/firestore/query-data/index-overview (automatic vs manual; modes; merging)
- .../firestore/quotas (limits) · /pricing · /best-practices (index-entry billing; cursors; 500/50/5)

## Realtime & Security <a id="realtime-and-security"></a>

Managed serverless doc DB. **Native mode** only — **Datastore mode** is server-side (IAM-gated), no listeners/offline/Rules, mode fixed at creation.

### Realtime listeners — `onSnapshot`
- Fires **immediately** with the current set, then on every change — no polling. Doc or query both stream.
- **Latency compensation:** local writes fire listeners *before* the backend confirms — read `metadata.hasPendingWrites` and `.fromCache` to tell optimistic local state from server-acked. Metadata-only changes don't re-fire without `includeMetadataChanges`.
- Iterate `snapshot.docChanges()` for `added`/`modified`/`removed` deltas, not re-diffing — with per-doc `oldIndex`/`newIndex` for ordered UIs.
- **Always detach:** call the returned unsubscribe fn on teardown, or leak connections + billing reads.
- **Cost:** billed **one read per document each time it's added or changed** (initial load = one per doc). Offline persistence: a disconnect **>30 min** re-charges the full set on reconnect; without it, every reconnect re-charges. Keep result sets tight (`limit`, narrow `where`).

### Security Rules — the credential gate
Rules gate **client SDKs (mobile/web) and REST/RPC calls authenticated with a Firebase Auth ID token**; Admin/server SDKs — and REST/RPC using service-account/OAuth credentials — **bypass all Rules** (govern with IAM). The **credential** decides, not the protocol. Start `rules_version = '2';` — v2 makes `{x=**}` match zero-or-more segments, **required for collection-group queries**.

```
match /databases/{database}/documents {
  match /stories/{id} {
    allow get: if resource.data.public || request.auth.uid == resource.data.owner;
    allow list: if request.query.limit <= 50;
    allow create: if request.resource.data.owner == request.auth.uid;
    allow update, delete: if request.auth.uid == resource.data.owner;
  } }
```
- `read`→`get`/`list`; `write`→`create`/`update`/`delete`. `resource.data` = stored doc; `request.resource.data` = incoming write; `request.auth` = caller.
- Rules are **non-cascading** — subcollections need their own `match` (or a recursive `{p=**}`).
- Cross-doc `get()`/`exists()`/`getAfter()` cap at **10 access calls** per single-doc/query request (**20** for multi-doc reads, txns, batches); also `match` depth 10, ≤1000 expressions, 256 KB source.

### Rules are NOT filters — the #1 gotcha
A query is **all-or-nothing**: if it *could* return a doc the caller can't read, the **whole request fails** (permission denied) — Rules never silently drop rows. The client must **constrain the query to prove** it only touches allowed docs, e.g. `where('public','==',true)` to satisfy a `public == true` list rule. Applies to `list`/queries, not single-doc `get`; mirror each list rule with a query constraint.

### DON'T
- DON'T treat Rules as validation-only — they're your **sole** authz layer for client access; `if true` exposes the whole collection.
- DON'T leave listeners attached across navigation or subscribe to unbounded collections — memory + read-cost leak.
- DON'T assume an offline client sees fresh data — cached snapshots carry `fromCache: true`, reflecting last sync.

### Sources
- https://firebase.google.com/docs/firestore/query-data/listen
- https://firebase.google.com/docs/firestore/security/rules-structure
- https://firebase.google.com/docs/firestore/security/rules-query
- https://firebase.google.com/docs/firestore/use-rest-api

## Performance <a id="performance"></a>

Managed serverless (Native mode): no server to tune — perf is **key/index/query design**, bounded by write distribution and index fanout, not CPU. No client connection pool (SDK-managed) → lore/deep/databases.md#connection-pooling N/A. Siblings (lore/deep/firestore.md): schema → lore/deep/firestore.md#data-model-and-documents, operators/indexes → lore/deep/firestore.md#queries-and-indexes, listeners → lore/deep/firestore.md#realtime-and-security.

### Levers, highest impact first
1. **Spread writes across the key range.** Hotspotting = high op rates to lexicographically close docs. Auto-IDs scatter; monotonic doc IDs or a monotonic *indexed* field (a timestamp) serialize onto one range, capping the **whole collection at 500 writes/s**.
2. **Ramp new traffic 500/50/5.** ≤500 ops/s to a new collection, +50% every 5 min; skipping it trips hotspot errors.
3. **Cut index fanout — the #1 write-latency cost.** Each indexed field adds index-entry writes per write. Exempt fields you never filter/sort on (single-field exemptions; disable Descending+Array scope): large strings, high-write sequential fields (dodge the 500/s cap), the TTL field, large arrays/maps nearing **40,000 index entries/doc**.
4. **Shard hot single docs.** A single doc's update rate is workload-dependent (load-test it); a global counter contends — split into N shards, sum on read.
5. **Page with cursors, project narrow.** `startAfter(...).limit(n)`, never `offset(n)` (skipped docs are read + billed). Keep docs small; reference past the 1 MiB cap; prefer async.
6. **Push work server-side.** `count()`/`sum()`/`avg()` return one value billed by index entries. Use BulkWriter (parallel, back-pressured) for large parallel writes; an atomic WriteBatch/transaction isn't capped at 500 writes — it's bounded by the 10 MiB request size.

### Anti-patterns
- Monotonic IDs / timestamp-ordered indexed key as the write hot spot.
- Indexes on fields you never query → fanout tax on every write.
- `offset` pagination; `orderBy` with no `limit`; fetching whole docs to count them.
- Listeners on huge or fast-churning result sets; with offline persistence on, one reconnecting after **30+ min** offline is rebilled as a fresh query — without persistence, any reconnect re-bills.
- Ignoring operator caps (`in`/`array-contains-any` ≤30, `not-in` ≤10, OR ≤30 disjunctions) — restructure, don't fan out reads.

### How to measure
- **Query Explain** — default returns `indexes_used` (plan only, 1 read); `analyze` executes, returning `executionStats` with `index_entries_scanned`/`documents_scanned` vs `resultsReturned`. Scanned ≫ returned = missing/weak index. Polled queries only.
- **Cloud Monitoring** — Document Reads/Writes/Deletes, Snapshot Listeners, `api/request_latencies`; sampled ~1/min.
- **Key Visualizer** — key-access heatmap; spot hot key ranges / write skew.
- **Cost is the profile.** Billed per doc read/write/delete + index entries read (1 read / ≤1000 entries; ≤1 range field ⇒ no index-entry charge) + stored bytes (incl. every index) + cross-region egress; min 1 read even on 0 results. Slow ≈ expensive; cut reads/index-entries. Timeout/retry → lore/deep/databases.md#resilience-and-observability.

### Sources
- https://firebase.google.com/docs/firestore/best-practices
- https://firebase.google.com/docs/firestore/query-explain
- https://firebase.google.com/docs/firestore/monitor-usage
- https://firebase.google.com/docs/firestore/quotas
- https://firebase.google.com/docs/firestore/pricing
