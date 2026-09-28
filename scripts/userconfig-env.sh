#!/usr/bin/env bash
# SessionStart hook: bridge magician's userConfig values into the Bash tool environment.
#
# Claude Code exports each userConfig option to hook processes as CLAUDE_PLUGIN_OPTION_<KEY>, but
# not to commands Claude runs through the Bash tool, which is where the bundled `jira` and
# `confluence` CLIs run. This hook appends one `export NAME='value'` line per NON-EMPTY Jira or
# Confluence option to $CLAUDE_ENV_FILE, which Claude Code sources before each Bash command in this
# session. It also exports MAGICIAN_DATA (this plugin's data dir, from CLAUDE_PLUGIN_DATA) so the
# CLIs keep their cache in the same place as the hooks, and MAGICIAN_USERCONFIG_BRIDGE=1 to show it ran.
#   * It never prints a value: stdout stays empty; stderr names a skipped option, never its value.
#   * Values are single-quoted with embedded ' written as '\'' so the file never expands anything.
#   * It only appends and never rewrites (SessionStart hooks run in parallel), and it skips lines
#     already present, so running it again (resume, clear, compact) adds nothing.
#   * It uses builtins only (printf/read/case), so no value ever appears in a process argv.
#   * A file it creates is mode 0600 (umask 077); an existing file keeps its mode.
LC_ALL=C

magician_bridge_userconfig() (
  [ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
  umask 077
  sq="'"; rep="'\\''"

  # Append $1 as one line unless the file already has that exact line. If the file's last line has
  # no trailing newline (written by something else), start a new line first.
  emit() {
    line=$1
    needs_nl=0
    if [ -f "$CLAUDE_ENV_FILE" ]; then
      while :; do
        if IFS= read -r existing; then
          [ "$existing" = "$line" ] && return 0
        else
          [ -n "$existing" ] || break
          [ "$existing" = "$line" ] && return 0
          needs_nl=1
          break
        fi
      done < "$CLAUDE_ENV_FILE"
    fi
    if [ "$needs_nl" = 1 ]; then
      printf '\n%s\n' "$line" >> "$CLAUDE_ENV_FILE"
    else
      printf '%s\n' "$line" >> "$CLAUDE_ENV_FILE"
    fi
  }

  # Emit `export NAME='value'` for a non-empty value; a value with a control character (a newline
  # would break the line-based file) is skipped with a note that names the variable only.
  emit_quoted() {
    name=$1; val=$2; hint=$3
    [ -n "$val" ] || return 0
    case "$val" in
      *[[:cntrl:]]*)
        printf '%s\n' "magician: skipped $name (contains a control character); $hint" >&2
        return 0 ;;
    esac
    esc=${val//$sq/$rep}
    emit "export $name=$sq$esc$sq"
  }

  for name in \
    CLAUDE_PLUGIN_OPTION_JIRA_BASE_URL \
    CLAUDE_PLUGIN_OPTION_JIRA_EMAIL \
    CLAUDE_PLUGIN_OPTION_JIRA_API_TOKEN \
    CLAUDE_PLUGIN_OPTION_CONFLUENCE_BASE_URL \
    CLAUDE_PLUGIN_OPTION_CONFLUENCE_EMAIL \
    CLAUDE_PLUGIN_OPTION_CONFLUENCE_API_TOKEN
  do
    emit_quoted "$name" "${!name:-}" "re-enter it with /plugin configure magician"
  done
  emit_quoted MAGICIAN_DATA "${CLAUDE_PLUGIN_DATA:-}" "the CLIs fall back to their default data dir"
  emit "export MAGICIAN_USERCONFIG_BRIDGE=1"
  exit 0
)

magician_bridge_userconfig
exit 0
