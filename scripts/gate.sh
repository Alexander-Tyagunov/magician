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
#   4. Token budget: an offline estimate (bytes / 4) of the always-on cost (skill and agent names and
#      descriptions, which sit in every session) and of each skill body, and, when the `claude` CLI
#      is installed, the CLI's own projection from `claude --plugin-dir . plugin details magician`
#      (text output; the command has no JSON flag). Fails when the CLI reports more than 1,500
#      always-on tokens or a skill body over 6,000 tokens, and when the offline always-on estimate
#      grew by more than 10% over the value recorded in evals/results/budget.json, unless the top
#      CHANGELOG entry mentions "token budget". Both numbers are recorded in that file on every run.
#   5. STE-lite (warn only): `tools/ste-lint --max 200` over skills/*/SKILL.md, README.md and lore/*.md;
#      prints the finding count and the rules that fire most, records the count as `ste_findings` in
#      evals/results/budget.json (merged into the file the token-budget tier wrote), and never fails.
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

# ---- Tier 4: token budget (always; the CLI projection when the `claude` CLI is installed) ------
BUDGET_FILE="$ROOT/evals/results/budget.json"
MAX_ALWAYS_ON=1500
MAX_SKILL_BODY=6000
GROWTH_PCT=10

# frontmatter_bytes FILE -> bytes of the name, description and when_to_use lines of the frontmatter
frontmatter_bytes() {
  local n=0 line infm=0 first=1
  while IFS= read -r line || [ -n "$line" ]; do
    if [ "$first" = 1 ]; then first=0; [ "$line" = "---" ] && { infm=1; continue; } || break; fi
    [ "$line" = "---" ] && break
    case "$line" in
      name:*|description:*|when_to_use:*) n=$((n + ${#line} + 1)) ;;
    esac
  done < "$1"
  printf '%s' "$n"
}
# body_bytes FILE -> bytes after the frontmatter
body_bytes() {
  local total fm
  total=$(wc -c < "$1" | tr -d ' ')
  fm=$(awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {print NR; exit}' "$1")
  if [ -n "$fm" ]; then
    printf '%s' "$(( total - $(head -n "$fm" "$1" | wc -c | tr -d ' ') ))"
  else
    printf '%s' "$total"
  fi
}
# Number in text such as ~1,797 or ~5k or ~730 -> plain integer
tok_number() {
  local s=$1
  s=${s#\~}; s=${s//,/}
  case "$s" in
    *k) s=${s%k}; case "$s" in *.*) s=$(( ${s%.*} * 1000 + ${s#*.} * 100 )) ;; *) s=$(( s * 1000 )) ;; esac ;;
  esac
  printf '%s' "$s"
}

check_token_budget() {
  local ok=1 bytes=0 f name b tok body_json="" line comp always invoke cli_always="" cli_json="" prev
  local changelog_ok=0 top
  # Offline estimate: always-on = name + description lines of every skill and agent, / 4.
  for f in "$ROOT"/skills/*/SKILL.md "$ROOT"/agents/*.md; do
    [ -f "$f" ] || continue
    bytes=$(( bytes + $(frontmatter_bytes "$f") ))
  done
  local offline_always=$(( bytes / 4 ))
  echo "offline estimate: always-on ~${offline_always} tokens (skill and agent names and descriptions, bytes / 4)"
  for f in "$ROOT"/skills/*/SKILL.md; do
    [ -f "$f" ] || continue
    name=${f%/SKILL.md}; name=${name##*/}
    b=$(body_bytes "$f"); tok=$(( b / 4 ))
    body_json="${body_json:+$body_json, }\"$name\": $tok"
    if [ "$tok" -gt "$MAX_SKILL_BODY" ]; then
      echo "skill body over ${MAX_SKILL_BODY} tokens (offline estimate): ${name} ~${tok}"
      ok=0
    fi
  done
  # The CLI's own projection, when available. `claude plugin details` prints text (no JSON flag is
  # documented); the "Always-on:" line and the per-component table are read from it.
  if command -v claude >/dev/null 2>&1; then
    local out
    out=$(cd "$ROOT" && claude --plugin-dir "$ROOT" plugin details magician 2>/dev/null) || out=""
    if [ -n "$out" ]; then
      always=$(printf '%s\n' "$out" | grep -E '^[[:space:]]*Always-on:' | head -1 | sed -E 's/.*Always-on:[[:space:]]*~?([0-9,.k]+).*/\1/')
      [ -n "$always" ] && cli_always=$(tok_number "$always")
      if [ -n "$cli_always" ]; then
        echo "claude plugin details: always-on ~${cli_always} tokens (limit ${MAX_ALWAYS_ON})"
        [ "$cli_always" -gt "$MAX_ALWAYS_ON" ] && { echo "always-on tokens over ${MAX_ALWAYS_ON}"; ok=0; }
      fi
      while IFS= read -r line; do
        set -- $line
        [ "$#" -eq 3 ] || continue
        comp=$1; invoke=$3
        case "$invoke" in ~[0-9]*) ;; *) continue ;; esac
        tok=$(tok_number "$invoke")
        [ -d "$ROOT/skills/$comp" ] || comp="agent:$comp"   # skills and agents can share a name
        cli_json="${cli_json:+$cli_json, }\"$comp\": $tok"
        if [ -d "$ROOT/skills/$comp" ] && [ "$tok" -gt "$MAX_SKILL_BODY" ]; then
          echo "skill body over ${MAX_SKILL_BODY} tokens (claude plugin details): ${comp} ~${tok}"
          ok=0
        fi
      done <<EOF_DETAILS
$(printf '%s\n' "$out" | sed -n '/^Per-component/,/^$/p' | sed -n '3,$p')
EOF_DETAILS
    else
      echo "claude plugin details gave no output; CLI projection skipped"
    fi
  else
    echo "claude CLI not found; CLI projection skipped (offline estimate only)"
  fi
  # Growth check against the recorded offline value, waived by a CHANGELOG note.
  top=$(awk '/^## /{n++} n==1' "$ROOT/CHANGELOG.md" 2>/dev/null)
  case "$top" in *"token budget"*) changelog_ok=1 ;; esac
  if [ -f "$BUDGET_FILE" ]; then
    prev=$(grep -oE '"offline_always_on_tokens": *[0-9]+' "$BUDGET_FILE" | head -1 | grep -oE '[0-9]+$')
    if [ -n "$prev" ] && [ "$prev" -gt 0 ]; then
      if [ $(( offline_always * 100 )) -gt $(( prev * (100 + GROWTH_PCT) )) ]; then
        if [ "$changelog_ok" = 1 ]; then
          echo "always-on estimate grew over ${GROWTH_PCT}% (${prev} -> ${offline_always}); accepted, the CHANGELOG's top entry mentions the token budget"
        else
          echo "always-on estimate grew over ${GROWTH_PCT}% (${prev} -> ${offline_always}) with no \"token budget\" note in the CHANGELOG's top entry"
          ok=0
        fi
      else
        echo "always-on estimate within ${GROWTH_PCT}% of the recorded ${prev}"
      fi
    fi
  else
    echo "no recorded budget yet; this run sets the baseline"
  fi
  mkdir -p "${BUDGET_FILE%/*}" 2>/dev/null
  {
    printf '{\n  "recorded_at": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '  "offline_always_on_tokens": %s,\n' "$offline_always"
    printf '  "offline_skill_body_tokens": {%s},\n' "$body_json"
    printf '  "cli_always_on_tokens": %s,\n' "${cli_always:-null}"
    if [ -n "$cli_json" ]; then printf '  "cli_on_invoke_tokens": {%s}\n' "$cli_json"; else printf '  "cli_on_invoke_tokens": null\n'; fi
    printf '}\n'
  } > "$BUDGET_FILE" 2>/dev/null && echo "recorded in ${BUDGET_FILE#$ROOT/}"
  [ "$ok" = 1 ]
}
run_tier "Token budget (always-on under ${MAX_ALWAYS_ON}, skill bodies under ${MAX_SKILL_BODY}, growth under ${GROWTH_PCT}%)" check_token_budget

# ---- Tier 5: STE-lite over magician's own prose (always; warn only, never fails) ---------------
# Skill bodies, the README and the lore cores are read by the model and by people; the count of
# ste-lint findings is a size and clarity signal recorded next to the token budget. The tier
# prints the count and the rules that fire most and passes whatever the count is.
STE_LINT="$ROOT/tools/ste-lint"
# Reads ste-lint's JSON report on stdin, prints one summary line, and merges ste_findings into the
# budget file (argument 1) without touching its other keys.
STE_MERGE='
import json, sys
from collections import Counter
budget = sys.argv[1]
try:
    doc = json.load(sys.stdin)
except ValueError:
    print("unreadable report"); sys.exit(0)
total = int(doc.get("total", 0))
tally = Counter(f.get("rule", "?") for f in doc.get("findings", []))
top = ", ".join("%s %d" % (r, c) for r, c in tally.most_common(6))
print("%d findings (%d errors, %d warnings) over %d files; most frequent among the first %d: %s" % (
    total, doc.get("errors", 0), doc.get("warnings", 0), len(doc.get("files", [])), doc.get("shown", 0), top or "none"))
try:
    cur = json.load(open(budget, encoding="utf-8"))
    if not isinstance(cur, dict):
        cur = {}
except (OSError, ValueError):
    cur = {}
cur["ste_findings"] = total
with open(budget, "w", encoding="utf-8") as fh:
    json.dump(cur, fh, indent=2)
    fh.write("\n")
'
check_ste_lite() {
  local n
  if [ ! -x "$STE_LINT" ]; then
    echo "tools/ste-lint not executable; STE-lite tier skipped"
    return 0
  fi
  n=$(cd "$ROOT" && "$STE_LINT" --json --max 200 skills/*/SKILL.md README.md lore/*.md 2>/dev/null | "$PY" -c "$STE_MERGE" "$BUDGET_FILE")
  echo "STE-lite: ${n:-no report}"
  echo "recorded as ste_findings in ${BUDGET_FILE#$ROOT/} (warn only; the gate never fails on this count)"
  return 0
}
run_tier "STE-lite (warn)" check_ste_lite

# ---- Tier 6: behavioral evals (opt-in, local only) ---------------------------------------------
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
