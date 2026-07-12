# mongoose — Schemas & models

Mongoose is a JS/Node ODM for MongoDB — distinct from the JVM `orm` lore. Assumes JS/TS/Node lore exists separately. Facts verified against mongoosejs.com (v9 docs, with 7/8 notes) 2026-07. Mongoose 7 and 8 share most of this surface; version-specific deltas are called out.

## Schema definition

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

## strict / strictQuery (version-sensitive)

- `strict: true` (default) drops fields not in the schema on writes. `'throw'` errors instead. Keep it on.
- `strictQuery` is a **separate** option applying only to query filters. **Default `false` in Mongoose 7 and 8.**
  - Consequence: `Model.find({ notInSchema: 1 })` is NOT stripped; unknown paths pass through to Mongo (returns `[]`, not all docs).
- DO set `mongoose.set('strictQuery', true)` app-wide if you want unknown filter keys stripped.

## Types + validation

DO
- Validation runs on `save()` and (by default) on `validateBeforeSave`. Update ops (`updateOne`, `findOneAndUpdate`) skip validators unless `{ runValidators: true }`.
- Add `{ runValidators: true }` to update calls when you need schema validation on updates.

DON'T
- Don't assume `findOneAndUpdate` validates or runs `save` hooks — it doesn't by default.

## Indexes

DO
- Path-level: `{ index: true, unique: true, sparse: true }`. Compound: `schema.index({ a: 1, b: -1 })`.
- `unique` is an index hint, NOT a validator — enforce uniqueness at the DB level and handle E11000 duplicate-key errors.
- In production set `autoIndex: false` (schema or `mongoose.set('autoIndex', false)`) and build indexes deliberately (`Model.syncIndexes()` / `createIndexes()` in a migration).

DON'T
- Don't leave `autoIndex: true` on large prod collections — Mongoose calls `createIndex` for every index on startup, blocking/foregrounding index builds.
- Don't expect `unique` to prevent races without the DB index actually present.

## refs + populate() (the N+1 cost)

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

## Subdocuments vs refs

DO
- Embed (subdocuments) when child data is always loaded with the parent, bounded in size, and owned by it — one read, no populate.
- Reference when data is shared, unbounded, or queried independently.

DON'T
- Don't embed unbounded arrays (comments, events) — you hit the 16MB doc cap and rewrite the whole doc on every push.

## lean() — read-only perf

DO
- Add `.lean()` on read-only paths (GET handlers, reports). Returns plain POJOs, skipping Mongoose document hydration/change-tracking — markedly faster, ~3x less Node memory.
- Combine with populate: `.populate(...).lean()` — populated docs also become POJOs.

DON'T
- Don't `.lean()` when you need `save()`, validators, getters/setters, or virtuals — none run on lean results.
- Don't expect virtuals/getters on lean docs without the `mongoose-lean-virtuals` / `mongoose-lean-getters` plugins.

## Virtuals

- Computed, non-persisted, non-queryable. `schema.virtual('fullName').get(fn).set(fn)`.
- Excluded from `toJSON()`/`toObject()` by default — enable with `{ toJSON: { virtuals: true }, toObject: { virtuals: true } }` (needed for API responses).

## Middleware / hooks

DO
- `schema.pre('save', fn)` / `post('save', fn)` for document lifecycle.
- Know the split: `save`/`validate`/`remove` are document middleware; `find`/`findOne`/`findOneAndUpdate`/`updateOne`/`deleteOne` default to **query** middleware (`this` is the Query, not the doc).
- Mongoose 7+ removed `remove()` — rewrite `pre('remove')` as `pre('deleteOne', { document: true, query: false }, fn)`.

DON'T
- Don't expect `save` hooks to fire on `updateOne`/`findOneAndUpdate` — they don't. Add explicit `pre('findOneAndUpdate')` if needed.
- Don't put slow/external calls in hooks without understanding they run on every op.

## Security — query-selector injection (NON-NEGOTIABLE)

Mongoose parameterizes normal writes, but **untrusted objects in filters are the injection surface.** A body like `{ pwd: { $ne: null } }` or `{ $where: '...' }` spliced into a filter bypasses auth / runs JS on the server.

DO
- Enable sanitization globally: `mongoose.set('sanitizeFilter', true)` (default `false`), or per-query `.setOptions({ sanitizeFilter: true })`. It wraps any nested `$`-prefixed object in `$eq`, forcing literal equality.
- Cast/validate untrusted input to expected scalar types before it ever reaches a filter (`String(req.query.id)`).
- Use `mongoose.trusted({...})` to whitelist operators you intentionally allow through sanitization.

DON'T
- Don't spread `req.query`/`req.body` directly into `.find()` / `.findOne()` — that is the vulnerability.
- Don't enable `$where` (server-side JS) on filters; never pass user strings to it.
- Don't rely on `strictQuery` for security — it strips unknown *paths*, not malicious *operators* on known paths.

## Sources
- https://mongoosejs.com/docs/guide.html
- https://mongoosejs.com/docs/queries.html
- https://mongoosejs.com/docs/populate.html
- https://mongoosejs.com/docs/tutorials/lean.html
- https://mongoosejs.com/docs/api/mongoose.html
- https://mongoosejs.com/docs/migrating_to_7.html
- https://mongoosejs.com/docs/migrating_to_8.html
