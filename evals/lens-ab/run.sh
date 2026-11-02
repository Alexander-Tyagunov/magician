#!/usr/bin/env bash
# Lens-model A/B (proposal L2): run the review cases tagged `lens-ab` once per model for the
# simplifier and verifier lenses, then print findings recall per lens per model.
#
# A lens's model comes from the `model:` line of its agents/<lens>.md frontmatter; claude plugin
# eval has no per-subagent model flag (its --model sets the main loop for every case). So for each
# model this copies the plugin to a scratch folder, rewrites that line in the copied lens files and
# runs the eval against the copy. The main loop keeps one model in every arm (--main-model, else
# the CLI default), so the lens model is the only thing that changes.
#
# Spends API credit: every model runs every lens-ab case `runs` times (no baseline arm). Nothing
# here runs in scripts/gate.sh. Bash 3.2 compatible.
#
# Usage: evals/lens-ab/run.sh [--models "haiku sonnet"] [--lenses "simplifier verifier"]
#          [--main-model M] [--judge-model M] [--runs N] [--max-cost USD] [--out DIR] [--dry-run]
# Writes <out>/<model>.json and <out>/<model>/aggregate-result.json, then runs summarize.py on them.
set -u
export LC_ALL=C

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="${PYTHON:-python3}"

MODELS="haiku sonnet"
LENSES="simplifier verifier"
MAIN_MODEL=""
JUDGE_MODEL="sonnet"
RUNS=""
MAX_COST="${MAGICIAN_EVAL_MAX_COST:-20}"
ALLOW="${MAGICIAN_EVAL_ALLOW_TOOLS:-Bash Edit Write}"
OUT=""
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --models) MODELS="$2"; shift ;;
    --lenses) LENSES="$2"; shift ;;
    --main-model) MAIN_MODEL="$2"; shift ;;
    --judge-model) JUDGE_MODEL="$2"; shift ;;
    --runs) RUNS="$2"; shift ;;
    --max-cost) MAX_COST="$2"; shift ;;
    --out) OUT="$2"; shift ;;
    --dry-run) DRY=1 ;;
    -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "lens-ab: unknown option '$1'" >&2; exit 64 ;;
  esac
  shift
done

if [ "$DRY" = 0 ] && ! command -v claude >/dev/null 2>&1; then
  echo "lens-ab: the 'claude' CLI is not installed" >&2
  exit 1
fi
[ -n "$OUT" ] || OUT="$(mktemp -d "${TMPDIR:-/tmp}/magician-lens-ab.XXXXXX")"
mkdir -p "$OUT"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/magician-lens-ab-plugin.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# set_model FILE MODEL: rewrite the frontmatter `model:` line only.
set_model() {
  local f="$1" m="$2" tmp="$1.tmp"
  awk -v m="$m" 'NR==1 && /^---$/ {fm=1; print; next}
                 fm && /^---$/ {fm=0}
                 fm && /^model:/ {print "model: " m; next}
                 {print}' "$f" > "$tmp" && mv "$tmp" "$f"
}

reports=""
status=0
for model in $MODELS; do
  copy="$WORK/$model"
  mkdir -p "$copy"
  (cd "$ROOT" && tar cf - --exclude=./.git --exclude=./evals/results --exclude='*/__pycache__' .) | (cd "$copy" && tar xf -)
  for lens in $LENSES; do
    if [ ! -f "$copy/agents/$lens.md" ]; then
      echo "lens-ab: no agents/$lens.md" >&2; exit 64
    fi
    set_model "$copy/agents/$lens.md" "$model"
  done
  cmd=(claude plugin eval "$copy" --trust-plugin --tag lens-ab --ablation none --no-publish --scaffold
       --json "$OUT/$model.json" --output-dir "$OUT/$model" --max-cost-usd "$MAX_COST" --judge-model "$JUDGE_MODEL")
  [ -n "$MAIN_MODEL" ] && cmd+=(--model "$MAIN_MODEL")
  [ -n "$RUNS" ] && cmd+=(--runs "$RUNS")
  # --allow-tools takes a list, so it goes last.
  cmd+=(--allow-tools $ALLOW)
  echo "lens-ab: $LENSES on $model"
  if [ "$DRY" = 1 ]; then
    printf '  %q' "${cmd[@]}"; echo
    continue
  fi
  "${cmd[@]}"
  rc=$?
  [ "$rc" -le 1 ] || { echo "lens-ab: eval for $model exited $rc (partial or interrupted)"; status=1; }
  [ -f "$OUT/$model.json" ] && reports="$reports $OUT/$model.json"
done

[ "$DRY" = 1 ] && exit 0
if [ -z "$reports" ]; then
  echo "lens-ab: no report was written" >&2
  exit 1
fi
echo
echo "Findings recall per lens (reports in $OUT):"
# shellcheck disable=SC2086
"$PY" "$HERE/summarize.py" $reports || status=1
exit "$status"
