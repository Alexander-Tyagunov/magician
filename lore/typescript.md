Common AI mistakes: using `any` instead of `unknown`; forgetting to narrow `unknown` before use; non-null assertion (!) hiding real bugs; missing `as const` for literal inference; using type assertion instead of a proper type guard.
Commands: type-check: `npx tsc --noEmit`, lint: `npm run lint`.
Gotchas: `satisfies` operator (TS 4.9+) validates shape without widening; discriminated unions require a shared literal field.
