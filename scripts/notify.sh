#!/usr/bin/env bash
# Notification(agent_completed|agent_needs_input) — OPT-IN desktop notification when a background
# session finishes or starts waiting for input. Off unless the user enables the
# `desktop_notifications` plugin option. Delivery is a terminal notification sequence that Claude
# Code writes: OSC 9 (iTerm2, WezTerm, Windows Terminal, ConEmu), OSC 99 (Kitty) or OSC 777 (Ghostty,
# Warp and every other terminal). Terminals without a notification escape (macOS Terminal.app, the
# VS Code and JetBrains terminals, Alacritty, plain tmux, many Linux terminals) ignore it and show no
# notification; this hook doesn't start a desktop notifier program.
# The notification text is the event's message with control characters removed, capped at 160 bytes.
# Nothing is stored.
# Plain bash; always exits 0.
export LC_ALL=C
case "${CLAUDE_PLUGIN_OPTION_DESKTOP_NOTIFICATIONS:-false}" in true|1|yes|on) ;; *) exit 0 ;; esac
INPUT=$(cat 2>/dev/null) || exit 0

re_type='"notification_type"[[:space:]]*:[[:space:]]*"([a-z_]+)"'
[[ $INPUT =~ $re_type ]] || exit 0
case ${BASH_REMATCH[1]} in
  agent_completed)   KIND="run complete" ;;
  agent_needs_input) KIND="needs your input" ;;
  *) exit 0 ;;
esac

MSG=""
re_msg='"message"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)"'
if [[ $INPUT =~ $re_msg ]]; then
  MSG=${BASH_REMATCH[1]}
  p=$'\001'
  MSG=${MSG//\\\\/$p}
  MSG=${MSG//\\\"/\"}; MSG=${MSG//\\\//\/}
  MSG=${MSG//\\u????/ }
  MSG=${MSG//\\n/ }; MSG=${MSG//\\t/ }; MSG=${MSG//\\r/ }
  MSG=${MSG//\\/}
  MSG=${MSG//$p/\\}
  MSG=$(printf '%s' "$MSG" | tr -d '\000-\037\177' | cut -c1-160)
  case $MSG in                                        # drop a UTF-8 character split by the cut
    *[$'\xc0'-$'\xff']) MSG=${MSG%?} ;;
    *[$'\xe0'-$'\xff'][$'\x80'-$'\xbf']) MSG=${MSG%??} ;;
    *[$'\xf0'-$'\xff'][$'\x80'-$'\xbf'][$'\x80'-$'\xbf']) MSG=${MSG%???} ;;
  esac
fi
[ -n "$MSG" ] || MSG=$KIND
case $MSG in -*) MSG=" $MSG" ;; esac

OSC=""
if [ -n "${KITTY_WINDOW_ID:-}" ]; then
  OSC=99
elif [ -n "${WT_SESSION:-}" ] || [ -n "${ConEmuPID:-}" ]; then
  OSC=9
else
  case "${TERM_PROGRAM:-}" in
    iTerm.app|WezTerm)     OSC=9 ;;
    ghostty|WarpTerminal)  OSC=777 ;;
  esac
fi

J=${MSG//\\/\\\\}; J=${J//\"/\\\"}                  # control characters were stripped above
# JSON escapes, single-quoted: the JSON parser decodes them to ESC and BEL; OSC 99 ends with ESC and a backslash.
if [ "$OSC" = 99 ]; then
  SEQ='\u001b]99;;Magician: '"$J"'\u001b\\'
elif [ "$OSC" = 9 ]; then
  SEQ='\u001b]9;Magician: '"$J"'\u0007'
else
  SEQ='\u001b]777;notify;Magician;'"$J"'\u0007'
fi
printf '{"terminalSequence":"%s"}\n' "$SEQ"
exit 0
