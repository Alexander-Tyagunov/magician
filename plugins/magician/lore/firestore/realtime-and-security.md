# Cloud Firestore — Realtime & Security

Managed serverless doc DB. **Native mode** only — **Datastore mode** is server-side (IAM-gated), no listeners/offline/Rules, mode fixed at creation.

## Realtime listeners — `onSnapshot`
- Fires **immediately** with the current set, then on every change — no polling. Doc or query both stream.
- **Latency compensation:** local writes fire listeners *before* the backend confirms — read `metadata.hasPendingWrites` and `.fromCache` to tell optimistic local state from server-acked. Metadata-only changes don't re-fire without `includeMetadataChanges`.
- Iterate `snapshot.docChanges()` for `added`/`modified`/`removed` deltas, not re-diffing — with per-doc `oldIndex`/`newIndex` for ordered UIs.
- **Always detach:** call the returned unsubscribe fn on teardown, or leak connections + billing reads.
- **Cost:** billed **one read per document each time it's added or changed** (initial load = one per doc). Offline persistence: a disconnect **>30 min** re-charges the full set on reconnect; without it, every reconnect re-charges. Keep result sets tight (`limit`, narrow `where`).

## Security Rules — the credential gate
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

## Rules are NOT filters — the #1 gotcha
A query is **all-or-nothing**: if it *could* return a doc the caller can't read, the **whole request fails** (permission denied) — Rules never silently drop rows. The client must **constrain the query to prove** it only touches allowed docs, e.g. `where('public','==',true)` to satisfy a `public == true` list rule. Applies to `list`/queries, not single-doc `get`; mirror each list rule with a query constraint.

## DON'T
- DON'T treat Rules as validation-only — they're your **sole** authz layer for client access; `if true` exposes the whole collection.
- DON'T leave listeners attached across navigation or subscribe to unbounded collections — memory + read-cost leak.
- DON'T assume an offline client sees fresh data — cached snapshots carry `fromCache: true`, reflecting last sync.

## Sources
- https://firebase.google.com/docs/firestore/query-data/listen
- https://firebase.google.com/docs/firestore/security/rules-structure
- https://firebase.google.com/docs/firestore/security/rules-query
- https://firebase.google.com/docs/firestore/use-rest-api
