---
name: weave
description: Compose and run a large delivery as ONE pipeline with magician's guardrails — for big multi-item work ("implement these N stories/tickets", "deliver the epic", "migrate X across the codebase", batch/sweep). Adaptive structure, but always TDD per unit, kg grounding, certify, multi-lens review + adversarial verify, write gates, no context loss. Use instead of hand-rolling many agents.
---

# $weave — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/weave/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and non-negotiables.

Codex equivalents:
- **Engine** — if agent tools are available, compose the delivery per `../../../skills/weave/references/template.md`: sequential TDD per unit → `$certify` → parallel multi-lens review → adversarially refute every Critical/High → consolidate. Use generic agents with self-contained role prompts; `reviewer`, `security`, `simplification`, and `verification` are responsibilities, not `magician:*` profiles. Otherwise execute the same stages locally.
- **Grounding** — `kg check`/`kg init`, then `kg query`/`kg blast` to scope each unit; pass `file:line` pointers into worker prompts, never whole files.
- **Write gates** — implement + test on a branch; never push, open/merge PRs, or do anything destructive without explicit approval. A unit commit requires authorization and must stage only enumerated task-owned files.
- **No context loss** — every worker prompt self-contained (Goal/Scope/Inputs/Constraints/Return); workers return distilled summaries.
- **Plan gate** — show units + structure + rough scale and get approval before running a large pipeline (use Codex's question/approval UI).
