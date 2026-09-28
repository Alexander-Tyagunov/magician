# mongoose — deep dive

> On-demand companion to `lore/mongoose.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Schemas & models](#schemas-and-models) · [Queries & pitfalls](#queries-and-pitfalls)

## Schemas & models <a id="schemas-and-models"></a>

Mongoose is a JS/Node ODM for MongoDB — distinct from the JVM `orm` lore. Assumes JS/TS/Node lore exists separately. Facts verified against mongoosejs.com (v9 docs, with 7/8 notes) 2026-07. Mongoose 7 and 8 share most of this surface; version-specific deltas are called out.

### Schema definition

DO
- Define with `new Schema({...})`; `title: String` is shorthand for `{ type: String }`.
- Use built-in SchemaTypes: `String, Number, Date, Buffer, Boolean, Mixed, ObjectId, Array, Decimal128, Map, UUID, Double, Int32`.
- Use `Decimal128` for money — never `Number` (float rounding).
- Add validation inline: `{ type: String, required: true, enum: [...], min, max, match, minlength, maxlength, validate }`.
- Set `timestamps: true` to auto-manage `createdAt`/`updatedAt`.
- Turn off `_id` on subdocs you don't address directly: `{ _id: false }`.

DON'T
- Don't use arrow functions for `methods`, `statics`, `virtuals`, or hooks — they break `this` binding.
- Don't rely on `Mixed`/`{}` for structured data — it disables casting and change tracking (must `markModified()`).
- Don't assume nested POJOs without a `type` create a queryable path — only leaves get paths.

### strict / strictQuery (version-sensitive)

- `strict: true` (default) drops fields not in the schema on writes. `'throw'` errors instead. Keep it on.
- `strictQuery` is a **separate** option applying only to query filters. **Default `false` in Mongoose 7 and 8.**
  - Consequence: `Model.find({ notInSchema: 1 })` is NOT stripped; unknown paths pass through to Mongo (returns `[]`, not all docs).
- DO set `mongoose.set('strictQuery', true)` app-wide if you want unknown filter keys stripped.

### Types + validation

DO
- Validation runs on `save()` and (by default) on `validateBeforeSave`. Update ops (`updateOne`, `findOneAndUpdate`) skip validators unless `{ runValidators: true }`.
- Add `{ runValidators: true }` to update calls when you need schema validation on updates.

DON'T
- Don't assume `findOneAndUpdate` validates or runs `save` hooks — it doesn't by default.

### Indexes

DO
- Path-level: `{ index: true, unique: true, sparse: true }`. Compound: `schema.index({ a: 1, b: -1 })`.
- `unique` is an index hint, NOT a validator — enforce uniqueness at the DB level and handle E11000 duplicate-key errors.
- In production set `autoIndex: false` (schema or `mongoose.set('autoIndex', false)`) and build indexes deliberately (`Model.syncIndexes()` / `createIndexes()` in a migration).

DON'T
- Don't leave `autoIndex: true` on large prod collections — Mongoose calls `createIndex` for every index on startup, blocking/foregrounding index builds.
- Don't expect `unique` to prevent races without the DB index actually present.

### refs + populate() (the N+1 cost)

`ref` names the model for population; store its `_id`. `populate()` is NOT a SQL join — it runs **separate query/queries**.

DO
- `Model.find().populate('author', 'name email')` — always project fields to limit payload.
- Chain for multiple paths: `.populate('author').populate('fans')`. Deep: `.populate({ path: 'friends', populate: { path: 'friends' } })`.
- Use `refPath` for polymorphic refs (model name lives in a sibling field).
- Virtual populate for reverse relations without storing arrays:
  ```js
  AuthorSchema.virtual('posts', { ref: 'Post', localField: '_id', foreignField: 'author' });
  ```
  Add `count: true` for counts, `match` to filter.

DON'T
- Don't populate inside a loop over documents — that's the N+1 trap. Populate the whole result set in one call.
- Don't use `perDocumentLimit` casually: it fixes per-doc `limit` correctness but runs a **separate query per parent doc** (explicit N+1). Plain `limit` on populate is applied as `numDocs * limit`, so it does NOT limit per document.
- Don't reach for populate when an embedded subdocument fits the access pattern.

### Subdocuments vs refs

DO
- Embed (subdocuments) when child data is always loaded with the parent, bounded in size, and owned by it — one read, no populate.
- Reference when data is shared, unbounded, or queried independently.

DON'T
- Don't embed unbounded arrays (comments, events) — you hit the 16MB doc cap and rewrite the whole doc on every push.

### lean() — read-only perf

DO
- Add `.lean()` on read-only paths (GET handlers, reports). Returns plain POJOs, skipping Mongoose document hydration/change-tracking — markedly faster, ~3x less Node memory.
- Combine with populate: `.populate(...).lean()` — populated docs also become POJOs.

DON'T
- Don't `.lean()` when you need `save()`, validators, getters/setters, or virtuals — none run on lean results.
- Don't expect virtuals/getters on lean docs without the `mongoose-lean-virtuals` / `mongoose-lean-getters` plugins.

### Virtuals

- Computed, non-persisted, non-queryable. `schema.virtual('fullName').get(fn).set(fn)`.
- Excluded from `toJSON()`/`toObject()` by default — enable with `{ toJSON: { virtuals: true }, toObject: { virtuals: true } }` (needed for API responses).

### Middleware / hooks

DO
- `schema.pre('save', fn)` / `post('save', fn)` for document lifecycle.
- Know the split: `save`/`validate`/`remove` are document middleware; `find`/`findOne`/`findOneAndUpdate`/`updateOne`/`deleteOne` default to **query** middleware (`this` is the Query, not the doc).
- Mongoose 7+ removed `remove()` — rewrite `pre('remove')` as `pre('deleteOne', { document: true, query: false }, fn)`.

DON'T
- Don't expect `save` hooks to fire on `updateOne`/`findOneAndUpdate` — they don't. Add explicit `pre('findOneAndUpdate')` if needed.
- Don't put slow/external calls in hooks without understanding they run on every op.

### Security — query-selector injection (NON-NEGOTIABLE)

Mongoose parameterizes normal writes, but **untrusted objects in filters are the injection surface.** A body like `{ pwd: { $ne: null } }` or `{ $where: '...' }` spliced into a filter bypasses auth / runs JS on the server.

DO
- Enable sanitization globally: `mongoose.set('sanitizeFilter', true)` (default `false`), or per-query `.setOptions({ sanitizeFilter: true })`. It wraps any nested `$`-prefixed object in `$eq`, forcing literal equality.
- Cast/validate untrusted input to expected scalar types before it ever reaches a filter (`String(req.query.id)`).
- Use `mongoose.trusted({...})` to whitelist operators you intentionally allow through sanitization.

DON'T
- Don't spread `req.query`/`req.body` directly into `.find()` / `.findOne()` — that is the vulnerability.
- Don't enable `$where` (server-side JS) on filters; never pass user strings to it.
- Don't rely on `strictQuery` for security — it strips unknown *paths*, not malicious *operators* on known paths.

### Sources
- https://mongoosejs.com/docs/guide.html
- https://mongoosejs.com/docs/queries.html
- https://mongoosejs.com/docs/populate.html
- https://mongoosejs.com/docs/tutorials/lean.html
- https://mongoosejs.com/docs/api/mongoose.html
- https://mongoosejs.com/docs/migrating_to_7.html
- https://mongoosejs.com/docs/migrating_to_8.html

## Queries & pitfalls <a id="queries-and-pitfalls"></a>

JS/Node ODM for MongoDB. Distinct from the JVM `orm` lore. Assumes JS/TS/Node lore exists separately.
Versions in scope: **Mongoose 7 / 8 / 9** (9 is current, docs at v9.x). State versions; give fallbacks.
Facts below verified against mongoosejs.com + context7 (2026-07). Verify version-specific claims before asserting.

Query objects are **thenables, not Promises**. `await` or `.exec()` runs them. Re-`.then()` throws `Query was already executed`. Never call `.then()` twice / mix `await` with `.exec()` on the same query.

---

### Query building

DO
- Build with either the POJO filter or the chainable builder — they're equivalent:
  ```js
  await Person.find({ age: { $gte: 18 } }).sort({ age: -1 }).limit(10);
  await Person.where('age').gte(18).sort('-age').limit(10).exec();
  ```
- Reach for statics that return Query objects: `find`, `findOne`, `findById`, `findOneAndUpdate`, `updateMany`, `countDocuments`, etc.
- Prefer plain queries over `aggregate()`. Aggregation results are **not hydrated** (POJOs, no getters/virtuals) and pipeline stages are **not cast** — casting types is on you.
- Set `strictQuery` intentionally. Mongoose **7+ defaults `strictQuery` to `false`** → unknown filter paths are passed through, not stripped. `mongoose.set('strictQuery', true)` to drop paths not in schema.

DON'T
- Don't send an empty/undefined filter by accident: `Model.find({})` / `Model.find(undefined)` returns **every document**. Guard filters built from optional input.
- Don't rely on `deleteMany()` with a loose filter — same empty-filter footgun deletes the collection.

---

### lean()

`.lean()` skips document hydration → returns POJOs. ~3x smaller in process memory; **network/JSON payload is identical**.

DO
- Use on read-only / GET paths: `const users = await User.find().lean();`
- Propagates through `populate()` (parent + populated docs both lean).

DON'T
- Don't `.lean()` when you need `save()`, validation, casting, getters/setters, or virtuals — none run. `doc instanceof mongoose.Document` is `false`.
- Don't expect virtuals/getters silently — restore via `mongoose-lean-virtuals` / `mongoose-lean-getters` / `mongoose-lean-defaults` if needed.
- BigInt: Mongo longs become JS `number` under lean. Add `.setOptions({ useBigInt64: true })` when precision matters.

---

### Projection

DO
- Select minimal fields: `.select('name email')` or `.select({ name: 1, email: 1 })` (2nd arg of `find` also works).
- Exclude with `-`: `.select('-password')`. Force-include a default-deselected path with `+`: `.select('+password')`.
- A projection must be **all-inclusive or all-exclusive** (except excluding `_id`). Mixing throws.
- Passing user input to `.select()`? Add **`.sanitizeProjection(true)`** — enforces numeric projection values and blocks `+` overriding `select: false` paths.

DON'T
- Don't ship `select: false` secrets by letting untrusted `+field` re-include them.

---

### Pagination

DO
- Small offsets: `.skip(n).limit(m).sort({ _id: 1 })`. **Always sort** — order is otherwise undefined.
- Large datasets: prefer **keyset / range pagination** over skip (skip scans+discards `n` docs, O(n)):
  ```js
  await Post.find({ _id: { $gt: lastId } }).sort({ _id: 1 }).limit(20);
  ```
- Streaming large result sets: `Query#cursor()` or `for await (const doc of Model.find())` — don't load everything into memory.

DON'T
- Don't `.skip()`/`.limit()` on `.distinct()` (unsupported).
- Don't leave cursors idle: default cursor timeout ~10 min (`MongoServerError: cursor id not found`); sessions still idle-timeout at 30 min even with `.addCursorFlag('noCursorTimeout', true)`.

---

### Transactions (sessions)

**Requires a replica set or sharded cluster.** A standalone `mongod` cannot run transactions (the driver errors). Use a single-node replica set locally.

DO
- Prefer the managed helper — it commits on success, aborts on throw, and **retries transient errors**:
  ```js
  const session = await mongoose.startSession();
  await session.withTransaction(async () => {
    await Customer.create([{ name: 'Test' }], { session }); // array form!
    await Account.updateOne({ _id }, { $inc: { bal: -10 } }, { session });
  });
  await session.endSession();
  ```
- Pass the session to **every** op: `.session(session)` on queries, `{ session }` option on writes. Ops without it run outside the txn and won't see uncommitted data.
- `Model.create` inside a txn must use the **array form** with `{ session }`: `Model.create([doc], { session })`.
- Want automatic session propagation? `Connection#transaction()` integrates change-tracking (resets `doc.isNew`/modified paths on abort). `mongoose.set('transactionAsyncLocalStorage', true)` (**Mongoose 8.4+**) auto-attaches the session so you can drop the per-op `{ session }`.
- Docs loaded with a session reuse it on `save()`; inspect/set via `doc.$session()`.

DON'T
- Don't parallelize inside a transaction. `Promise.all` / `allSettled` / `race` on one session is **undefined behavior**.
- Don't nest transactions on the same session → `Transaction already in progress`.
- Don't forget `endSession()` (leaks server sessions).

---

### SECURITY — query-selector / operator injection (non-negotiable)

NoSQL injection is real. Mongoose filters are objects, so an attacker who controls a value that you spread into a filter can inject **operators**: `{ $gt: '' }` matches everything, `{ $ne: null }` bypasses equality, `$where`/`$expr`/`$function` run **arbitrary server-side JS**.

DON'T
- **Never** pass an untrusted object straight into a filter:
  ```js
  await User.find(req.query);                       // ✗ ?age[$gt]= dumps table
  await User.findOne({ user, pwd: req.body.pwd });  // ✗ pwd={$ne:null} = auth bypass
  ```
- Never build `$where` from user input. Avoid `$where` entirely — it's slow and JS-eval'd; every operator has a safer equivalent (`$lt`, `$expr`, …).

DO
- **Cast/validate every input** to its expected primitive (zod/joi, or coerce: `Number(x)`, `String(x)`, `new mongoose.Types.ObjectId(x)`). A `string`/`number` can't carry an operator.
- Enumerate expected fields; never spread raw request objects:
  ```js
  await User.find({ name: req.query.name, age: req.query.age })
    .setOptions({ sanitizeFilter: true }); // ✓
  ```
- **`sanitizeFilter: true`** (Mongoose **6+**; per-query via `setOptions` or global `mongoose.set('sanitizeFilter', true)`) wraps any value that is an object with a `$`-key in `$eq`, neutralizing operator injection: `{ pwd: { $ne: null } }` → `{ pwd: { $eq: { $ne: null } } }`. Allow a **known** selector through with `mongoose.trusted({ $gt: 10 })`.
- Strip `$`/`.` keys at the edge with **`express-mongo-sanitize`** (a.k.a. the `mongo-sanitize` family) middleware — defense in depth, not a replacement for casting.
- Disable server-side JS at the DB (`security.javascriptEnabled: false` in mongod) so `$where`/`$function` can't run at all.

---

### Sources
- https://mongoosejs.com/docs/queries.html
- https://mongoosejs.com/docs/guide.html
- https://mongoosejs.com/docs/tutorials/lean.html
- https://mongoosejs.com/docs/transactions.html
- https://mongoosejs.com/docs/api/query.html
- https://mongoosejs.com/docs/api/mongoose.html
- https://mongoosejs.com/docs/migrating_to_6.html
- context7 `/websites/mongoosejs` (sanitizeFilter, trusted, transactions)
