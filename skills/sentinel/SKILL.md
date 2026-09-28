---
name: sentinel
description: Security scan — OWASP Top 10, credential/secret detection, injection surfaces, dependency audit, git-history secret scan, auth spot-check. Never modifies code; produces a severity-ranked report. Use to audit a codebase for vulnerabilities.
allowed-tools: Read, Grep, Glob, Bash(magician-scan *), Bash(npm audit), Bash(npm audit --json), Bash(pip-audit), Bash(pip-audit -f json), Bash(safety check), Bash(govulncheck ./...), Bash(cargo audit)
context: fork
background: false
argument-hint: "[path]"
---

# /sentinel — Security Scan

Run a comprehensive security scan of the codebase. Available as CLI: `magician-scan` (plugin-provided; on PATH when the plugin is enabled).

For very large repos, raise /effort so the analysis stays thorough across the codebase (your model's deepest level — `xhigh`, or `max` where unsupported). See [lore/models.md](../../lore/models.md).

## The scan can change models under you

Opus 5 and Fable 5 run cybersecurity classifiers, and Claude Code responds to a flag by **re-running the request on a fallback model and continuing the session there** (Fable 5 → Opus 4.8; Opus 5 → Opus 4.8). A long sweep can therefore finish on a different tier than it started on, with only a transcript notice to say so. Three things follow:

- **Frame the work defensively and concretely.** "Audit this code for injection surfaces and report them" reads as the defensive review it is. Asking for working exploits, attack tooling, or evasion techniques is what trips the classifier — and it is outside this skill's scope anyway: sentinel is read-only and reports findings with remediation.
- **Notice the switch.** If a fallback notice appears mid-scan, say so in the report rather than presenting mixed-tier findings as one uniform pass, and offer `/model` to return.
- **When it fires on nothing.** A flag on the *first* request usually comes from workspace context — `CLAUDE.md`, skills, directory names, git status — not from what was asked. `claude --safe-mode` runs without customizations and isolates that. To be asked instead of switched, set `switchModelsOnFlag: false`.

See [lore/models.md](../../lore/models.md#safety-classifiers-change-which-model-you-end-up-on).

## Destructive-command hard gate (always on, not part of a scan)

Independent of any scan, magician ships a `PreToolUse(Bash|PowerShell)` hook, `scripts/destructive-guard.sh` (self-contained plain bash — no other interpreter), that **unconditionally blocks catastrophic commands**: recursive deletes of system or home roots, raw writes to disk devices, fork bombs, piping a network download straight into a shell or interpreter, decoding base64 straight into a shell, evaluating a downloaded command substitution, and a Bash command that reads or dumps the plugin's `CLAUDE_PLUGIN_OPTION_*` userConfig secrets (a bare `env`/`printenv`/`export`/`set`/`declare -x`/`declare -p`/`compgen -e`, a read of `/proc/<pid>/environ`, or a direct reference to the secret variable). It exits 2, so the block lands **before permission rules are evaluated** — it overrides `allow` rules and fires in every mode (default/acceptEdits/auto/bypass), with **no escape hatch**. Common command wrappers (`sudo`, `timeout`, `nohup`, `command`, ...), `( )`/`{ }` grouping and inline `sh -c` payloads (other shell options before the `-c` included) are unwrapped before the check. If a Bash or PowerShell call is refused with a `magician destructive-guard: refused` message, do **not** retry, rephrase, or obfuscate — the human must run it themselves outside the agent. Honest limit (CWE-78): a denylist can't catch every obfuscation, so this is a deterministic net layered under OS sandboxing + auto-mode's classifier + model judgment, not a complete sandbox.

## Process

### 1. Static Analysis (via magician-scan)
```bash
magician-scan .
```

`magician-scan` is plugin-provided (on PATH when the plugin is enabled) and makes no network calls. If the command is not found, note that in the report, skip this step, and continue with the remaining checks.

Reports: hardcoded credentials, private keys, eval() calls, SQL injection via % formatting, innerHTML XSS, dangerouslySetInnerHTML, os.system calls, shell=True subprocess.

### 2. Dependency Audit
Run for detected stack:
- Node.js: `npm audit`
- Python: `pip-audit` (if installed) or `safety check`
- Go: `govulncheck ./...` (if installed)
- Rust: `cargo audit`
- Java: OWASP dependency-check (if configured)

These audit tools reach the network: `npm audit` sends the dependency list to the npm registry; `pip-audit` sends package names and versions to PyPI (or OSV, if you choose it); `safety check` downloads Safety's vulnerability database and, when you use a Safety API key, sends the package list to Safety's servers; `govulncheck` asks the Go vulnerability database at vuln.go.dev about the modules you use, and the go command downloads any module missing from its cache from your module proxy (proxy.golang.org by default); and `cargo audit` downloads the RustSec advisory database from GitHub and, to spot yanked versions, fetches the crates.io index entry of each crate in Cargo.lock. Skip any the user doesn't want run.

### 2.5 Dependency Supply-Chain Check
Known-CVE audits miss supply-chain attacks — the vector behind recent registry compromises where a plain install exfiltrates SSH keys, cloud creds, and env secrets. Check the install-time surface:
- **Install-time scripts** — flag lifecycle hooks that run arbitrary code on install:
  ```bash
  grep -rEn '"(preinstall|install|postinstall)"\s*:' package.json 2>/dev/null
  ```
  (Python equivalent: custom `setup.py`/`pyproject.toml` build hooks.)
- **Newly added / unfamiliar deps** — review new lockfile entries and dependencies that are typosquats of popular packages.
- **Exfiltration shape** — a dependency that reads credentials (`~/.ssh`, `~/.aws`, env vars, wallets) *and* reaches the network is high-risk; escalate as Critical.
- Prefer lockfile integrity in CI (`npm ci`, not `npm install`) and pinned versions.

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

### 6. CI Integration Note
For CI pipeline use: `magician-scan` exits 0 (clean) or 1 (issues).

```yaml
# .github/workflows/security.yml
- name: Security scan
  run: magician-scan .
```

## Obstacles

If this skill runs as a dispatched unit (under /orchestrate, /weave, /manifest, /transmute, or another skill) and hits something that blocks or degrades the work, do not wait for a human who is not there and do not silently ship a degraded result — return an Obstacles block to the caller, alongside whatever you did complete:

```
STATUS: BLOCKED | DEGRADED | NEEDS_CONTEXT
OBSTACLE: <one-line label of what blocked or degraded the task — the claim alone>
BLOCKER: <the specific, actionable cause — distilled, never a raw traceback or dumped log>
SEVERITY: Critical | High | Medium | Low
WORKAROUND: <what you did to proceed and what it leaves unverified; empty if still fully blocked>
RECURRENCE: First-seen | Recurring | Systemic
SCOPE: <this task only | likely hits sibling/downstream work too>
NEXT: <the action or decision the caller must make to clear it — retry with X, supply input Y, accept degraded, or escalate>
```

When invoked interactively by a human, surface the same obstacle in prose instead. Omit the block entirely on a clean run. See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

"Sentinel complete. <N total findings>. Review report above and run /scrutinize for systematic remediation."
