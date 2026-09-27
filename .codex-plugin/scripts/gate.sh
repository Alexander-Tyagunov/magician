#!/usr/bin/env bash
# Codex-branch gate: the committed package must equal build(main@SOURCE_REF), and tests/codex must pass.
# Usage: .codex-plugin/scripts/gate.sh <main-checkout>   (or MAGICIAN_MAIN_SOURCE)
#        MAGICIAN_CODEX_SMOKE=1 adds an isolated Codex install smoke (throwaway CODEX_HOME only).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE="${1:-${MAGICIAN_MAIN_SOURCE:-}}"
PY="${PYTHON:-python3}"
if [ -z "$SOURCE" ] || [ ! -f "$SOURCE/.claude-plugin/plugin.json" ]; then
  echo "gate: pass a magician main checkout (or set MAGICIAN_MAIN_SOURCE)" >&2; exit 2
fi
REF="$(tr -d '[:space:]' < "$ROOT/.codex-plugin/SOURCE_REF")"
[ -n "$REF" ] || { echo "gate: .codex-plugin/SOURCE_REF is empty" >&2; exit 2; }
# Temp trees are left in $TMPDIR on purpose (no recursive cleanup in this script).
MAIN_TREE="$(mktemp -d "${TMPDIR:-/tmp}/magician-main.XXXXXX")"
git -C "$SOURCE" archive "$REF" | tar -x -C "$MAIN_TREE" || { echo "gate: cannot export $REF from $SOURCE" >&2; exit 2; }
fail=0
tier() { label="$1"; shift; echo "== $label"; if "$@"; then echo "PASS $label"; else echo "FAIL $label"; fail=1; fi; echo; }
tier "package == build(main@$REF)" "$PY" "$ROOT/.codex-plugin/scripts/build_package.py" --source "$MAIN_TREE" --check
tier "tests/codex" env MAGICIAN_MAIN_SOURCE="$MAIN_TREE" PYTHONDONTWRITEBYTECODE=1 "$PY" -m unittest discover -s "$ROOT/tests/codex" -p 'test_*.py'
if [ "${MAGICIAN_CODEX_SMOKE:-0}" = 1 ]; then
  tier "isolated Codex install smoke" env MAGICIAN_MAIN_SOURCE="$MAIN_TREE" bash "$ROOT/.codex-plugin/scripts/smoke-install.sh"
fi
exit "$fail"
