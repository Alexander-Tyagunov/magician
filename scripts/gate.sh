#!/usr/bin/env bash
# Magician quality gate — the single pass/fail entrypoint for the whole plugin.
#
# Runs the offline gates every time (fast, deterministic, no network, no cost):
#   * Claude-side gates  (tests/claude)  — hooks, agents, skills, manifest, destructive guard,
#                                          compaction boundary, eval-suite shape, guardrails.
#   * Codex-side gates   (tests/codex)   — packaging, adapters, guard, project context.
#
# The behavioral eval suite (`claude plugin eval`) spends API budget and needs the network, so it
# is OPT-IN: pass `--evals` (or set MAGICIAN_GATE_EVALS=1). CI can gate on the offline tiers and
# schedule evals separately.
#
# Exit 0 only if every selected tier passes. Any failure → non-zero, and the gate stops reporting
# GO. Usage:  scripts/gate.sh [--evals] [--threshold N] [--eval-model M] [--judge-model M]
set -uo pipefail

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PY="${PYTHON:-python3}"

RUN_EVALS="${MAGICIAN_GATE_EVALS:-0}"
THRESHOLD="0.8"
EVAL_MODEL=""
JUDGE_MODEL=""

while [ $# -gt 0 ]; do
  case "$1" in
    --evals) RUN_EVALS=1 ;;
    --threshold) THRESHOLD="$2"; shift ;;
    --eval-model) EVAL_MODEL="$2"; shift ;;
    --judge-model) JUDGE_MODEL="$2"; shift ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "gate: unknown option '$1'" >&2; exit 64 ;;
  esac
  shift
done

fail=0
hr() { printf '%s\n' "────────────────────────────────────────────────────────"; }
run_tier() {
  local label="$1"; shift
  hr; echo "▶ ${label}"; hr
  if "$@"; then
    echo "✔ ${label}: PASS"
  else
    echo "✘ ${label}: FAIL"
    fail=1
  fi
  echo
}

# ---- Tier 1 & 2: offline gates (always) --------------------------------------------------------
run_tier "Claude gates (tests/claude)" \
  "$PY" -m unittest discover -s "$ROOT/tests/claude" -p 'test_*.py'
run_tier "Codex gates (tests/codex)" \
  "$PY" -m unittest discover -s "$ROOT/tests/codex" -p 'test_*.py'

# ---- Tier 2b: official manifest/skill validator (offline, no cost; needs the `claude` CLI) ------
# `claude plugin validate` is Anthropic's own frontmatter/schema/path check. It is local and free,
# so run it whenever the CLI is present; skip (do not fail) where it isn't installed.
if command -v claude >/dev/null 2>&1; then
  run_tier "Plugin validator (claude plugin validate)" \
    claude plugin validate "$ROOT"
else
  echo "· Plugin validator skipped ('claude' CLI not found)."
  echo
fi

# ---- Tier 3: behavioral evals (opt-in) ---------------------------------------------------------
if [ "$RUN_EVALS" = "1" ]; then
  if command -v claude >/dev/null 2>&1; then
    eval_cmd=(claude plugin eval "$ROOT" --trust-plugin --threshold "$THRESHOLD" --json "$ROOT/.gate-evals.json")
    [ -n "$EVAL_MODEL" ]  && eval_cmd+=(--model "$EVAL_MODEL")
    [ -n "$JUDGE_MODEL" ] && eval_cmd+=(--judge-model "$JUDGE_MODEL")
    run_tier "Behavioral evals (claude plugin eval)" "${eval_cmd[@]}"
  else
    hr; echo "▶ Behavioral evals (claude plugin eval)"; hr
    echo "✘ 'claude' CLI not found — cannot run the eval tier."; fail=1; echo
  fi
else
  echo "· Behavioral eval tier skipped (pass --evals or set MAGICIAN_GATE_EVALS=1 to run it)."
  echo
fi

hr
if [ "$fail" = "0" ]; then
  echo "GATE: GO — all selected tiers passed."
else
  echo "GATE: NO-GO — at least one tier failed (see above)."
fi
hr
exit "$fail"
