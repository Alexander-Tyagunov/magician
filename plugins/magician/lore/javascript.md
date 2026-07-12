# JavaScript — core digest

DO use `===`/`!==` (only `== null` to catch null+undefined together); `const`/`let`, never `var`; `?.` and `??` for defaults (nullish — not `||`, which also eats `0`/`""`/`false`). DO `await` (or return) EVERY promise — no floating promises; wrap awaits in try/catch. DO prefer immutable ops (`map`/`filter`/spread) over in-place mutation.

DON'T trust `typeof null` (it's `"object"`) or `NaN === NaN` (false — use `Number.isNaN`). DON'T rely on return values of `forEach`/`push`/`sort` (forEach→undefined; sort/reverse mutate). DON'T declare loop vars with `var` (one shared binding — use `let`/`const`). DON'T exceed `Number.MAX_SAFE_INTEGER` — use `BigInt`. DON'T deep-clone via `JSON.parse(JSON.stringify(x))` — use `structuredClone(x)`.

Modern: `Object.groupBy`/`Map.groupBy` (ES2024), `Array.fromAsync` (ES2026); `arr.at(-1)`, `Object.hasOwn` (ES2022). Know your module system: ESM vs CJS — set `"type":"module"` in package.json.

Version cue: latest spec ES2025 (16th ed.); Node 24 Active LTS + 22 Maintenance LTS (20 EOL Apr 2026, 18 EOL 2025); prefer ESM.
Commands: install `npm i` / `pnpm i`; run `npm run <s>` / `pnpm <s>`; test `npm test`; lint `npm run lint`.

Deep dive when writing non-trivial javascript — read lore/javascript/{language-and-idioms,async,types-and-coercion,errors-and-resources}.md

Sources: developer.mozilla.org/en-US/docs/Web/JavaScript; tc39.es/ecma262; nodejs.org/en/about/previous-releases
