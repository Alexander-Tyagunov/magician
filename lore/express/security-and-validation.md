# express — Security & validation

Senior-reviewer checklist. OWASP-aligned. Assumes node/js/ts lore exists separately. DB parameterization → defer to `lore/orm.md`.

Version cues (verify against package.json):
- **Express 5** (5.1.x is the current `npm install express` default; requires **Node 18+**): async handlers/middleware that reject/throw auto-forward to error middleware; `path-to-regexp` rewritten (named wildcards, no bare `*`, no inline regexp in path strings — cuts route-based ReDoS); `req.query` is a read-only getter; `express.urlencoded` `extended` defaults `false`; `express.static` `dotfiles` defaults `"ignore"`; `req.body` is `undefined` (not `{}`) when unparsed.
- **Express 4** (4.21.x maintenance): async errors are NOT auto-caught — you must `.catch(next)` / `next(err)`. Express 2/3 are EOL.

## Security headers (helmet)

DO
- `import helmet from 'helmet'; app.use(helmet())` first, before routes. Sets CSP, HSTS, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, COOP, CORP, frame-ancestors, etc.; removes `X-Powered-By`; disables the legacy `X-XSS-Protection`.
- Also `app.disable('x-powered-by')` explicitly (helmet already strips it; belt-and-suspenders if helmet is ever removed).
- Tune CSP for real apps: `helmet({ contentSecurityPolicy: { directives: { ... } } })`. The default CSP is strict and will block inline scripts/CDNs — configure, don't blanket-disable.

DON'T
- Don't disable CSP/HSTS wholesale to "fix" a broken page — scope directives.
- Don't rely on `X-XSS-Protection` or `X-Frame-Options` alone; prefer CSP `frame-ancestors`.

## CORS

DO
- Explicit allow-list; reflect a specific validated origin. `import cors from 'cors'`.
```js
app.use(cors({ origin: ['https://app.example.com'], credentials: true }));
```
- For dynamic lists use the function form `origin(origin, cb){ cb(null, allowed.includes(origin)) }`.
- Understand the boundary: **CORS is not access control.** Every request still reaches your handler — curl/Postman/servers ignore CORS. Protect with authn/authz.

DON'T
- **Never `origin: '*'` with `credentials: true`.** Browsers reject `ACAO: *` alongside credentials, and it defeats the point. Credentialed → explicit origin. Don't blindly reflect `req.header('Origin')` back either.

## Input validation & sanitization

Validate at the boundary; treat all of `req.body/query/params/headers/cookies` as hostile. Pick ONE library.

**express-validator** (v7.x): chains `body/query/param/cookie/header`, then `validationResult`, then `matchedData`.
```js
import { body, validationResult, matchedData } from 'express-validator';
app.post('/signup',
  body('email').isEmail().normalizeEmail(),
  body('password').isLength({ min: 12 }),
  body('name').trim().notEmpty().escape(),
  (req, res) => {
    const r = validationResult(req);
    if (!r.isEmpty()) return res.status(400).json({ errors: r.array() });
    const data = matchedData(req); // only validated fields — use THIS, not raw req.body
    // ...
  });
```
- `checkSchema({...})` for declarative schemas; append `.run(req)` when running manually/async.

**zod** (TS-first): parse into typed data; reject on failure.
```js
import { z } from 'zod';
const Body = z.object({ email: z.string().email(), age: z.number().int().min(0) });
const p = Body.safeParse(req.body);
if (!p.success) return res.status(400).json({ errors: p.error.issues });
// use p.data (typed, stripped of unknown keys)
```

DO
- Whitelist allowed fields; use `matchedData`/`safeParse` output downstream, never the raw request object (prevents mass-assignment).
- Set body size limits: `express.json({ limit: '100kb' })`.
- `trim()` BEFORE `notEmpty()`/length checks (order matters in chains).

DON'T
- Don't hand-roll regex validators on untrusted input (ReDoS) — if unavoidable, vet with `safe-regex`.
- Don't trust `Content-Type`; enforce it and reject unexpected types.
- Don't validate only on the client.

## Injection

DO
- Parameterize ALL DB access — bind params / prepared statements / ORM query builders. See `lore/orm.md` for JPA/jOOQ/MyBatis and the JS ORM lore (prisma/drizzle/sequelize/typeorm/mongoose) for driver-specific binding.
- MongoDB: cast/validate types; reject object-valued fields where a scalar is expected (blocks `{$gt:''}`-style NoSQL operator injection). Validation above already does this if schema types are strict.
- Validate/allow-list any user value used as a table/column/sort field (can't be bound).

DON'T
- Never string-concat or template user input into SQL/NoSQL/HQL, shell commands, or file paths.
- Never pass `req.query`/`req.body` objects straight into a Mongo filter without type-checking.

## Rate limiting & brute force

**express-rate-limit** (v7+):
```js
import { rateLimit } from 'express-rate-limit';
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 100,              // v7 renamed `max` → `limit`
  standardHeaders: 'draft-8',
  legacyHeaders: false,
});
app.use(limiter);
app.use('/auth', rateLimit({ windowMs: 15*60*1000, limit: 5 })); // stricter on login
```
DO
- Tighter limits on auth/password-reset endpoints; block on failed-attempts per (IP + username) — see `rate-limiter-flexible` for two-metric brute-force defense.
- Behind a proxy/LB set `app.set('trust proxy', n)` (n = number of trusted hops) so the real client IP is keyed. Get `n` wrong and you either key everyone as the proxy or trust spoofable `X-Forwarded-For`.
- Use a shared store (Redis/Memcached) for multi-instance deployments — the default memory store is per-process.

DON'T
- Don't `trust proxy` = `true` (trust-all) in production; it lets clients spoof IPs.

## Cookies & sessions

DO
- `express-session` (server-side store) for anything sensitive — the cookie holds only the session id. `cookie-session` serializes state INTO the cookie (client-readable, ≤ ~4KB) — small non-secret data only.
```js
app.set('trust proxy', 1);
app.use(session({
  name: 'sid',               // rename off the default `connect.sid` (fingerprinting)
  secret: process.env.SESSION_SECRET,
  resave: false, saveUninitialized: false,
  cookie: { httpOnly: true, secure: true, sameSite: 'lax', maxAge: 3600_000 },
}));
```
- `httpOnly` (blocks JS/XSS theft), `secure` (HTTPS only), `sameSite` (`lax`/`strict`, CSRF defense), short `maxAge`. Regenerate the session id on login (`req.session.regenerate`) to prevent fixation.
- Replace the default in-memory store with a real store (Redis/DB) in production.
- CSRF: for cookie-based auth add token protection (`csrf-csrf` / double-submit) or require `SameSite=strict` + custom header for state-changing routes.

DON'T
- Don't ship the default session cookie name or a hardcoded/committed secret.
- Don't set `secure: true` without TLS terminating correctly (cookie silently dropped) — pair with `trust proxy`.

## Error handling — no leaks

DO
- One 4-arg error handler LAST: `app.use((err, req, res, next) => {...})`. Log server-side; return a generic message + status to the client.
```js
app.use((err, req, res, next) => {
  if (res.headersSent) return next(err);
  req.log?.error(err);
  res.status(err.status || 500).json({ error: 'Internal Server Error' });
});
```
- Run with `NODE_ENV=production` — Express's default handler then hides stack traces (sends only the status message); non-production leaks `err.stack`.
- Express 4: wrap async handlers (`.catch(next)` or an asyncHandler wrapper). Express 5: async rejections auto-forward — still add the handler.
- Add a custom 404 before the error handler.

DON'T
- Never send `err.stack`, SQL errors, or internal paths to clients.
- Don't `throw` in async Express-4 handlers expecting Express to catch it — it won't.

## TLS & dependencies

Terminate TLS (reverse proxy / Let's Encrypt); HSTS via helmet. Run `npm audit` / Snyk in CI; watch the GitHub Advisory DB. Never expose HTTP in prod; never ignore transitive-dep CVEs.

## Sources
- https://expressjs.com/en/advanced/best-practice-security.html
- https://expressjs.com/en/guide/error-handling.html
- https://expressjs.com/en/guide/migrating-5.html
- https://expressjs.com/en/resources/middleware/cors.html
- https://expressjs.com/en/guide/routing.html
- https://helmetjs.github.io/
- https://express-rate-limit.github.io/ (express-rate-limit v7)
- https://express-validator.github.io/docs/ (v7.x)
- https://zod.dev/
- https://owasp.org/www-project-top-ten/
