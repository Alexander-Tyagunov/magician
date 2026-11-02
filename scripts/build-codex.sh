#!/usr/bin/env bash
# Build the Codex / ChatGPT plugin package from this tree, then validate it.
#
# Usage: scripts/build-codex.sh [--out DIR] [--no-validate]
#   --out DIR      the plugin folder to write (default dist/codex/magician). The marketplace file goes
#                  to DIR/../.agents/plugins/marketplace.json. An existing DIR is replaced only when it
#                  holds a plugin.json from an earlier build.
#   --no-validate  skip the checks (frontmatter keys, description length, links, plugin variables,
#                  JSON) and `codex plugin validate`.
#
# The work is done by scripts/build_codex.py (Python 3, stdlib only). The output is deterministic and
# is not committed: dist/ is gitignored.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"

case "${1:-}" in
  -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "build-codex: python3 not found" >&2
  exit 1
fi
exec "$PY" "$ROOT/scripts/build_codex.py" "$@"
