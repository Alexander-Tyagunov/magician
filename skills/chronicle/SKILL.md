---
name: chronicle
description: View session-learning history AND manage the global reference store (repos, projects, ideas remembered across every session). Use to review past sessions or to remember/recall/forget a reference.
allowed-tools: Bash(ls:*), Bash(python3:*), Bash(cat:*), Read, Write, Edit
argument-hint: [last N | branch X | since DATE | clear N | remember <fact> | references | forget <text>]
---

# /chronicle — Session History & Global References

Two stores, both global to this machine (survive across all projects and sessions):

- **Session history** — `~/.local/share/magician/chronicle/` — one JSON per session (written by the Stop hook).
- **Global references** — `~/.local/share/magician/references.md` — repos, projects, and ideas worth remembering. Loaded into context at every session start.

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

1. Parse the request from `$ARGUMENTS` (or ask): `last N`, `branch X`, `since DATE`, `clear N`, `remember <fact>`, `references`, `forget <text>`. **If you must ask, end your turn and wait.**
2. For reads (history view, `references`): run the command and present results.
3. For `remember`: classify the fact as Repository / Project / Idea, state what you'll save, **wait for confirmation**, then append.
4. For `forget` / `clear`: show what will be removed and **wait for an explicit yes** before deleting (this is permanent).

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
