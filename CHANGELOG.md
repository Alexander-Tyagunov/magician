# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.3.1] — 2026-06-26

Performance & ergonomics for the Jira/Confluence CLIs.

### Added
- One-shot Jira commands that collapse common multi-step queries into a single call — no JQL to compose, fewer model→tool round-trips: `jira mine` (my open work), `jira sprint <boardId>` (active sprint **+** my not-done, resolved in one call instead of two), `jira comments <KEY>`, `jira board <name>`; plus `confluence children <id>`.

### Changed
- CLIs request gzip (`curl --compressed`) and minimal field sets, keeping responses and on-screen output compact. (`jira get` ≈ 5 lines; a sprint view ≈ 10.)

## [3.3.0] — 2026-06-26

`/jira` and `/confluence` now run through bundled CLIs — quieter, faster, less screen noise.

### Changed
- `/jira` and `/confluence` call a bundled **`jira` / `confluence` CLI** (`bin/`, on PATH when the plugin is enabled) instead of composing inline `curl`. Each operation is one clean word-command, so the skills pre-allow them via `allowed-tools: Bash(jira:*)` / `Bash(confluence:*)` — **no per-request permission prompts** (the previous inline `curl | python` was a *compound* command that Claude Code re-prompted on every distinct URL), far less screen space, and faster to compose. The CLI shells out to `curl`, so corporate/self-signed CA trust (system keychain) works where Python's `urllib` failed. Output is compact and formatted; raw REST stays reachable via `jira raw` / `confluence raw`. Setup verifies with `jira myself` / `confluence whoami`.

## [3.2.1] — 2026-06-26

Respect users who don't use an integration.

### Added
- **Integration opt-out memory** (`lore/integration-prefs.md`): when the user says they don't use Jira/Confluence (or declines setup with "don't ask again"), `/jira`, `/confluence`, `/magic`, and `/divine` stop *proactively* suggesting it — stored per-user in `integration-prefs.json`. A direct request later re-enables it. The auto-trigger hook also no longer nudges toward a service the user says they don't have ("I don't have jira" → no suggestion).

## [3.2.0] — 2026-06-26

Direct-HTTP **Jira & Confluence** skills (no MCP / no proxy) and the **`/divine`** code-review skill.

### Added
- `/jira` and `/confluence` — work with Jira and Confluence over their **REST APIs directly via HTTPS** (no MCP server, no LiteLLM/proxy — fully independent). Support Atlassian **Cloud** (Basic, email + API token) and **Server/Data Center** (Bearer PAT), auto-detected. First-run **setup** flow guides the user to create a token and save it to `~/.claude/settings.json` `env` (the assistant never handles the secret) and verifies connectivity. Jira: read/search (JQL), create/comment/@mention/transition/link/worklog, field discovery, bulk-write playbook, MR investigation, clone, INVEST + Gherkin AC/DoD authoring. Confluence: read/search (CQL), sections, create/update/comment/label, storage/wiki authoring. Both carry per-action write gates, treat ticket/page content as untrusted data, and keep user-specific boards/people/spaces/field-ids in on-demand per-user memory (not in the plugin). Auto-trigger wired into `scripts/pattern-detect.sh`; `/magic` and `/divine` use them for internal grounding (tickets/specs); Codex adapters included.
- `/divine` — standalone, research-grounded **code-review** skill. Auto-triggers on review intent ("review this PR/MR", "do a code review"). Establishes change context (GitHub PR / GitLab MR / branch / working tree, with intent from the PR description + linked tickets and CI/merge-gate status), gates **depth** via AskUserQuestion (Quick / Standard / Deep / Exhaustive), grounds via `/magic` when the change needs external/domain evidence, dispatches the four specialist agents in parallel under the subagent context contract, **adversarially verifies** Critical/High findings (and lists dropped false positives), and produces a severity-ranked report with impact + fix + requirement traceability. Can post the review back to the PR/MR with explicit confirmation. Depth spans a Quick simple-logic pass through an Exhaustive review that grounds in PRDs/docs/external+internal data and maps **blast radius** (affected downstream services & infrastructure). Can optionally **spin an agent to implement Critical/High fixes and commit/push** (gated), and runs **unattended via `/loop`** to monitor repos for new PRs/MRs (idempotent by head SHA, review-only). Fully stack- and company-agnostic. Complements the pipeline-internal `/scrutinize`. Auto-trigger wired into `scripts/pattern-detect.sh`; Codex adapter included.

## [3.1.0] — 2026-06-25

Modernization for the 2026 Claude Code era (skills/agents best practices, model/effort currency, cross-session memory, and the multiplayer/agent-teams workflow). **Breaking:** three skills were merged away.

### Breaking
- Merged 21 → 18 skills:
  - `/absorb` → folded into `/scrutinize` (now reviews **and** remediates Critical/High findings).
  - `/forge` → folded into `/ward` (now also runs `/ward task <N>` to execute a single blueprint task end-to-end with TDD).
  - `/summon` → folded into `/orchestrate` (parallel fan-out is part of wave coordination).
- `/manifest` chain updated accordingly (… → orchestrate → certify → scrutinize → seal).

### Added
- `lore/models.md` — model & effort currency guidance: never hardcode versions; prefer the latest tier (Opus 4.8 daily, Fable 5 for code), scale `/effort` to task size, and suggest upgrading when the session is on an older model.
- `lore/subagent-context.md` — a self-contained **context contract** for every subagent spawn and skill handoff (subagents/teammates don't inherit conversation history), preventing context loss in parallel/async work.
- **Global reference memory** — `$CLAUDE_PLUGIN_DATA/references.md` (repos, projects, ideas) loaded into every session by the SessionStart hook and managed via `/chronicle` (`remember`/`references`/`forget`); saved only with user confirmation.
- `monitors/monitors.json` + `scripts/ci-watch.sh` — a background CI-red watcher that starts on first `/deploy` and degrades quietly when `gh`/remote are absent.
- Agent definitions (`reviewer`, `sentinel`, `simplifier`, `verifier`) now have `description` (enables auto-delegation and agent-team reuse), scoped `tools`, a `model` tier, and a context-completeness guard.
- `/magic` stays standalone but is now pipeline-integrated: research saves to a first-class `.workspace/shared/research/` artifact, and handoffs pass the artifact **path** into `/conjure`, `/blueprint`, and `/unravel`. Those skills (and `/manifest`'s design phase) read that directory and suggest `/magic` when a decision needs external evidence. `/almanac` now creates `research/` (and `plans/`).

### Changed
- Removed the undocumented/no-op `keep-coding-instructions` field from all skills and from `/inscribe`'s generated template + checklist.
- Added modern frontmatter across skills: `allowed-tools` (fewer auto-mode prompts), `disable-model-invocation` on standalone side-effecting skills only (never on in-chain pipeline stages), `argument-hint`, and `context: fork` for `/sentinel`.
- Split oversized skills via progressive disclosure: `/conjure` 874 → 198, `/magic` 738 → 221, `/almanac` 300 → 140 lines (reference material moved to `references/`).
- `/orchestrate` now dispatches concurrent subagents with self-contained prompts and is aware of native dynamic workflows, nested subagents, and agent teams.

### Fixed
- `/magic`: corrected MCP tool names `mcp__context7-global__*` → `mcp__context7__*` (calls previously failed).
- `/almanac`: workspace-strategy save now reflects the user's actual shared/private choice instead of hardcoding `mode='shared'`.
- `/scrutinize` and `/seal`: dispatch review agents via `Task` subagent types (`magician:reviewer|sentinel|simplifier`) instead of reading `agents/<role>.md` by a path that didn't resolve from the project directory.
- `/chronicle`: `clear N` now honors the user-supplied N instead of a hardcoded 30-day cutoff.
- Removed hardcoded `Claude Sonnet 4.6` commit trailers (now generic `Claude`).
- README: security section now credits the enforced `PreToolUse` guard (plugin `settings.json` permission rules are advisory, not enforced).

## [2.0.1] — 2026-05-03

### Fixed
- README: installation instructions corrected — `github:` shorthand does not resolve; correct flow is `/plugin marketplace add https://github.com/Alexander-Tyagunov/magician` then `/plugin install magician@magician-marketplace`
- README: wizard cat mascot reworked — replaced blank `o o` eyes and neutral whiskers with `^.^` happy expression and `~(u)~` smile; added curling tail (`/~`); redesigned to uniform 15-char line width so art centers correctly in GitHub view mode
- `.agents/plugins/marketplace.json`: fixed canonical Codex plugin marketplace path
- `.codex/INSTALL.md`: clarified Codex plugin enablement steps

## [2.0.0] — 2026-05-03

### Added
- Codex plugin support via `.codex-plugin/plugin.json`, including Codex marketplace metadata, capabilities, keywords, and default prompts.
- Codex marketplace catalog at `.agents/plugins/marketplace.json`, so `codex plugin marketplace add Alexander-Tyagunov/magician` can expose Magician in the Codex Plugins UI.
- 21 Codex adapter skills under `.codex-plugin/skills/`, one for each Magician source skill, so Codex can invoke the same SDLC workflows without changing Claude Code behavior.
- `.codex-plugin/references/codex-adapter.md`: shared Codex translation layer for Claude Code-specific tool names, approvals, subagents, browser automation, web access, file editing, MCP setup, and completion rules.
- `.codex/INSTALL.md`: standalone Codex installation, enablement, verification, update, uninstall, and design-capability notes.
- README installation instructions for both Claude Code and Codex, including the `magician@magician` enablement fallback for Codex.

### Changed
- Bumped plugin release metadata to `2.0.0`.
- Codex `/conjure` now documents feature parity with the existing Magician visual companion: local Node.js server, Browser Use navigation, click-event feedback, versioned mockups, and approved design artifacts.
- Codex design routing now treats Magician's built-in `/conjure` visual companion as the primary free/local path. Figma is optional and only for Figma-specific workflows; OpenAI Build Web Apps is an optional enhancement, not a dependency.

### Compatibility
- Claude Code remains on the existing `.claude-plugin/`, `hooks/`, `settings.json`, and source `skills/` path. The Codex adapter layer is isolated so Claude Code behavior is not changed by the Codex integration.

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
