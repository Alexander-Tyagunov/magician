#!/usr/bin/env bash
# SessionStart hook: put magician's bundled commands (kg, ctx, jira, confluence, ...) on the PATH of
# the shell Claude uses, so skills can call them by name.
#
# The commands ship in the plugin's tools folder, not in a top-level bin folder (a plugin with one
# can't be installed in Claude chat or Cowork), so Claude Code no longer adds them to PATH itself.
# This hook writes one small launcher per command into a folder of its own under
# CLAUDE_PLUGIN_DATA/tools, and appends one line to $CLAUDE_ENV_FILE that puts that folder first on PATH.
#   * There is one launcher folder per plugin root (per installed version), named by the root's path,
#     so sessions on different versions never repoint each other's launchers. A session resumed
#     after an update appends the new version's line after the old one, and the last line wins.
#     Folders of roots that no longer exist are removed.
#   * Every other file or link in the launcher folder is removed, including launchers for commands
#     the plugin no longer ships. A folder that is a link, or not this user's, is refused.
#   * A launcher is replaced by renaming a finished temporary file over it, so a session running in
#     parallel never sees a half-written one; the temporary file is never written through a link.
#   * Paths are single-quoted with embedded ' written as '\'' so the launchers and the PATH line never
#     expand anything; a path holding a control character, or a data folder whose path holds a colon
#     (PATH can't carry it), is refused with a note on stderr. The skills then use the full path.
#     Windows paths (Git Bash) are converted with cygpath first.
#   * stdout stays empty. It only appends to the session env file and skips a line already there.
LC_ALL=C

magician_tools_path() (
  [ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
  [ -n "${CLAUDE_PLUGIN_DATA:-}" ] || exit 0
  [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] || exit 0
  note() { printf 'magician: bundled commands not added to PATH (%s)\n' "$1" >&2; }
  posix() {   # C:\x or C:/x from Git Bash on Windows as /c/x; any other path unchanged
    case "$1" in
      [A-Za-z]:[\\/]*) command -v cygpath >/dev/null 2>&1 && { cygpath -u "$1"; return; } ;;
    esac
    printf '%s\n' "$1"
  }
  root=$(posix "$CLAUDE_PLUGIN_ROOT")
  data=$(posix "$CLAUDE_PLUGIN_DATA")
  case "$root$data" in *[[:cntrl:]]*) note "a plugin path has a control character"; exit 0 ;; esac
  case "$data" in *:*) note "the plugin data folder path has a colon"; exit 0 ;; esac
  case "$root" in /*) ;; *) exit 0 ;; esac
  case "$data" in /*) ;; *) exit 0 ;; esac
  src_dir=$root/tools
  [ -d "$src_dir" ] || exit 0
  # The launcher folder's name is the root path with = written as =3D, / as =2F and : as =3A.
  key=${root//=/=3D}; key=${key//\//=2F}; key=${key//:/=3A}
  base=$data/tools
  dir=$base/$key

  # The folder goes first on PATH and everything in it but the launchers is removed, so it must be
  # a real folder of this user's, never a link to another folder such as ~/bin.
  [ -L "$base" ] && { note "$base is a link"; exit 0; }
  umask 077
  mkdir -p "$dir" 2>/dev/null || exit 0
  for d in "$base" "$dir"; do
    if [ -L "$d" ] || [ ! -d "$d" ] || [ ! -O "$d" ]; then
      note "$d is a link or not a folder of yours"
      exit 0
    fi
  done
  set -C   # > never writes through a file or link already at the temporary name
  sq="'"; rep="'\\''"

  wrote=0
  for src in "$src_dir"/*; do
    [ -f "$src" ] && [ -x "$src" ] || continue
    name=${src##*/}
    case "$name" in .*|*[!A-Za-z0-9._-]*) continue ;; esac
    dst=$dir/$name
    [ -L "$dst" ] && rm -f "$dst" 2>/dev/null   # mv would move into a linked folder
    if [ -d "$dst" ]; then
      printf '%s\n' "magician: $name not added to PATH (a folder is in the way at $dst)" >&2
      continue
    fi
    tmp=$dir/.$name.$$
    rm -f "$tmp" 2>/dev/null
    if printf '#!/bin/sh\nexec %s "$@"\n' "$sq${src//$sq/$rep}$sq" > "$tmp" 2>/dev/null \
        && chmod 755 "$tmp" 2>/dev/null && mv -f "$tmp" "$dst" 2>/dev/null; then
      wrote=$((wrote + 1))
    else
      rm -f "$tmp" 2>/dev/null
    fi
  done
  # Remove every file and link that isn't a launcher for a shipped command, hidden and dangling
  # ones included: nothing else may shadow a command from this folder. Folders are skipped by
  # command lookup and left alone.
  for dst in "$dir"/* "$dir"/.[!.]* "$dir"/..?*; do
    [ -f "$dst" ] || [ -L "$dst" ] || continue
    name=${dst##*/}
    case "$name" in
      .*|*[!A-Za-z0-9._-]*) ;;
      *) [ -f "$src_dir/$name" ] && [ -x "$src_dir/$name" ] && continue ;;
    esac
    rm -f "$dst" 2>/dev/null
  done
  # Remove the launcher folders of plugin roots that no longer exist (versions Claude Code removed).
  for sub in "$base"/*; do
    [ -d "$sub" ] && [ ! -L "$sub" ] || continue
    old=${sub##*/}; old=${old//=2F//}; old=${old//=3A/:}; old=${old//=3D/=}
    case "$old" in /*) ;; *) continue ;; esac
    [ -d "$old" ] && continue
    for f in "$sub"/* "$sub"/.[!.]* "$sub"/..?*; do
      if [ -f "$f" ] || [ -L "$f" ]; then rm -f "$f" 2>/dev/null; fi
    done
    rmdir "$sub" 2>/dev/null
  done
  [ "$wrote" -gt 0 ] || exit 0

  # Append the PATH line unless the file already has it. If the file's last line has no trailing
  # newline (written by something else), start a new line first. ${PATH:+...} keeps an empty PATH
  # from becoming the current directory.
  line="export PATH=$sq${dir//$sq/$rep}$sq\${PATH:+:\"\$PATH\"}"
  needs_nl=0
  if [ -f "$CLAUDE_ENV_FILE" ]; then
    while :; do
      if IFS= read -r existing; then
        [ "$existing" = "$line" ] && exit 0
      else
        [ -n "$existing" ] || break
        [ "$existing" = "$line" ] && exit 0
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
  exit 0
)

magician_tools_path
exit 0
