# Cloud Firestore — Queries & indexes

Managed serverless document DB; no version — verify live. **Native mode** (real-time listeners, mobile/web SDKs) vs *Datastore mode* (server-only GQL API). **No server-side JOINs**; Firestore *refuses* any query it can't index (never a silent scan). Schema follows the access pattern, not normalization.

## Operators & compound-query rules
Filters: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not-in`, `array-contains`, `array-contains-any`.
- `in` / `array-contains-any`: **up to 30** values. `not-in`: **up to 10**; can't combine with `!=`, excludes docs where the field is absent, `null` never matches.
- OR queries expand to disjunctive normal form, capped at **30 disjunctions** (fixed) — `in` is itself a disjunction, so nesting multiplies the count.
- Multiple equality (`==`/`in`) AND is fine. Adding any range/inequality (`<,<=,>,>=,!=`) across fields needs a **composite index**; range/inequality is allowed on **up to 10** fields per query.
- `orderBy` picks the index (its prefix must match). **First `orderBy` = the first range/inequality field**; order by *decreasing selectivity* (tightest first) so the leftmost index range narrows the scan.

## Automatic (single-field) vs manual (composite) indexes
- **Automatic** (per field, on by default): asc+desc for scalars; asc+desc+`array-contains` for arrays; maps indexed recursively.
- **Manual composite**: sorted mapping over an *ordered* field list for multi-field queries. Not auto-created — a missing one throws `FAILED_PRECONDITION` with a **console link to the exact index**; also declared in `firestore.indexes.json` (CLI)/Terraform. Modes: ascending, descending, array-contains, vector (`FindNearest`).
- **Index merging**: Firestore zig-zag-merges single-field indexes for some equality-only multi-field queries without a composite (`in`/`==` share one). It adds latency — for `array-contains(-any)` + other clauses, build the composite.

## Exemptions & limits
Single-field **exemptions** override the DB-wide auto-index setting (`*` scopes a collection group); exempting fields you never filter/sort cuts storage and write latency.

| Limit | Value |
|---|---|
| Composite indexes / DB | 200 (no billing) · **1000** (billing) |
| Single-field configs / DB | 200 · **1000** |
| Index entries / document | **40,000** |
| One entry / entries-sum per doc | 7.5 KiB / 8 MiB |
| Indexed value size | 1500 bytes (larger → truncated, inconsistent) |
| Fields / composite · range fields / query | 100 · 10 |

## Billing & the write-side cost of indexes
Reads bill **per doc returned + per batch of ≤1000 index entries**; a query with ≤1 range field isn't charged for them. Every query bills **≥1 read even at 0 results**; `count()`/aggregations bill 1 read per 1000 entries (min 1). `offset` still *reads and bills* skipped docs — **paginate with cursors** (`startAfter`/`endBefore`). Storage bills data **+ index overhead** (automatic + composite).
Writes fan out to every affected index — more indexes = higher write latency/cost. An indexed **monotonic value** (timestamp, counter) or **sequential doc IDs** make a hot index range capping the collection near **500 writes/s** — exempt the field if unqueried, prefer auto IDs (scatter algorithm), and ramp new collections by the **500/50/5 rule** (500 ops/s, +50%/5 min). See performance.md.

## Sources
- cloud.google.com/firestore/native/docs/query-data/queries (operators; in/not-in 30/10; 30 disjunctions)
- .../query-data/multiple-range-fields (multi-field range ≤10; orderBy/selectivity)
- firebase.google.com/docs/firestore/query-data/index-overview (automatic vs manual; modes; merging)
- .../firestore/quotas (limits) · /pricing · /best-practices (index-entry billing; cursors; 500/50/5)
