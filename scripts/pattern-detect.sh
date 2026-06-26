#!/usr/bin/env bash
# Reads incoming prompt JSON from stdin, tracks intent patterns,
# offers skill creation when a pattern repeats 3+ times.

set -euo pipefail

PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.local/share/magician}"
PATTERNS_FILE="$PLUGIN_DATA/patterns.json"

mkdir -p "$PLUGIN_DATA"

INPUT=$(cat)

python3 - "$PATTERNS_FILE" "$INPUT" <<'PYEOF'
import json, re, sys, os

patterns_file = sys.argv[1]
raw_input = sys.argv[2] if len(sys.argv) > 2 else ""

try:
    hook_data = json.loads(raw_input)
except Exception:
    hook_data = {}

prompt = hook_data.get("prompt", "") or hook_data.get("message", "")
if not prompt or len(prompt) < 10:
    sys.exit(0)

if os.path.exists(patterns_file):
    with open(patterns_file) as f:
        store = json.load(f)
else:
    store = {"patterns": []}

patterns = store.get("patterns", [])

STOP = {"this", "that", "with", "from", "have", "will", "been", "they",
        "were", "when", "what", "your", "just", "also", "then", "than",
        "more", "some", "make", "need", "want", "like", "only"}
words = [w for w in re.findall(r'\b[a-z]{4,}\b', prompt.lower()) if w not in STOP]
fingerprint = list(dict.fromkeys(words[:25]))

if not fingerprint:
    sys.exit(0)

# --- /magic auto-invoke: research-intent keyword detection ---
MAGIC_KEYWORDS = {
    "research", "investigate", "analyze", "analyse", "explore",
    "examine", "assess", "evaluate", "discover", "audit",
    "study", "survey", "probe", "benchmark"
}
MAGIC_PHRASES = ["find out", "look into", "dig into", "find information", "tell me about", "learn about"]

prompt_lower = prompt.lower()
# code-review intent (a review verb near a PR/MR/diff/branch noun) — takes precedence over /magic research
review_trigger = bool(
    re.search(r'\b(code review|do a (?:code )?review)\b', prompt_lower)
    or re.search(r'\b(review|audit|evaluat\w+|assess\w*|critiqu\w+|look at|go over)\b[^.?!]{0,40}\b(prs?|mrs?|pull requests?|merge requests?|diffs?|changesets?|changes|branch|commit|this code)\b', prompt_lower)
    or re.search(r'\b(prs?|mrs?|pull requests?|merge requests?|diffs?|changesets?|changes)\b[^.?!]{0,40}\b(review|audit|evaluat\w+|assess\w*|critiqu\w+)\b', prompt_lower)
)
# Jira / Confluence intent — take precedence over /magic research.
# Negation guard: don't nudge toward a service the user says they don't have/use.
def _neg(svc):
    return bool(re.search(r"(?:\b(?:no|not|never|without|none|cannot|lack)\b|n['’]?t)[^.!?]{0,25}\b" + svc + r"\b", prompt_lower))
jira_trigger = (not _neg("jira")) and bool(
    re.search(r'\bjira\b', prompt_lower)
    or re.search(r'\b(my|the)\s+(board|sprint|backlog)\b', prompt_lower)
    or re.search(r'\btickets?\b', prompt_lower)
)
confluence_trigger = (not _neg("confluence")) and bool(
    re.search(r'\bconfluence\b', prompt_lower)
    or re.search(r'\bwiki\s+(page|space|doc)\b', prompt_lower)
)
words_in_prompt = set(re.findall(r'\b[a-z]+\b', prompt_lower))
magic_hit = words_in_prompt & MAGIC_KEYWORDS
magic_phrase_hit = [ph for ph in MAGIC_PHRASES if ph in prompt_lower]

already_invoking = any(t in prompt_lower for t in ["/magic", "magician:magic", "/conjure"])
is_short = len(prompt.split()) < 4

if (magic_hit or magic_phrase_hit) and not already_invoking and not is_short and not review_trigger and not jira_trigger and not confluence_trigger:
    matched = list(magic_hit)[:2] or magic_phrase_hit[:1]
    print(json.dumps({
        "additionalContext": (
            "[MAGICIAN] Research/analysis intent detected ({}). "
            "Auto-activating /magic skill. Invoke magician:magic before responding to this request."
        ).format(", ".join(str(m) for m in matched))
    }))
    sys.exit(0)
# --- end /magic auto-invoke ---

# --- /divine auto-invoke: code-review intent (review_trigger computed above, before /magic) ---
already_reviewing = any(t in prompt_lower for t in ["/divine", "magician:divine", "/scrutinize"])

if review_trigger and not already_reviewing:
    print(json.dumps({
        "additionalContext": (
            "[MAGICIAN] Code-review intent detected. Auto-activating /divine — establish change "
            "context, ask the user how deep via AskUserQuestion, then run the multi-lens review. "
            "Invoke magician:divine before responding."
        )
    }))
    sys.exit(0)
# --- end /divine auto-invoke ---

# --- /jira & /confluence auto-invoke ---
if jira_trigger and not any(t in prompt_lower for t in ["/jira", "magician:jira"]):
    print(json.dumps({
        "additionalContext": (
            "[MAGICIAN] Jira intent detected. Use the magician:jira skill (direct HTTP REST, no MCP; "
            "it runs first-time setup if Jira isn't configured) for this request."
        )
    }))
    sys.exit(0)
if confluence_trigger and not any(t in prompt_lower for t in ["/confluence", "magician:confluence"]):
    print(json.dumps({
        "additionalContext": (
            "[MAGICIAN] Confluence intent detected. Use the magician:confluence skill (direct HTTP REST, no MCP; "
            "it runs first-time setup if Confluence isn't configured) for this request."
        )
    }))
    sys.exit(0)
# --- end /jira & /confluence auto-invoke ---

best_match = None
best_score = 0.0
for p in patterns:
    stored_fp = set(p.get("fingerprint", []))
    current_fp = set(fingerprint)
    if not stored_fp:
        continue
    overlap = len(stored_fp & current_fp)
    score = overlap / max(len(stored_fp | current_fp), 1)
    if score > 0.55 and score > best_score:
        best_score = score
        best_match = p

if best_match:
    best_match["count"] = best_match.get("count", 1) + 1
    count = best_match["count"]
    if count == 3:
        print(json.dumps({
            "additionalContext": "I've seen this type of request 3 times now. Would you like me to create a reusable skill for it using /inscribe?"
        }))
    elif count == 5:
        print(json.dumps({
            "additionalContext": "This pattern has come up 5 times. I'll draft a skill — invoke /inscribe to review and save it."
        }))
else:
    patterns.append({
        "fingerprint": fingerprint,
        "count": 1,
        "sample": prompt[:120]
    })

store["patterns"] = patterns
with open(patterns_file, "w") as f:
    json.dump(store, f, indent=2)

sys.exit(0)
PYEOF
