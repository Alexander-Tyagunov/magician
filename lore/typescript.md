# TypeScript — core digest

DO enable `strict` (+ `noUncheckedIndexedAccess`); prefer `unknown` over `any` and narrow with type guards, not `as`. DO model data as discriminated unions (shared literal tag) + exhaustive `switch` with a `never` default; use `as const` for literal inference and `satisfies` (4.9) to check a value's shape without widening it.
DON'T use non-null `!` or `as` casts to silence errors — narrow instead. DON'T annotate what's inferable. DON'T use `enum`/`namespace` (runtime emit) on type-stripping runtimes — set `erasableSyntaxOnly` (5.8).
DO scope resources with `using`/`await using` (5.2). DO set `moduleResolution` `nodenext` (Node) or `bundler` (5.0); add `verbatimModuleSyntax` (5.0) + `isolatedModules` for predictable per-file emit; keep `skipLibCheck` on.

Version cue: TS 7.x = native Go compiler (`tsc`), ~10x faster, drop-in for 5.x semantics; 6.x transitional (deprecations); 4.9 `satisfies`, 5.0 verbatim/bundler, 5.2 `using`, 5.8 `erasableSyntaxOnly`. Node 22.18+/24 run `.ts` directly (type-stripping = erasable syntax only). Target ES2022+.
Commands: install `npm i -D typescript` / `pnpm add -D typescript`; type-check `npx tsc --noEmit`; run `node file.ts` (Node 22.18+/23.6+, unflagged type-stripping); test `npm test`; lint `npm run lint`.

Deep dive when writing non-trivial typescript — read lore/typescript/{type-system,tsconfig-and-strictness,advanced-types,patterns-and-pitfalls}.md

Sources: typescriptlang.org/tsconfig + /docs/handbook/release-notes/overview.html; github.com/microsoft/typescript-go; nodejs.org type-stripping docs.
