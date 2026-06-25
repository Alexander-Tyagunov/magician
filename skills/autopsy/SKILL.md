---
name: autopsy
description: Blameless post-mortem / RCA — gathers facts, reconstructs a timeline, runs 5-Whys, defines action items, writes the post-mortem file and commits it. Use after an incident or outage.
allowed-tools: Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(gh run list:*), Write, Read
disable-model-invocation: true
argument-hint: [incident name or description]
---

# /autopsy — Post-Mortem Analysis

Run a structured post-mortem for an incident or significant failure.

## Blameless Principle

This process is blameless. The goal is to understand what happened and prevent recurrence — not to assign fault.

## Process

### Phase 1: Gather Facts

Ask all three questions in one message:
> "To run a proper post-mortem, I need the basics:
> 1. What was the incident? (brief description)
> 2. What was the impact? (users affected, duration, data loss, revenue)
> 3. When did it start and end? (approximate times / dates)"

**End your turn. Wait for all three answers before running any git or CI commands.**

Then collect timeline evidence:
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

### Phase 7: Remember the Incident (optional)

Offer to remember this incident in the global reference store via `/chronicle`: one line capturing **what + date + postmortem path**. Only do this with explicit user confirmation.

## Completion Signal

"Autopsy complete. Post-mortem written to `.workspace/shared/postmortems/<filename>.md`. N action items identified."
