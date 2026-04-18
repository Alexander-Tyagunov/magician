---
name: autopsy
description: Post-mortem analysis for incidents — timeline reconstruction, 5 Whys root cause, action items
keep-coding-instructions: true
---

# /autopsy — Post-Mortem Analysis

Run a structured post-mortem for an incident or significant failure.

## Blameless Principle

This process is blameless. The goal is to understand what happened and prevent recurrence — not to assign fault.

## Process

### Phase 1: Gather Facts
1. Ask: what was the incident? (brief description)
2. Ask: what was the impact? (users affected, duration, data loss, revenue)
3. Ask: when did it start and end?

Collect timeline evidence:
```bash
git log --oneline --since="<start>" --until="<end>"
gh run list --limit 20
```

### Phase 2: Timeline Reconstruction
Build a chronological timeline:
```
HH:MM — <event> (source: git log / monitoring / manual)
HH:MM — <event>
...
```

### Phase 3: Root Cause Analysis (5 Whys)
```
Problem: <symptom>
Why 1: <immediate cause>
Why 2: <cause of cause>
Why 3: <deeper cause>
Why 4: <systemic cause>
Why 5: <root cause>
```

The root cause is where action items should be aimed.

### Phase 4: Action Items
For each root cause identified:
```
ACTION: <what to do>
OWNER: <role, not person>
DEADLINE: <date>
PREVENTS: <which Why this addresses>
```

Categories: Detection (better monitoring), Prevention (code/process), Response (runbook), Recovery (backup/rollback).

### Phase 5: Write Post-Mortem
Save to `.workspace/shared/postmortems/YYYY-MM-DD-<incident-name>.md`:

```markdown
# Post-Mortem: <incident name>

**Date:** <date>
**Severity:** P1/P2/P3
**Duration:** <N minutes/hours>
**Impact:** <users/systems affected>

## Timeline
<reconstructed timeline>

## Root Cause
<5 Whys analysis>

## Action Items
| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| <item> | <role> | <date> | Open |

## What Went Well
- <things that helped limit the incident>

## What Could Be Improved
- <systemic improvements>
```

### Phase 6: Commit
```bash
git add .workspace/shared/postmortems/
git commit -m "docs: add post-mortem for <incident>"
```

## Completion Signal

"Autopsy complete. Post-mortem written to `.workspace/shared/postmortems/<filename>.md`. N action items identified."
