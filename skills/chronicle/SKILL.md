---
name: chronicle
description: View and manage accumulated session learnings from the Stop hook chronicle
keep-coding-instructions: true
---

# /chronicle — Session History

View what the Stop hook has been recording across sessions.

## Chronicle Location

`~/.local/share/magician/chronicle/` — one JSON file per session (`YYYY-MM-DD-HH-MM.json`).

Each file contains:
```json
{
  "timestamp": "2026-04-17T22:00:00Z",
  "branch": "feature/auth",
  "commits": ["abc123 feat: add login endpoint"],
  "changed_files": ["src/auth.ts", "tests/auth.test.ts"],
  "summary": "3 commit(s) on feature/auth: add login endpoint, add JWT validation..."
}
```

## Commands

### View recent sessions
```bash
ls -t ~/.local/share/magician/chronicle/*.json | head -10
```

### Read a session
```bash
python3 -c "import json; d=json.load(open('<path>')); print(json.dumps(d, indent=2))"
```

### View summaries (last 10)
```bash
python3 -c "
import json, os, glob
files = sorted(glob.glob(os.path.expanduser('~/.local/share/magician/chronicle/*.json')))[-10:]
for f in files:
    d = json.load(open(f))
    print(d.get('timestamp','?')[:10], '|', d.get('branch','?'), '|', d.get('summary','')[:80])
"
```

## Process

1. Ask: "What do you want to see?
   - `last N` — show last N session summaries
   - `branch X` — sessions on branch X
   - `since YYYY-MM-DD` — sessions from that date onward
   - `clear N` — delete entries older than N days"

   **End your turn. Wait for their choice before running any commands.**

2. Execute the relevant command and present results.

3. For `clear`: before deleting anything, ask: "This will permanently delete chronicle entries older than N days. Confirm?" **End your turn. Wait for an explicit 'yes' or 'confirm' before running the delete.**

## Clearing Old Chronicles
```bash
python3 -c "
import os, json, glob
from datetime import datetime, timedelta
cutoff = datetime.utcnow() - timedelta(days=30)
for f in glob.glob(os.path.expanduser('~/.local/share/magician/chronicle/*.json')):
    d = json.load(open(f))
    ts = datetime.fromisoformat(d.get('timestamp','').rstrip('Z'))
    if ts < cutoff:
        os.remove(f)
        print('Removed:', f)
"
```

## Completion Signal

"Chronicle viewed. N sessions recorded since <earliest date>."
