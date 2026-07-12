# express — Middleware & routing

Framework-specific lore. Assumes Node/JS/TS lore exists elsewhere. Verify the
installed major before applying: `express@5` (current stable, Node 18+) changed
path matching and async error handling vs `express@4`. Feature notes below name
the version that introduced/changed behavior — never assume earlier.

## Middleware order & next()

DO
- Register middleware in execution order — Express runs `app.use`/route handlers
  top-to-bottom, first match wins. Parsers and security headers go before routes.
- Call `next()` to pass control, or terminate with a response method
  (`res.send/json/end/sendFile/redirect/render/sendStatus`). Exactly one path.
- Scope middleware with a mount path when it shouldn't run globally:
  `app.use('/api', apiLimiter)`.
- Use `next('route')` to skip remaining handlers of the *current* route and jump
  to the next matching route (pre-condition gating).

DON'T
- Don't forget `next()` in a non-terminating middleware — the request hangs and
  never gets GC'd.
- Don't call `next()` *and* send a response, or send twice — throws
  "headers already sent".
- Don't place `express.static`/catch-all before routes you expect to win.

```js
app.use(express.json());                 // 1. parse body
app.use(helmet());                       // 2. security headers
app.use('/api', requireAuth, apiRouter); // 3. scoped auth + routes
app.use((req, res) => res.status(404).send('Not found')); // 4. 404 fallback
```

## Routing

DO
- Use `app.METHOD(path, ...handlers)` (`get/post/put/delete/patch/all`).
  Handlers may be a fn, an array of fns, or a mix — all behave like middleware.
- Chain methods on one path with `app.route('/book').get(...).post(...).put(...)`.
- Read named segments from `req.params`, query from `req.query`. Query string is
  NOT part of the route path and never matches against it.

DON'T
- Don't use `app.del()` — removed in v5. Use `app.delete()`.
- Don't rely on `req.param(name)` — removed in v5. Read `req.params` /
  `req.query` / `req.body` explicitly.
- Don't put regexp metacharacters inside a path string in v5 (see below).

```js
// /users/34/books/8989 -> { userId: '34', bookId: '8989' }
app.get('/users/:userId/books/:bookId', (req, res) => res.json(req.params));

// literal - and . delimit params: /flights/LAX-SFO -> {from:'LAX',to:'SFO'}
app.get('/flights/:from-:to', (req, res) => res.json(req.params));
```

## Path matching — Express 5 vs 4 (path-to-regexp v8)

Express 5 uses path-to-regexp **v8**. Param names must be word chars
`[A-Za-z0-9_]`. Reserved chars `( ) [ ] ? + ! *` must be escaped with `\`.

| Intent | Express 4 | Express 5 |
|---|---|---|
| Wildcard | `/*` (unnamed) | `/*splat` (named, **captured as array**) |
| Wildcard incl. root | `/*` | `/{*splat}` |
| Optional segment | `/:file.:ext?` | `/:file{.:ext}` |
| Alternation | `/[a\|b]/:x` string | array: `['/a/:x','/b/:x']` |

DO
- In v5, name every wildcard; `req.params.splat` is a **string array** of
  segments (e.g. `['images','logo.png']`), not a string.
- Prefer a real `RegExp` (`app.get(/.*fly$/, h)`) or a path array over cramming
  regex syntax into a string.

DON'T
- Don't port v4 `*` / `?` path syntax verbatim to v5 — it throws or misbehaves.
- Note: v5 `req.params` has a **null prototype** for string paths; unmatched
  optional params are omitted (not `''`/`undefined`).

## Router modularization & mounting

DO
- Build feature modules with `express.Router()` (a self-contained mini-app) and
  mount with `app.use('/birds', birdsRouter)`.
- Pass `express.Router({ mergeParams: true })` when a child router must read the
  parent mount's params (e.g. `/users/:id` -> nested router).
- Use `caseSensitive` / `strict` router options deliberately if `/Foo` vs `/foo`
  or trailing-slash distinctions matter.

DON'T
- Don't expect child routers to see parent `req.params` without `mergeParams`.

```js
const router = express.Router({ mergeParams: true });
router.use(timeLog);                       // router-scoped middleware
router.get('/', (req, res) => res.send('home'));
module.exports = router;
// app.js
app.use('/birds', router);                 // handles /birds and /birds/*
```

## Body parsers & static files (built-in since 4.16.0)

`express.json()`, `express.urlencoded()`, `express.text()`, `express.raw()`,
`express.static()` are built in — no `body-parser` dependency needed on 4.16+.

DO
- `app.use(express.json({ limit: '100kb' }))` — set a `limit` to cap payloads.
- For forms: `express.urlencoded({ extended: true })`. **v5 defaults `extended`
  to `false`** — set `true` explicitly if you need nested objects (`qs`).
- Serve assets with `express.static('public', { maxAge: '1d' })`; mount under a
  prefix (`app.use('/static', express.static('public'))`) to namespace.

DON'T
- Don't assume `req.body` is `{}` when unparsed — in v5 it's `undefined`. Guard
  before reading.
- Don't serve dotfiles by accident: v5 `static`/`sendFile` default
  `dotfiles: 'ignore'` (`.well-known` now 404s — opt in with `dotfiles:'allow'`).
- Don't set an unbounded body limit — DoS vector.

## Error handling

DO
- Define error middleware **last**, with the 4-arg signature
  `(err, req, res, next)` — arity is how Express detects it.
- Forward errors with `next(err)`; anything passed to `next` except the string
  `'route'` triggers error handling and skips non-error handlers.
- Chain handlers: `app.use(logErrors)` -> `app.use(clientErrorHandler)` ->
  `app.use(catchAll)`, each calling `next(err)` until one responds.
- When `res.headersSent`, delegate: `if (res.headersSent) return next(err)`.

DON'T
- Don't hand-wrap every async route in try/catch on **Express 5** — handlers
  returning a rejected Promise auto-forward to `next(err)`. On **Express 4** you
  MUST `.catch(next)` or manually `next(err)` — async throws are lost otherwise.
- Don't leak stack traces: the default handler hides `err.stack` only when
  `NODE_ENV=production`. Set it.

```js
// Express 5: async errors auto-forwarded
app.get('/user/:id', async (req, res) => {
  const user = await getUserById(req.params.id); // reject -> next(err)
  res.send(user);
});
app.use((err, req, res, next) => {               // 4 args, defined last
  if (res.headersSent) return next(err);
  res.status(err.status || 500).json({ error: 'Internal error' });
});
```

## Security (non-negotiable)

DO
- `app.use(helmet())` for security headers (CSP, HSTS, X-Content-Type-Options,
  removes `X-Powered-By`, etc.). Also `app.disable('x-powered-by')`.
- Validate/sanitize all input (`req.body/query/params`); parameterize DB access
  (defer ORM specifics to ORM lore) to block SQL injection.
- Rate-limit auth/expensive routes (`rate-limiter-flexible`); front with TLS.
- Cookies: `secure`, `httpOnly`, non-default session `name`; `express-session`
  needs a production store (not the in-memory default).
- Validate redirect targets before `res.redirect(req.query.url)` (open-redirect).
- `npm audit` / Snyk; never run Express 2.x/3.x (unmaintained).

DON'T
- Don't return raw errors/stack traces to clients. Custom 404 + error handler.
- Don't trust `Content-Type`; pin parser `type`/`limit`. Guard regex against
  ReDoS (`safe-regex`).

## Sources
- https://expressjs.com/en/guide/routing.html
- https://expressjs.com/en/guide/error-handling.html
- https://expressjs.com/en/guide/migrating-5.html
- https://expressjs.com/en/advanced/best-practice-security.html
- https://expressjs.com/en/api.html
