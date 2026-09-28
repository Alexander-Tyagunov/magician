#!/usr/bin/env bash
# Magician quality gate — the single pass/fail entrypoint for the whole plugin.
#
# Runs the offline tiers every time (fast, deterministic, no network, no cost):
#   1. Claude-side gates (tests/claude) — hooks and hook scripts, session start, compaction,
#      userConfig bridge, magician-ui, agents, skills, strict frontmatter, manifest, lore,
#      destructive guard, eval-suite shape, guardrails.
#   2. Official validator, strict: `claude plugin validate .claude-plugin/plugin.json --strict`
#      and `claude plugin validate . --strict` (warnings fail). Skipped with a note when the
#      `claude` CLI isn't installed (CI has no claude CLI; run it locally before a release).
#   3. Directory limits: at most 512 tracked files, no non-image file of 256 KiB or more, only text,
#      SVG, PNG, JPEG, GIF, WebP and font files, and no OS junk (.DS_Store, Thumbs.db, desktop.ini,
#      __MACOSX).
#   (The Codex package is built and gated on the `codex-plugin` branch.)
#
# The behavioral eval suite (claude plugin eval --trust-plugin) spends API budget and needs the
# network, so it is OPT-IN and local-only: pass `--evals` (or set MAGICIAN_GATE_EVALS=1). CI never
# runs it.
#
# Exit 0 only if every selected tier passes. Any failure → non-zero, and the gate stops reporting
# GO. Usage:  scripts/gate.sh [--evals] [--threshold N] [--eval-model M] [--judge-model M]
set -uo pipefail
export LC_ALL=C

ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
PY="${PYTHON:-python3}"

RUN_EVALS="${MAGICIAN_GATE_EVALS:-0}"
THRESHOLD="0.8"
EVAL_MODEL=""
JUDGE_MODEL=""

MAX_FILES=512
MAX_BYTES=262144   # 256 KiB; applies to every file that isn't an image

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

# Files that ship: tracked files still present in the working tree. Outside a git checkout
# (e.g. an installed plugin copy) every regular file except .git/ and caches counts.
list_files() {
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "$ROOT" ls-files -z | while IFS= read -r -d '' f; do
      [ -f "$ROOT/$f" ] && printf '%s\n' "$f"
    done
  else
    (cd "$ROOT" && find . -type f ! -path './.git/*' ! -path '*/__pycache__/*' | sed 's|^\./||')
  fi
}

check_file_count() {
  local n
  n=$(list_files | wc -l | tr -d ' ')
  echo "files: ${n} (limit ${MAX_FILES})"
  [ "$n" -le "$MAX_FILES" ]
}

check_file_sizes() {
  local f sz big=0
  while IFS= read -r f; do
    case "$f" in
      *.png|*.PNG|*.jpg|*.JPG|*.jpeg|*.JPEG|*.gif|*.GIF|*.webp|*.WEBP|*.svg|*.SVG) continue ;;
    esac
    sz=$(wc -c < "$ROOT/$f" 2>/dev/null | tr -d ' ')
    if [ "${sz:-0}" -ge "$MAX_BYTES" ]; then
      echo "too large: ${f} (${sz} bytes; limit is under ${MAX_BYTES})"
      big=1
    fi
  done < <(list_files)
  [ "$big" = 0 ] && echo "no non-image file is ${MAX_BYTES} bytes or larger"
  [ "$big" = 0 ]
}

# The directory accepts text, SVG, PNG, JPEG, GIF, WebP and fonts. It blocks OS junk files and holds
# any other type (.ico, .pdf, archives, executables), so fail on both. A file with a NUL byte that
# isn't an image or font counts as binary.
check_file_types() {
  local f base bad=0
  while IFS= read -r f; do
    base=${f##*/}
    case "/$f/" in
      */__MACOSX/*) echo "OS junk: ${f}"; bad=1; continue ;;
    esac
    case "$base" in
      .DS_Store|Thumbs.db|desktop.ini) echo "OS junk: ${f}"; bad=1; continue ;;
    esac
    shopt -s nocasematch
    case "$base" in
      *.png|*.jpg|*.jpeg|*.gif|*.webp|*.svg|*.woff|*.woff2|*.ttf|*.otf) shopt -u nocasematch; continue ;;
      *.ico|*.pdf|*.zip|*.gz|*.tgz|*.tar|*.7z|*.rar|*.jar|*.class|*.exe|*.dll|*.so|*.dylib|*.o|*.a|\
      *.bin|*.dmg|*.pyc|*.wasm|*.bmp|*.tif|*.tiff|*.heic|*.mp4|*.mov|*.mp3)
        shopt -u nocasematch; echo "type not accepted: ${f}"; bad=1; continue ;;
    esac
    shopt -u nocasematch
    if [ "$(tr -d '\000' < "$ROOT/$f" | wc -c)" != "$(wc -c < "$ROOT/$f")" ]; then
      echo "binary file: ${f}"; bad=1
    fi
  done < <(list_files)
  [ "$bad" = 0 ] && echo "every file is text, an accepted image type or a font, and there is no OS junk"
  [ "$bad" = 0 ]
}

# ---- Tier 1: Claude-side gates (always) --------------------------------------------------------
run_tier "Claude gates (tests/claude)" \
  "$PY" -m unittest discover -s "$ROOT/tests/claude" -p 'test_*.py'

# ---- Tier 2: official manifest/skill validator (local, no cost; needs the `claude` CLI) ---------
# `claude plugin validate` is Anthropic's own schema/frontmatter/path check. --strict turns warnings
# into failures. Skip (do not fail) where the CLI isn't installed, as in CI.
if command -v claude >/dev/null 2>&1; then
  run_tier "Plugin validator, manifest (claude plugin validate .claude-plugin/plugin.json --strict)" \
    claude plugin validate "$ROOT/.claude-plugin/plugin.json" --strict
  run_tier "Plugin validator, repository (claude plugin validate . --strict)" \
    claude plugin validate "$ROOT" --strict
else
  echo "· Plugin validator skipped ('claude' CLI not found; run it locally before a release)."
  echo
fi

# ---- Tier 3: directory limits (always) ----------------------------------------------------
run_tier "File count (at most ${MAX_FILES} files)" check_file_count
run_tier "File sizes (no non-image file of 256 KiB or more)" check_file_sizes
run_tier "File types (text, SVG, PNG, JPEG, GIF, WebP and fonts; no OS junk)" check_file_types

# ---- Tier 4: behavioral evals (opt-in, local only) ---------------------------------------------
if [ "$RUN_EVALS" = "1" ]; then
  if command -v claude >/dev/null 2>&1; then
    eval_cmd=(claude plugin eval --trust-plugin "$ROOT" --threshold "$THRESHOLD" --json "$ROOT/.gate-evals.json")
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
