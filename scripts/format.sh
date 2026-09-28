#!/usr/bin/env bash
# PostToolUse(Write|Edit) — OPT-IN auto-format of the file Claude just wrote or edited.
# Off unless the user enables the `auto_format` plugin option; prettier additionally needs
# `auto_format_prettier`. Runs only a formatter that is already on PATH (ruff or black, gofmt,
# rustfmt, shfmt, prettier); a formatter that isn't there is skipped. When the file changed on
# disk, Claude is told so through PostToolUse additionalContext. Plain bash; always exits 0.
export LC_ALL=C
case "${CLAUDE_PLUGIN_OPTION_AUTO_FORMAT:-false}" in true|1|yes|on) ;; *) exit 0 ;; esac
INPUT=$(cat 2>/dev/null) || exit 0

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

F=$(json_str file_path) || exit 0
case $F in /*|[A-Za-z]:*) ;; *) exit 0 ;; esac      # absolute paths only
[ -f "$F" ] || exit 0
before=$(cksum < "$F" 2>/dev/null) || exit 0
tool=""
case "${F##*.}" in
  py)      if command -v ruff >/dev/null 2>&1; then ruff format --quiet "$F" >/dev/null 2>&1; tool=ruff
           elif command -v black >/dev/null 2>&1; then black --quiet "$F" >/dev/null 2>&1; tool=black; fi ;;
  go)      if command -v gofmt >/dev/null 2>&1; then gofmt -w "$F" >/dev/null 2>&1; tool=gofmt; fi ;;
  rs)      if command -v rustfmt >/dev/null 2>&1; then rustfmt "$F" >/dev/null 2>&1; tool=rustfmt; fi ;;
  sh|bash) if command -v shfmt >/dev/null 2>&1; then shfmt -w "$F" >/dev/null 2>&1; tool=shfmt; fi ;;
  js|jsx|ts|tsx|json|css|scss|html|md)
           case "${CLAUDE_PLUGIN_OPTION_AUTO_FORMAT_PRETTIER:-false}" in true|1|yes|on)
             if command -v prettier >/dev/null 2>&1; then prettier --write --log-level silent "$F" >/dev/null 2>&1; tool=prettier; fi ;;
           esac ;;
esac
[ -n "$tool" ] || exit 0
after=$(cksum < "$F" 2>/dev/null) || exit 0
[ "$before" = "$after" ] && exit 0
msg="Magician auto_format (enabled in the plugin options): $tool reformatted $F after this edit, so the file on disk now differs from the text that was written."
printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}\n' "$(json_escape "$msg")"
exit 0
