#!/usr/bin/env bash
# PostToolUse(Write|Edit) — STE-lite check of a Markdown deliverable Claude just wrote or edited.
# Runs the bundled `tools/ste-lint` on the file and hands its first findings back to Claude as
# PostToolUse additionalContext, so the prose is fixed in the same turn. It runs only when
# STE-lite is on (first match wins: env MAGICIAN_STE=1|0, a per-project .magician/ste file holding
# `on` or `off`, the "ste" flag in cli-ui.json, else off) AND the file is a .md under
# .workspace/shared/ or matches a glob in the per-project .magician/ste-paths list (one glob per
# line, relative to the project folder; `*` and `**` match any text, `/` included). Reads only tool_input.file_path from the event; reads
# the file through ste-lint; writes nothing; never blocks; plain bash; always exits 0.
export LC_ALL=C
INPUT=$(cat 2>/dev/null) || exit 0
[ -n "$INPUT" ] || exit 0

# First value of a JSON string key, unescaped (\\ \" \/ only; anything else -> not a plain path).
json_str() {
  local re="\"$1\"[[:space:]]*:[[:space:]]*\"(([^\"\\\\]|\\\\.)*)\""
  [[ $INPUT =~ $re ]] || return 1
  local v=${BASH_REMATCH[1]} p=$'\001'
  case $v in *\\*)
    v=${v//\\\\/$p}; v=${v//\\\"/\"}; v=${v//\\\//\/}
    case $v in *\\*) return 1 ;; esac
    v=${v//$p/\\} ;;
  esac
  printf '%s' "$v"
}
json_escape() {
  local s=$1
  s=${s//\\/\\\\}; s=${s//\"/\\\"}
  s=${s//$'\n'/\\n}; s=${s//$'\r'/\\r}; s=${s//$'\t'/\\t}
  printf '%s' "$s" | tr -d '\000-\010\013\014\016-\037'
}

# ---- is STE-lite on? env -> .magician/ste -> cli-ui.json -> off ----
STE=""
case "$(printf '%s' "${MAGICIAN_STE:-}" | tr '[:upper:]' '[:lower:]')" in
  1|on|true|yes) STE=on ;;
  0|off|false|no) STE=off ;;
esac
if [ -z "$STE" ] && [ -f ".magician/ste" ]; then
  case "$(head -c16 .magician/ste 2>/dev/null | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')" in
    on|1|true) STE=on ;;
    off|0|false) STE=off ;;
  esac
fi
if [ -z "$STE" ]; then
  UI_CFG="${MAGICIAN_HOME:-$HOME/.claude/magician}/cli-ui.json"
  if [ -f "$UI_CFG" ]; then
    if head -c65536 "$UI_CFG" 2>/dev/null | grep -qE '"ste"[[:space:]]*:[[:space:]]*true'; then
      STE=on
    fi
  fi
fi
[ "$STE" = on ] || exit 0

# ---- the file: an existing .md, absolute path, under .workspace/shared/ or an opted-in glob ----
F=$(json_str file_path) || exit 0
case $F in /*|[A-Za-z]:*) ;; *) exit 0 ;; esac
case $F in *.md|*.MD|*.markdown) ;; *) exit 0 ;; esac
[ -f "$F" ] || exit 0
REL=$F
case $F in "$PWD"/*) REL=${F#"$PWD"/} ;; esac
MATCH=0
case "/$REL" in */.workspace/shared/*) MATCH=1 ;; esac
if [ "$MATCH" = 0 ] && [ -f ".magician/ste-paths" ]; then
  # Each line is a glob, matched against the project-relative path with a bash case pattern,
  # where `*` and `**` both match any text, `/` included. Nothing is expanded.
  set -f
  while IFS= read -r pat || [ -n "$pat" ]; do
    pat=${pat%%#*}
    pat="${pat#"${pat%%[![:space:]]*}"}"; pat="${pat%"${pat##*[![:space:]]}"}"
    [ -n "$pat" ] || continue
    pat=${pat#./}
    case "$REL" in $pat) MATCH=1; break ;; esac
  done < .magician/ste-paths
fi
[ "$MATCH" = 1 ] || exit 0

LINT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}/tools/ste-lint"
[ -x "$LINT" ] || exit 0
OUT=$("$LINT" --max 10 "$F" 2>/dev/null)
rc=$?
[ "$rc" = 1 ] || exit 0          # 0 clean, 2 unreadable or usage: nothing to say
[ -n "$OUT" ] || exit 0
OUT=$(printf '%s\n' "$OUT" | head -c 6000)
msg="STE-lite: fix these in the same turn. Findings of the STE-lite linter for $F, as path:line: RULE: message:
$OUT"
printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "$(json_escape "$msg")"
exit 0
