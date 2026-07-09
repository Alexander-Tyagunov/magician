# Engineering principles /transmute is built on

These are the load-bearing principles behind this skill, grounded in **official guidance** — not
personal opinion. Cited to the source docs; read them if a trade-off is unclear.

Sources:
- *Building effective agents* — https://www.anthropic.com/engineering/building-effective-agents
- *Effective context engineering for AI agents* — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- *Claude Code best practices* — https://code.claude.com/docs/en/best-practices
- Claude Code docs (subagents, workflows) — https://code.claude.com/docs
- In-repo: [lore/autonomy.md](../../../lore/autonomy.md), [lore/subagent-context.md](../../../lore/subagent-context.md), [lore/tdd.md](../../../lore/tdd.md), [lore/models.md](../../../lore/models.md)

---

## 1. No context loss on handoff — the rule that matters most

Every time work crosses a boundary — to a subagent, a pipeline stage, a spawned Workflow, the next
skill — the receiver gets a **complete, self-contained brief plus artifact paths**, and it **never
re-derives what an upstream stage already established.** A lower level must never re-comprehend the
feature, re-fingerprint the vendor, re-run a capture, re-read a whole file the parent already
distilled, or re-discover a decision already made. Upstream distills; downstream consumes.

Mechanics (enforced throughout the skill):
- **Artifacts are the shared memory.** The dossier, parity contract, and golden fixtures live in
  `.workspace/shared/research/`; every handoff passes the **path**, not a dump.
- **Self-contained prompts.** Each subagent/stage prompt carries Goal · Scope · Inputs (paths) ·
  Constraints · Return format ([lore/subagent-context.md](../../../lore/subagent-context.md)) — it
  sees none of the parent conversation and needs none.
- **Distilled returns.** Workers return ~1–2k-token summaries + paths, not raw output, so the parent
  (and the next stage) integrate without re-reading.
- **A running capsule.** `.workspace/local/session-state.md` (goal · mode · tier · done/remaining ·
  decisions · artifact paths) is refreshed each phase, so a mid-run compaction loses nothing and no
  stage restarts from zero.

This is context engineering applied to *hand-offs*: give the next actor exactly the high-signal state
it needs, once, so nobody pays to rebuild it. The self-contained stage/subagent contract is mandated
in-repo by [lore/subagent-context.md](../../../lore/subagent-context.md); the distilled-return and
external-memory mechanics follow *Effective context engineering for AI agents* and the Claude Code
subagent docs.

## 2. Context engineering, not prompt stuffing

Treat the context window as a finite, high-value budget. Give each stage the **smallest set of
high-signal tokens** that lets it act; retrieve **just-in-time** (kg ranked `file:line`, not
whole-file reads or blind greps); push durable state **out** to artifacts rather than carrying it
in-context. More tokens ≠ better; signal-to-noise is what matters (*Effective context engineering*).

## 3. Use the simplest pattern that works

Prefer a single well-scoped call; add orchestration only when it earns its keep. `/transmute` maps
each Anthropic agent pattern to where it genuinely fits (*Building effective agents*):
- **Routing** → GATE 0 mode selection.
- **Prompt-chaining with gates** → the phase pipeline (each gate ends the turn).
- **Parallelization / sectioning** → the Phase-A comprehension fan-out (Tier A/B only).
- **Orchestrator-workers** → `/weave` delivery.
- **Evaluator-optimizer** → the parity loop and the review/remediate loop.

Don't fan out when a sequential single context is cheaper and loses nothing (small features).

## 4. Keep a human on the autonomy slider

Autonomy is a dial, not a switch. Gate every consequential decision through **AskUserQuestion**,
keep steps small and reversible, and never take an outward-facing/irreversible action (push, PR,
ticket-create, destructive git, form submit) without explicit confirmation. Dial autonomy up only
where verification is cheap and rollback is real (*Claude Code best practices*).

## 5. Verify, don't trust

The model is a fallible generator. Every Critical/High finding is **adversarially refuted** before it
counts; parity is **proven** against golden behavior, not asserted; black-box findings carry a
confidence tag and are confirmed with the user; the gateway checklist gates "done"
(*Building effective agents* — evaluator-optimizer; *Claude Code best practices* — verification).

## 6. Ground the model in truth

Retrieve targeted evidence instead of guessing: `kg` for the codebase, docs/context7 for external
contracts, the live app for actual behavior. Every claim is traceable to a source (the dossier's
`[S:]` tags) (*Effective context engineering for AI agents* — just-in-time retrieval of targeted
evidence; *Claude Code best practices* — give specific context / point to sources).

## 7. Tight tools + test-first

A small, well-described tool surface and TDD per unit so behavior is **proven as it's built**, not
after (*Claude Code best practices*; [lore/tdd.md](../../../lore/tdd.md)). Prefer the latest
code-optimal model at appropriate effort ([lore/models.md](../../../lore/models.md)).

---

**If in doubt, optimize for two things at once:** the *least* context that carries the *most* signal,
and *zero* rework at any lower level. Everything else in this skill serves those two.
