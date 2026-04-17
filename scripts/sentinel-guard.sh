#!/usr/bin/env bash
# PreToolUse(Bash) hook — scans command for dangerous patterns before execution.

set -euo pipefail

INPUT=$(cat)

python3 - "$INPUT" <<'PYEOF'
import json, re, sys

try:
    data = json.loads(sys.argv[1])
except Exception:
    sys.exit(0)

command = ""
if isinstance(data, dict):
    inp = data.get("input", data)
    command = inp.get("command", inp.get("cmd", "")) if isinstance(inp, dict) else ""

if not command:
    sys.exit(0)

BLOCK_RULES = [
    (r'curl\b.+\|\s*(bash|sh)\b',           "pipe-to-shell via curl"),
    (r'wget\b.+\|\s*(bash|sh)\b',            "pipe-to-shell via wget"),
    (r'\beval\s+["\$`]',                      "eval with dynamic content"),
    (r'\brm\s+(-\w*r\w*f|-\w*f\w*r)\s+/',   "rm -rf on absolute path"),
    (r'cat\s+[~]?/?\.?ssh/',                  "reading SSH directory"),
    (r'cat\s+[~]?/?\.?aws/credentials',       "reading AWS credentials"),
    (r'\bcat\s+\.env\b',                      "reading .env file"),
]

for pattern, reason in BLOCK_RULES:
    if re.search(pattern, command, re.IGNORECASE | re.DOTALL):
        print(json.dumps({
            "decision": "block",
            "reason": f"Security guard blocked: {reason}. Review the command and run manually if intended."
        }))
        sys.exit(0)

has_private = bool(re.search(r'(\.ssh|\.aws|\.env|password|secret|token)', command, re.I))
has_network = bool(re.search(r'\b(curl|wget|nc|ncat|ssh|scp|rsync)\b', command, re.I))
has_exec    = bool(re.search(r'\|\s*(bash|sh|python|ruby|node)\b', command, re.I))

if has_private and has_network and has_exec:
    print(json.dumps({
        "decision": "block",
        "reason": "Lethal trifecta detected: private data + network access + execution. Requires manual review."
    }))
    sys.exit(0)

sys.exit(0)
PYEOF
