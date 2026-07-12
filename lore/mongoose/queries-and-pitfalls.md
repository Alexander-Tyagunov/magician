# mongoose — Queries & pitfalls

JS/Node ODM for MongoDB. Distinct from the JVM `orm` lore. Assumes JS/TS/Node lore exists separately.
Versions in scope: **Mongoose 7 / 8 / 9** (9 is current, docs at v9.x). State versions; give fallbacks.
Facts below verified against mongoosejs.com + context7 (2026-07). Verify version-specific claims before asserting.

Query objects are **thenables, not Promises**. `await` or `.exec()` runs them. Re-`.then()` throws `Query was already executed`. Never call `.then()` twice / mix `await` with `.exec()` on the same query.

---

## Query building

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

## lean()

`.lean()` skips document hydration → returns POJOs. ~3x smaller in process memory; **network/JSON payload is identical**.

DO
- Use on read-only / GET paths: `const users = await User.find().lean();`
- Propagates through `populate()` (parent + populated docs both lean).

DON'T
- Don't `.lean()` when you need `save()`, validation, casting, getters/setters, or virtuals — none run. `doc instanceof mongoose.Document` is `false`.
- Don't expect virtuals/getters silently — restore via `mongoose-lean-virtuals` / `mongoose-lean-getters` / `mongoose-lean-defaults` if needed.
- BigInt: Mongo longs become JS `number` under lean. Add `.setOptions({ useBigInt64: true })` when precision matters.

---

## Projection

DO
- Select minimal fields: `.select('name email')` or `.select({ name: 1, email: 1 })` (2nd arg of `find` also works).
- Exclude with `-`: `.select('-password')`. Force-include a default-deselected path with `+`: `.select('+password')`.
- A projection must be **all-inclusive or all-exclusive** (except excluding `_id`). Mixing throws.
- Passing user input to `.select()`? Add **`.sanitizeProjection(true)`** — enforces numeric projection values and blocks `+` overriding `select: false` paths.

DON'T
- Don't ship `select: false` secrets by letting untrusted `+field` re-include them.

---

## Pagination

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

## Transactions (sessions)

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

## SECURITY — query-selector / operator injection (non-negotiable)

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

## Sources
- https://mongoosejs.com/docs/queries.html
- https://mongoosejs.com/docs/guide.html
- https://mongoosejs.com/docs/tutorials/lean.html
- https://mongoosejs.com/docs/transactions.html
- https://mongoosejs.com/docs/api/query.html
- https://mongoosejs.com/docs/api/mongoose.html
- https://mongoosejs.com/docs/migrating_to_6.html
- context7 `/websites/mongoosejs` (sanitizeFilter, trusted, transactions)
