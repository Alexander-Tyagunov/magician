---
name: sentinel
description: Read-only security scan; OWASP Top 10, secrets, injection, dependencies, git history, auth. Use to audit a codebase for vulnerabilities.
effort: high
allowed-tools: Read, Grep, Glob, Bash(ugrep *), Bash(bfs *), Bash(rg *), Bash(grep *), Bash(find *), Bash(mkdir -p .workspace/local/security), Bash(touch .workspace/local/security-scan.active), Bash(magician-scan *), Bash(npm audit), Bash(npm audit --json), Bash(pip-audit), Bash(pip-audit -f json), Bash(safety check), Bash(govulncheck ./...), Bash(cargo audit), Edit(./.workspace/local/security/findings.jsonl)
context: fork
background: false
argument-hint: "[path]"
---

# /sentinel — Security Scan

> **Bundled command:** if `magician-scan` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/magician-scan`. If that is missing too (Claude chat ships no plugin tools), skip the static-analysis step, say so in the report, and run the rest.

For very large repos, raise /effort so the analysis stays thorough across the codebase (`xhigh`; `max` only as an opt-in for a frontier problem). See [lore/models.md](../../lore/models.md).

## When to use

To audit a codebase for vulnerabilities: OWASP Top 10, credential and secret detection, injection surfaces, a dependency audit, a git-history secret scan and an auth spot-check. It never modifies code and ends with a severity-ranked report. Trigger phrases: "run a security scan", "audit for vulnerabilities", "check for leaked secrets". Not for fixing findings (`/scrutinize`) or a general code review (`/divine`).

## The scan can change models under you

Cyber classifiers can move a flagged request to a fallback model, and the session continues there ([lore/models.md](../../lore/models.md#safety-classifiers-change-which-model-you-end-up-on)).
- **Frame the work defensively.** Audit and report. Never ask for working exploits, attack tooling or evasion techniques: they trip the classifier and are out of scope.
- **Print the active model at start and end.** If a fallback notice appears mid-scan, say so in the report and offer `/model` to return.
- **A flag on the first request** usually comes from workspace context (`CLAUDE.md`, skills, directory names). `claude --safe-mode` isolates that. `switchModelsOnFlag: false` asks before a switch.

## Destructive-command hard gate (always on, not part of a scan)

Independent of any scan, magician ships a `PreToolUse(Bash|PowerShell)` hook, `scripts/destructive-guard.sh` (self-contained plain bash — no other interpreter), that **unconditionally blocks catastrophic commands**: recursive deletes of system or home roots, raw writes to disk devices, fork bombs, piping a network download straight into a shell or interpreter, decoding base64 straight into a shell, evaluating a downloaded command substitution, and a Bash command that could expose the secrets saved in magician's plugin options (one that names any of those options or the session environment file, reads another process's environment through the proc filesystem, or prints the whole environment with `env`, `set` or one of the other listing commands the guard checks). It exits 2, so the block lands **before permission rules are evaluated** — it overrides `allow` rules and fires in every mode (default/acceptEdits/auto/bypass), with **no escape hatch**. Common command wrappers (`sudo`, `timeout`, `nohup`, `command`, ...), `( )`/`{ }` grouping and inline `sh -c` payloads (other shell options before the `-c` included) are unwrapped before the check. If a Bash or PowerShell call is refused with a `magician destructive-guard: refused` message, do **not** retry, rephrase, or obfuscate — the human must run it themselves outside the agent. Honest limit (CWE-78): a denylist can't catch every obfuscation, so this is a deterministic net layered under OS sandboxing + auto-mode's classifier + model judgment, not a complete sandbox.

## Cadence and ledger

Findings persist in `.workspace/local/security/findings.jsonl`, never committed: open rows map unfixed vulnerabilities. A dismiss reason keeps a closed item closed. The first run is the baseline. Scan weekly: Claude Security scheduled scans where available, else `/loop 1w /sentinel`. Fixes are bounded patches in a reviewed PR. A fixed finding class becomes a scan rule or an eval. Format and steps: [`references/cadence-ledger.md`](references/cadence-ledger.md). The ledger and the scan marker are the only files this skill writes.

## Process

### 0. Mark the scan active
```bash
mkdir -p .workspace/local/security && touch .workspace/local/security-scan.active
```

While this marker exists, magician's PreModelSwitch hook (`scripts/pre-model-switch.sh`) holds any model switch for confirmation, because a safety-classifier fallback would otherwise change the model tier in the middle of the scan. Remove it at the end (`rm -f .workspace/local/security-scan.active`), and also when the scan is abandoned or fails; `.workspace/local/` is never committed.

Then read the ledger ([`references/cadence-ledger.md`](references/cadence-ledger.md#each-run), step 1).

### 1. Static Analysis (via magician-scan)
```bash
magician-scan .
```

`magician-scan` is plugin-provided (on PATH when the plugin is enabled) and makes no network calls. If `magician-scan` can't be run, note that in the report, skip this step, and continue with the remaining checks.

Reports: hardcoded credentials, private keys, eval() calls, SQL injection via % formatting, innerHTML XSS, dangerouslySetInnerHTML, os.system calls, shell=True subprocess.

### 2. Dependency Audit
Run for detected stack:
- Node.js: `npm audit`
- Python: `pip-audit` (if installed) or `safety check`
- Go: `govulncheck ./...` (if installed)
- Rust: `cargo audit`
- Java: OWASP dependency-check (if configured)

The audit tools reach the network, and step 2.5 checks the install-time supply chain. What each tool sends, and the supply-chain checks, are in [`references/dependencies.md`](references/dependencies.md). Skip any tool the user doesn't want run.

### 3. Secret Detection
Check for secrets in git history:
```bash
git log --all -i -G'(password|secret|token|api[_-]?key)[[:space:]]*[:=]' --pretty=format:'%h %ad %an' --date=short --name-only -- '*.env' '*.key' '*.pem' 2>/dev/null | head -40
```

This lists commits and files only (it never prints values). Open a specific commit to confirm, but never paste secret values into the report; tell the user to rotate anything found.

### 4. Auth/Authz Spot Check
For web archetypes: identify all API endpoints and verify auth middleware is applied.

### 5. Input Validation Check
Scan for user input without sanitization.

## Report Format

```
=== SENTINEL SECURITY REPORT ===
Date: <timestamp>
Target: <path>

CRITICAL: N
HIGH:     N
MEDIUM:   N
LOW:      N

[CRITICAL] src/auth.ts:45 — Hardcoded API key
[HIGH] src/db.ts:12 — SQL query built with string concatenation
...

DEPENDENCY AUDIT: N vulnerabilities found

OVERALL POSTURE: Clean | Needs attention | Requires immediate action
```

Update the ledger before the report, and put the delta (new, fixed, still open) first ([`references/cadence-ledger.md`](references/cadence-ledger.md#each-run), steps 2–3).

### 6. CI Integration Note
For CI pipeline use: `magician-scan` exits 0 (clean), 1 (issues) or 2 (unknown option or missing path); `magician-scan --help` shows the usage.

```yaml
# .github/workflows/security.yml
- name: Security scan
  run: magician-scan .
```

## Obstacles

If this skill runs as a dispatched unit and hits something that blocks or degrades the work, do not wait for a human who is not there and do not silently ship a degraded result — return the Obstacles block from [lore/obstacles.md](../../lore/obstacles.md) (fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT) to the caller alongside whatever you completed; interactively, say the same in prose.

## Completion Signal

Remove the marker first (`rm -f .workspace/local/security-scan.active`), so model switches are no longer held; then:

"Sentinel complete. <N total findings>. Review report above and run /scrutinize for systematic remediation."
