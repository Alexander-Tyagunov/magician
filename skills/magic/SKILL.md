---
name: magic
description: Structured multi-source research (consulting, library docs, web) with guided output delivery. Use when asked to research, investigate, analyze, explore, examine, audit, or evaluate something.
allowed-tools: Read, Grep, Glob, Bash(ugrep *), Bash(bfs *), Bash(rg *), Bash(grep *), Bash(find *), AskUserQuestion, mcp__context7__resolve-library-id, mcp__context7__query-docs, Bash(kg check), Bash(kg query *), Bash(kg neighbors *), Bash(kg blast *), Edit(./.workspace/shared/research/**), Bash(git commit -m *)
argument-hint: "[topic or research question]"
---

# /magic — Research, Analysis & Consulting

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg` and give subagents that full path. If that is missing too (Claude chat ships no plugin tools), skip the `kg` steps and search the code directly.

Structured research and consulting over web search, document analysis and library documentation. Every decision point uses `AskUserQuestion`, so the user drives the process through the structured prompt UI. This file is the router. The procedure for each phase is in [`references/phases.md`](references/phases.md), the question blocks are in [`references/questions.md`](references/questions.md), and the next-step templates are in [`references/next-steps.md`](references/next-steps.md).

<HARD-GATE>
Put every consultation, clarification, and decision to the user through AskUserQuestion rather than plain prose, so they see the structured prompt UI. This applies to every gate in this skill.
</HARD-GATE>

## Completion Signal

Before the Completion Signal, grade the findings against [`references/rubric.md`](references/rubric.md); list unmet items.

"Magic complete. Researched <topic> across <N> sources. Findings <saved to .workspace/shared/research/… | delivered above>. Suggested next: <skill>."

## Obstacles

If this skill runs as a dispatched unit and hits something that blocks or degrades the work, do not wait for a human who is not there and do not silently ship a degraded result — return the Obstacles block from [lore/obstacles.md](../../lore/obstacles.md) (fields: STATUS, OBSTACLE, BLOCKER, SEVERITY, WORKAROUND, RECURRENCE, SCOPE, NEXT) to the caller alongside whatever you completed; interactively, say the same in prose.

## Autonomy — approve the plan, then run

Once the **Phase 0 scope/source/depth answers** are in, **Phase 1–2 execution runs to completion** without extra consultation questions: `Read`, context7 doc queries and `kg query`/`blast`/`neighbors` are pre-approved by this skill, and read-only git never prompts. **Web search and web fetches are not pre-approved** — they go through Claude Code's normal permission prompts (none in auto mode, or once the user approves them), and every query or URL leaves the machine, so keep private or proprietary details out of them. The skill's real side effects — the **Phase 4** save (pre-approved only inside `.workspace/shared/research/`) and `git add`/`git commit` — are already `AskUserQuestion`-gated. The interactive consultation gates (Phase 0 sources/depth, Phase 3 output/persistence, Phase 5 next steps) stay — magic is question-driven by design. Doctrine: [lore/autonomy.md](../../lore/autonomy.md).

## Standalone and pipeline use

`/magic` is a standalone skill. Run it any time to research, analyze or consult. It also plugs into the SDLC chain with no context loss:

- **Feeds the pipeline.** Inside a magician workspace (`.workspace/` present), saved research goes to `.workspace/shared/research/<topic>-<date>.md`, a first-class artifact like specs and plans. Phase 5 hands that path (not only a summary) to the next stage. A research artifact that describes a system or a flow carries a Mermaid block (the `architecture.mmd` convention: a component diagram for structure, a sequence diagram for a flow). An SVG is rendered next to it only when `mmdc` is on PATH. Convention: [conjure's `architecture.md`](../conjure/references/architecture.md).
- **Fed by the pipeline.** `/conjure`, `/blueprint`, `/unravel` and `/manifest` read `.workspace/shared/research/`. They suggest `/magic` when a decision needs external evidence.
- **Internal sources.** For the user's own Jira tickets, epics, boards or Confluence pages, use the `magician:jira` and `magician:confluence` skills (bundled CLIs, with a guided setup when not configured) rather than web search. If the user prefers another installed Jira or Confluence integration, use that. Fold what they return into the findings like any other source. Skip a source the user opted out of ([`lore/integration-prefs.md`](../../lore/integration-prefs.md)) and do not suggest setting it up.
- **The codebase itself.** When the question is about the user's own repo, query the knowledge graph first: `kg check`, then `kg query "<topic>"`, with `kg neighbors` and `kg blast` for relationships. `Read` the ranked `file:line` ranges it returns rather than broad greps. If there is no index, fall back to grep and Read and offer once to build one (`kg init`, run only on the user's yes). The offer is opt-out aware ([`lore/integration-prefs.md`](../../lore/integration-prefs.md), key `knowledge-graph`). Details: [knowledge-graph skill](../knowledge-graph/references/retrieval.md).

## When it is suggested

Magician's `UserPromptSubmit` hook may add a note that this skill covers research and analysis when a prompt contains research-intent words (for example research, investigate, analyze, explore, examine, assess, evaluate, discover, audit, study, survey, probe, benchmark). The note is a suggestion, not an instruction. Use this skill only when the request really is research. When you start it from such a note, say so before any other action:

> "Starting /magic for structured research. Let me gather a few inputs before diving in."

## Phases

Read the matching section of [`references/phases.md`](references/phases.md) when you enter a phase.

**Phase 0 — Scope and sources.** Classify the request from the message alone (academic, software library, financial, document analysis, general). Then run one batched AskUserQuestion with both the source selection and the research depth. The depth maps onto reasoning effort: quick ≈ low, standard ≈ medium, deep ≈ high ([`lore/models.md`](../../lore/models.md)).

**Phase 1 — Tool availability.** Check context7 only for a genuine library question the user routed to it. When context7 is absent, deliver the install question and continue without it. Collect document paths when the user chose local files.

**Phase 2 — Research execution.** Run the selected sources in parallel. Web search uses 2–4 targeted queries built from the public topic only, with academic-targeted prefixes for scientific work. context7 queries use the public library name. Local documents go through Read with type-specific extraction. The phase ends with a synthesis of consensus, contradictions, key facts and recommendations.

**Phase 3 — Output format.** Two AskUserQuestion gates. The first is the output format (academic variants carry a citation-style follow-up, and "Visual design via /conjure" hands off and returns). The second is the persistence decision, with `.workspace/shared/research/<topic>-<date>.md` as the default inside a workspace.

**Phase 4 — Deliver and persist.** Present the findings with source attribution, file references, headings and a conclusion. Offer an Artifact only on request and keep public links free of confidential material. Save with Write (pre-approved under `.workspace/shared/research/`), then commit through the commit-message question.

**Phase 5 — Navigate and suggest.** Classify the result and pick the 2 most relevant next skills, plus "Dig deeper" and "Done". Deliver the matching template from [`references/next-steps.md`](references/next-steps.md). Hand off with the artifact path and a 2–3 sentence summary ([`lore/subagent-context.md`](../../lore/subagent-context.md)). On "Done", close with one sentence and a warm sign-off.
