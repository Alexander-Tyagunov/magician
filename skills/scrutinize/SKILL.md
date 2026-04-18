---
name: scrutinize
description: Dispatches 3 specialist reviewers (correctness, security, simplification) and consolidates findings
keep-coding-instructions: true
---

# /scrutinize — Multi-Agent Code Review

Run three specialist agents in parallel: correctness reviewer, sentinel, simplifier.

## Process

1. **Collect review scope** — list all files changed since the feature branch diverged from main:
   ```bash
   git diff main...HEAD --name-only
   ```
2. **Dispatch 3 specialist agents simultaneously** using the agent definitions:
   - `agents/reviewer.md` — correctness and edge cases
   - `agents/sentinel.md` — security vulnerabilities
   - `agents/simplifier.md` — over-engineering
3. **Collect all findings**
4. **Deduplicate** — if two agents flag the same issue, consolidate into one finding
5. **Prioritize** — Critical first, then High, Medium, Low
6. **Present consolidated findings** to user:
   ```
   === SCRUTINY REPORT ===
   Critical: N | High: N | Medium: N | Low: N

   [Critical] FILE:LINE — Issue description (Source: reviewer/sentinel/simplifier)
   Fix: remediation steps
   ...
   ```
7. Ask: "Ready to `/magician:absorb` these findings, or are there any you want to discuss first?" **End your turn. Wait for their reply before closing.**

## Agent Prompt Template

You are the <role> agent reviewing a code change.

Files changed:
<list of changed files with contents>

Agent role definition:
<contents of agents/<role>.md>

Review all changed files against your checklist. Output findings in the specified format.

## Completion Signal

"Scrutiny complete. N total findings (C critical, H high, M medium, L low). Run /absorb to integrate."
