# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] — 2026-05-03

### Fixed
- `scripts/pattern-detect.sh`: replaced invalid `{"decision":"suggest"}` and `{"decision":"ask"}` hook JSON with correct `{"additionalContext":"..."}` format — fixes /magic auto-invoke and pattern suggestion delivery
- `scripts/format.sh`: fixed hook input extraction to use `tool_input` key (consistent with other scripts)
- `skills/seal/SKILL.md`: fixed step numbering after docs update insertion (was duplicate step 5)
- `skills/summon/SKILL.md`: added missing `/magic` to the skill registry injected into every subagent

### Added
- `skills/conjure/SKILL.md`: design personality commitment gate before any CSS — forces a named aesthetic direction (editorial, brutalist, luxury, retro-futuristic, etc.); explicitly bans default AI aesthetics (Inter, purple gradients, generic card layouts); alternates light/dark base; brand book now captures personality + motion + spatial character, not just hex values

## [1.2.0] — 2026-05-03

### Fixed
- `marketplace.json`: renamed top-level `name` from `"magician-marketplace"` to `"magician"` to match the expected URL slug at `claude.com/plugins/magician`
- `marketplace.json`: moved `description` out of non-standard `metadata` wrapper to root level per official schema
- `marketplace.json`: replaced github-ref source with `"./"` self-reference (matches the pattern used by officially published plugins)
- `marketplace.json`: removed redundant `homepage`, `repository`, `license`, `keywords`, and `category` from plugin entry — not present in reference implementations
- `scripts/access-tracker.sh`: removed invalid `{"decision":"ask"}` JSON hook output that caused `Hook JSON output validation failed`; now emits plain text which the harness injects as context
- `/portal`: accepts feature name via `$ARGUMENTS` so `/manifest` can pass it directly without re-prompting the user
- `/manifest`: worktree creation is now a user gate (GATE 3.5) with an explicit branch name proposal; added `Autonomous Continuation` rule so manifest drives through blueprint → orchestrate without stopping
- `/certify`: UI projects now auto-open the browser after starting the dev server
- `/seal`: added docs update step (CLAUDE.md + README) before commit
- `/conjure`: creates `.workspace/shared/brand.md` before the first UI mockup if absent; all subsequent mockups reference it for visual consistency

### Added
- Agent color identifiers: reviewer (orange), sentinel (red), simplifier (cyan), verifier (green) — visible in the Claude Code UI when agents are working

### Changed
- README installation simplified to single command: `/plugin install github:Alexander-Tyagunov/magician`

## [1.1.1] — 2026-04-21

### Fixed
- README.md: added missing `/magic` skill to the skills table
- README.md: updated version badge from 1.0.0 to 1.1.1

## [1.1.0] — 2026-04-21

### Added
- `/magic` skill — structured research, analysis, and consulting with AskUserQuestion-driven gates
  - Web search via WebSearch tool
  - Library documentation search via context7 MCP (auto-detects if missing, offers install)
  - Local document analysis (financial reports, PDFs, text files)
  - Multi-phase workflow: scope → sources → research → output format → persistence
  - Every decision gate uses AskUserQuestion for explicit action-reaction UI
  - Clear separation between Tech Library Docs (context7, for software/framework questions only)
    and Document/File analysis (Read tool, for Excel/PDF/reports/articles — no MCP needed)
  - context7 guarded by topic classification: only invoked for genuine software library questions
  - Academic/scientific research support: targets Google Scholar, arXiv, PubMed, IEEE, ACM;
    citation-aware output formats (literature review, annotated bibliography, research outline);
    citation style selection (APA, MLA, IEEE, Harvard, Chicago); academic Phase 5 navigation
  - Context-aware skill navigation (Phase 5): after delivering findings, intelligently proposes
    relevant next magician skills (/conjure, /blueprint, /unravel, /sentinel, /accelerate)
    based on research type — with a warm graceful exit when the user is done
  - Auto-invokes /conjure when visual output is requested
  - Save and git-commit output from within the skill
- Keyword auto-invoke via `pattern-detect.sh` — triggers /magic on research-intent terms:
  research, investigate, analyze, explore, examine, assess, evaluate, discover, audit, study, and more

## [1.0.0] — 2026-04-17

### Added
- Plugin manifest and marketplace catalog for one-command installation
- Dynamic project inspector — detects stack automatically, no manual pack selection
- Lore system — modular tech-specific knowledge assembled per session
- 20 skills: conjure, blueprint, forge, ward, unravel, certify, summon, orchestrate,
  scrutinize, absorb, portal, seal, almanac, chronicle, sentinel, accelerate, deploy,
  inscribe, manifest, autopsy
- 4 specialist agents: reviewer, simplifier, verifier, sentinel
- Full hook system: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
  PreCompact, Stop, SubagentStart, SubagentStop, WorktreeCreate
- Pattern recognition — tracks repeated prompts, offers skill creation at threshold
- Self-learning via chronicle — session summaries persist across plugin updates
- Team workspace — .workspace/shared/ committed, .workspace/local/ always gitignored
- Security as infrastructure — hard deny rules in settings.json + PreToolUse guard
- Wizard cat ASCII art on every session start
- GitHub Sponsors support
- magician-scan standalone security CLI for CI integration
