# Express — core

Version cue: Express 5 (current) uses path-to-regexp v8 + auto-forwards async errors; Express 4 does not. Check `express` in package.json first.

DO define the error handler `(err,req,res,next)` LAST, after all routes/middleware.
DO in Express 5 let async handlers throw/reject — auto-calls `next(err)`. In Express 4 wrap: `.catch(next)` (rejections NOT auto-forwarded).
DO pass errors via `next(err)`; `next('route')` skips to next matching route, not an error.
DO name wildcards in Express 5: `/files/*splat` (array); optional segs use braces `/:file{.:ext}` — `?+*()[` are reserved.
DO validate/sanitize all input; parameterize DB queries (never string-concat SQL); allow-list redirect/`res.location` hosts.
DO `app.use(helmet())`; `app.disable('x-powered-by')`; cookies `httpOnly:true,secure:true,sameSite`; rate-limit auth; `npm audit`.

DON'T leak stack traces — set `NODE_ENV=production` (default handler then hides them); log server-side, send generic bodies.
DON'T write after `res.headersSent` — `return next(err)`.
DON'T use Express 4 optional `?`/unnamed `*` patterns under Express 5.
DON'T trust `req.query/params/body` unvalidated; DON'T ship secrets to the client.

Commands: `npm i express helmet express-rate-limit` · `npm audit` · `NODE_ENV=production node app.js`

Deep dive when writing non-trivial express — read lore/express/{middleware-and-routing,errors-and-async,security-and-validation}.md

## Sources
expressjs.com/en/guide/{routing,error-handling}.html · expressjs.com/en/advanced/best-practice-security.html
