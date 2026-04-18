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

1. Ask user: what do you want to see?
   - "last N sessions" — show summaries
   - "sessions on branch X" — filter by branch
   - "sessions since date Y" — filter by date
   - "clear old chronicles" — delete entries older than N days
2. Execute the relevant command and present results
3. For clear: ask confirmation before deleting

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
