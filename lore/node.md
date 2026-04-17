Common AI mistakes: callback hell instead of async/await; not handling promise rejections; blocking the event loop with sync operations; forgetting to handle `process.on('unhandledRejection')`.
Commands: test: `npm test`, lint: `npm run lint`, start: `node index.js`.
Gotchas: `__dirname` not available in ESM — use `import.meta.url`; `util.promisify` converts callback APIs; streams are more memory-efficient than loading files fully.
