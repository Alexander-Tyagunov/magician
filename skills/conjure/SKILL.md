---
name: conjure
description: Structured design dialogue — produces an approved spec before any implementation begins
keep-coding-instructions: true
---

# /conjure — Design Dialogue

Run a structured design dialogue before writing any code. Produce an approved spec.

<HARD-GATE>
Do NOT write any code, scaffold any project, or take any implementation action until the user has approved the spec. This applies regardless of perceived simplicity.
</HARD-GATE>

## Process

1. **Explore context** — read relevant files, recent git log, existing specs in `.workspace/shared/specs/`
2. **Understand the inspector** — note detected stack and archetype from session additionalContext
3. **Ask clarifying questions** — one at a time. Focus on: purpose, constraints, success criteria, edge cases
   - Skip stack questions the inspector already answered
   - Use multiple choice when possible
4. **Propose 2–3 approaches** — with tradeoffs and your recommendation
5. **Present design** — architecture, components, data flow, error handling, testing strategy
6. **Get user approval** — ask explicitly. Do not proceed until the user says yes.
7. **Write spec** — save to `.workspace/shared/specs/YYYY-MM-DD-<feature>.md`
8. **Commit** — `git add .workspace/shared/specs/ && git commit -m "docs: add spec for <feature>"`

## Design Principles

- Each unit has one responsibility and a clear interface
- Prefer smaller focused files over large ones that do too much
- YAGNI: no features the user did not request
- Design for testability: every component independently verifiable

## Spec File Format

```markdown
# <Feature> Spec

**Goal:** <one sentence>
**Archetype:** <from inspector>
**Stack:** <from inspector>

## Requirements
- <requirement 1>
- <requirement 2>

## Architecture
<2-3 paragraphs>

## Components
- `path/to/file.ts` — responsibility

## Error Handling
<approach>

## Testing Strategy
<approach>
```

## After Approval

Say: "Spec approved. Run /blueprint to create the implementation plan."
