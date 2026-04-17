Common AI mistakes: forgetting await on async calls; using == instead of ===; mutating arrays in-place and returning undefined (forEach does not return); assuming typeof null === "null" (it is "object"); closures in loops capturing loop variable by reference.
Commands: test: `npm test`, lint: `npm run lint`, build: `npm run build`.
Gotchas: ESM vs CJS — check "type" in package.json; optional chaining (?.) short-circuits to undefined, not null.
