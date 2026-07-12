# fastify — Schema validation & serialization

Version baseline: **Fastify v5** (latest v5.9.x, requires Node.js >= 20). v5 ships **Ajv v8** for validation and **fast-json-stringify** for response serialization. Fastify v4 (v4.29.x) also uses Ajv 8; v3 used Ajv 6. Schemas use JSON Schema (docs target Draft 7).

Two independent jobs, one `schema` object:
- **Validate** incoming `body` / `querystring` / `params` / `headers` (Ajv).
- **Serialize** outgoing responses keyed by status code (fast-json-stringify) — a major throughput win AND a security boundary.

## DO — validate inputs via schema, never by hand

- Attach a `schema` to route options; let Fastify compile it. Four targets:
  ```js
  fastify.post('/user/:id', {
    schema: {
      params:      { type: 'object', properties: { id: { type: 'integer' } }, required: ['id'] },
      querystring: { type: 'object', properties: { q: { type: 'string' } } },
      headers:     { type: 'object', properties: { 'x-api-key': { type: 'string' } }, required: ['x-api-key'] },
      body:        { type: 'object', properties: { name: { type: 'string' } }, required: ['name'], additionalProperties: false }
    }
  }, handler)
  ```
  `query` is an alias for `querystring`. Failures auto-return **400** `{ statusCode, error, message }`; every validation error has `.statusCode === 400`.
- Set `additionalProperties: false` on body/params schemas to reject unexpected keys. Note the default Ajv config has `removeAdditional: true`, so extra props are stripped, not rejected, unless you set this.
- Trust `request.body`/`params`/`query` AFTER validation — Ajv coerces types (`coerceTypes: 'array'`) and applies `useDefaults`, so `?ids=1` becomes `{ ids: ["1"] }` for array schemas.
- Body validation runs only for `application/json` unless you use the `content` keyword to key schemas by MIME type:
  ```js
  body: { content: { 'application/json': { schema: {...} }, 'text/plain': { schema: { type: 'string' } } } }
  ```

## DON'T — hand-validate or trust unvalidated parsers

- DON'T write `if (!req.body.name) return reply.code(400)...`. Declare it `required` in the schema.
- DON'T register a custom content-type parser (regex) and forget a matching `content` schema — unmatched types are **parsed but not validated**. Add a catch-all schema (no `content`) or a `content` key per accepted type.
- DON'T enable `allErrors: true` or `jsonPointers: true` casually — documented DoS risk (CVE-2020-8192). Default `allErrors: false` is intentional.
- DON'T use Ajv `$async` for validation that hits a DB (DoS surface) — do that in a `preHandler` hook instead.
- DON'T pass user-supplied schemas to the compiler — schemas are application code compiled with `new Function()`.

## DO — serialize responses with a `response` schema (perf + security)

- Define output per status code. fast-json-stringify emits **only schema-defined fields** — this prevents accidental leakage of passwords, tokens, internal fields.
  ```js
  schema: {
    response: {
      200:     { type: 'object', properties: { id: { type: 'integer' }, name: { type: 'string' } } },
      '2xx':   { type: 'object', properties: { ok: { type: 'boolean' } } },
      default: { type: 'object', properties: { error: { type: 'string' } } }
    }
  }
  ```
  Keys: exact status (`'201'`), ranges (`'2xx'`, `'4xx'`), or `default` fallback. Per-content-type via nested `content` (supports `*/*`).
- Rely on serialization as a whitelist: a field absent from the response schema is never sent, even if present on the object you return. This is the primary defense against overexposing DB rows.

## DON'T — return raw objects without a response schema

- DON'T `reply.send(userRowFromDb)` on sensitive routes with no `response` schema — every column ships to the client. Define the response shape.
- DON'T assume validation and serialization share config — they're separate compilers (Ajv vs fast-json-stringify).

## DO — share schemas with `addSchema` + `$ref`

- Register reusable schemas (encapsulated to the instance/plugin scope):
  ```js
  fastify.addSchema({ $id: 'user', type: 'object', properties: { id: { type: 'integer' } } })
  // reference by root:
  fastify.get('/u', { schema: { response: { 200: { $ref: 'user#' } } } }, h)
  ```
- `$ref` resolution: `'#foo'` → local `$id: '#foo'`; `'#/definitions/foo'` → local `definitions.foo`; `'user#'` → shared schema by `$id`; `'user#/definitions/foo'` → shared schema's definition. `$ref` works in BOTH validator and serializer.
- Inspect with `getSchema(id)` / `getSchemas()`.

## DON'T — mix addSchema with a fully custom validator

- With a custom validator compiler, `fastify.addSchema` is not seen — register shared schemas on your Ajv instance directly.

## DO — use TypeScript type providers for end-to-end types

- `withTypeProvider<...>()` infers `request.body/query/params` types from the schema. Official providers follow `@fastify/type-provider-{name}`:
  - **TypeBox** — `@fastify/type-provider-typebox`, schemas are JSON Schema, no extra compilers needed:
    ```ts
    const app = Fastify().withTypeProvider<TypeBoxTypeProvider>()
    app.get('/r', { schema: { querystring: Type.Object({ foo: Type.Number() }) } }, (req) => req.query.foo)
    ```
  - **Zod** — `@fastify/type-provider-zod`; MUST wire both compilers:
    ```ts
    app.setValidatorCompiler(validatorCompiler)
    app.setSerializerCompiler(serializerCompiler)
    app.withTypeProvider<ZodTypeProvider>()
    ```
  - **json-schema-to-ts** — `@fastify/type-provider-json-schema-to-ts` (plain JSON Schema, `as const`).
- TypeBox needs no custom compiler (it IS JSON Schema); Zod does — don't forget to set both, or serialization falls back to default JSON.

## DO — customize errors deliberately

- `attachValidation: true` on a route puts the error in `req.validationError` (with raw `.validation`) instead of auto-400 — handle in-route.
- `setErrorHandler((err, req, reply) => ...)`: check `err.validation` (Ajv errors) and `err.validationContext` (value is `body`|`params`|`query`|`headers` — note the context value is `query`, not `querystring`).
- `setSchemaErrorFormatter((errors, dataVar) => Error)` (sync) to shape messages. `ajv-errors` enables per-field `errorMessage`; `ajv-i18n` localizes. Pin `ajv-errors` to the version matching your Fastify's Ajv (v8 on Fastify 4/5).
- Security: default 400 payloads include validator detail. Sanitize via `setErrorHandler` if messages might leak schema/internal info.

## Custom validators / other libraries

- `setValidatorCompiler(({ schema, method, url, httpPart }) => fn)`; use `httpPart` to apply different Ajv instances per target (e.g., disable `coerceTypes` for body only).
- Non-Ajv validators (Joi/yup): the compiled fn MUST return `{ value }` on success or `{ error }` on failure — **never throw** (throwing in async preValidation crashes the process).
- `setSerializerCompiler(...)` / `reply.serializer(fn)` for a custom serializer (must return a string).

## Sources

- https://fastify.dev/docs/latest/Reference/Validation-and-Serialization/
- https://fastify.dev/docs/latest/Reference/Type-Providers/
- https://fastify.dev/docs/latest/ (version/Node baseline)
- https://github.com/fastify/fastify/blob/main/docs/Reference/Type-Providers.md (via context7)
