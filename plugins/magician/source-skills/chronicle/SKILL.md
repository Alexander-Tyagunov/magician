---
name: chronicle
description: Memory & context steward — view session-learning history, manage the global reference store (repos, projects, ideas), AND manage live context (size status, post-compaction resume capsule, project learnings, promotion). Use to review past sessions, remember/recall/forget a reference, check context size, resume after compaction, or capture/consolidate learnings.
allowed-tools: Bash(ls:*), Bash(python3:*), Bash(cat:*), Bash(ctx:*), Bash(stat:*), Read, Write, Edit
argument-hint: [status | resume | learn <fact> [--global] | consolidate | last N | remember <fact> | references | forget <text> | clear N]
---

# /chronicle — Memory, History & Context Steward

Three stores, all global to this machine (survive across all projects and sessions):

- **Session history** — `~/.local/share/magician/chronicle/` — one JSON per session (written by the Stop hook).
- **Global references** — `~/.local/share/magician/references.md` — repos, projects, and ideas worth remembering. Loaded into context at every session start.
- **Context state & project learnings** — driven by the bundled **`ctx`** CLI (size tracking, resume capsule, per-project learnings). The honest limits and internals are in [references/context-mgmt.md](references/context-mgmt.md).

## Context self-management (`ctx`)

The plugin tracks context size every prompt and captures a resume capsule before any compaction (so nothing is lost) — automatically, via hooks. These subcommands expose it:

| Command | Does |
|---|---|
| `/chronicle status` | `ctx pct --transcript <transcript_path>` → current context %; plus last capsule + project learnings count. The transcript path comes from the hook environment; if unknown, say so. |
| `/chronicle resume` | `ctx resume --keep` → print the latest resume capsule (goal, open threads, decisions, changed files, artifact paths) to restore bearings after a compaction. |
| `/chronicle learn "<fact>" [--global]` | `ctx learn --add "<fact>"` (project) or `--global` (promote to references.md). **Confirm before `--global`.** |
| `/chronicle consolidate` | `ctx consolidate` → show recurring project learnings; offer to promote high-frequency ones to global references (**confirm each**) and prune stale ones. |

Honest limits (never overclaim): a plugin can't read a live token count (we parse the transcript's latest `usage` — accurate, one turn stale), and **can't force or steer compaction** — only the user/auto-threshold compacts. We warn before it balloons and make loss impossible via the capsule. Details: [references/context-mgmt.md](references/context-mgmt.md).

## Session history

Each JSON: `{ timestamp, branch, commits, changed_files, summary }`.

```bash
# last 10 summaries
python3 -c "
import json, os, glob
files = sorted(glob.glob(os.path.expanduser('~/.local/share/magician/chronicle/*.json')))[-10:]
for f in files:
    d = json.load(open(f))
    print(d.get('timestamp','?')[:10], '|', d.get('branch','?'), '|', d.get('summary','')[:80])
"
```

## Global references (cross-session memory)

The reference store holds things you want every future session to know: repositories you work in, projects and their goals, and ideas to revisit. SessionStart injects it automatically, so once remembered, a fact is available everywhere.

It is deliberately an **explicit, legible artifact** — a plain markdown file the user can read and edit directly (an "idea file" / personal knowledge base), not opaque implicit memory. Keep entries terse and durable, and prune stale ones with `forget`: an overgrown store distracts the model more than it helps.

**Always confirm before writing to or deleting from the global store** — it persists across all projects. Saving a reference is permissioned: state exactly what you'll save and wait for a yes.

```bash
# View the store
cat ~/.local/share/magician/references.md 2>/dev/null || echo "(no references yet)"
```

To **remember** a fact (after the user confirms), append under the right section, creating the file/headers if absent:
```bash
python3 - "$ENTRY" "$SECTION" <<'PY'
import os, sys
entry, section = sys.argv[1], sys.argv[2]  # section: Repositories | Projects | Ideas
path = os.path.expanduser('~/.local/share/magician/references.md')
header = "# Magician — Global References\n<!-- Remembered across all sessions. Managed by /chronicle. -->\n"
text = open(path).read() if os.path.exists(path) else header
if f"## {section}" not in text:
    text += f"\n## {section}\n"
lines = text.splitlines()
out, added = [], False
for ln in lines:
    out.append(ln)
    if ln.strip() == f"## {section}" and not added:
        out.append(f"- {entry}"); added = True
open(path, "w").write("\n".join(out) + "\n")
print(f"Remembered under {section}: {entry}")
PY
```

To **forget**, show the matching lines, confirm, then remove them with an Edit.

## Process

1. Parse the request from `$ARGUMENTS` (or ask): `status`, `resume`, `learn <fact> [--global]`, `consolidate`, `last N`, `branch X`, `since DATE`, `clear N`, `remember <fact>`, `references`, `forget <text>`. **If you must ask, end your turn and wait.**
2. For reads (history view, `references`, `status`, `resume`): run the command and present results.
3. For `remember` / `learn --global`: classify the fact, state what you'll save, **wait for confirmation**, then append (global store persists across all projects). Project-scoped `learn` (no `--global`) needs no confirmation — it's local and cheap.
4. For `forget` / `clear` / `consolidate` pruning: show what will be removed and **wait for an explicit yes** before deleting (this is permanent).

## Clearing old chronicles (uses the N you were given)

```bash
python3 - "$N_DAYS" <<'PY'
import os, json, glob, sys
from datetime import datetime, timedelta
n = int(sys.argv[1])
cutoff = datetime.utcnow() - timedelta(days=n)
for f in glob.glob(os.path.expanduser('~/.local/share/magician/chronicle/*.json')):
    try:
        d = json.load(open(f))
        ts = datetime.fromisoformat(d.get('timestamp','').rstrip('Z'))
        if ts < cutoff:
            os.remove(f); print('Removed:', f)
    except Exception:
        pass
PY
```

## Model note

If a remembered project would benefit from a more capable model than the current session (see [lore/models.md](../../lore/models.md)), mention it when the reference surfaces — don't switch silently.

## Completion Signal

"Chronicle done. <N sessions recorded> · <M references stored>."
