---
name: conjure
description: Structured design dialogue with a visual companion — produces an approved spec and design artifacts before implementation. Use at the start of a feature, before writing code.
allowed-tools: Read, Grep, Glob, AskUserQuestion, Edit(./.workspace/shared/**), Edit(./.workspace/local/designs/**), Edit(./.workspace/local/mockups/**), Bash(${CLAUDE_SKILL_DIR}/scripts/vc-start.sh *), Bash(${CLAUDE_SKILL_DIR}/scripts/vc-stop.sh *), Bash(git commit -m *), Bash(kg query *), mcp__playwright__browser_take_screenshot, mcp__playwright__browser_snapshot, mcp__playwright__browser_wait_for, mcp__playwright__browser_close
argument-hint: "[feature or what you want to design]"
---

# /conjure — Design Dialogue

> **Bundled command:** if `kg` is not found, run it as `${CLAUDE_PLUGIN_ROOT}/tools/kg`; if that is missing too, skip the `kg` steps and search the code directly.

Run a structured design dialogue before writing any code, and produce an approved spec and design artifacts. In every mode, the approaches, architecture and directions are written as Mermaid + HTML under `<design-dir>` (`.workspace/shared/designs/`, or `.workspace/shared/mockups/` in Design-Only mode), so they outlive the surface that showed them.

<HARD-GATE>
Do NOT write any code, scaffold any project, or take any implementation action until the user has approved the spec. This applies regardless of perceived simplicity.
</HARD-GATE>

## Process — Gated Dialogue

**Core rule: each gate is one turn. End your turn after each gate. Do NOT advance until the user replies. Never collapse two gates into one message.** Order: Explore → Clarify → GATE 0 → 1 → 2 → 3 (UI only) → 3.5 or 4 → commit. Read a gate's reference when you reach it.

**Autonomy:** the GATEs (0–4) and the final commit are the only pauses. Around them, exploration runs autonomously: Read/Grep/Glob, `kg query` and read-only git need no confirmation; a read is never a gate. Re-gate only on real side effects: writing specs/tokens/mockups and `git add`/`commit`. Commands this skill does not pre-approve (`openssl rand`, `command -v mmdc`, `node`, the browser opener, WebFetch) prompt as usual. See [lore/autonomy.md](../../lore/autonomy.md).

## Completion Signal

Before the Completion Signal, grade the spec against [references/rubric.md](references/rubric.md); list unmet items.

"Conjure complete. Spec for <feature> approved and committed to .workspace/shared/specs/ (or, in Design-Only mode, mockups saved to .workspace/shared/mockups/). Screens: <design-dir>/screens/v<n>/; screenshots: <PNG paths per capture.md, or 'none'>. Run /magician:blueprint to create the implementation plan."

## References (read on demand)

- GATE 0 menu, mode → surface map, paths, live loop: [references/design-mode.md](references/design-mode.md)
- Explore, Clarify, GATE 1–2 procedures: [references/gates.md](references/gates.md)
- Architecture as code (`.mmd` + HTML): [references/architecture.md](references/architecture.md)
- GATE 3 steps 0–5 (UI design, `/design-sync`): [references/ui-design.md](references/ui-design.md)
- Design tokens, variation, light/dark, responsive: [references/design-tokens.md](references/design-tokens.md)
- Design principles and platform guidelines: [references/design-principles.md](references/design-principles.md)
- Brand book template: [references/brand-book.md](references/brand-book.md)
- Companion server, screen templates (surface B): [references/visual-companion.md](references/visual-companion.md)
- Screenshots as evidence (capture, diff v<n> vs v<n+1>): [references/capture.md](references/capture.md)
- GATE 3.5, GATE 4, commit, sharing: [references/after-approval.md](references/after-approval.md); spec file format: [references/spec-format.md](references/spec-format.md)

## Steps 1–2 — Explore, Clarify

Read the code, git log, prior specs and research silently, plus `.workspace/shared/north-star.md` when it exists; then ask one clarifying question per turn until purpose, constraints, success criteria and edge cases are clear (details in gates.md).

## GATE 0 — Design Mode

Call `AskUserQuestion` with exactly the four options in [references/design-mode.md](references/design-mode.md): **Visual + Strict**, **Visual + Reference**, **Text only**, **Design Only (Visual)**. End your turn. Visual options use one of two surfaces: **(A) `/design` artboards** — Claude Code's bundled `/design` skill, a research preview (v2.1.234+, Pro/Max/Team/Enterprise), used when the session has the Artifact tool (detect by tool presence); **(B) the local companion** — `${CLAUDE_SKILL_DIR}/scripts/vc-start.sh`, works offline and in CI, the documented fallback. When both are available ask once "artboards or local companion?"; when one is, use it and say so; when neither is, continue as **(C) text**. Design Only is a flag on A or B (no spec). **Do not propose approaches until the user picks a mode.** "Skip" switches to text and stops the companion.

## GATE 1 — Approach Selection

Present 2–3 approaches: write `<design-dir>/screens/v1/approaches.html` in every mode, then show it on the chosen surface or describe it and ask with `AskUserQuestion`. End your turn. **Do not present architecture until the user confirms an approach** ([references/gates.md](references/gates.md)). On the choice, record it in `.workspace/shared/decisions/` (format in gates.md).

## GATE 2 — Architecture Review

For the chosen approach only: write `architecture.mmd` (C4-style component diagram + a sequence diagram of the main flow), render `architecture.svg` only when `mmdc` is already on PATH (never install it), embed it in `architecture.html` (else a pre-rendered box diagram, no CDN), then show or describe it and ask **Approve / Request changes**. End your turn; advance only on explicit approval ([references/architecture.md](references/architecture.md)).

## GATE 3 — UI Design (skip if no UI involved)

A design system, not a one-off mockup: read [references/design-tokens.md](references/design-tokens.md), then follow [references/ui-design.md](references/ui-design.md) step by step. **Step 0 is mandatory:** ground in the current design (`brand.md`, `design-tokens.css`, the app's styles and components; it is the constraint unless the user asked for a rework or the app is greenfield) and in the platform guidelines ([lore/deep/design-principles.md](../../lore/deep/design-principles.md)). Step 1: three directions inside those constraints. Steps 2–4: viewports; emit `design-tokens.css` + `brand.md`; ONE mockup (light+dark, responsive) after the [review checklist](../../lore/deep/design-principles.md#review-checklist), captured when approved ([references/capture.md](references/capture.md)). Step 5: offer `/design-sync` once; never auto-run it.

## GATE 3.5 — Design-Only Close (`DESIGN_ONLY` only)

Write `<design-dir>/design-notes.md`, stop the companion (`${CLAUDE_SKILL_DIR}/scripts/vc-stop.sh <design-dir>`), say how to reopen the mockup. No spec, no plan (after-approval.md).

## GATE 4 — Spec Approval, then commit

Write `.workspace/shared/specs/YYYY-MM-DD-<feature>.md` (format: spec-format.md), ask *"Spec ready — lock it in?"* (**Approve / Request changes**), end your turn. On approval: `git add` the spec (asks), `git commit -m "docs: add spec for <feature>"`, stop the companion, point to `/magician:blueprint` ([references/after-approval.md](references/after-approval.md)).

**Design principles:** one responsibility per unit, clear interfaces, small files, YAGNI, testable components.

## Obstacles

A human-in-the-loop dialogue — every gate needs the user — so it reports to the human directly, not upward to an orchestrator, and emits no upward Obstacles block: say any blocker (the companion, `/design` or Playwright not starting, unreadable brand assets, a missing input) in prose and stop. See [lore/obstacles.md](../../lore/obstacles.md).
