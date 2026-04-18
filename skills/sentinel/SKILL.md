---
name: sentinel
description: Runs a full security scan — OWASP Top 10, credential detection, injection surfaces, dependency audit
keep-coding-instructions: true
---

# /sentinel — Security Scan

Run a comprehensive security scan of the codebase. Available as CLI: `bin/magician-scan`.

## Process

### 1. Static Analysis (via magician-scan)
```bash
SCAN=$(command -v magician-scan 2>/dev/null || echo "${CLAUDE_PLUGIN_ROOT}/bin/magician-scan")
"$SCAN" .
```

Reports: hardcoded credentials, private keys, eval() calls, SQL injection via % formatting, innerHTML XSS, dangerouslySetInnerHTML, os.system calls, shell=True subprocess.

### 2. Dependency Audit
Run for detected stack:
- Node.js: `npm audit`
- Python: `pip-audit` (if installed) or `safety check`
- Go: `govulncheck ./...` (if installed)
- Rust: `cargo audit`
- Java: OWASP dependency-check (if configured)

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
For CI pipeline use: `bin/magician-scan` exits 0 (clean) or 1 (issues).

```yaml
# .github/workflows/security.yml
- name: Security scan
  run: bin/magician-scan .
```

## Completion Signal

"Sentinel complete. <N total findings>. Review report above and run /absorb for systematic remediation."
