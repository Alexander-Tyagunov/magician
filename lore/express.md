Common AI mistakes: not using next(err) for error propagation; missing error-handling middleware (4 args); not validating request body; synchronous throws not caught by Express error handler.
Commands: start: `node app.js`, test: `npm test`.
Gotchas: error middleware must have 4 parameters `(err, req, res, next)`; use `express.json()` middleware for JSON bodies; `res.json()` sets Content-Type automatically.
