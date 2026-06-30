#!/usr/bin/env bash
# UserPromptSubmit hook: context self-management (size warnings + post-compaction
# resume capsule) ALWAYS, plus intent routing (/magic, /divine, /jira, /confluence)
# and repeat-pattern → /inscribe nudges.

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
PATTERNS_FILE="$PLUGIN_DATA/patterns.json"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

mkdir -p "$PLUGIN_DATA"

INPUT=$(cat)

python3 - "$PATTERNS_FILE" "$INPUT" "$PLUGIN_ROOT" <<'PYEOF'
import json, re, sys, os, subprocess

patterns_file = sys.argv[1]
raw_input = sys.argv[2] if len(sys.argv) > 2 else ""
plugin_root = sys.argv[3] if len(sys.argv) > 3 else ""

try:
    hook_data = json.loads(raw_input)
except Exception:
    hook_data = {}

prompt = hook_data.get("prompt", "") or hook_data.get("message", "")
session_id = hook_data.get("session_id", "default") or "default"
transcript = hook_data.get("transcript_path", "") or ""

# --- Context self-management: run EVERY prompt (independent of prompt content) ---
# bin/ctx hook re-injects a resume capsule after compaction (once) and emits a
# size-band warning (once per band). Failure is swallowed so the hook never breaks.
ctx_note = ""
if plugin_root:
    try:
        p = subprocess.run([os.path.join(plugin_root, "bin", "ctx"), "hook",
                            "--session", session_id, "--transcript", transcript],
                           capture_output=True, text=True, timeout=10)
        ctx_note = (p.stdout or "").strip()
    except Exception:
        ctx_note = ""

pending = [ctx_note] if ctx_note else []


def flush(extra=None):
    notes = list(pending)
    if extra:
        notes.append(extra)
    if notes:
        print(json.dumps({"additionalContext": "\n\n".join(notes)}))
    sys.exit(0)


if not prompt or len(prompt) < 10:
    flush()

# load pattern store
if os.path.exists(patterns_file):
    try:
        store = json.load(open(patterns_file))
    except Exception:
        store = {"patterns": []}
else:
    store = {"patterns": []}
patterns = store.get("patterns", [])

STOP = {"this", "that", "with", "from", "have", "will", "been", "they",
        "were", "when", "what", "your", "just", "also", "then", "than",
        "more", "some", "make", "need", "want", "like", "only"}
words = [w for w in re.findall(r'\b[a-z]{4,}\b', prompt.lower()) if w not in STOP]
fingerprint = list(dict.fromkeys(words[:25]))
if not fingerprint:
    flush()

prompt_lower = prompt.lower()


def _neg(svc):
    return bool(re.search(r"(?:\b(?:no|not|never|without|none|cannot|lack)\b|n['’]?t)[^.!?]{0,25}\b" + svc + r"\b", prompt_lower))


def _has(*pats):
    return any(re.search(p, prompt_lower) for p in pats)


def _invoking(*names):
    return any(t in prompt_lower for t in names)


# --- intent triggers (computed here; routed below in STRICT precedence — exactly one wins) ---
review_trigger = _has(
    r'\b(code review|do a (?:code )?review)\b',
    r'\b(review|audit|evaluat\w+|assess\w*|critiqu\w+|look at|go over)\b[^.?!]{0,40}\b(prs?|mrs?|pull requests?|merge requests?|diffs?|changesets?|changes|branch|commit|this code)\b',
    r'\b(prs?|mrs?|pull requests?|merge requests?|diffs?|changesets?|changes)\b[^.?!]{0,40}\b(review|audit|evaluat\w+|assess\w*|critiqu\w+)\b',
)
autopsy_trigger = _has(
    r'\b(post-?mortem|\brca\b|root cause analysis|blameless|incident (?:review|report|retro(?:spective)?)|write up the (?:incident|outage))\b',
)
debug_trigger = _has(
    r'\b(bugs?|debug|broken|crash\w*|stack ?trace|tracebacks?|exceptions?|regressions?|defects?|segfaults?|panic)\b',
    r'\w*exception\b',  # CamelCase class names, e.g. NullPointerException
    r"\b(not working|isn'?t working|doesn'?t work|won'?t work|stopped working|something(?:'s| is) wrong)\b",
    r'\b(throw\w*|getting|hit(?:ting)?|raises?)\s+an?\s+\w*(error|exception)\b',
    r'\b(production|prod|deploy\w*)\b[^.?!]{0,30}\b(issues?|outage|incident|down|broken|failing|errors?|problems?|not working)\b',
    r'\b(issues?|problems?|outage|incident|errors?|bug)\b[^.?!]{0,30}\b(production|prod|deploy\w*)\b',  # reversed order
    r'\b(report\w*|there(?:\'s| is| was))\b[^.?!]{0,30}\b(bug|defect|problem|issue|error)\b',
    r'\b(problem|issue)\b[^.?!]{0,20}\b(report\w*|happening|occurr\w*|in prod\w*|persist\w*)\b',
)
security_trigger = (not _neg("security")) and _has(
    r'\b(security (?:scan|audit|review|issue|check)|vulnerabilit\w+|owasp|\bcve\b|secrets? (?:leak|expos\w+|scan)|injection (?:risk|vuln\w*|attack)|pen ?test|hardening)\b',
    r'\bexpos\w+ (?:secret|credential|key|token|api key)s?\b',                 # "exposed secrets"
    r'\b(secret|credential|api[ -]?key|token)s?\b[^.?!]{0,20}\bexpos\w+',       # "secrets ... exposed"
    r'\bis\b[^.?!]{0,25}\bsecure\b',                                            # "is this code secure"
    r'\bsecure\b[^.?!]{0,20}\b(against|from|injection|xss|csrf|attack|exploit)\b',
)
# A described multi-step PIPELINE (numbered steps, first/then/finally, "here's the flow",
# for-each). Soft fallback: nudge to DECIDE the engine, only when no specific action fired.
flow_shape = _has(
    r"\b(here(?:'s| is| are)|this is|below is)\b[^.?!]{0,24}\b(the )?(flow|steps|plan|pipeline|process|sequence|stages|phases)\b",
    r'\bthe (flow|steps|plan|pipeline|process|sequence|stages|phases)\b\s+(is|are)\b',  # "the steps are …"
    r'\b(steps|plan|flow|process|pipeline|sequence|stages|phases)\b\s*(?:are|is)?\s*:',  # "steps:", "plan is:"
    r'(^|\n)\s*1[.)]\s+\S.*\n\s*2[.)]\s+',                                  # numbered list 1. .. 2. ..
    r'\bstep\s*1\b[^.?!]{0,90}\bstep\s*2\b',
    r'\bfirst\b[^.?!]{0,90}\b(then|next)\b[^.?!]{0,140}\b(then|next|finally|lastly|after that|and then)\b',
    r'\bfor each\b[^.?!]{0,40}\b(then|do|implement|create|run|build|generate|process)\b',
)
weave_trigger = _has(
    r'\b(implement|deliver|build|ship|complete|do|finish)\b[^.?!]{0,40}\b(all|these|every|each|the (?:whole )?(?:epic|batch|backlog|list|set))\b[^.?!]{0,30}\b(stories|tickets|tasks|features|items|endpoints|jiras?|issues|components|modules|files)\b',
    r'\b(implement|deliver|build|ship)\b[^.?!]{0,20}\b(\d+|several|multiple|many)\b[^.?!]{0,20}\b(stories|tickets|tasks|features|items|endpoints|jiras?|issues|components|modules)\b',
    r'\bmigrat\w+\b[^.?!]{0,40}\b(across|everywhere|all|the (?:whole )?(?:codebase|repo)|every (?:file|module|component))\b',
    r'\b(for each of|one (?:per|each)|batch (?:of|process))\b[^.?!]{0,30}\b(stories|tickets|tasks|features|items|files|components|modules)\b',
)
perf_trigger = _has(
    r'\b(slow|sluggish|too slow|laggy|latency|bottleneck|memory leak|high (?:cpu|memory)|throughput|p9[59])\b',
    r'\bperformance (?:issue|problem|bottleneck|regression)\b',
    r'\boptimi[sz]e (?:the )?(?:speed|performance|latency|throughput)\b',
    r'\bspeed (?:it|this|things) up\b',
)
deploy_trigger = _has(
    r'\b(ci/cd|ci pipeline|deployment pipeline|github actions|gitlab ci|circleci|jenkins)\b',
    r'\bset up (?:a |the )?(?:ci|pipeline|deploy\w*)\b',
    r'\bdeploy\w*\b[^.?!]{0,20}\b(pipeline|config|workflow|to (?:prod|staging))\b',
    r'\bpipeline\b[^.?!]{0,30}\b(staging|prod|production|deploy\w*)\b',
    r'\bthe (?:ci|build) (?:is )?(?:failing|red|broken)\b',
)
jira_trigger = (not _neg("jira")) and _has(r'\bjira\b', r'\b(my|the)\s+(board|sprint|backlog)\b', r'\btickets?\b')
confluence_trigger = (not _neg("confluence")) and _has(r'\bconfluence\b', r'\bwiki\s+(page|space|doc)\b')

MAGIC_KEYWORDS = {"research", "investigate", "analyze", "analyse", "explore", "examine",
                  "assess", "evaluate", "discover", "audit", "study", "survey", "probe", "benchmark"}
MAGIC_PHRASES = ["find out", "look into", "dig into", "find information", "tell me about", "learn about"]
words_in_prompt = set(re.findall(r'\b[a-z]+\b', prompt_lower))
magic_hit = bool(words_in_prompt & MAGIC_KEYWORDS) or any(ph in prompt_lower for ph in MAGIC_PHRASES)
matched_magic = list(words_in_prompt & MAGIC_KEYWORDS)[:2] or [ph for ph in MAGIC_PHRASES if ph in prompt_lower][:1]
is_short = len(prompt.split()) < 4

# --- route: STRICT precedence, first match flushes & exits → never multi-skill ---
if review_trigger and not _invoking("/divine", "magician:divine", "/scrutinize"):
    flush("[MAGICIAN] Code-review intent detected. Auto-activating /divine — establish change context, ask the user "
          "how deep via AskUserQuestion, then run the multi-lens review. Invoke magician:divine before responding.")
if autopsy_trigger and not _invoking("/autopsy", "magician:autopsy"):
    flush("[MAGICIAN] Post-mortem/RCA intent detected. Use magician:autopsy — gather facts, reconstruct the timeline, "
          "run 5-Whys, write blameless action items.")
if debug_trigger and not _invoking("/unravel", "magician:unravel"):
    flush("[MAGICIAN] Bug/problem-report intent detected. Auto-activating /unravel (systematic debugging: hypothesis "
          "preflight, evidence before any change). Ground it comprehensively with /magic and the knowledge graph "
          "(kg query / kg blast on the affected area) for root-cause research; invoke magician:unravel before responding.")
if weave_trigger and not _invoking("/weave", "magician:weave"):
    flush("[MAGICIAN] Large multi-item delivery detected. Use /weave — compose ONE native Workflow that delivers all "
          "units with magician's guardrails (TDD per unit, kg grounding, certify, parallel multi-lens review + "
          "adversarial verify, write gates) instead of hand-rolling many agents. Invoke magician:weave before responding.")
if security_trigger and not _invoking("/sentinel", "magician:sentinel"):
    flush("[MAGICIAN] Security intent detected. Use magician:sentinel — OWASP Top 10, secret/credential scan, injection "
          "surfaces, dependency + git-history audit (read-only).")
if perf_trigger and not _invoking("/accelerate", "magician:accelerate"):
    flush("[MAGICIAN] Performance intent detected. Use magician:accelerate — baseline-first: measure before changing, "
          "re-measure after; use the knowledge graph (kg blast) to scope hot paths.")
if deploy_trigger and not _invoking("/deploy", "magician:deploy"):
    flush("[MAGICIAN] CI/CD intent detected. Use magician:deploy — create/update/monitor the pipeline "
          "(GitHub Actions / GitLab CI / CircleCI).")
if jira_trigger and not _invoking("/jira", "magician:jira"):
    flush("[MAGICIAN] Jira intent detected. Use the magician:jira skill (direct HTTP REST, no MCP; it runs first-time "
          "setup if Jira isn't configured) for this request.")
if confluence_trigger and not _invoking("/confluence", "magician:confluence"):
    flush("[MAGICIAN] Confluence intent detected. Use the magician:confluence skill (direct HTTP REST, no MCP; it runs "
          "first-time setup if Confluence isn't configured) for this request.")
if flow_shape and not is_short and len(prompt.split()) >= 12 and not _invoking("/weave", "magician:weave", "/manifest", "magician:manifest", "/orchestrate"):
    flush("[MAGICIAN] This reads like a multi-step delivery. Decide the engine before diving in: if it's N similar "
          "units (tickets/files/features) → run it via /weave as ONE guarded Workflow (TDD per unit, kg grounding, "
          "certify, multi-lens review + adversarial verify, write gates); if it's distinct SDLC stages → /manifest. "
          "Either way, don't hand-roll many ad-hoc agents.")
if magic_hit and not is_short and not _invoking("/magic", "magician:magic", "/conjure"):
    flush("[MAGICIAN] Research/analysis intent detected ({}). Auto-activating /magic skill. Invoke magician:magic "
          "before responding to this request.".format(", ".join(str(m) for m in matched_magic)))

# repeat-pattern detection → /inscribe nudge
best_match, best_score = None, 0.0
cur = set(fingerprint)
for p in patterns:
    stored_fp = set(p.get("fingerprint", []))
    if not stored_fp:
        continue
    score = len(stored_fp & cur) / max(len(stored_fp | cur), 1)
    if score > 0.55 and score > best_score:
        best_score, best_match = score, p

inscribe_msg = None
if best_match:
    best_match["count"] = best_match.get("count", 1) + 1
    if best_match["count"] == 3:
        inscribe_msg = "I've seen this type of request 3 times now. Would you like me to create a reusable skill for it using /inscribe?"
    elif best_match["count"] == 5:
        inscribe_msg = "This pattern has come up 5 times. I'll draft a skill — invoke /inscribe to review and save it."
else:
    patterns.append({"fingerprint": fingerprint, "count": 1, "sample": prompt[:120]})

store["patterns"] = patterns
try:
    json.dump(store, open(patterns_file, "w"), indent=2)
except Exception:
    pass

flush(inscribe_msg)
PYEOF
