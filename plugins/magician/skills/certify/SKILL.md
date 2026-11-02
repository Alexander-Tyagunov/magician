---
name: "certify"
description: "Verification loop; tests, types, lint, build, Playwright for UI; evidence before success claims. Use to verify a change is green."
license: "MIT"
allowed-tools: "Read, Grep, Glob, Bash(ugrep *), Bash(bfs *), Bash(rg *), Bash(grep *), Bash(find *), Grep, Bash(npm test *), Bash(npm run lint), Bash(npm run build), Bash(pytest *), Bash(mypy *), Bash(ruff check .), Bash(go test ./...), Bash(go vet ./...), Bash(golangci-lint run), Bash(cargo test *), Bash(cargo check), Bash(cargo clippy), Bash(mvn test), Bash(gradle test)"
metadata: {"claude-code.effort": "high"}
---

# /certify — Verification Loop

Run the full verification suite and collect evidence of passing state.

**This is tool evidence, not self-review.** Every check below is a command whose exit code and output are the proof; nothing here asks the model to re-read its own work and reassure itself. Keep it that way — current models already self-correct, so layering "double-check", "re-verify", or a dedicated verify-my-own-output subagent on top of these commands burns tokens without changing the result. The gate is the clean pass, and it does not move. See [lore/model-behavior.md](../../lore/model-behavior.md).

## Autonomy — approve the plan, then run

Once /certify is invoked and the stack is detected, the required checks run as **one autonomous pass**: Tests → Type Check → Lint → Build → the UI browser check *are* the run, not per-step decisions — the check commands, dev server, and read-only git need no confirmation question (optionally echo the detected check list once before running). The test, lint, build and type-check commands listed below are pre-approved exactly as written, except that `npm test`, `pytest`, `mypy` and `cargo test` also accept arguments (to run one test file, say); a fix mode such as `--fix` is not pre-approved; anything else (the dev server, a typecheck script, opening the browser) goes through Claude Code's normal permission prompt unless the session is in auto mode. Re-gate **only** when a failing check needs a real side effect: a file-edit fix (or any outward action) — that returns to the owner. Doctrine: [lore/autonomy.md](../../lore/autonomy.md).

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
- TypeScript: the project's own script (`npm run typecheck`, if `package.json` defines one), else the locally installed compiler `./node_modules/.bin/tsc --noEmit`
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
Verify the build succeeds (if applicable), e.g. `npm run build`.

### 5. Evidence Collection
After all checks pass, write a brief evidence summary:
```
✅ Tests: N passing, 0 failing
✅ Types: clean
✅ Lint: clean
✅ Build: success
✅ UI: golden path ok; screenshots: .workspace/local/screens/<feature>/v<n>/light-desktop.png, … (or "no UI")
```

## For UI Projects
If the project has a UI:
1. Start the dev server (e.g. `npm run dev`, `yarn dev`) with the Bash tool's background option, and read its output to find the local port (the `dev` script in `package.json` or the server's startup line; default to 3000 if neither says).
2. Open the browser to that URL: `open http://localhost:<port>` on macOS, `xdg-open http://localhost:<port>` on Linux.
3. Manually verify (or use Playwright if available):
   - [ ] Golden path works end-to-end
   - [ ] Edge cases handled gracefully
   - [ ] No console errors
   - [ ] If a `/transmute` parity contract exists (`.workspace/shared/research/<feature>-parity.md`), the **behavioral golden fixtures pass** (behavioral parity — the G1 gateway), not just the generic golden path
4. **Evidence screenshots.** With Playwright available, capture the golden path per theme and per viewport into `.workspace/local/screens/<feature>/v<n>/<theme>-<viewport>.png` as [conjure's capture.md](../conjure/references/capture.md) describes, and list the paths in the evidence summary. When an approved `/conjure` mockup exists (`.workspace/shared/designs/<date>-<feature>/screens/v<n>/`), diff the new capture against the design's screenshots with `node ../../skills/conjure/scripts/screen-diff.cjs <design-screens> <build-screens>` (prompts; nothing is installed) and treat an unexplained change as a failing check under a STRICT spec, a note under a REFERENCE one. Without Playwright, write "no screenshot (Playwright unavailable)" in the summary rather than skipping the line.

While you check, re-read the background dev server's output (and the browser console, via Playwright if available) so a runtime error that appears mid-check is not missed on a one-shot glance.

## Obstacles

If this skill runs as a dispatched unit and hits something that blocks or degrades the work, do not wait for a human who is not there and do not silently ship a degraded result — return the Obstacles block from [lore/obstacles.md](../../lore/obstacles.md) (fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT) to the caller alongside whatever you completed; interactively, say the same in prose.

## Completion Signal

Before emitting this signal, apply the verification gate ([lore/verification.md](../../lore/verification.md)): no "passing / clean / done" claim without the actual command output read **this run** — a remembered result or "should pass" doesn't count. /certify **is** the runnable suite; that discipline is the reason it exists. The evidence summary must reflect output you read from this pass, not extrapolation.

"Certify complete. Evidence: [summary]. Ready for /scrutinize (code review) or /seal (ship)."

## On Codex

Read the Claude Code features this skill names as follows on Codex and ChatGPT (full table: [On Codex](../../lore/skill-authoring.md#on-codex)).

- Subagents (`Task`/`Agent`): Codex subagents are `.codex/agents/*.toml` files (`name`, `description`, `developer_instructions`); the review lenses ship here as `*-lens` skills.
- Skill commands: `/<skill>` is `$<skill>` on Codex and `@<skill>` in ChatGPT.
- Paths such as `../../tools/kg` are relative to the folder of the file that names them; resolve them to an absolute path before you run them.
