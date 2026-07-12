# Amazon Neptune — Data loading & modeling

Managed AWS graph service; no version knob (verify limits). One **property-graph** store serves both **Gremlin and openCypher** — either CSV dialect is queryable by both; **RDF/SPARQL** is a separate triple store. Neptune auto-indexes; **no user-defined secondary indexes**.

## Bulk loader, not per-element writes
DON'T ingest with loops of `addV`/`addE`/`MERGE`/`INSERT` — use the **Loader** (`POST …:port/loader`). Prereqs: files in **S3 same-Region**, an **IAM role attached to the cluster** (S3 read/list; no SSE-C), and an **S3 VPC endpoint**. Files: **UTF-8**, per-file `.gz`/`.bz2` only. Formats: `csv` (Gremlin), `opencypher`, `ntriples`, `nquads`, `turtle`, `rdfxml`. Params: `source` (S3 prefix), `format`, `iamRoleArn`, `mode` (`AUTO|NEW|RESUME`), `failOnError` (default TRUE), `parallelism` (`LOW|MEDIUM|HIGH`(default)`|OVERSUBSCRIBE`), `updateSingleCardinalityProperties`, `queueRequest` (**64** FIFO).

## Property-graph CSV headers (exact)
Gremlin — vertex: `~id` (required, unique), `~label` (multi via `;`); edge: `~id`,`~from`,`~to`,`~label` (single). Properties `name:Type`; cardinality `name:Type(single|set)` (default **set**), arrays `name:Type[]`; **edge props single-valued only**. Typed: numeric/Bool/String/Date/Datetime.
openCypher — nodes: `:ID` (+optional `:ID(space)`), `:LABEL`; rels: `:START_ID`,`:END_ID` (required), `:TYPE`, `:ID` required unless `userProvidedEdgeIds=FALSE`. Auto-cast types (Date/Duration/Point) stored verbatim.

## Ordering, resume & duplicate gotchas
Loader loads **all vertices before edges** — put nodes and edges under **separate S3 prefixes**. `edgeOnlyLoad=TRUE` skips the classification scan but errors `FROM_OR_TO_VERTEX_ARE_MISSING` if endpoints are absent. `mode=RESUME/AUTO` skips already-loaded files (cheap retries). Duplicate node IDs **merge** (single-value props chosen non-deterministically). Supply explicit relationship `:ID`s — without them the loader can't dedupe edges or resume, and a reload **duplicates every edge**. `HIGH`/`OVERSUBSCRIBE` on openCypher can throw `LOAD_DATA_DEADLOCK` → lower `parallelism`.

## Modeling for traversal
Use meaningful **user-supplied string IDs** — `g.V('user_42')` is a direct auto-indexed lookup; ID-less property lookups scan. **Anchor every traversal on an indexed start**, then index-free adjacency costs O(edges-visited). **Specific edge labels** prune early. Break **supernodes** with intermediate/bucket nodes; move hot attributes off the hub. Model a value as an **edge** when you traverse it, a **property** when you won't.

## Runtime writes & Neptune Analytics
Live writes: batch `UNWIND` + `mergeV()`/`mergeE()` upserts (parameterized), single writer. **Neptune Analytics** loads via `CALL neptune.load({source,region,format,concurrency,failOnError})` using the **caller's IAM creds** (no `iamRoleArn`) and adds `parquet` (`columnar`); ~2.5 GB/request per 128 m-NCU (scales ~linearly). Reloading the same edge file duplicates edges.

Deep dive: lore/neptune/performance.md; lore/databases/{connection-pooling,resilience-and-observability}.md

## Sources
AWS docs (docs.aws.amazon.com): neptune/latest/userguide/{bulk-load, bulk-load-tutorial-format-gremlin, bulk-load-tutorial-format-opencypher, load-api-reference-load, bulk-load-optimize}.html; neptune-analytics/latest/userguide/batch-load.html
