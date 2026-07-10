---
name: sentinel
description: Security scan — OWASP Top 10, credential/secret detection, injection surfaces, dependency audit, git-history secret scan, auth spot-check. Read-only; produces a severity-ranked report. Use to audit a codebase for vulnerabilities.
allowed-tools: Bash, Read, Grep, Glob
context: fork
argument-hint: [path]
---

# /sentinel — Security Scan

Run a comprehensive security scan of the codebase. Available as CLI: `magician-scan` (plugin-provided; on PATH when the plugin is enabled).

For very large repos, raise /effort so the analysis stays thorough across the codebase. See [lore/models.md](../../lore/models.md).

## Destructive-command hard gate (always on, not part of a scan)

Independent of any scan, magician ships a `PreToolUse(Bash|PowerShell)` hook (`scripts/destructive-guard.sh` → `destructive_guard.py`) that **unconditionally blocks catastrophic commands** — filesystem wipes (`rm -rf /` · `~` · `$HOME` · `--no-preserve-root` · system roots), disk/device destruction (`dd of=/dev/…`, `mkfs`, `wipefs`, `blkdiscard`, `shred /dev/…`, `diskutil erase…`), redirection onto a block device or over `/etc/passwd|shadow|sudoers|fstab`, fork bombs, recursive `chmod`/`chown` on system roots, `curl|bash` / `base64 -d|sh` / `eval "$(…)"`, and `git clean -x`. It exits 2, so the block lands **before permission rules are evaluated** — it overrides `allow` rules and fires in every mode (default/acceptEdits/auto/bypass), with **no escape hatch**. Wrappers (`sudo`, `env`, `timeout`, …) and `sh -c '…'` payloads are unwrapped first. If you hit `[MAGICIAN HARD-GATE]`, do **not** retry, rephrase, or obfuscate — the human must run it themselves outside the agent. Honest limit (CWE-78): a denylist can't catch every obfuscation, so this is a deterministic net layered under OS sandboxing + auto-mode's classifier + model judgment, not a complete sandbox.

## Process

### 1. Static Analysis (via magician-scan)
```bash
SCAN=$(command -v magician-scan 2>/dev/null || echo "${CLAUDE_PLUGIN_ROOT}/bin/magician-scan")
[ -x "$SCAN" ] && "$SCAN" . || echo "magician-scan not found; skipping static-analysis step (continuing with remaining checks)"
```

`magician-scan` is plugin-provided (on PATH when the plugin is enabled). If absent, this step degrades gracefully and the remaining checks still run.

Reports: hardcoded credentials, private keys, eval() calls, SQL injection via % formatting, innerHTML XSS, dangerouslySetInnerHTML, os.system calls, shell=True subprocess.

### 2. Dependency Audit
Run for detected stack:
- Node.js: `npm audit`
- Python: `pip-audit` (if installed) or `safety check`
- Go: `govulncheck ./...` (if installed)
- Rust: `cargo audit`
- Java: OWASP dependency-check (if configured)

### 2.5 Dependency Supply-Chain Check
Known-CVE audits miss supply-chain attacks — the vector behind recent real incidents (litellm/PyPI, npm axios) where a plain install exfiltrates SSH keys, cloud creds, and env secrets. Check the install-time surface:
- **Install-time scripts** — flag lifecycle hooks that run arbitrary code on install:
  ```bash
  grep -rEn '"(preinstall|install|postinstall)"\s*:' package.json 2>/dev/null
  ```
  (Python equivalent: custom `setup.py`/`pyproject.toml` build hooks.)
- **Recently added / unfamiliar deps** — review new lockfile entries and dependencies that are typosquats of popular packages.
- **Exfiltration shape** — a dependency that reads credentials (`~/.ssh`, `~/.aws`, env vars, wallets) *and* reaches the network is high-risk; escalate as Critical.
- Prefer lockfile integrity in CI (`npm ci`, not `npm install`) and pinned versions.

### 3. Secret Detection
Check for secrets in git history:
```bash
git log --all --full-history -p -- "*.env" "*.key" "*.pem" 2>/dev/null | grep -i "password\|secret\|key\|token" | head -20
```

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

## Completion Signal

"Sentinel complete. <N total findings>. Review report above and run /scrutinize for systematic remediation."
