#!/usr/bin/env bash
# Setup hook (matcher "init", run by `claude --init` and `--init-only`): the non-interactive part of
# /almanac for a first run on a cloud or CI machine. In the current folder, when it is the top of a
# git work tree, it creates .workspace/shared/ (decisions, specs, plans, research, postmortems) and
# .workspace/local/, and appends the .workspace/local/ entry to .gitignore when no line already
# covers it. It changes nothing when .workspace/ already exists, and reports what it did in a
# systemMessage. It reads nothing from the event. Plain bash 3.2; always exits 0.
export LC_ALL=C

[ ! -t 0 ] && head -c65536 >/dev/null 2>&1   # drain stdin; nothing in the event is used

TOP=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$TOP" ] || exit 0
HERE=$(pwd -P 2>/dev/null)
[ "$HERE" = "$(cd "$TOP" 2>/dev/null && pwd -P)" ] || exit 0
[ -e ".workspace" ] && exit 0

mkdir -p .workspace/shared/decisions .workspace/shared/specs .workspace/shared/plans \
         .workspace/shared/research .workspace/shared/postmortems .workspace/local 2>/dev/null || exit 0

IGN="unchanged"
if [ -e ".gitignore" ] && [ ! -f ".gitignore" ]; then
  IGN="left alone (.gitignore is not a regular file)"
elif grep -qsE '^\.?/?\.workspace/?$|^\.?/?\.workspace/local/?$' .gitignore 2>/dev/null; then
  IGN="already covers .workspace/local/"
else
  NL=""
  if [ -s ".gitignore" ] && [ "$(tail -c 1 .gitignore 2>/dev/null)" != "" ]; then NL=$'\n'; fi
  if printf '%s# Magician workspace (local machine only)\n.workspace/local/\n' "$NL" >> .gitignore 2>/dev/null; then
    IGN="now lists .workspace/local/"
  else
    IGN="left alone (not writable)"
  fi
fi

printf '{"systemMessage":"magician: created .workspace/shared/ and .workspace/local/ in %s; .gitignore %s. /almanac adds the project context file and CLAUDE.md notes."}\n' "$(printf '%s' "$HERE" | tr -d '\\"\000-\037')" "$IGN"
exit 0
