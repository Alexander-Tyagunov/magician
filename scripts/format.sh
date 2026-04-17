#!/usr/bin/env bash
# PostToolUse(Write|Edit) hook — auto-formats written/edited files.

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(python3 - "$INPUT" <<'PYEOF'
import json, sys
try:
    d = json.loads(sys.argv[1])
    inp = d.get("input", d)
    print(inp.get("file_path", inp.get("path", "")) if isinstance(inp, dict) else "")
except:
    pass
PYEOF
)

[ -z "$FILE_PATH" ] && exit 0
[ -f "$FILE_PATH" ] || exit 0

EXT="${FILE_PATH##*.}"

case "$EXT" in
  js|jsx|ts|tsx|json|css|scss|html|md)
    command -v prettier &>/dev/null && prettier --write "$FILE_PATH" --log-level silent 2>/dev/null || true
    ;;
  py)
    if command -v ruff &>/dev/null; then
      ruff format "$FILE_PATH" --quiet 2>/dev/null || true
    elif command -v black &>/dev/null; then
      black "$FILE_PATH" --quiet 2>/dev/null || true
    fi
    ;;
  go)
    command -v gofmt &>/dev/null && gofmt -w "$FILE_PATH" 2>/dev/null || true
    ;;
  rs)
    command -v rustfmt &>/dev/null && rustfmt "$FILE_PATH" 2>/dev/null || true
    ;;
  sh|bash)
    command -v shfmt &>/dev/null && shfmt -w "$FILE_PATH" 2>/dev/null || true
    ;;
esac

exit 0
