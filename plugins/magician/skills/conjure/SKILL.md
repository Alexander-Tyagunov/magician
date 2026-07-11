---
name: conjure
description: Structured design dialogue with a visual companion — produces an approved spec and design artifacts before any implementation begins. Use at the start of a feature, before writing code.
---

# $conjure — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/conjure/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

For visual modes, apply the adapter's "Magician Visual Companion in Codex" section exactly: use Magician's built-in local companion as the primary design surface, open it with Codex Browser Use, and keep Figma or Build Web Apps optional unless the user explicitly asks for them.

**v3.8.0 — two-way design studio:** designs use the two-tier token system ([design-tokens.md](../../source-skills/conjure/references/design-tokens.md)) so light/dark are ONE design and each run varies; GATE 3 asks target viewports. The browser streams clicks/selections + optional (opt-in) companion-chat to `state/events.jsonl` (read by cursor via the `events.json` endpoint); reply via `state/outbox.jsonl`. Use Browser Use for the pull path (read the live selection).
