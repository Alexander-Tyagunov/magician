---
name: weave
description: Compose and run a large delivery as ONE pipeline with magician's guardrails — for big multi-item work ("implement these N stories/tickets", "deliver the epic", "migrate X across the codebase", batch/sweep). Adaptive structure, but always TDD per unit, kg grounding, certify, multi-lens review + adversarial verify, write gates, no context loss. Use instead of hand-rolling many agents.
---

# /weave — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../../skills/weave/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates and non-negotiables.

Codex equivalents:
- **Engine** — if a native workflow/orchestration primitive is available, compose the delivery as one pipeline per `../../../skills/weave/references/template.md`. Otherwise dispatch the same stages with Codex's agent/subtask mechanism: sequential TDD per unit (one commit each) → certify → parallel multi-lens review (`magician:reviewer`/`sentinel`/`simplifier`/`verifier`) → adversarially refute every Critical/High → consolidate.
- **Grounding** — `kg check`/`kg init`, then `kg query`/`kg blast` to scope each unit; pass `file:line` pointers into worker prompts, never whole files.
- **Write gates** — implement + test on a branch; never push, open/merge PRs, or do anything destructive without explicit approval. One commit per unit, surfaced.
- **No context loss** — every worker prompt self-contained (Goal/Scope/Inputs/Constraints/Return); workers return distilled summaries.
- **Plan gate** — show units + structure + rough scale and get approval before running a large pipeline (use Codex's question/approval UI).
