#!/usr/bin/env bash
# UserPromptSubmit — keyword-based skill hint, plus two optional Magician status line markers.
#   * Hint: at most one per prompt. When the prompt matches a skill's keywords, one factual line
#     ("Magician: the magician:divine skill covers code review ...") is added to Claude's context.
#     No hint when the prompt already contains a slash command. Jira / Confluence are mentioned only
#     when the prompt itself names /jira or /confluence.
#   * Status line markers (only while the Magician status line is enabled in cli-ui.json):
#     status/<session>.json records the hinted skill name; status/<session>.effort.json records
#     "ultracode" when the prompt switches that mode on, and is removed when it is switched off.
# Nothing derived from the prompt is stored (no prompt text or excerpt), and the transcript is
# never read. Plain bash; always exits 0.
export LC_ALL=C

INPUT=$(cat 2>/dev/null) || exit 0
INPUT=${INPUT:0:262144}

re_sid='"session_id"[[:space:]]*:[[:space:]]*"([A-Za-z0-9_-]{1,64})"'
SID=""
[[ $INPUT =~ $re_sid ]] && SID=${BASH_REMATCH[1]}

re_prompt='"prompt"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)'
[[ $INPUT =~ $re_prompt ]] || exit 0
P=${BASH_REMATCH[1]}
P=${P:0:4000}

# JSON string -> plain text for matching (newlines, tabs and other escapes become spaces).
sq="'"; rsq=$'\xe2\x80\x99'; ph=$'\001'
case $P in *\\*)
  P=${P//\\\\/$ph}
  P=${P//\\u2019/$sq}
  P=${P//\\u????/ }
  P=${P//\\n/ }; P=${P//\\t/ }; P=${P//\\r/ }; P=${P//\\b/ }; P=${P//\\f/ }
  P=${P//\\\"/\"}; P=${P//\\\//\/}
  P=${P//\\/}
  P=${P//$ph/\\} ;;
esac
P=${P//$rsq/$sq}
PL=$(printf '%s' "$P" | tr '[:upper:]' '[:lower:]')

# ---- regex building blocks (POSIX ERE has no \b: boundaries are spelled out) ----
B='(^|[^[:alnum:]_])'                 # left word boundary
E='([^[:alnum:]_]|$)'                 # right word boundary
W='[[:alnum:]_]'
S='[[:space:]]'
N='[^[:alnum:]_.?!]'                  # a non-word character inside one sentence
G14="$N([^.?!]{0,12}$N)?"             # Gnn: word boundary, then up to nn characters of the
G16="$N([^.?!]{0,14}$N)?"             # same sentence, then a word boundary
G18="$N([^.?!]{0,16}$N)?"
G20="$N([^.?!]{0,18}$N)?"
G24="$N([^.?!]{0,22}$N)?"
G25="$N([^.?!]{0,23}$N)?"
G30="$N([^.?!]{0,28}$N)?"
G40="$N([^.?!]{0,38}$N)?"
G45="$N([^.?!]{0,43}$N)?"
G50="$N([^.?!]{0,48}$N)?"
G55="$N([^.?!]{0,53}$N)?"
G60="$N([^.?!]{0,58}$N)?"

any() {  # any <regex>... : true when the lowercased prompt matches one of them
  local r
  for r in "$@"; do [[ $PL =~ $r ]] && return 0; done
  return 1
}

# ---- status line markers (only when the status line is enabled) ----
MHOME=${MAGICIAN_HOME:-}
if [ -z "$MHOME" ] && [ -n "${HOME:-}" ]; then MHOME="$HOME/.claude/magician"; fi
UI_ON=0
if [ -n "$SID" ] && [ -n "$MHOME" ] && [ -f "$MHOME/cli-ui.json" ]; then
  CFG=$(head -c65536 "$MHOME/cli-ui.json" 2>/dev/null)
  re_on='"state"[[:space:]]*:[[:space:]]*"enabled"'
  [[ $CFG =~ $re_on ]] && UI_ON=1
fi
put_marker() {  # put_marker <file> <json>
  mkdir -p "$MHOME/status" 2>/dev/null || return 0
  printf '%s\n' "$2" > "$MHOME/status/$1.$$" 2>/dev/null && mv -f "$MHOME/status/$1.$$" "$MHOME/status/$1" 2>/dev/null
  return 0
}

if [ "$UI_ON" = 1 ]; then
  # Ultracode reports as xhigh on the status line input; this overlay lets the bar show the mode.
  if any "${B}(exit|stop|leave|end|disable|turn off|no more|out of)${G14}ultracode${E}"; then
    rm -f "$MHOME/status/$SID.effort.json" 2>/dev/null
  elif any "${B}ultracode${E}"; then
    put_marker "$SID.effort.json" "{\"mode\":\"ultracode\",\"ts\":$(date +%s)}"
  elif any "${B}(set|switch|change|go back|reset|revert)${G24}(mode|effort|reasoning)${G16}(default|normal|standard|off|low|medium|high|xhigh|max)${E}" \
           "/effort${S}+(low|medium|high|xhigh|max)${E}"; then
    rm -f "$MHOME/status/$SID.effort.json" 2>/dev/null
  fi
fi

[ "${#P}" -ge 10 ] || exit 0

# ---- keyword triggers ----
t_review() { any \
  "${B}(code review|do a (code )?review)${E}" \
  "${B}(review|audit|evaluat${W}+|assess${W}*|critiqu${W}+|look at|go over)${G40}(prs?|mrs?|pull requests?|merge requests?|diffs?|changesets?|changes|branch|commit|this code)${E}" \
  "${B}(prs?|mrs?|pull requests?|merge requests?|diffs?|changesets?|changes)${G40}(review|audit|evaluat${W}+|assess${W}*|critiqu${W}+)${E}"; }
t_autopsy() { any \
  "${B}(post-?mortem|rca|root cause analysis|blameless|incident (review|report|retro(spective)?)|write up the (incident|outage))${E}"; }
t_audit() { any \
  "${B}(walk|go|going)${S}+(me${S}+)?(through|to)${G30}(flow|page|feature|journey|checkout|screen|experience)${G60}(recommend|suggest|improv${W}+|slow(ness)?|issues?|problems?|friction|awkward|better)${E}" \
  "${B}(be|act as|as)${S}+(a${S}+)?user${G50}(recommend|suggest|improv${W}+|issues?|friction|slow(ness)?|problems?)${E}" \
  "${B}(check out|check|look at)${G25}(this|the)${G20}(flow|page|journey|checkout|experience)${G55}(recommend|suggest|improv${W}+|friction|slow(ness)?)${E}"; }
t_debug() { any \
  "${B}(bugs?|debug|broken|crash${W}*|stack ?trace|tracebacks?|exceptions?|regressions?|defects?|segfaults?|panic)${E}" \
  "exception${E}" \
  "${B}(not working|isn'?t working|doesn'?t work|won'?t work|stopped working|something('s| is) wrong)${E}" \
  "${B}(throw${W}*|getting|hit(ting)?|raises?)${S}+an?${S}+${W}*(error|exception)${E}" \
  "${B}(production|prod|deploy${W}*)${G30}(issues?|outage|incident|down|broken|failing|errors?|problems?|not working)${E}" \
  "${B}(issues?|problems?|outage|incident|errors?|bug)${G30}(production|prod|deploy${W}*)${E}" \
  "${B}(report${W}*|there('s| is| was))${G30}(bug|defect|problem|issue|error)${E}" \
  "${B}(problem|issue)${G20}(report${W}*|happening|occurr${W}*|in prod${W}*|persist${W}*)${E}"; }
t_weave() { any \
  "${B}(implement|deliver|build|ship|complete|do|finish)${G40}(all|these|every|each|the (whole )?(epic|batch|backlog|list|set))${G30}(stories|tickets|tasks|features|items|endpoints|jiras?|issues|components|modules|files)${E}" \
  "${B}(implement|deliver|build|ship)${G20}([0-9]+|several|multiple|many)${G20}(stories|tickets|tasks|features|items|endpoints|jiras?|issues|components|modules)${E}" \
  "${B}migrat${W}+${G40}(across|everywhere|all|the (whole )?(codebase|repo)|every (file|module|component))${E}" \
  "${B}(for each of|one (per|each)|batch (of|process))${G30}(stories|tickets|tasks|features|items|files|components|modules)${E}"; }
t_security() {
  # A negated mention ("no security changes", "don't need security") is not a security request.
  any "${B}(no|not|never|without|none|cannot|lack|[a-z]+n't|dont|doesnt|didnt|isnt|arent|wasnt|werent|wont|cant|shouldnt)${G25}security${E}" && return 1
  any \
  "${B}(security (scan|audit|review|issue|check)|vulnerabilit${W}+|owasp|cve|secrets? (leak|expos${W}+|scan)|injection (risk|vuln${W}*|attack)|pen ?test|hardening)${E}" \
  "${B}expos${W}+ (secret|credential|key|token|api key)s?${E}" \
  "${B}(secret|credential|api[ -]?key|token)s?${G20}expos${W}+" \
  "${B}leak${W}+${G20}(secret|credential|api[ -]?key|key|token|password)s?${E}" \
  "${B}(secret|credential|api[ -]?key|token|password)s?${G20}leak${W}+" \
  "${B}is${G25}secure${E}" \
  "${B}secure${G20}(against|from|injection|xss|csrf|attack|exploit)${E}"; }
t_perf() { any \
  "${B}(slow|sluggish|too slow|laggy|latency|bottleneck|memory leak|high (cpu|memory)|throughput|p9[59])${E}" \
  "${B}performance (issue|problem|bottleneck|regression)${E}" \
  "${B}optimi[sz]e (the )?(speed|performance|latency|throughput)${E}" \
  "${B}speed (it|this|things) up${E}"; }
t_deploy() { any \
  "${B}(ci/cd|ci pipeline|deployment pipeline|github actions|gitlab ci|circleci|jenkins)${E}" \
  "${B}set up (a |the )?(ci|pipeline|deploy${W}*)${E}" \
  "${B}deploy${W}*${G20}(pipeline|config|workflow|to (prod|staging))${E}" \
  "${B}pipeline${G30}(staging|prod|production|deploy${W}*)${E}" \
  "${B}the (ci|build) (is )?(failing|red|broken)${E}"; }
t_transmute() { any \
  "${B}(port|re-?implement|recreate|replicate|clone)${G40}(feature|flow|search|widget|component|functionality|module|page|screen)${E}" \
  "${B}(port|re-?implement|recreate|replicate|clone|copy)${G40}(into|onto|to)${G25}(our|another|a (new|different)|the other|this)${G18}(app|application|codebase|project|service|stack|site)${E}" \
  "${B}(swap|replace|migrat${W}+|switch)${G40}(vendor|3rd[- ]?party|third[- ]?party|provider|supplier)${E}" \
  "${B}chang${W}+${G25}how${G45}(vendor|provider|3rd[- ]?party|third[- ]?party|supplier|api|backend|service)${E}" \
  "${B}(behind the scenes|under the hood)${G40}(keep|preserv${W}+|same)${G20}(ux|user experience|experience|behavio${W}+)${E}" \
  "${B}(keep|preserv${W}+|same)${G20}(ux|user experience)${G45}(swap|replace|migrat${W}+|switch|vendor|provider|3rd[- ]?party)${E}" \
  "${B}(comprehend|understand how|figure out how|reverse[- ]?engineer)${G45}(works?|working)${G45}(rebuild|recreate|re-?implement|port)${E}"; }
t_statusline() { any \
  "${B}magician${S}+(ui|bar)${E}" \
  "${B}cli ui${E}" \
  "${B}status[[:space:]-]?(line|bar)${E}" \
  "${B}(enable|turn on|turn off|disable|show|hide|configure|set up|customi[sz]e)${G30}the bar${E}" \
  "${B}(context|tokens?)${G24}(footer|the bar)${E}"; }
t_magic() {
  case $PL in *"find out"*|*"look into"*|*"dig into"*|*"find information"*|*"tell me about"*|*"learn about"*) return 0 ;; esac
  any "${B}(research|investigate|analy[sz]e|explore|examine|assess|evaluate|discover|audit|study|survey|probe|benchmark)${E}"; }

set -f; set -- $PL; NWORDS=$#; set +f
SHORT=0; [ "$NWORDS" -lt 4 ] && SHORT=1
TM=""
transmute_hit() { [ -n "$TM" ] || { if t_transmute; then TM=1; else TM=0; fi; }; [ "$TM" = 1 ]; }

SKILL=""; MSG=""
LEAD=${PL#"${PL%%[![:space:]]*}"}
case $LEAD in /*) ;;                                           # the prompt is a slash command
*)
  if any "(^|[[:space:](])/(magician:)?jira([^[:alnum:]_-]|$)"; then
    SKILL=jira
    MSG="Magician: the prompt mentions /jira. The magician:jira skill uses the bundled jira CLI. If the user prefers another available Jira integration, use that."
  elif any "(^|[[:space:](])/(magician:)?confluence([^[:alnum:]_-]|$)"; then
    SKILL=confluence
    MSG="Magician: the prompt mentions /confluence. The magician:confluence skill uses the bundled confluence CLI. If the user prefers another available Confluence integration, use that."
  elif any "(^|[[:space:]])/[a-z][a-z0-9_:-]*([[:space:]]|$|[.,;!?)])" "magician:"; then
    :                                                          # the user already named a command
  elif t_review; then
    SKILL=divine;     MSG="Magician: the magician:divine skill covers code review (change context first, then a multi-lens review)."
  elif t_autopsy; then
    SKILL=autopsy;    MSG="Magician: the /magician:autopsy command covers post-mortems and root-cause write-ups (timeline, 5 Whys, blameless action items). It runs when the user types it."
  elif [ "$SHORT" = 0 ] && t_audit; then
    SKILL=transmute;  MSG="Magician: the /magician:transmute command has an AUDIT mode that walks a flow as a user, read-only, and ranks recommendations. It runs when the user types it."
  elif t_debug && ! transmute_hit; then
    SKILL=unravel;    MSG="Magician: the magician:unravel skill covers systematic debugging (hypotheses first, evidence before any change)."
  elif t_weave; then
    SKILL=weave;      MSG="Magician: the magician:weave skill covers delivering many similar items (tickets, files, features) as one guarded workflow."
  elif t_security && ! transmute_hit; then
    SKILL=sentinel;   MSG="Magician: the magician:sentinel skill covers read-only security review (OWASP Top 10, secrets, injection surfaces, dependencies)."
  elif t_perf && ! transmute_hit; then
    SKILL=accelerate; MSG="Magician: the magician:accelerate skill covers performance work (measure a baseline, change, then re-measure)."
  elif t_deploy && ! transmute_hit; then
    SKILL=deploy;     MSG="Magician: the /magician:deploy command covers CI/CD pipelines (GitHub Actions, GitLab CI, CircleCI). It runs when the user types it."
  elif [ "$SHORT" = 0 ] && transmute_hit; then
    SKILL=transmute;  MSG="Magician: the /magician:transmute command covers understanding an existing feature, then porting it to another app or integrating a change behind a parity check. It runs when the user types it."
  elif t_statusline; then
    SKILL=statusline; MSG="Magician: the magician:statusline skill covers the Magician status line (enable, configure, disable) through the bundled magician-ui CLI."
  elif [ "$SHORT" = 0 ] && t_magic; then
    SKILL=magic;      MSG="Magician: the magician:magic skill covers research and analysis requests."
  fi ;;
esac

[ -n "$MSG" ] || exit 0
[ "$UI_ON" = 1 ] && put_marker "$SID.json" "{\"skill\":\"$SKILL\",\"ts\":$(date +%s)}"
printf '{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"%s"}}\n' "$MSG"
exit 0
