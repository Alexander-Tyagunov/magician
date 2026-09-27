---
name: magic
description: Use when the user asks to research, investigate, analyze, find out, explore, examine, audit, or evaluate something — structured multi-source research with consulting, library-doc search, web search, and guided output delivery.
---

# $magic — Codex Adapter

Read `../../references/codex-adapter.md`, then read `../../source-skills/magic/SKILL.md` and follow the source skill through that Codex adapter. Keep the source skill's gates, safety checks, and completion criteria.

Feature-detect every research capability. Use official documentation tools or primary-source web browsing when available; use Context7 only when installed. For codebase grounding invoke the absolute `<plugin-root>/bin/kg` path with the Codex `MAGICIAN_HOME` defined by the shared adapter. Translate consultant/researcher Claude profiles into generic self-contained agent prompts, or research locally when agent tools are unavailable.
