---
name: autopsy
description: Blameless post-mortem / RCA — gathers facts, reconstructs a timeline, runs 5-Whys, defines action items, writes the post-mortem file and commits it. Use after an incident or outage.
allowed-tools: Read, AskUserQuestion, Edit(./.workspace/shared/postmortems/**), Bash(gh run list *), Bash(kg query *), Bash(git commit -m *)
disable-model-invocation: true
argument-hint: "[incident name or description]"
---

# /autopsy — Post-Mortem Analysis

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg` and give subagents that full path. If that is missing too (Claude chat ships no plugin tools), skip the `kg` steps and search the code directly.

Run a structured post-mortem for an incident or significant failure.

## Blameless Principle

This process is blameless. The goal is to understand what happened and prevent recurrence — not to assign fault.

## Autonomy — approve the plan, then run

After Phase 1's three facts are answered (the incident / impact / timeframe gate), run Phases 2–5 — timeline reconstruction, 5-Whys, action items, and drafting the post-mortem — **autonomously**: `git log`, `gh run list`, `kg query`, and other reads need no confirmation question. A one-line scope preview after Phase 1 (incident, time window, what to scan) is enough; then proceed.

Re-gate **only** on this skill's real side effects — show the drafted post-mortem and confirm before the Phase 6 `git add`/`git commit`, and before any Phase 7 `/chronicle` write. See [lore/autonomy.md](../../lore/autonomy.md).

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

Show the drafted post-mortem, then gate the commit with the **AskUserQuestion** tool (not a bare sentence). Frame it "Post-mortem ready — commit it?" with options:
- **Commit it** — stage and commit the post-mortem
- **Revise** — edit the timeline / root cause / action items first
- **Skip commit** — leave the file uncommitted

**End your turn at the AskUserQuestion call.** Treat any free-form "yes / looks good / approved" as **Commit it**. Only run `git add`/`git commit` on approval:
```bash
git add .workspace/shared/postmortems/YYYY-MM-DD-<incident-name>.md
git commit -m "docs: add post-mortem for <incident>"
```

Stage only this post-mortem, so a draft the user chose not to commit stays out. Claude Code asks before the `git add` (only the commit is pre-approved); if the user declines it, stop without committing.

For wide circulation, you can also publish the post-mortem as a Claude Code **Artifact** (a live page on claude.ai, team-co-editable on Team/Enterprise) — offer it, don't create it unprompted. Publishing to a **public** link (anyone with the URL can view it) is an outward sharing action: **confirm it, keep it account-private by default, and never expose an internal incident's proprietary detail, secrets, or affected-system specifics to a public link.**

### Phase 7: Remember the Incident (optional)

Offer to remember this incident in the global reference store via `/chronicle` — one line capturing **what + date + postmortem path**. Ask with the **AskUserQuestion** tool (not a bare sentence), then end your turn:
- **Remember it** — record the one-line entry via `/chronicle`
- **Skip** — don't record it

Only write via `/chronicle` on **Remember it** (or a free-form "yes"). On **Skip**, stop here.

## Obstacles

This is a terminal, user-facing skill — it reports to the human directly, not upward to an orchestrator — so it emits no upward Obstacles block: surface any blocker in prose to the user and stop.

See [lore/obstacles.md](../../lore/obstacles.md).

## Completion Signal

"Autopsy complete. Post-mortem written to `.workspace/shared/postmortems/<filename>.md`. N action items identified."
