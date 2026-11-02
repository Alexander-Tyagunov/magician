---
name: "autopsy"
description: "Blameless post-mortem / RCA; timeline, 5-Whys, action items, committed write-up. Use after an incident or outage."
license: "MIT"
allowed-tools: "Read, AskUserQuestion, Edit(./.workspace/shared/postmortems/**), Bash(gh run list *), Bash(kg query *), Bash(git commit -m *)"
metadata: {"claude-code.argument-hint": "[incident name or description]", "claude-code.disable-model-invocation": "true"}
---

# /autopsy — Post-Mortem Analysis

> **Bundled command:** if `kg` is not found, run it as `../../tools/kg` and give subagents that full path. If that is missing too (Claude chat ships no plugin tools), skip the `kg` steps and search the code directly.

Run a structured post-mortem for an incident or significant failure.

## Blameless Principle

This process is blameless. The goal is to understand what happened and prevent recurrence — not to assign fault.

## Autonomy — approve the plan, then run

After Phase 1's three facts are answered (the incident / impact / timeframe gate), run Phases 2–5b — timeline reconstruction, 5-Whys, action items, drafting the post-mortem and its eval skeleton — **autonomously**: `git log`, `gh run list`, `kg query`, and other reads need no confirmation question. A one-line scope preview after Phase 1 (incident, time window, what to scan) is enough; then proceed.

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

### Phase 5b: Incident to eval skeleton

Turn the incident into a regression eval, so the same failure cannot pass a later run unnoticed.

1. Write `.workspace/shared/postmortems/YYYY-MM-DD-<incident-name>.eval.md` (inside this skill's write grant). It holds two fenced blocks in the eval format of `evals/*/`:
   - `prompt.md`: frontmatter `name`, `description` (name the post-mortem path), `tags: [incident]`, `runs: 3`, `max_turns`, `allowed_tools` and `expected_outcome` (the correct behavior). The body is the triggering input or request, in the user's own words, with secrets and personal data removed.
   - `case.yaml`, written as JSON: `{"schema_version": "1.1", "name": "<incident-name>", "graders": [{"name": "TODO-<check>", "type": "llm", "criteria": "TODO: PASS if <correct behavior>. FAIL if <the failure from the timeline>."}]}`. Add a `regex` or `tool_used` grader when the failure is mechanical. A human replaces each TODO before the case runs.
2. When the project has an `evals/` folder, offer to copy the skeleton to `evals/<incident-name>/prompt.md` and `evals/<incident-name>/case.yaml`. That write is outside the grant, so it prompts.
3. When the incident has no testable trigger (a vendor outage, a hardware fault), skip the skeleton and say why in the post-mortem.

Before the Phase 6 gate, grade the draft against [references/rubric.md](references/rubric.md); list unmet items.

### Phase 6: Commit

Show the drafted post-mortem, then gate the commit with the **AskUserQuestion** tool (not a bare sentence). Frame it "Post-mortem ready — commit it?" with options:
- **Commit it** — stage and commit the post-mortem
- **Revise** — edit the timeline / root cause / action items first
- **Skip commit** — leave the file uncommitted

**End your turn at the AskUserQuestion call.** Treat any free-form "yes / looks good / approved" as **Commit it**. Only run `git add`/`git commit` on approval:
```bash
git add .workspace/shared/postmortems/YYYY-MM-DD-<incident-name>.md
git add .workspace/shared/postmortems/YYYY-MM-DD-<incident-name>.eval.md
git commit -m "docs: add post-mortem for <incident>"
```

Run the `.eval.md` line only when the skeleton exists: `git add` of a missing path fails and stages nothing. Stage only this post-mortem, so a draft the user chose not to commit stays out. Claude Code asks before the `git add` (only the commit is pre-approved); if the user declines it, stop without committing.

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

"Autopsy complete. Post-mortem written to `.workspace/shared/postmortems/<filename>.md` (eval skeleton: `<filename>.eval.md`, or none with the reason). N action items identified."

## On Codex

Read the Claude Code features this skill names as follows on Codex and ChatGPT (full table: [On Codex](../../lore/skill-authoring.md#on-codex)).

- Subagents (`Task`/`Agent`): Codex subagents are `.codex/agents/*.toml` files (`name`, `description`, `developer_instructions`); the review lenses ship here as `*-lens` skills.
- `AskUserQuestion`: Codex has no question form; ask the same question in prose, with the same options, and wait for the reply.
- Skill commands: `/<skill>` is `$<skill>` on Codex and `@<skill>` in ChatGPT.
- Paths such as `../../tools/kg` are relative to the folder of the file that names them; resolve them to an absolute path before you run them.
