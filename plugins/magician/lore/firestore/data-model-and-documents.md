# Cloud Firestore — Data model & documents

Managed serverless document DB (Google Cloud / Firebase); no user version — quotas/pricing/features evolve, verify live. Use **Native mode** (realtime listeners, collection-group + richer queries); Datastore mode is legacy. An Enterprise edition (MongoDB-compatible) also exists.

## Documents, collections, subcollections
A **document** is a fields→values record (JSON-like plus native types), the unit of storage and atomicity. Documents live only in **collections** (which hold documents and nothing else). A **subcollection** hangs off a document: `users/{uid}/orders/{orderId}` — paths alternate collection/document. Both are created implicitly on first write and vanish when empty; no CREATE/DROP, no schema.

Subcollections aren't fetched with the parent, and deleting a parent doesn't delete them (orphans persist — delete recursively). A **collection-group query** hits the same subcollection ID across all parents (needs a collection-group index).

## Field types & sort order
Types: null, boolean, integer & double (64-bit; sorted interleaved, `NaN` < `-Infinity`), timestamp (µs), string (UTF-8; queries compare first 1,500 bytes), bytes, reference, geopoint, array, vector, map. Mixed-type sort follows that order. Arrays compare element-wise (shorter first) and can't nest arrays; maps compare key-then-value.

## Model for the query, not for normalization
No JOINs — pick per access pattern:
- **Map / nested object**: small, bounded, read + updated with the parent (address, settings); counts against its 1 MiB + index entries.
- **Array**: small `array-contains` sets (tags); unbounded arrays bloat the doc and near the 40,000-index-entry/doc cap.
- **Subcollection**: large/unbounded children queried on their own; parent stays small, children paginate independently.
- **Top-level collection + reference/duplicated key**: many-to-many or globally-queried children; use collection-group queries or denormalize the key + fan-out updates.

Range/inequality filters may span **up to 10 fields** per query, each also in `orderBy`; composite queries need composite indexes, and index-exempted fields can't be filtered or ordered.

## Document ID / key design — avoid hotspots
Prefer **auto-IDs** (scatter-distributed, no write hotspot). Never use monotonic IDs (`cust1, cust2…`) or a high-rate monotonic indexed field (raw timestamp): an ascending-indexed sequential field caps the collection near **500 writes/s**. Sustained single-document writes are limited (~1/s) — shard hot counters, reverse/shard sequential keys, and ramp new-collection or narrow-range traffic via **500/50/5** (start 500 ops/s, +50%/5 min). IDs: UTF-8 ≤ 1,500 bytes, no `/`, not `.`/`..`, not matching `__.*__`.

## Limits that shape schema
Document ≤ **1 MiB**; field nesting ≤ 20; subcollection depth ≤ 100; ≤ 40,000 index entries/doc; field name/path and indexed values cap at 1,500 bytes. A write rewrites the doc + all its index entries across a replica quorum, so wide docs and many indexes raise write latency — **exempt from indexing** large or never-filtered fields.

## Cost-aware modeling
Billed on doc reads/writes/deletes, index-entry reads, stored bytes, and egress; a query bills one read **per returned document** (min one, even for zero results). Paginate with cursors (`startAt`), never offsets (skipped docs are billed); each index adds storage + write cost — index only what you query. See performance.md.

## Sources
- https://firebase.google.com/docs/firestore/data-model
- https://firebase.google.com/docs/firestore/manage-data/data-types
- https://firebase.google.com/docs/firestore/quotas
- https://firebase.google.com/docs/firestore/best-practices
- https://firebase.google.com/docs/firestore/pricing
