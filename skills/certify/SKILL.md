---
name: certify
description: Full verification loop — tests, types, lint, and evidence collection before any PR
keep-coding-instructions: true
---

# /certify — Verification Loop

Run the full verification suite and collect evidence of passing state.

## Required Checks (all must pass)

Run these in order. Stop and fix before continuing if any fail.

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

Required: zero lint errors (warnings acceptable if pre-existing).

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
If the project has a UI, run the dev server and manually verify:
- [ ] Golden path works end-to-end
- [ ] Edge cases handled gracefully
- [ ] No console errors

## Completion Signal

"Certify complete. Evidence: [summary]. Ready for /scrutinize (code review) or /seal (ship)."
