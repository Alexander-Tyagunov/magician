# Jira authoring — formatting & templates

Loaded on demand from [SKILL.md](SKILL.md). How to write well-formed issues and comments, and the body format per deployment.

## Body format

- **Server / Data Center (REST v2)** — bodies are **Jira wiki markup** strings. Write Markdown, then convert the few tokens wiki needs (below), or write wiki directly.
- **Cloud (REST v3)** — bodies are **ADF** (JSON document). For prose, build a `doc` with `paragraph`/`heading`/`bulletList` nodes, or convert Markdown → ADF.

## Wiki markup quick reference (Server/DC)
- Headings `h1.`…`h6.`; `*bold*`; `_italic_`; `{{monospace}}`; `-strike-`
- Code `{code:java}…{code}` · plain `{noformat}…{noformat}` · quote `{quote}…{quote}`
- Panel `{panel:title=Note}…{panel}` · color `{color:#de350b}text{color}`
- Tables: header `||A||B||` then `|a|b|` · lists `* bullet`, `# numbered`
- Mention `[~username]` · issue link `[KEY-123]` · external `[text|https://…]`

Jira's macro set is smaller than Confluence's — no built-in info/note/warning in descriptions; use `{panel}`/`{color}`. `{toc}`/`{expand}` exist only if a plugin provides them.

## Creating good issues (INVEST + testable AC/DoD)

A good story is clear, concise, and testable:
- **Summary** — specific, action-oriented; no vague verbs.
- **User Story** — _As_ a `<role>`, _I want_ `<capability>`, _so that_ `<benefit>`.
- **Context & Inputs** — the facts an implementer needs (refs, inputs, outputs) so nothing is guessed.
- **Acceptance Criteria** — Gherkin scenarios, each independently testable.
- **Definition of Done** — measurable exit criteria (tests passing, coverage, edge cases, docs).
- **Dependencies** — `Depends on: <KEY>`.
- **INVEST** — Independent, Negotiable, Valuable, Estimable, Small, Testable. If you can't write the AC, the story isn't ready — clarify first (and use `/magic` if it needs research).

## Acceptance criteria — Gherkin

Wrap scenarios in a `{code}` block so Jira renders them cleanly:
```
{code}
Scenario: <case>
  Given <precondition>
  When <action>
  Then <expected outcome>
  And <additional assertion>

Scenario Outline: <table-driven case>
  Given <input> of <value>
  Then <result>
  Examples: | value | result |  | a | x |  | b | y |
{code}
```

## Templates

**Bug** (Markdown → wiki):
```markdown
## Summary
One-line statement of the defect.
## Environment
- Service / app · Env
## Steps to reproduce
1. … 2. …
## Expected
## Actual
## Acceptance criteria
- [ ] …
```

**Story:**
```markdown
## User Story
_As_ a <role>, _I want_ <capability>, _so that_ <benefit>.
## Context & Inputs
- <facts, refs, inputs/outputs>
## Acceptance Criteria
<Gherkin scenarios inside a {code} block>
## Definition of Done
- Every scenario covered by automated tests; <coverage target>.
- <other measurable exit criteria>.
## Engineering Notes
- <files/classes touched>. Depends on: <KEY>.
```

**Clarifying comment:** context line → precise question(s) → mention.

## Validations & gotchas

- **Required on create**: project key, summary, issue type. The issue type must exist in that project (Story/Task/Bug/Sub-task/Epic vary).
- **Status** is not a field edit — transition it (workflow-gated).
- **Priority schemes can differ by issue type** — if a value is rejected, re-check allowed values via `createmeta` and use the project's actual scheme. Cache the user's instance quirks in memory.
- **@mentions** need the username/accountId, not email.
- **Match the team's existing ticket style** — concise structured sections beat heavy macro use. Verify complex tables/macros rendered after a write.
