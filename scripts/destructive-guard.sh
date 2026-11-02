#!/usr/bin/env bash
# PreToolUse(Bash|PowerShell) — ABSOLUTE hard gate against catastrophic commands, plus a softer
# permission-style stage folded in from the former sentinel-guard. Ported to plain bash 3.2 (the macOS
# system bash, and GNU bash on Linux), so the whole hook is shell in this one file; a static
# contract test covers this.
#
# On a catastrophic command it writes ONE reason line to stderr and exits 2, which stops the tool
# call BEFORE Claude Code evaluates permission rules — the block overrides allow-rules and fires in
# every permission mode. It never echoes the command back. A second, softer stage runs only after
# every hard check passes clean: on a risky-but-not-catastrophic shape it prints a
# {"decision":"block"} verdict on stdout and exits 0, matching the deprecated-but-still-honored
# top-level PreToolUse decision/reason shape.
#
# Honest scope (CWE-78): a denylist cannot catch every obfuscation — arbitrary encoding or variable
# indirection can still hide something from a fixed set of rules. This is a deterministic net for
# KNOWN catastrophic shapes plus common command wrappers, layered under OS sandboxing, Claude Code's
# own classifier, and model judgment. It only inspects the command text; it never executes anything.
# On empty/unparseable input, a missing command field, or its own internal error, it fails OPEN
# (exit 0) so a bug here can never brick the user's shell. A command too long to check in full
# gets the soft verdict up front instead of a partial check (see the size limit below).
export LC_ALL=C

block() {  # the hard gate: one plain-words reason on stderr, exit 2 (never echoes the command)
  printf 'magician destructive-guard: refused - %s.\n' "$1" >&2
  exit 2
}

soft_block() {  # permission-style verdict on stdout, exit 0
  if [ "$ALL_SOFT" = 1 ] && [ "$1" != "$TOO_LONG" ]; then
    add_soft "$1"
    return 0
  fi
  if [ "$ALL_SOFT" = 1 ]; then
    add_soft "$1"
    emit_all_soft
  fi
  printf '{"decision": "block", "reason": "%s"}\n' "$1"
  exit 0
}

# All-soft mode, opt-in through MAGICIAN_GUARD_ALL_SOFT=1, which only the magician mod
# (mods/register.js) sets, in the env of its own $.process.run of this script. The hard checks
# run first and exit 2 exactly as always; the soft stage then evaluates EVERY soft check instead of
# stopping at the first, and prints one verdict naming all of them:
#   {"decision": "block", "reasons": ["<r1>", "<r2>"], "reason": "<r1>"}   (exit 0)
# so the mod can tell a pure blast-radius command from one that also reads credentials. It only
# ever reports more; it never turns a block into a pass. With the variable unset the output is
# byte-identical to the single-reason verdict above.
ALL_SOFT=0
[ "${MAGICIAN_GUARD_ALL_SOFT:-}" = 1 ] && ALL_SOFT=1
SOFT_REASONS=()
add_soft() {  # append a reason once
  local _r
  for _r in "${SOFT_REASONS[@]}"; do [ "$_r" = "$1" ] && return 0; done
  SOFT_REASONS+=("$1")
}
emit_all_soft() {  # print the all-soft verdict and exit 0 (only called with >= 1 reason)
  local _r _list=""
  for _r in "${SOFT_REASONS[@]}"; do _list="$_list, \"$_r\""; done
  printf '{"decision": "block", "reasons": [%s], "reason": "%s"}\n' "${_list#, }" "${SOFT_REASONS[0]}"
  exit 0
}

IFS= read -r -d '' INPUT   # slurps all of stdin; a non-empty payload with no trailing NUL makes
                           # read report failure even though INPUT is fully populated, so its exit
                           # status is intentionally not checked here
[ -n "$INPUT" ] || exit 0

# Size limit. Every check below reads the whole command, so a command is either checked in full or
# refused; it is never cut short, which would let anything past the cut run unchecked. Past
# MAX_CMD bytes of the JSON-escaped command (LC_ALL=C, so a non-ASCII character counts 2-4) the
# checks take seconds on dense input, so the command is refused with a pointer to the Write tool,
# which carries large content without a shell. An event far larger than any command allowed here is refused on sight, before it is read
# further.
MAX_CMD=50000
TOO_LONG="a command over $MAX_CMD bytes (JSON-escaped), too long to check; write large content with the Write tool, or split the command"
[ "${#INPUT}" -gt 200000 ] && _big=1 || _big=0
INPUT=${INPUT:0:200000}

re_tool='"tool_name"[[:space:]]*:[[:space:]]*"([^"]*)"'
[[ $INPUT =~ $re_tool ]] || exit 0
TOOL=${BASH_REMATCH[1]}
case "$TOOL" in
  Bash|PowerShell) ;;
  *) exit 0 ;;
esac
[ "$_big" = 1 ] && soft_block "$TOO_LONG"

re_cmd='"command"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)'
[[ $INPUT =~ $re_cmd ]] || exit 0
RAW=${BASH_REMATCH[1]}
[ -n "$RAW" ] || exit 0
[ "${#RAW}" -gt "$MAX_CMD" ] && soft_block "$TOO_LONG"

# The event's working directory, when it is a plain absolute path: a delete of `.` or `*` is read
# against it, and a `cd DIR &&` earlier in the command replaces it (see CD_HINT below).
EVENT_CWD=""
re_cwd='"cwd"[[:space:]]*:[[:space:]]*"(/[^"\\]*)"'
[[ $INPUT =~ $re_cwd ]] && EVENT_CWD=${BASH_REMATCH[1]}

# ---- linear text helpers ----
# Every edit of the command text below goes through these. bash 3.2's ${var//x/y}, ${var#*x} and
# a loop that re-slices the remaining text all cost time in proportion to the text length for
# each match, so a 19 KB command took seconds. Splitting on one character and joining the fields
# back both happen in a single pass inside bash, so these stay linear. SENT is appended before a
# split, so a delimiter at the very end is not dropped, and removed after the join. It is a
# control character, which a JSON string can only carry escaped. IFS is local to each helper and
# nothing is called while it is changed.
SENT=$'\002'
NL=$'\n'

# Pathname expansion stays off for the whole script: every unquoted word split below is the
# command's own text, and a glob in it, such as a * in a path, must never expand against the filesystem.
set -f

# repl_char TEXT CHAR [TO] -> sets REPL_OUT to TEXT with every CHAR replaced by TO (one character
# or nothing).
repl_char() {
  case "$1" in
    *"$2"*) ;;
    *) REPL_OUT=$1; return 0 ;;
  esac
  local IFS="$2" parts
  parts=($1$SENT)
  IFS="${3-}"
  REPL_OUT="${parts[*]}"
  REPL_OUT=${REPL_OUT%"$SENT"}
}

# unescape TEXT MODE -> sets REPL_OUT to TEXT with its backslash escapes undone. MODE json: \\ \"
# and \/ become the character, \n a line break, \t a space, and any other escape stays as written.
# MODE dq: \\ \" \$ and \` become the character, as bash does inside double quotes. In both, a
# backslash right before a line break continues the line, so the pair becomes a space. After a
# split on the backslash, an empty field is an escaped backslash, and any other field starts with
# the escaped character.
unescape() {
  case "$1" in
    *\\*) ;;
    *) REPL_OUT=$1; return 0 ;;
  esac
  local IFS='\' parts out f first=1 esc=0 lone=0
  parts=($1$SENT)
  for f in "${parts[@]}"; do
    if [ "$first" = 1 ]; then
      first=0
      out=("$f")
    elif [ "$esc" = 1 ]; then
      # A JSON \\ with nothing after it: if a \n follows, that is a line continuation.
      esc=0
      out[${#out[@]}]="\\$f"
      [ -z "$f" ] && [ "$2" = json ] && lone=1
      continue
    elif [ -z "$f" ]; then
      esc=1
    elif [ "$lone" = 1 ] && [ "${f:0:1}" = n ]; then
      out[${#out[@]}-1]=" ${f:1}"
    else
      case "$2:${f:0:1}" in
        json:n) out[${#out[@]}]="$NL${f:1}" ;;
        json:t|"dq:$NL") out[${#out[@]}]=" ${f:1}" ;;
        json:'"'|json:/|dq:'"'|dq:'$'|dq:'`') out[${#out[@]}]=$f ;;
        *) out[${#out[@]}]="\\$f" ;;
      esac
    fi
    lone=0
  done
  IFS=
  REPL_OUT="${out[*]}"
  REPL_OUT=${REPL_OUT%"$SENT"}
}

# Undo JSON string escaping. CMD_ML keeps the command's line breaks for the per-line pass below;
# CMD collapses every run of whitespace, line breaks included, to one space.
unescape "$RAW" json
CMD_ML=$REPL_OUT
CMD=$CMD_ML

set -- $CMD
CMD="$*"
# Clear the words again: bash copies the caller's positional parameters on every function call,
# and a long command would make each of the thousands of calls below pay for all of them.
set --
[ -n "$CMD" ] || exit 0

# ---- shared token lists (also read by the test suite via the regex ^NAME="([^"]*)"$) ----
# Real multi-word command names (lwp-download, Invoke-WebRequest, Invoke-RestMethod,
# Invoke-Expression) are stored here with their hyphen removed; resolve_head() below strips
# hyphens from whatever it extracts before comparing, so the two sides always line up.
DOWNLOADERS="aria2c fetch curl wget lwpdownload http https iwr irm invokewebrequest invokerestmethod"
RUNNERS="sh bash zsh dash ksh fish python python2 python3 perl ruby node php pwsh powershell iex invokeexpression source ."
WRAPPERS="timeout sudo doas env nohup nice ionice command builtin exec time setsid stdbuf xargs chrt taskset"

# The shell builtin that runs a string as code, spelled in two pieces so the bare word this rule
# looks for never sits on one line of this file.
EV="ev"
EVALWORD="${EV}al"

# Catastrophic path targets, as space lists rather than one literal command string apiece.
ROOTS_ALL="bin boot dev etc lib lib32 lib64 libx32 opt proc root run sbin srv sys usr var home Users System Library Applications private Volumes cores mnt media"
ROOTS_SYS="bin boot dev etc lib lib32 lib64 libx32 proc root sbin sys usr System Library"
CRIT_FILES="passwd shadow sudoers fstab hosts group master.passwd"

in_list() {  # in_list WORD "space separated list" -> true on an exact-token match
  case " $2 " in
    *" $1 "*) return 0 ;;
  esac
  return 1
}

# flag_takes_value WRAPPER FLAG -> true when that wrapper's flag consumes the NEXT word as its
# own argument (a user name, a signal name, a niceness, a file, a count, ...), so resolve_head
# must skip both words rather than mistaking the value for the real command (e.g. `sudo -u root
# rm ...` must not resolve to a command named "root").
flag_takes_value() {
  case "$1:$2" in
    sudo:-u|sudo:-g|sudo:-C|sudo:-D|sudo:-h|sudo:-p|sudo:-r|sudo:-t|sudo:-U) return 0 ;;
    timeout:-s|timeout:-k) return 0 ;;
    nice:-n) return 0 ;;
    env:-u|env:-C|env:-S) return 0 ;;
    ionice:-c|ionice:-n|ionice:-p) return 0 ;;
    chrt:-p) return 0 ;;
    taskset:-p) return 0 ;;
    stdbuf:-i|stdbuf:-o|stdbuf:-e) return 0 ;;
    xargs:-n|xargs:-I|xargs:-P|xargs:-L|xargs:-d|xargs:-s|xargs:-E) return 0 ;;
  esac
  return 1
}

# resolve_head SEG -> sets RH_HEAD (the segment's effective leading command word) and RH_REST
# (everything after it). Skips VAR=value assignments, flags (including a value consumed by a
# wrapper's own flag per flag_takes_value), bare numeric args (a wrapper's duration/priority) and
# WRAPPERS words; strips a leading path component and any hyphens so multi-word names line up
# with the token lists above.
BQ=$'\x60'   # a backquote, written as its code so no backquoted span sits in this file
resolve_head() {
  local seg="$1" w lastwrap="" skip=0 i=0 echoed=0
  RH_HEAD=""
  RH_REST=""
  set -f
  # A for loop, not set -- and shift: bash 3.2 copies the positional parameters on every function
  # call, so a call per word of a long chain of repeated nice wrappers would be quadratic. The case tests
  # skip the calls for the usual word; this runs several times for every statement.
  for w in $seg; do
    i=$((i + 1))
    if [ "$skip" = 1 ]; then skip=0; continue; fi
    # An echo substitution, $(echo X) or the backquoted form, runs X, so X is the head: the opener
    # is dropped and the closing ) or backquote is cut from the next word. The same for printf.
    if [ "$echoed" = 1 ]; then
      echoed=0
      case "$w" in *')') w=${w%)} ;; *"$BQ") w=${w%"$BQ"} ;; esac
    else
      case "$w" in
        '$(echo'|"${BQ}echo"|'$(printf'|"${BQ}printf") echoed=1; continue ;;
      esac
    fi
    case "$w" in
      *=*) continue ;;
      [0-9]*) continue ;;
      -*)
        [ -n "$lastwrap" ] && flag_takes_value "$lastwrap" "$w" && skip=1
        continue
        ;;
    esac
    # A leading backslash (\rm skips an alias) and quote characters inside the word (r''m, 'r'm,
    # r""m) are gone by the time the shell looks the command up, so they go here too.
    case "$w" in \\*) w=${w#\\} ;; esac
    case "$w" in *\'*|*\"*) strip_quotes "$w"; w=$STRIP_OUT ;; esac
    case "$w" in '('*) w=${w#(} ;; '{'*) w=${w#\{} ;; esac   # a subshell or group opener
    [ -n "$w" ] || continue
    case "$w" in */*) last_part "$w" /; w=$PART_OUT ;; esac
    case "$w" in *-*) drop_char "$w" -; w=$DROP_OUT ;; esac
    case " $WRAPPERS " in *" $w "*) lastwrap=$w; continue ;; esac
    RH_HEAD=$w
    set -- $seg
    shift "$i"
    RH_REST="$*"
    set --
    return 0
  done
}

collect_flags() {  # sets SHORTS (concatenated short-flag letters) and LONGS (space list of --long)
  local text="$1" w
  SHORTS=""
  LONGS=""
  set -f
  set -- $text
  for w in "$@"; do
    case "$w" in
      --*) LONGS="$LONGS $w" ;;
      -*) SHORTS="$SHORTS${w#-}" ;;
    esac
  done
}

has_target() {  # true if $1 names a catastrophic root itself, or a subpath of a system-critical one.
  # Callers pass the strip_quotes()'d form of an argument list so a quoted "$HOME" still matches.
  local padded=" $1 " tok
  case "$padded" in
    *' / '*|*' /* '*|*' /. '*|*' ~ '*|*' ~/ '*|*' ~/* '*|\
*' $HOME '*|*' $HOME/ '*|*' $HOME/* '*|\
*' ${HOME} '*|*' ${HOME}/ '*|*' ${HOME}/* '*) return 0 ;;
  esac
  for tok in $ROOTS_ALL; do
    case "$padded" in
      *" /$tok "*|*" /$tok/ "*|*" /$tok/* "*) return 0 ;;
    esac
  done
  # A subpath counts only where the word starts at the root (/etc/nginx), not where a project path
  # merely contains the segment (./build/etc/cache).
  for tok in $ROOTS_SYS; do
    case "$padded" in
      *" /$tok/"?*) return 0 ;;
    esac
  done
  return 1
}

is_device() {  # true if $1 names a raw block-device path (not /dev/null|zero|random|tty|fd|...)
  case "$1" in
    *"/dev/sd"[a-z]*|*"/dev/nvme"[0-9]*|*"/dev/hd"[a-z]*|*"/dev/vd"[a-z]*|*"/dev/xvd"[a-z]*|\
*"/dev/mmcblk"[0-9]*|*"/dev/disk"[0-9]*|*"/dev/rdisk"[0-9]*|*"/dev/mapper/"*|*"/dev/loop"[0-9]*)
      return 0 ;;
  esac
  return 1
}

# strip_quotes TEXT -> sets STRIP_OUT to TEXT with every quote character removed but the content
# between them kept, e.g. `-rf "$HOME"` -> `-rf $HOME`. Used only right before has_target/is_device
# so a quoted target argument is still recognized; flag/word extraction elsewhere still sees the
# original, quoted text.
strip_quotes() {
  repl_char "$1" '"'
  repl_char "$REPL_OUT" "'"
  STRIP_OUT=$REPL_OUT
}

# lower TEXT -> sets LOWER_OUT to TEXT with A-Z folded to a-z, one repl_char per capital letter
# that occurs. Plain bash instead of `tr`: this hook runs on every Bash/PowerShell call, and command
# substitution forks a process just like an external tool would, so every helper below sets a
# global instead of being captured with $(...).
UPPER_AZ=ABCDEFGHIJKLMNOPQRSTUVWXYZ
LOWER_AZ=abcdefghijklmnopqrstuvwxyz
lower() {
  local s="$1" i u
  for (( i = 0; i < 26; i++ )); do
    case "$s" in
      *[A-Z]*) ;;
      *) break ;;
    esac
    u=${UPPER_AZ:i:1}
    case "$s" in
      *"$u"*) repl_char "$s" "$u" "${LOWER_AZ:i:1}"; s=$REPL_OUT ;;
    esac
  done
  LOWER_OUT=$s
}

# blank_single/blank_double TEXT -> sets BLANK_OUT to TEXT with '...'/"..." spans replaced by
# " Q ", using only parameter expansion (no sed/regex process). An unterminated quote leaves the
# remainder as-is.
blank_quoted() {  # QUOTE-CHAR TEXT
  case "$2" in
    *"$1"*) ;;
    *) BLANK_OUT=$2; return 0 ;;
  esac
  # After a split on the quote character the fields alternate outside, inside, outside, ...
  local IFS="$1" parts out n i=2
  parts=($2$SENT)
  n=${#parts[@]}
  out=("${parts[0]}")
  while [ "$i" -lt "$n" ]; do
    out[${#out[@]}]=" Q ${parts[i]}"
    i=$((i + 2))
  done
  # An even field count means an odd number of quotes: the last one never closes.
  [ $((n % 2)) -eq 0 ] && out[${#out[@]}]=" $1${parts[n-1]}"
  IFS=
  BLANK_OUT="${out[*]}"
  BLANK_OUT=${BLANK_OUT%"$SENT"}
}
blank_single() { blank_quoted "'" "$1"; }
blank_double() { blank_quoted '"' "$1"; }

# split_on CHAR TEXT -> sets SPLIT_OUT to the fields of TEXT between each CHAR, the same fields
# read -r -a returns with IFS set to CHAR. Word splitting keeps it in memory; giving the text to
# read instead would make bash 3.2 write a temporary file, and this runs once per statement. IFS is local
# and nothing is called while it is changed; pathname expansion is already off.
split_on() {
  local IFS="$1"
  SPLIT_OUT=($2)
}

# split_join CHAR WORD... -> sets JOIN_OUT to the WORDs joined by CHAR.
split_join() {
  local IFS="$1"
  shift
  JOIN_OUT="$*"
}

# last_part TEXT CHAR -> sets PART_OUT to what follows the last CHAR in TEXT, or to all of TEXT
# when it has none. ${TEXT##*CHAR} says the same, but bash tries every split point, so on a long
# word with no CHAR it takes over a second. A split on CHAR is one pass.
last_part() {
  case "$1" in
    *"$2") PART_OUT= ;;
    *"$2"*)
      local IFS="$2" parts
      parts=($1)
      PART_OUT=${parts[${#parts[@]}-1]}
      ;;
    *) PART_OUT=$1 ;;
  esac
}

# drop_char TEXT CHAR -> sets DROP_OUT to TEXT with every CHAR removed. ${TEXT//CHAR/} does the
# same, but bash 3.2 takes quadratic time on a word full of them.
drop_char() {
  case "$1" in
    *"$2"*) ;;
    *) DROP_OUT=$1; return 0 ;;
  esac
  local IFS="$2" parts
  parts=($1)
  IFS=
  DROP_OUT="${parts[*]}"
}

# in_order TEXT WORD... -> true when each WORD occurs in TEXT, each one after the one before. A
# glob with several stars (*a*b*c*) asks the same thing, but bash tries every placement of every
# star, so on a long text with many a's and b's and no c it runs for minutes. This looks for each
# WORD once, left to right, and never goes back.
in_order() {
  local t=$1 before
  shift
  while [ "$#" -gt 0 ]; do
    case "$t" in
      *"$1"*) ;;
      *) return 1 ;;
    esac
    before=${t%%"$1"*}
    t=${t:${#before}+${#1}}
    shift
  done
}

# flat_split TEXT -> sets REPL_OUT to TEXT with every & and | turned into ; so each command in a
# list or pipeline becomes its own ;-separated field (&& and || leave an empty field between).
flat_split() {
  repl_char "$1" '&' ';'
  repl_char "$REPL_OUT" '|' ';'
}

# squash TEXT -> sets SQUASH_OUT to TEXT with every run of whitespace, line breaks included, as
# one space: the form every whole-text check below reads.
squash() {
  set -- $1
  SQUASH_OUT="$*"
}

# join_quoted QUOTE-CHAR TEXT -> sets JOIN_OUT to TEXT with the line breaks inside each
# QUOTE-CHAR span turned into spaces, pairing quotes the same way blank_quoted does.
join_quoted() {
  case "$2" in
    *"$1"*) ;;
    *) JOIN_OUT=$2; return 0 ;;
  esac
  local IFS="$1" parts out lines n i=1
  parts=($2$SENT)
  n=${#parts[@]}
  out=("${parts[0]}")
  while [ "$i" -lt "$n" ]; do
    if [ $((i + 1)) -lt "$n" ]; then
      IFS=$NL
      lines=(${parts[i]})
      IFS=' '
      out[${#out[@]}]="$1${lines[*]}$1${parts[i+1]}"
    else
      # The last quote never closes; the rest stays as written.
      out[${#out[@]}]="$1${parts[i]}"
    fi
    i=$((i + 2))
  done
  IFS=
  JOIN_OUT="${out[*]}"
  JOIN_OUT=${JOIN_OUT%"$SENT"}
}

# line_texts TEXT -> sets LINES to the commands TEXT puts on separate lines. A line break inside
# quotes is joined first, so only one the shell would act on splits. LINES stays empty when TEXT
# is a single line, which the whole-text checks already cover. A multi-line script counts line by
# line too, because a shell runs it one line at a time.
line_texts() {
  LINES=()
  case "$1" in
    *"$NL"*) ;;
    *) return 0 ;;
  esac
  join_quoted "'" "$1"
  join_quoted '"' "$JOIN_OUT"
  split_on "$NL" "$JOIN_OUT"
  [ "${#SPLIT_OUT[@]}" -gt 1 ] && LINES=("${SPLIT_OUT[@]}")
}

# ---- fast path: a command with no candidate token is allowed here, before any full check ----
# Every rule below fires only on a command whose text holds one of a small set of tokens: a
# command word the per-command rules resolve to (rm, dd, mkfs, ..., or clean for git clean), a
# DOWNLOADERS word or base64 (the pipeline, substitution and soft download rules), a network word
# (the trifecta), an environment-dump builtin, a PowerShell cmdlet fragment, a device or /etc path,
# a secret-variable prefix, the indirect-expansion opener, or a { with an & (fork bombs). The text
# is matched the way the rules see it: folded to lowercase (PowerShell folds, and lowercase is the
# wider net for Bash), with hyphens removed (resolve_head drops them, so r-m resolves to rm) and
# quotes removed (strip_quotes does the same before a target is compared). A command word counts
# at a boundary that is not a letter or digit (resolve_head takes the word after the last / of a
# whitespace-separated word). Holding none of these, a command cannot match any rule, so it is
# allowed at once; holding one, it goes through every check unchanged. test_guard_latency.py and
# the parity corpus in test_destructive_guard.py hold this to the full checks' verdicts.
FAST_HEADS="rm find dd mkfs wipefs blkdiscard shred sgdisk sfdisk diskutil chmod chown chgrp tee clean push reset truncate cat set env printenv export declare typeset compgen nc ncat ssh scp rsync base64"
FAST_PARTS='removeitem formatvolume cleardisk removepartition resetphysicaldisk initializedisk claude_ /proc/ /sessionenv/ /etc/ /dev/sd /dev/nvme /dev/hd /dev/vd /dev/xvd /dev/mmcblk /dev/disk /dev/rdisk /dev/mapper/ /dev/loop ${!'
fast_path() {  # true when the command holds no candidate token
  local t re tok
  lower "$1"
  t=$LOWER_OUT
  drop_char "$t" -; t=$DROP_OUT
  drop_char "$t" '"'; t=$DROP_OUT
  drop_char "$t" "'"; t=$DROP_OUT
  case "$t" in
    *'{'*) case "$t" in *'&'*) return 1 ;; esac ;;
  esac
  for tok in $FAST_PARTS; do
    case "$t" in *"$tok"*) return 1 ;; esac
  done
  re=""
  for tok in $FAST_HEADS $DOWNLOADERS $EVALWORD; do re="$re|$tok"; done
  re="(^|[^a-z0-9])(${re#|})([^a-z0-9]|$)"
  [[ $t =~ $re ]] && return 1
  return 0
}
fast_path "$CMD" && exit 0

# ---- normalize case once, for the checks below that must run the same for Bash and PowerShell ----
# PowerShell cmdlet resolution is case-insensitive (Invoke-WebRequest / iwr / IWR are equivalent),
# so a PowerShell payload is folded to lowercase before any token match. A Bash payload is left
# exactly as typed: real shell command lookup is case-sensitive, so "RM -rf /" is not the rm binary.
if [ "$TOOL" = PowerShell ]; then
  lower "$CMD"
  proc_cmd="$LOWER_OUT"
  lower "$CMD_ML"
  proc_ml="$LOWER_OUT"
else
  proc_cmd="$CMD"
  proc_ml="$CMD_ML"
fi

# whole_dq: proc_cmd with single-quoted spans blanked (double-quoted spans, and any $(...)/<(...)
# they carry, stay intact — needed so a downloader inside a double-quoted substitution stays visible).
# whole_nq: whole_dq with double-quoted spans ALSO blanked, so a merely-quoted MENTION of an
# operator or a downloader name (a commit message, an echo string) can't be misread as real syntax.
blank_single "$proc_cmd"
whole_dq="$BLANK_OUT"
blank_double "$whole_dq"
whole_nq="$BLANK_OUT"

# check_pipeline_text QUOTE-BLANKED-TEXT -> blocks on a network download / decoded payload piped
# straight into an interpreter. Split on ; && || & into statements, then each statement on | into
# pipeline stages; once a DOWNLOADERS or "base64 -d" stage has been seen, the very next stage may
# not resolve to a RUNNERS word (except the harmless json.tool pretty-printer module of Python, run with -m).
check_pipeline_text() {
  local t st pseg src
  # & and && end a statement. || stays: it splits into an empty pipeline stage, which resets the
  # download-seen state just as a statement break would.
  repl_char "$1" '&' ';'
  t=$REPL_OUT
  split_on ';' "$t"
  _STMTS=("${SPLIT_OUT[@]}")
  for st in "${_STMTS[@]}"; do
    split_on '|' "$st"
    _PSEGS=("${SPLIT_OUT[@]}")
    src=0
    for pseg in "${_PSEGS[@]}"; do
      resolve_head "$pseg"
      if in_list "$RH_HEAD" "$DOWNLOADERS"; then
        src=1
        continue
      fi
      if [ "$RH_HEAD" = base64 ]; then
        case " $pseg " in
          *' -d '*|*' -d')  src=1 ;;
          *' --decode '*|*' --decode') src=1 ;;
          *' -D '*|*' -D') src=1 ;;
        esac
        continue
      fi
      if [ "$src" = 1 ] && in_list "$RH_HEAD" "$RUNNERS"; then
        case "$pseg" in
          *' -m json.tool'*) src=0; continue ;;
        esac
        block "the output of a network download or a decoded payload piped straight into an interpreter"
      fi
      src=0
    done
  done
}

# check_subst STATEMENT -> 0 if a $(...) or <(...) inside STATEMENT resolves to a downloader.
# STATEMENT is split on ( once. A piece whose predecessor ends in $ or < opens a substitution, and
# its command is the piece up to the first ). When that command is only wrappers, flags or
# assignments and no ) closes it, the next piece continues it, so a substitution that runs sudo on
# a parenthesised group holding the downloader, and a substitution nested in another, are both seen.
check_subst() {
  case "$1" in
    *'$('*|*'<('*) ;;
    *) return 1 ;;
  esac
  local IFS='(' parts p open=0 opens_next=0
  parts=($1)
  IFS=$' \t\n'
  for p in "${parts[@]}"; do
    [ "$opens_next" = 1 ] && open=1
    case "$p" in
      *'$'|*'<') opens_next=1 ;;
      *) opens_next=0 ;;
    esac
    [ "$open" = 1 ] || continue
    resolve_head "${p%%')'*}"
    in_list "$RH_HEAD" "$DOWNLOADERS" && return 0
    case "$p" in
      *')'*) open=0 ;;
      *) [ -n "$RH_HEAD" ] && open=0 ;;
    esac
  done
  return 1
}

# check_substitution_text QUOTE-BLANKED-TEXT (doubles preserved) -> blocks on a command/process
# substitution whose inner command is a downloader, executed by a runner or by the shell's own
# dynamic-execution builtin.
check_substitution_text() {
  local t st
  flat_split "$1"
  t=$REPL_OUT
  split_on ';' "$t"
  _STMTS=("${SPLIT_OUT[@]}")
  for st in "${_STMTS[@]}"; do
    resolve_head "$st"
    if [ "$RH_HEAD" = "$EVALWORD" ] || in_list "$RH_HEAD" "$RUNNERS"; then
      if check_subst "$st"; then
        block "a downloaded command substitution executed by an interpreter"
      fi
    fi
  done
}

# check_lines TEXT -> the same two checks on each line of TEXT, since a line break ends a command
# just as ; does, and a command on a later line would otherwise read as more arguments to the one
# before it. Every line is also kept in ML_LINES for the per-command rules further down.
ML_LINES=()
check_lines() {
  local ln
  line_texts "$1"
  for ln in "${LINES[@]}"; do
    ML_LINES[${#ML_LINES[@]}]=$ln
    blank_single "$ln"
    _ln_dq=$BLANK_OUT
    blank_double "$_ln_dq"
    check_pipeline_text "$BLANK_OUT"
    check_substitution_text "$_ln_dq"
  done
}

check_pipeline_text "$whole_nq"
check_substitution_text "$whole_dq"
check_lines "$proc_ml"

# ---- Bash only: unwrap a single- or double-quoted -c payload given to sh, bash, zsh, ksh or dash,
# iteratively, up to 4 levels deep (matching the reference implementation's bounded recursion), so
# a catastrophic command wrapped in nested shell invocations is still caught by EVERY check above,
# not just the per-command rules further down. Each unwrapped level gets its own quote-blanked
# pipeline/substitution check.
UNWRAPPED=()
UNWRAPPED_NQ=()
if [ "$TOOL" = Bash ]; then
  _sq="'"
  # A double-quoted body may hold backslash escapes (\" \\ \$ \`), so it runs to the first
  # UNESCAPED quote, and those escapes are undone below as bash does before the next level.
  _dq_body='((\\.|[^"\\])*)'
  # Any number of option words may sit between the shell name and its -c cluster (sh -e -c, bash
  # -x -c, bash --norc -c, bash -o pipefail -c, bash --rcfile x -c, ...); -o/+o/--rcfile/--init-file
  # each consume the next word as their own value so it is never mistaken for the -c cluster. The
  # cluster itself may hold c anywhere (-ce, -ec) and an optional `--` may sit before the payload.
  _optword="(-o[[:space:]]+[^[:space:]]+|\+o[[:space:]]+[^[:space:]]+|--rcfile[[:space:]]+[^[:space:]]+|--init-file[[:space:]]+[^[:space:]]+|-[A-Za-z]+|\+[A-Za-z]+|--[a-z-]+)"
  _inner_re="(sh|bash|zsh|ksh|dash)[[:space:]]+(${_optword}[[:space:]]+)*-[A-Za-z]*c[A-Za-z]*([[:space:]]+--)?[[:space:]]+(\"${_dq_body}\"|${_sq}([^${_sq}]*)${_sq})"
  _cur="$proc_ml"
  _depth=0
  while [ "$_depth" -lt 4 ]; do
    if [[ $_cur =~ $_inner_re ]]; then
      if [ -n "${BASH_REMATCH[6]}" ]; then
        unescape "${BASH_REMATCH[6]}" dq
        _inner=$REPL_OUT
      else
        _inner=${BASH_REMATCH[8]}
      fi
      if [ -n "$_inner" ]; then
        UNWRAPPED=("${UNWRAPPED[@]}" "$_inner")
        _cur="$_inner"
        _depth=$((_depth + 1))
        continue
      fi
    fi
    break
  done
  for _lvl in "${UNWRAPPED[@]}"; do
    squash "$_lvl"
    blank_single "$SQUASH_OUT"; _lvl_dq="$BLANK_OUT"
    blank_double "$_lvl_dq"; _lvl_nq="$BLANK_OUT"
    UNWRAPPED_NQ[${#UNWRAPPED_NQ[@]}]=$_lvl_nq
    check_pipeline_text "$_lvl_nq"
    check_substitution_text "$_lvl_dq"
    check_lines "$_lvl"
  done
fi

if [ "$TOOL" = PowerShell ]; then
  # ---- PowerShell-specific catastrophes (minimal parity with the reference implementation) ----
  if in_order "$proc_cmd" remove-item -recurse -force || in_order "$proc_cmd" remove-item -force -recurse; then
    # Any drive root (not just C:), as a whole word, in any of its PowerShell spellings
    # ([A-Za-z]:  [A-Za-z]:\  [A-Za-z]:\*  [A-Za-z]:/  [A-Za-z]:/*), quoted or not. A drive
    # SUBPATH (D:\proj\build) is deliberately left alone: only an exact root word matches.
    # System and home folders are whole words too: anything under C:\Windows ($env:SystemRoot,
    # $env:windir) counts, but a home folder only as itself or its contents (\*), where C:\Users\<name>
    # is a home folder, so a project deeper inside one (C:\Users\me\proj\dist, ~\proj) is ordinary work.
    _drive_root=0
    _ps_root=0
    for _w in $proc_cmd; do
      strip_quotes "$_w"
      case "$STRIP_OUT" in
        [a-z]:|[a-z]:\\|[a-z]:\\\*|[a-z]:/|[a-z]:/\*) _drive_root=1 ;;
      esac
      # case patterns and slicing only: ${w//x/y} and ${w%x} are quadratic on one long word.
      _p=$STRIP_OUT
      case "$_p" in
        *[\\/]\*) _p=${_p:0:${#_p}-2} ;;
        *[\\/]) _p=${_p:0:${#_p}-1} ;;
      esac
      case "$_p" in
        c:[\\/]windows|c:[\\/]windows[\\/]*|'$env:systemroot'|'$env:systemroot'[\\/]*|\
'$env:windir'|'$env:windir'[\\/]*|'~'|'$home'|'${home}'|'$env:userprofile'|c:[\\/]users)
          _ps_root=1 ;;
        c:[\\/]users[\\/]*)
          case "${_p:9}" in *[\\/]*) ;; *) _ps_root=1 ;; esac ;;
      esac
    done
    if [ "$_drive_root" = 1 ]; then
      block "Remove-Item -Recurse -Force targeting a drive root"
    fi
    if [ "$_ps_root" = 1 ]; then
      block "Remove-Item -Recurse -Force targeting a system or home folder"
    fi
  fi
  case "$proc_cmd" in
    *'format-volume'*|*'clear-disk'*|*'remove-partition'*|*'reset-physicaldisk'*|*'initialize-disk'*)
      block "a destructive disk cmdlet (Format-Volume / Clear-Disk / Remove-Partition / ...)" ;;
  esac
  exit 0
fi

# ---- everything below here is Bash-only, matching the reference implementation's scope ----

# FSEGS: proc_cmd flat-split on ; && || & |, plus the same flat split applied to every level
# UNWRAPPED already found above (so a per-command rule below also sees inside nested shell -c
# invocations, up to the same 4-level depth) and to every line check_lines collected.
# All of them are joined with ; and split once: re-copying FSEGS for each of hundreds of lines
# would cost time in proportion to lines times segments.
_all=$proc_cmd
for _lvl in "${UNWRAPPED[@]}"; do
  squash "$_lvl"
  _all="$_all;$SQUASH_OUT"
done
if [ "${#ML_LINES[@]}" -gt 0 ]; then
  split_join ';' "${ML_LINES[@]}"
  _all="$_all;$JOIN_OUT"
fi
flat_split "$_all"
split_on ';' "$REPL_OUT"
FSEGS=("${SPLIT_OUT[@]}")

# CD_HINT: the folder a bare `.`, `./`, `./*` or `*` target stands for. It starts as the event's
# working directory and follows every `cd DIR` statement in the command (an absolute path, ~ or
# $HOME replaces it; a relative name is appended; `cd -`, `..` or an unreadable form clears it).
# `cd` is context for the rm and find rules, not a rule of its own, so it is not a fast-path head.
CD_HINT=$EVENT_CWD
# cwd_expand TEXT -> sets CWD_OUT to TEXT with each bare . ./ ./* or * word replaced by the folder
# CD_HINT names (or its contents), so has_target reads `rm -rf .` after `cd /` as a root wipe.
cwd_expand() {
  local w out="" hint=$CD_HINT
  CWD_OUT=$1
  [ -n "$hint" ] || return 0
  case " $1 " in *' . '*|*' ./ '*|*' ./* '*|*' * '*) ;; *) return 0 ;; esac
  # The home folder is known by its path too: the event's cwd is spelled out, never as ~.
  [ -n "${HOME:-}" ] && { [ "$hint" = "$HOME" ] || [ "$hint" = "$HOME/" ]; } && hint='~'
  for w in $1; do
    case "$w" in
      .|./) w=$hint ;;
      './*'|'*') case "$hint" in */) w="${hint}*" ;; *) w="$hint/*" ;; esac ;;
    esac
    out="$out $w"
  done
  CWD_OUT=${out# }
}
# Soft-stage flags set by the hard loop below (emitted only once every hard check passed clean).
CWD_WIDE_RM=0      # rm -rf on the whole working directory (. ./ ./* *)
XARGS_RM=0         # rm -rf with no path, fed by xargs
CWD_WIDE_FIND=0    # find -delete over the working tree with no name filter
TRUNC_OUTSIDE=0    # truncate of a file outside the working directory
GIT_SOFT=""        # git push --force / git reset --hard, with its reason (the last one found)
GIT_SOFT_ALL=""    # every one found, a line each (read only in all-soft mode)
git_soft() { GIT_SOFT=$1; GIT_SOFT_ALL="$GIT_SOFT_ALL$1"$'\n'; }

for seg in "${FSEGS[@]}"; do
  resolve_head "$seg"
  if [ "$RH_HEAD" = cd ] || [ "$RH_HEAD" = pushd ]; then
    _d=""
    for _w in $RH_REST; do
      case "$_w" in -*) continue ;; esac
      _d=$_w
      break
    done
    strip_quotes "$_d"
    _d=$STRIP_OUT
    case "$_d" in
      '') CD_HINT='~' ;;
      -|..|../*|'$'*) case "$_d" in '$HOME'*|'${HOME}'*) CD_HINT=$_d ;; *) CD_HINT="" ;; esac ;;
      /*|'~'|'~/'*) CD_HINT=$_d ;;
      *)
        _d=${_d#./}
        if [ -n "$CD_HINT" ]; then
          case "$CD_HINT" in */) CD_HINT="$CD_HINT$_d" ;; *) CD_HINT="$CD_HINT/$_d" ;; esac
        fi
        ;;
    esac
    continue
  fi
  case "$RH_HEAD" in
    rm)
      case " $RH_REST " in
        *' --no-preserve-root '*)
          block "rm --no-preserve-root, which defeats the root-deletion failsafe" ;;
      esac
      collect_flags "$RH_REST"
      _rec=0; _frc=0
      case "$SHORTS" in *r*|*R*) _rec=1 ;; esac
      case " $LONGS " in *' --recursive '*) _rec=1 ;; esac
      case "$SHORTS" in *f*) _frc=1 ;; esac
      case " $LONGS " in *' --force '*) _frc=1 ;; esac
      strip_quotes "$RH_REST"
      drop_char "$STRIP_OUT" ')'          # a subshell's closing paren sits on the last target
      STRIP_OUT=$DROP_OUT
      if [ "$_rec" = 1 ] && [ "$_frc" = 1 ]; then
        cwd_expand "$STRIP_OUT"
        if has_target "$STRIP_OUT" || has_target "$CWD_OUT"; then
          block "a recursive, forced delete targeting a system or home root"
        fi
        _ops=0
        for _w in $STRIP_OUT; do
          case "$_w" in -*) continue ;; esac
          _ops=$((_ops + 1))
          case "$_w" in .|./|'./*'|'*') CWD_WIDE_RM=1 ;; esac
        done
        if [ "$_ops" = 0 ]; then
          case " $seg " in *' xargs '*) XARGS_RM=1 ;; esac
        fi
      fi
      ;;
    find)
      strip_quotes "$RH_REST"
      drop_char "$STRIP_OUT" ')'
      STRIP_OUT=$DROP_OUT
      cwd_expand "$STRIP_OUT"
      if has_target "$STRIP_OUT" || has_target "$CWD_OUT"; then
        case " $RH_REST " in
          *' -delete '*|*' -delete') block "find on a system/home root with -delete" ;;
        esac
        case "$RH_REST" in
          *'-exec rm '*|*'-execdir rm '*) block "find on a system/home root with -exec rm" ;;
        esac
      fi
      case " $RH_REST " in
        *' -delete '*|*' -delete')
          # The whole working tree (no path, . or ./) with no name, path, time or size filter.
          _fp=""
          for _w in $STRIP_OUT; do
            case "$_w" in -*) break ;; esac
            _fp=$_w
            break
          done
          case "$_fp" in ''|.|./)
            case " $RH_REST " in
              *' -name '*|*' -iname '*|*' -path '*|*' -ipath '*|*' -wholename '*|*' -regex '*|\
*' -iregex '*|*' -newer'*|*' -mtime '*|*' -mmin '*|*' -empty '*|*' -size '*|*' -samefile '*) ;;
              *) CWD_WIDE_FIND=1 ;;
            esac ;;
          esac
          ;;
      esac
      ;;
    truncate)
      # -s/--size and -r/--reference take a value; every other word is a file to empty.
      _skipv=0
      for _w in $RH_REST; do
        if [ "$_skipv" = 1 ]; then _skipv=0; continue; fi
        case "$_w" in
          -s|-r|--size|--reference) _skipv=1; continue ;;
          -*) continue ;;
        esac
        strip_quotes "$_w"
        has_target "$STRIP_OUT" && block "truncate of a file under a system or home root"
        case "$STRIP_OUT" in /*|'~'|'~/'*|'$HOME'*|'${HOME}'*|../*) TRUNC_OUTSIDE=1 ;; esac
      done
      ;;
    dd)
      case " $RH_REST " in
        *' of=/dev/'*)
          _of=""
          for _w in $RH_REST; do
            case "$_w" in of=*) _of=${_w#of=} ;; esac
          done
          strip_quotes "$_of"
          is_device "$STRIP_OUT" && block "dd writing to a block device"
          ;;
      esac
      for _cf in $CRIT_FILES; do
        case " $RH_REST " in
          *" of=/etc/$_cf "*|*" of=/etc/$_cf") block "overwriting a critical system file" ;;
        esac
      done
      ;;
    mkfs|mkfs.*)
      [ -n "$RH_REST" ] && block "mkfs formatting a filesystem"
      ;;
    wipefs)
      strip_quotes "$RH_REST"
      is_device "$STRIP_OUT" && block "wipefs on a block device"
      ;;
    blkdiscard)
      strip_quotes "$RH_REST"
      is_device "$STRIP_OUT" && block "blkdiscard on a block device"
      ;;
    shred)
      strip_quotes "$RH_REST"
      is_device "$STRIP_OUT" && block "shred on a block device"
      ;;
    sgdisk)
      case " $RH_REST " in
        *' --zap-all '*|*' --zap '*) block "sgdisk --zap, which destroys partition tables" ;;
      esac
      collect_flags "$RH_REST"
      case "$SHORTS" in *Z*) block "sgdisk --zap, which destroys partition tables" ;; esac
      ;;
    sfdisk)
      strip_quotes "$RH_REST"
      is_device "$STRIP_OUT" && block "sfdisk writing a partition table to a device"
      ;;
    diskutil)
      lower "$RH_REST"
      _rr="$LOWER_OUT"
      case " $_rr " in
        *' erasedisk '*|*' erasevolume '*|*' zerodisk '*|*' randomdisk '*|*' reformat '*|*' secureerase '*|*'apfs delete'*)
          block "diskutil erase/zero/reformat/delete, which destroys a disk or volume" ;;
      esac
      ;;
    chmod|chown|chgrp)
      collect_flags "$RH_REST"
      _rec=0
      case "$SHORTS" in *R*) _rec=1 ;; esac
      case " $LONGS " in *' --recursive '*) _rec=1 ;; esac
      strip_quotes "$RH_REST"
      if [ "$_rec" = 1 ] && has_target "$STRIP_OUT"; then
        block "a recursive chmod/chown/chgrp targeting a system or home root"
      fi
      ;;
    tee)
      for _w in $RH_REST; do
        case "$_w" in -*) continue ;; esac
        strip_quotes "$_w"
        is_device "$STRIP_OUT" && block "tee writing to a block device"
        case "$STRIP_OUT" in
          "/etc/"*)
            for _cf in $CRIT_FILES; do
              case "$STRIP_OUT" in "/etc/$_cf") block "overwriting a critical system file" ;; esac
            done
            ;;
        esac
      done
      ;;
    git)
      set -f; set -- $RH_REST
      # Skip git's own global options before the subcommand (git -C dir clean ..., git -c k=v
      # clean ..., git --git-dir=... --no-pager clean ...), so `clean` is still found right after
      # them instead of only when it is literally the first word.
      _gskip=0
      while [ "$#" -gt 0 ]; do
        if [ "$_gskip" = 1 ]; then _gskip=0; shift; continue; fi
        case "$1" in
          -C|-c) _gskip=1; shift; continue ;;
          -*) shift; continue ;;
        esac
        break
      done
      _gsub="${1:-}"
      if [ "$_gsub" = clean ]; then
        shift
        _gargs="$*"
        set --
        collect_flags "$_gargs"
        _gx=0
        case "$SHORTS" in *x*|*X*) _gx=1 ;; esac
        _gf=0
        case "$SHORTS" in *f*) _gf=1 ;; esac
        case " $LONGS " in *' --force '*) _gf=1 ;; esac
        if [ "$_gx" = 1 ] && [ "$_gf" = 1 ]; then
          block "git clean -x, which irreversibly deletes ignored and untracked files"
        fi
      elif [ "$_gsub" = push ]; then
        # A plain force push rewrites the remote branch blindly; --force-with-lease (or
        # --force-if-includes) refuses when the remote moved, so it stays allowed.
        shift
        _gargs="$*"
        set --
        collect_flags "$_gargs"
        _gforce=0; _glease=0
        case "$SHORTS" in *f*) _gforce=1 ;; esac
        case " $LONGS " in *' --force '*) _gforce=1 ;; esac
        case " $LONGS " in *' --force-with-lease'*|*' --force-if-includes'*) _glease=1 ;; esac
        # A refspec with a leading plus (`+main`, `+HEAD:main`) is a force push too.
        case " $_gargs " in *' +'[A-Za-z0-9_./:-]*) _gforce=1 ;; esac
        if [ "$_gforce" = 1 ] && [ "$_glease" = 0 ]; then
          case " $_gargs " in
            *' main '*|*' master '*|*':main '*|*':master '*|*'/main '*|*'/master '*)
              git_soft "git push --force to main or master without --force-with-lease" ;;
            *) git_soft "git push --force without --force-with-lease, which overwrites the remote branch blindly" ;;
          esac
        fi
      elif [ "$_gsub" = reset ]; then
        shift
        case " $* " in
          *' --hard '*) git_soft "git reset --hard, which discards every uncommitted change in the working tree" ;;
        esac
        set --
      fi
      set --
      ;;
  esac
done

# ---- device / critical-file overwrite via redirection (whole-string) ----
# Scans proc_cmd, not the quote-blanked whole_nq: blanking would also erase a quoted target
# argument (a double-quoted system file path after >), which is exactly the token this rule needs
# to see.
case "$proc_cmd" in
  *'>'*)
    # Each field after a split on '>' starts with that redirect's target; an empty field is the
    # first half of '>>'.
    split_on '>' "$proc_cmd"
    for _rest in "${SPLIT_OUT[@]:1}"; do
      [ -n "$_rest" ] || continue
      _tgt=${_rest# }
      _tgt=${_tgt%% *}
      strip_quotes "$_tgt"
      is_device "$STRIP_OUT" && block "redirecting command output onto a block device"
      for _cf in $CRIT_FILES; do
        case "$STRIP_OUT" in "/etc/$_cf") block "overwriting a critical system file" ;; esac
      done
    done
    ;;
esac

# ---- fork bombs (structural, so no runnable copy of either shape sits in this file) ----
# check_forkbomb QUOTE-BLANKED-TEXT -> blocks on either shape anywhere in TEXT. The classic one, a
# function named ':', is matched with every space removed, so any spacing is seen. The general one
# is a function whose body calls it with a | and an & still to come before the first }:
# NAME() { ... NAME ... | ... & ... }. That is found in one pass: TEXT is split on }, each piece is
# cut at its last | or its last &, whichever comes first, then split on {, and each part into
# words. A part ending in NAME(), NAME ( ) or `function NAME` opens NAME's body, and NAME is kept
# as a variable _FD_NAME holding the piece number, so looking up a word later in the piece takes
# the same time however many functions came before. A word is a run of letters, digits and _.
_c=':'
_FB_CLASSIC="$_c(){$_c|$_c&};$_c"
# Every ASCII character but letters, digits and _, so a split on it leaves a text's words (the
# single quote and the backtick are written as \x27 and \x60).
_FB_WORD_IFS=$' \t\n\r\f\v!"#$%&\x27()*+,-./:;<=>?@[\\]^\x60{|}~'
# fb_words TEXT -> sets FB_WORDS to the words of TEXT. IFS holds * only for this one split: while
# it does, bash 3.2 stops matching * in case patterns.
fb_words() {
  local IFS=$_FB_WORD_IFS
  FB_WORDS=($1)
}
check_forkbomb() {
  local text=$1 IFS=$' \t\n\r\f\v' nows chunks c a b cid=0 parts p w v t name n open
  set -- $text
  IFS=
  nows="$*"
  IFS=$' \t\n'
  set --
  case "$nows" in
    *"$_FB_CLASSIC"*) block "a fork bomb (a function named ':' that pipes itself to itself in the background)" ;;
  esac
  case "$text" in *'{'*) ;; *) return 0 ;; esac
  case "$text" in *'|'*) ;; *) return 0 ;; esac
  case "$text" in *'&'*) ;; *) return 0 ;; esac
  split_on '}' "$text"
  chunks=("${SPLIT_OUT[@]}")
  for c in "${chunks[@]}"; do
    cid=$((cid + 1))
    case "$c" in *'{'*) ;; *) continue ;; esac
    case "$c" in *'|'*) ;; *) continue ;; esac
    case "$c" in *'&'*) ;; *) continue ;; esac
    a=${c%'|'*}
    b=${c%'&'*}
    if [ "${#a}" -lt "${#b}" ]; then c=$a; else c=$b; fi
    split_on '{' "$c"
    parts=("${SPLIT_OUT[@]}")
    open=0
    for p in "${parts[@]}"; do
      if [ "$open" = 1 ]; then
        fb_words "$p"
        for w in "${FB_WORDS[@]}"; do
          case "$w" in
            [A-Za-z_]*) ;;
            *) continue ;;
          esac
          case "$w" in *[!A-Za-z0-9_]*) continue ;; esac
          v=_FD_$w
          [ "${!v-}" = "$cid" ] &&
            block "a fork bomb (a self-replicating function piped to itself in the background)"
        done
      fi
      t=${p% }
      case "$t" in
        *')')
          t=${t%')'}
          t=${t% }
          case "$t" in
            *'(') t=${t%'('}; t=${t% } ;;
            *) continue ;;
          esac
          fb_words "$t"
          ;;
        *function*)
          fb_words "$t"
          n=${#FB_WORDS[@]}
          [ "$n" -ge 2 ] && [ "${FB_WORDS[n-2]}" = function ] || continue
          ;;
        *) continue ;;
      esac
      n=${#FB_WORDS[@]}
      [ "$n" -ge 1 ] || continue
      name=${FB_WORDS[n-1]}
      # The name must end the text, right before the ( ) or the {.
      case "$t" in *"$name") ;; *) continue ;; esac
      case "$name" in
        [A-Za-z_]*) ;;
        *) continue ;;
      esac
      case "$name" in *[!A-Za-z0-9_]*) continue ;; esac
      printf -v "_FD_$name" '%s' "$cid"
      open=1
    done
  done
}

# The whole command, and each shell -c payload unwrapped above.
for _fb_text in "$whole_nq" "${UNWRAPPED_NQ[@]}"; do
  check_forkbomb "$_fb_text"
done

# ---- userConfig secrets: block a Bash command that reads or dumps them ----
# Matched against proc_cmd (the raw, unescaped command, quotes included) rather than a
# quote-blanked variant: whole_dq/whole_nq blank single- or double-quoted spans, which would hide
# a quoted userConfig option name given to printenv, or a quoted CLAUDE_ENV_FILE reference. A
# quoted MENTION (e.g. a commit message) is accepted as an over-block here, since this rule
# protects real secrets.
case "$proc_cmd" in
  *CLAUDE_PLUGIN_OPTION_*)
    block "a command references a magician userConfig secret variable" ;;
esac
# Spelled in two pieces (never contiguous in this file's own source) so this script itself still
# passes the "only the env writers name the session env file" contract that every OTHER hook is
# held to, while still matching the real environment variable name at runtime.
_CEFNAME="CLAUDE_ENV"
_CEFNAME="${_CEFNAME}_FILE"
case "$proc_cmd" in
  *"$_CEFNAME"*)
    block "a command references the session env file that holds magician's userConfig secrets" ;;
esac
in_order "$proc_cmd" /proc/ /environ && block "reading another process's environment via /proc"
case "$proc_cmd" in
  *'/session-env/'*)
    block "a command reads Claude Code's per-session environment files" ;;
esac
# Prefix-match indirect expansion (a dollar sign, an opening brace and a !, then a name prefix and
# * or @) can read a variable by prefix match without ever naming it, which would otherwise dodge
# the check above. whole_dq (not whole_nq) is used so a real, evaluable indirect expansion is caught
# whether it's bare or inside double quotes, while a single-quoted LITERAL mention of the text never
# expands and is correctly ignored.
case "$whole_dq" in
  *'${!'*)
    block "indirect variable-name expansion, which can read a secret without naming it" ;;
esac

for seg in "${FSEGS[@]}"; do
  _fw=""
  _fr=""
  _lastwrap=""
  _skip=0
  set -f; set -- $seg
  # Strip a layer of ( { } ) ; grouping punctuation around a word (so an env run inside
  # parentheses or braces is still seen), VAR=value assignments, bare numeric args, and WRAPPERS words (sudo, command,
  # nohup, timeout N, time, builtin, env with an operand, ...; a value-taking flag is consumed via
  # flag_takes_value) to reach the real command, same as resolve_head does for the rm/dd/... loop
  # above — except a trailing env/printenv with NO further command is the dump itself, not a
  # wrapper to see through: env/printenv with no operand always prints the whole environment.
  while [ "$#" -gt 0 ]; do
    if [ "$_skip" = 1 ]; then _skip=0; shift; continue; fi
    _w=$1
    case "$_w" in '('*) _w=${_w#(} ;; esac
    case "$_w" in '{'*) _w=${_w#\{} ;; esac
    case "$_w" in *')') _w=${_w%)} ;; esac
    case "$_w" in *'}') _w=${_w%\}} ;; esac
    case "$_w" in *';') _w=${_w%;} ;; esac
    case "$_w" in
      '') shift; continue ;;
      *=*) shift; continue ;;
      [0-9]*) shift; continue ;;
      -*)
        [ -n "$_lastwrap" ] && flag_takes_value "$_lastwrap" "$_w" && _skip=1
        shift; continue
        ;;
    esac
    case "$_w" in */*) last_part "$_w" /; _w=$PART_OUT ;; esac
    case " $WRAPPERS " in
      *" $_w "*) _lastwrap=$_w; shift; continue ;;
    esac
    _fw=$_w
    shift
    _fr="$*"
    break
  done
  set --
  if [ -z "$_fw" ]; then
    case "$_lastwrap" in
      env|printenv) _fw=$_lastwrap ;;
    esac
  fi
  case "$_fw" in
    set)
      [ -z "$_fr" ] && block "a command prints the whole process environment"
      ;;
    env|printenv)
      # Any of these with ONLY flags (env -0, printenv --null) still dumps everything; a real
      # operand (env FOO=1 ./build, printenv PATH) is a normal, narrow use and stays allowed. A
      # value-taking flag's own value (env -u FOO, with no command after) isn't that operand: env
      # with no command always prints the resulting environment, regardless of what came before.
      _allflags=1
      _skipnext=0
      for _w in $_fr; do
        if [ "$_skipnext" = 1 ]; then _skipnext=0; continue; fi
        case "$_w" in
          -*) flag_takes_value "$_fw" "$_w" && _skipnext=1 ;;
          *) _allflags=0 ;;
        esac
      done
      if [ -z "$_fr" ] || [ "$_allflags" = 1 ]; then
        block "a command prints the whole process environment"
      fi
      ;;
    export)
      if [ -z "$_fr" ] || [ "$_fr" = '-p' ]; then
        block "a command prints the whole process environment"
      fi
      ;;
    declare|typeset)
      # typeset is the ksh/bash synonym for declare. -x/-p dump everything UNLESS a specific
      # variable is also named (declare -p HOME), which is a narrow, allowed read; short flags
      # may be combined (-px), so this collects them rather than comparing $_fr verbatim.
      collect_flags "$_fr"
      case "$SHORTS" in
        *x*|*p*)
          _has_operand=0
          for _w in $_fr; do
            case "$_w" in -*) ;; *) _has_operand=1 ;; esac
          done
          [ "$_has_operand" = 0 ] && block "a command prints the whole process environment"
          ;;
      esac
      ;;
    compgen)
      case " $_fr " in
        *' -e '*) block "a command prints the whole process environment" ;;
      esac
      ;;
  esac
done

# ---- soft-block stage (folded in from the former sentinel-guard) ----
# Reached only once every hard check above has passed clean. Same intent as the reference
# implementation's second, softer pass: a {"decision":"block"} permission verdict, not the
# unconditional exit-2 gate above.
lower "$proc_cmd"
CMD_LC="$LOWER_OUT"

# Run on the quote-blanked, lowercased text (not raw proc_cmd): a curl/wget MENTION inside a
# string (a commit message) is blanked away here, so it can't be misread as a real pipeline. The
# stage immediately after the pipe must RESOLVE (via resolve_head) to an exact RUNNERS word, not
# just contain "sh" as a substring — otherwise a later stage such as shasum would falsely match
# on "shasum". Mirrors check_pipeline_text's adjacency (only the very next stage counts, same
# json.tool pretty-printer carve-out) so the soft heuristic agrees with the hard gate above it.
lower "$whole_nq"
NQ_LC="$LOWER_OUT"
split_on '|' "$NQ_LC"
_dlstages=("${SPLIT_OUT[@]}")
_dlsrc=""
for _stg in "${_dlstages[@]}"; do
  case "$_stg" in
    *curl*) _dlsrc=curl; continue ;;
    *wget*) _dlsrc=wget; continue ;;
  esac
  if [ -n "$_dlsrc" ]; then
    resolve_head "$_stg"
    if in_list "$RH_HEAD" "$RUNNERS"; then
      case "$_stg" in
        *' -m json.tool'*) ;;
        *) soft_block "pipe-to-shell via $_dlsrc" ;;
      esac
    fi
  fi
  _dlsrc=""
done

for seg in "${FSEGS[@]}"; do
  resolve_head "$seg"
  if [ "$RH_HEAD" = "$EVALWORD" ]; then
    case "$RH_REST" in
      \"*|\$*|\`*|\'*) soft_block "the ${EVALWORD} builtin used with dynamic content" ;;
    esac
  fi
  if [ "$RH_HEAD" = rm ]; then
    collect_flags "$RH_REST"
    _rf=0
    case "$SHORTS" in *r*|*R*) case "$SHORTS" in *f*) _rf=1 ;; esac ;; esac
    if [ "$_rf" = 1 ]; then
      for _w in $RH_REST; do
        strip_quotes "$_w"
        case "$STRIP_OUT" in /*) soft_block "rm -rf on an absolute path" ;; esac
      done
    fi
  fi
  if [ "$RH_HEAD" = cat ]; then
    case " $RH_REST " in
      *'ssh/'*) soft_block "reading the SSH directory" ;;
    esac
    case "$RH_REST" in
      *aws/credentials*) soft_block "reading AWS credentials" ;;
    esac
    case "$RH_REST" in
      *'.config/gcloud/'*|*application_default_credentials.json*)
        soft_block "reading gcloud credentials" ;;
    esac
    case "$RH_REST" in
      *'.azure/'*) soft_block "reading Azure credentials" ;;
    esac
    # .env as a path component, quotes stripped first so a quoted argument (space-padded exact-
    # token matching would miss it) is still recognized: bare .env, a leading path (./.env,
    # config/.env) and a .env.* suffix (.env.local) all count; .envrc / .envrc.example do not, and
    # neither does a committed template that holds names, not values (.env.example, .env.local.sample).
    for _w in $RH_REST; do
      strip_quotes "$_w"
      last_part "$STRIP_OUT" /
      case "$PART_OUT" in
        .env.*.example|.env.*.sample|.env.*.template|.env.*.dist|\
.env.example|.env.sample|.env.template|.env.dist) ;;
        .env|.env.*) soft_block "reading .env file" ;;
      esac
    done
  fi
done

[ "$CWD_WIDE_RM" = 1 ] && soft_block "rm -rf on the whole working directory, dot or star; needs manual review"
[ "$XARGS_RM" = 1 ] && soft_block "rm -rf with no path, deleting whatever xargs feeds it; needs manual review"
[ "$CWD_WIDE_FIND" = 1 ] && soft_block "find -delete over the whole working tree with no name or path filter; needs manual review"
[ "$TRUNC_OUTSIDE" = 1 ] && soft_block "truncate of a file outside the working directory; needs manual review"
if [ "$ALL_SOFT" = 1 ]; then
  while IFS= read -r _gs; do [ -n "$_gs" ] && soft_block "$_gs"; done <<EOF_GS
$GIT_SOFT_ALL
EOF_GS
fi
[ -n "$GIT_SOFT" ] && soft_block "$GIT_SOFT"

_priv=0
case "$CMD_LC" in
  *.ssh*|*.aws*|*.env*|*password*|*secret*|*token*) _priv=1 ;;
esac
_net=0
case " $CMD_LC " in
  *' curl '*|*' wget '*|*' nc '*|*' ncat '*|*' ssh '*|*' scp '*|*' rsync '*) _net=1 ;;
esac
_exec=0
for _r in sh python ruby node; do
  in_order "$CMD_LC" '|' "$_r" && _exec=1
done
if [ "$_priv" = 1 ] && [ "$_net" = 1 ] && [ "$_exec" = 1 ]; then
  soft_block "private data, network access and execution together (a lethal trifecta); needs manual review"
fi

[ "$ALL_SOFT" = 1 ] && [ "${#SOFT_REASONS[@]}" -gt 0 ] && emit_all_soft
exit 0
