---
name: certify
description: Full verification loop — tests, types, lint, build, and a Playwright browser check for UI projects; collects evidence before any success claim. Use to verify a change is actually green.
allowed-tools: Bash, Read, Glob, Grep, Monitor
---

# /certify — Verification Loop

Run the full verification suite and collect evidence of passing state.

## Required Checks (all must pass)

Run these in order. Stop and fix before continuing if any fail. This is a **loop, not a checklist**: if a check fails, fix it and re-run from the top — /certify only completes when a single clean pass runs end-to-end with no fixes in between.

### 1. Tests
Run the test command for the detected stack:
- JavaScript/TypeScript: `npm test`
- Python: `pytest`
- Go: `go test ./...`
- Rust: `cargo test`
- Java: `mvn test` or `gradle test`

Required: all tests pass, no skipped tests without documented reason.

### 2. Type Check
- TypeScript: `npx tsc --noEmit`
- Python: `mypy .` (if configured)
- Go: `go vet ./...`
- Rust: `cargo check`

Required: zero type errors.

### 3. Lint
- JavaScript/TypeScript: `npm run lint`
- Python: `ruff check .`
- Go: `golangci-lint run`
- Rust: `cargo clippy`

Required: zero lint errors (warnings acceptable if pre-existing). Also hold the code to the project's **documented conventions** ([lore/code-standards.md](../../lore/code-standards.md)) — a style rule the reviewer or a `code-review.md` would flag (e.g. async/await vs `.then`, import order) is a fail even when the linter is silent about it.

### 4. Build
Verify the build succeeds (if applicable).

### 5. Evidence Collection
After all checks pass, write a brief evidence summary:
```
✅ Tests: N passing, 0 failing
✅ Types: clean
✅ Lint: clean
✅ Build: success
```

## For UI Projects
If the project has a UI:
1. Start the dev server (e.g. `npm run dev`, `yarn dev`) in the background
2. Auto-open the browser to the local URL:
   ```bash
   # detect and open
   URL=$(grep -E '"dev"' package.json | grep -oE 'localhost:[0-9]+' | head -1 || echo "localhost:3000")
   open "http://$URL" 2>/dev/null || xdg-open "http://$URL" 2>/dev/null || true
   ```
3. Manually verify (or use Playwright if available):
   - [ ] Golden path works end-to-end
   - [ ] Edge cases handled gracefully
   - [ ] No console errors
   - [ ] If a `/transmute` parity contract exists (`.workspace/shared/research/<feature>-parity.md`), the **behavioral golden fixtures pass** (behavioral parity — the G1 gateway), not just the generic golden path

Use the **Monitor tool** to tail the dev-server output and browser console in the background so a runtime error surfaces as an event mid-check instead of being missed on a one-shot glance.

## Completion Signal

"Certify complete. Evidence: [summary]. Ready for /scrutinize (code review) or /seal (ship)."
