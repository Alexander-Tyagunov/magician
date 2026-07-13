# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.9.3] — 2026-07-13

**Artifacts: shareable, multiplayer — and gated.** Claude Code Artifacts now support public link-sharing and team multiplayer co-editing (and can be created from Claude Tag). Magician already offered Artifacts in `/conjure` and `/divine`; this teaches the report-producing skills to use the new capability and — critically — adds a safety gate, since publishing a design, a code review, or a post-mortem to a public link can expose proprietary or sensitive detail. Docs only; no runtime/hook/CLI change.

### Changed
- **`/conjure` + `/divine` — updated Artifacts guidance + public-share gate.** Both now note the artifact can be **team co-edited** (multiplayer, Team/Enterprise), and both add a hard gate: publishing to a **public** link (anyone with the URL can view) is an outward, permission-changing action — confirm explicitly, keep artifacts account-private by default, and never expose secrets, proprietary/internal code, or (for `/divine`) unremediated vulnerability detail to a public link.
- **Extended the shareable-Artifact pointer to the other report-producing skills** — `/scrutinize` (scrutiny report), `/autopsy` (post-mortem), `/magic` (research findings), `/accelerate` (perf report) — each with the same "offer, don't auto-create" rule and the same public-share gate.
- **`lore/subagent-context.md` — Artifacts currency note.** Records the capability (public share + multiplayer + Claude-Tag creation), explicitly disambiguated from `.workspace/` artifacts, with the public-publish-is-outward gate that the skills above follow.

### Notes
- The plugin can only *wield* Artifacts (Claude Code owns the feature); this release makes its skills use them well and safely. Public publishing stays behind explicit confirmation and defaults to account-private. Source: @ClaudeDevs (2026-07-13). Restart Claude Code to pick up the refreshed guidance.

## [4.9.2] — 2026-07-13

**Doctrine: rigor that doesn't drift with model or language.** A docs-only patch grounded in Anthropic's research on how Claude's expressed values vary across models & languages — the values a model shows (caution, rigor, candor, thoroughness) shift with the model version and the *language of the conversation* in ways not deliberately chosen. For a verification-first plugin that's a risk to guard, not ignore. No runtime, hook, or CLI changes.

### Changed
- **`lore/verification.md` — language-invariant rigor.** Added a rule that the verification bar does not bend to the conversation's language: the research finds the same request draws more rigor in some languages (English, Russian) and more warmth/accommodation in others. So a review, a security pass, a "is it really done?" check, and the willingness to push back must be **equally hard in every language** — match the user's language for *tone*, never for *standards* (same evidence gate, same pushback, same honest flagging of uncertainty). This is re-injected post-compaction with the rest of the core doctrine.
- **`lore/models.md` — choose models for behavior, not just capability.** Added a "value profile" note: model *version* shifts expressed values, not only correctness — newer frontier models tend to push back and flag risks more, lighter/older tiers lean warmer and briefer. So critique/review/security/debugging (`/divine`, `/scrutinize`, `/sentinel`, `/unravel`) prefer the more cautious+candid top tier, and skill posture should be **re-verified after a model bump**. Deliberately keeps the principle without hardcoding the research's per-version numbers (they go stale).

### Notes
- Grounded in `anthropic.com/research/claude-values-models-languages`. No individuals named; no per-version metrics baked in (only the durable principle). Docs only — restart Claude Code to pick up the refreshed doctrine at session start.

## [4.9.1] — 2026-07-12

**Codex progressive project-lore routing + voice-chip polish.** A patch release: Codex gains an on-demand stack-lore router mirroring the Claude SessionStart lore behavior, and the voice status-line chip renders its glyph correctly. No change to Claude Code's runtime, hooks, or skills.

### Added
- **Codex-only `$project-context` lore router** — a read-only, standard-library stack detector now selects concise language/database/observability cores and ranks at most eight task-matched deep dives from the packaged lore. It honors `MAGICIAN_LORE` and `.magician/lore.off`, emits no manifest or environment values, makes no network calls or state writes, and does not modify or emulate Claude Code's SessionStart hook.

### Fixed
- **Voice status-line glyph** — the `🗣️ voice:` chip now renders with the emoji presentation selector (U+FE0F) so the icon shows at full width with its trailing space, matching the `📚 lore` / `🧠 effort` chips (previously `🗣` fell back to text presentation and collapsed against the label).

## [4.9.0] — 2026-07-12

**Tunable output brevity — lower token cost, no quality loss.** Output tokens cost several times more than input on every current model, so the cheapest saving on a coding-agent bill is simply emitting fewer of them. Magician now injects an output-brevity **voice** at session start — a style directive that trims filler while preserving every fact — with three levels and a leaner-than-default setting out of the box.

### Added
- **`voice` setting** — `magician-ui voice warrior|scribe|bard` (and `voice status`). Three levels, least → most wordy: **`warrior`** (minimal but complete — the shortest fully-correct answer, no preamble/examples/recaps), **`scribe`** (the default — leaner than usual; necessary explanation only), **`bard`** (standard/native verbosity, nothing injected). Resolution (first match wins): env `MAGICIAN_VOICE` → per-project `.magician/voice` → global `cli-ui.json` → default `scribe`.
- **No-quality-loss directive** — for warrior/scribe, SessionStart injects a brevity directive that shortens by *cutting filler, not facts*: it drops preambles, postambles, restatements of the request, and recaps of work just done, and leads with the outcome — while keeping **all** substance and all code, commands, file paths, identifiers, numbers, and error text **verbatim**. It explicitly forbids compressing prose into fragments, telegraphese, arrow-chains, abbreviations, or jargon (readability over raw length), and never touches code, tests, diffs, or the actual work.
- **`🗣 voice:` status-bar chip** — shows the active level live (warrior/scribe/bard), rendered locally at zero token cost; toggle its visibility with `magician-ui set …,voice`.

### Notes
- Auto-injection is a Claude Code SessionStart behavior (as with bundled lore); the `magician-ui voice` command and stored setting work everywhere. Takes effect at the next session start.
- Default is `scribe` (leaner than standard), so sessions save output tokens from the first message. Set `bard` for the previous, fully-native verbosity.

## [4.8.1] — 2026-07-12

**Hook performance — fewer Python cold-starts per turn, zero behavior change.** A profiling pass found the plugin's latency was dominated by Python process spawns (~26–52ms each): SessionStart spawned Python ~11 times, and every Bash tool call fired three separate hooks (two spawning Python). None of it was broken — just spawn-heavy. This release cuts the spawn count on the hot paths; every change is verified equivalent to the prior behavior.

### Performance
- **SessionStart ~644ms → ~412ms (measured, this repo).** One Python pass now parses `source` + `session_id` **and** computes `md5(cwd)` (reused for both the observability and project hashes) — replacing four separate spawns. The two `bin/ctx` spawns (resume capsule, project learnings) are now gated on a cheap file-existence check, so a normal start with no capsule/learnings skips them entirely (ctx no-ops in that case anyway). The lore status-bar marker is written in the same Python call that emits the SessionStart context. Python spawn sites in `session-start.sh`: 11 → 7. The additionalContext output is **byte-identical** across startup / resume / a JS+DB repo.
- **Every Bash call ~181ms → ~122ms (3 hooks → 2).** `sentinel-guard.sh` is folded into `destructive_guard.py`: the catastrophic check runs first (exits 2, the absolute hard gate — unchanged), and only if it passes does the sentinel soft-block stage run in the **same** process (Bash-only, preserving the exact `{"decision":"block"}` semantics). Verified **byte-identical decisions on a 46-case block/allow matrix** (26 hard-block / 7 soft-block / 13 allow). The separate `sentinel-guard.sh` hook is removed.
- **Every whole-file Read ~115ms → ~72ms.** `access-tracker.sh` now uses a single Python pass (was two) and reads the hook JSON on **stdin** instead of `argv` (also removes a latent `E2BIG` failure on large payloads). The access-log schema and suggestion behavior are unchanged.

### Fixed
- The Codex adapter link-resolution test no longer false-positives on inline-code snippets (e.g. `fiber.Params[int](c,"id")` was misread as a `[text](target)` link); it now strips fenced + inline code before extracting links. No lore content changed.

### Notes
- No functional change to any hook's decisions or output — this is purely a spawn-count reduction. The destructive-command hard gate's guarantees (deterministic, pre-permission, no escape hatch) are untouched and re-verified. Restart Claude Code (hooks load at session start) to pick up the faster hooks.

## [4.8.0] — 2026-07-12

**Knowledge lore overhaul + platform-aware logging.** Magician now ships deep, live-doc-verified guidance for the languages, databases, and observability platforms a project actually uses — injected concisely at session start (progressive disclosure: small always-injected cores, rich on-demand deep-dive trees), version-adaptive, and switchable off when it conflicts with your own conventions.

### Added
- **Language lore** — concise, version-adaptive cores + on-demand deep-dive trees for Rust, Java (+ the JVM ecosystem: Spring/Micronaut/Quarkus/JDBC/ORM/migrations), JavaScript/TypeScript (frameworks, ORMs, UI-styling), Python (web/data/ML-AI/ORM), and Go — each grounded in current official docs.
- **Database lore** — 7 tracks, ~30 engines, each with a concise core, an on-demand deep-dive tree, and a canonical `performance.md` playbook: Relational/OLTP (Postgres, MySQL, Oracle, SQL Server, SQLite), Analytics/OLAP (DuckDB, ClickHouse, Snowflake, BigQuery, Redshift), Document/NoSQL (MongoDB, DynamoDB, Cassandra, Couchbase, Firestore), Key-value/Cache (Redis, Memcached), Vector (Pinecone, Weaviate, Qdrant, Milvus, Chroma, pgvector), Graph (Neo4j, Neptune, ArangoDB), Search/Time-series (Elasticsearch, InfluxDB, TimescaleDB, Prometheus) — plus a shared cross-engine `databases` foundation.
- **Logging & observability lore** — a language-agnostic logging-principles core (levels × environment, what/where to log for flow capture, structured/correlation IDs, errors, PII/secrets, sampling) + six platform stacks centered on log shipping and the exact query language: Dynatrace (DQL), Grafana/Loki (LogQL), Splunk (SPL), Google Cloud Logging, Amazon CloudWatch (Logs Insights), Azure Monitor (KQL).
- **Platform-aware logging behavior** — SessionStart detects the project's log platform (from SDKs/config) or, when unknown, prompts once (AskUserQuestion) and records the choice per-project; thereafter it writes platform-shaped structured logs at meaningful execution points and proposes exact queries in that platform's language. It updates when you say the platform changed and never re-asks once known.
- **Lore enable/disable flag** (default ON) — `magician-ui lore on|off|status`, a per-project `.magician/lore.off`, or `MAGICIAN_LORE=0`; plus a `📚 lore:N` / `lore:off` status-bar chip. Bundled lore is a baseline *below* the repo's own rules; this is the escape hatch when it conflicts with local/project knowledge.

### Changed
- **Cross-ecosystem stack + database detection** in SessionStart (drivers/clients across JS/Python/Go/JVM + docker-compose images + connection URIs), with **tier-ordered injection** (primary language → database/observability layer → frameworks → security) so the most relevant lore is never crowded out.
- Always-injected lore budget raised (`MAX_LORE` 3000 → 8000; ≈2k tokens once per session, **zero per-turn** — deep-dive trees stay on-demand). The `security` core is now reserved so it is never budget-starved.

### Performance
- Rewrote the `kg-nudge` PreToolUse hook: a pure-bash throttle fast-path + a single collapsed Python pass (was up to three interpreter spawns + a git call). ~4× faster on the hot paths (≈62 → ≈14 ms post-cap) with byte-for-byte identical behavior, adversarially verified.

### Notes
- Codex parity: the language/database/observability lore ships in the Codex package for on-demand use; the lore flag and SessionStart injection are Claude Code features.

## [4.7.2] — 2026-07-11

**Codex compatibility correction — Claude Code behavior is unchanged.** Live cache validation showed that Codex skips outward symlinks while installing a marketplace plugin, so v4.7.1 still produced an empty cache even though its checkout paths resolved locally.

### Fixed
- Replaced the symlink-only Codex marketplace package with a generated, self-contained `plugins/magician/` archive: canonical root `skills/` adapters, immutable `source-skills/`, shared adapter references, lore, CLIs, and the curated Codex hook/runtime. A deterministic builder plus tests reject stale packages and any symlink.
- Added a separate Codex-only destructive guard and regression matrix. It handles executable paths, wrappers/options, normalized roots, HOME globs, substitutions, quoted critical redirections/devices, and `git clean` variants; permits documented benign lookalikes; uses a five-second hook timeout; and honestly documents POSIX/`write_stdin` limits. Claude's existing hook and matcher are untouched.
- Aligned all 25 Codex adapters: `$skill` syntax, available agent/process primitives, explicit-only invocation metadata, safe commit/staging gates, Codex state paths, manual lifecycle fallbacks, capability detection, and no Claude-settings writes.
- Corrected Codex install/update/uninstall instructions and replaced the dangerous live `rm -rf /` test with a direct JSON-to-matcher simulation.

### Verification
- Added Codex package, adapter, and guard contract tests plus an isolated marketplace install/cache smoke check. The release gate verifies 25 adapters, a non-empty self-contained cache, hook discovery inputs, executable CLIs, and zero changes to Claude-owned runtime files.

## [4.7.1] — 2026-07-11

**Fix: the Codex destructive-guard hook now actually installs.** Live Codex testing surfaced `/hooks → PreToolUse: Installed 0 / Active 0` — Codex's marketplace plugin root (`plugins/magician/`, a relative-symlink layout) exposed only `.codex-plugin` and `skills`, so the manifest's `./hooks/codex-hooks.json` and the hook's `$PLUGIN_ROOT/scripts/…` (and `$PLUGIN_ROOT/bin/…` for the CLIs) resolved to nothing.

### Fixed
- **`plugins/magician/` now also symlinks `hooks/`, `scripts/`, and `bin/`** (relative, matching the existing `.codex-plugin`/`skills` symlinks) → Codex discovers `destructive-guard` (`Installed 1`), the hook resolves to the real guard, and the bundled CLIs are reachable at `$PLUGIN_ROOT/bin/<cli>`. Verified with `PLUGIN_ROOT` set to the actual install root (`plugins/magician`): `dd`→device and `rm -rf /` → exit-2 deny; safe commands pass.

Codex A (skills load) and D (only the curated hook) passed on 4.7.0; this unblocks B (guard fires after `/hooks` trust) and C (CLI resolves by absolute path).

## [4.7.0] — 2026-07-11

**The destructive-command hard gate now covers Codex too.** Verified against the current Codex model: Codex supports the same `PreToolUse` hook contract as Claude Code (deny via `permissionDecision: "deny"` / `{"decision":"block"}` / **exit code 2**, reading `tool_input.command`), and plugins can bundle hooks. Previously magician's `.codex-plugin` shipped skills only, so the guard did **not** run under Codex — users there relied solely on Codex's sandbox.

### Added
- **Codex destructive-guard** — `hooks/codex-hooks.json` (declared via the `hooks` field in `.codex-plugin/plugin.json`, so Codex uses this curated set, not the full Claude `hooks/hooks.json`) wires a `PreToolUse(Bash)` hook that runs `"$PLUGIN_ROOT/scripts/destructive-guard.sh"` — using **Codex's own native `$PLUGIN_ROOT`** (set for every plugin hook, **no Claude required**), reusing the same matcher, which already speaks Codex's exit-2 deny contract. Verified with Codex-shaped payloads: `rm -rf /` · `~` · `$HOME` · `dd` to a device → denied (exit 2); safe commands pass.
- **Codex CLI resolution** — Codex has no `bin`-on-`PATH`, so `codex-adapter.md` now instructs adapters to invoke the bundled CLIs (`jira`/`confluence`/`kg`/`ctx`/`magician-scan`/`magician-ui`) by **absolute path** (`<plugin-root>/bin/<cli>`, resolved from the skill's base directory) instead of by bare name. Wherever a skill says "on PATH when the plugin is enabled," Codex reads it as `<plugin-root>/bin/<cli>`.

### Note
Codex does **not** auto-trust a plugin's hooks — after enabling magician, run `/hooks` once to trust `destructive-guard`, or Codex skips it. Independently, Codex's `workspace-write`/`read-only` **sandbox** already blocks writes/deletes outside the workspace root (so `rm -rf ~` fails there regardless); the hook adds a deterministic layer that also covers `danger-full-access`. Docs: `.codex-plugin/references/codex-adapter.md`, `.codex/INSTALL.md`. Also fixed a stale "21 skills" count in the Codex install guide (now 25).

**Codex compatibility is under active end-to-end validation on a live Codex install** (skill loading, hook trust + firing, absolute-path CLI resolution). The wiring is verified in simulation; any gaps found on real Codex will ship as **4.7.1**.

## [4.6.0] — 2026-07-10

**An absolute destructive-command hard gate — plus a rebuilt, animated README.**

### Added
- **Destructive-command guard** (`scripts/destructive-guard.sh` → `destructive_guard.py`) — a `PreToolUse(Bash|PowerShell)` hook that **unconditionally blocks catastrophic commands**: filesystem wipes (`rm -rf /` · `~` · `$HOME` · `--no-preserve-root` · system roots), disk/device destruction (`dd of=/dev/…` · `mkfs` · `wipefs` · `blkdiscard` · `shred /dev/…` · `diskutil erase…`), block-device / critical-file overwrite (`> /dev/sd*` · over `/etc/passwd|shadow|sudoers|fstab`), fork bombs, recursive `chmod`/`chown` on system roots, opaque download-and-execute (`curl|bash` · `base64 -d|sh` · `eval "$(…)"`), and `git clean -x`. It exits 2, so the block lands **before permission rules are evaluated** — overriding `allow` rules in every mode (default/acceptEdits/auto/bypass), with **no escape hatch**. Wrappers (`sudo`/`env`/`timeout`/…) and `sh -c '…'` payloads are unwrapped; a dangerous command merely *named* in a quoted argument is not mistaken for execution. Honest scope (CWE-78): a deterministic floor layered under OS sandboxing + auto-mode's classifier + model judgment — not a complete sandbox. Verified against a 90-case block/allow matrix; runs first in the PreToolUse chain; documented in `/sentinel`.

### Changed
- **Rebuilt README** — an animated hero + SDLC-pipeline SVG (`assets/`), a consistent card-grid layout end-to-end, badges, and GitHub-faithful HTML throughout (no markdown-in-cells that GitHub would render literally).

## [4.5.0] — 2026-07-10

**Reliability discipline — evidence over claims, diff-verified orchestration, sharper debugging & plans.** A hardening pass so skills that finish work can't talk themselves into "done" without proof.

### Added
- **`lore/verification.md`** — a magician-native *evidence over claims* discipline: no "done/fixed/passing" without a verification command run **this turn** whose output you read; an evidence table (incl. **"a subagent's task is done → the VCS diff shows it, NOT the agent's success report"**) plus red-flag and rationalization tables. Wired into `/certify`, `/seal`, `/ward`, `/unravel`, `/orchestrate`.
- **Post-compaction re-anchor** — on a `compact`/`resume` SessionStart, magician re-surfaces its core doctrine (auto mode, kg-first, MCP-free CLIs, plan-then-execute, verification) so conventions survive a context compaction.

### Changed
- **`/orchestrate` — per-task quality loop:** each returned task is confirmed from the **VCS diff** (not the subagent's report) and put through a two-stage review — spec-compliance then code-quality — with a fresh fix-subagent on Critical/Important findings and a re-review, running task-to-task without per-task check-ins (`Bash(git diff/show)` added to its allow-list).
- **`/unravel` — debugging technique:** read the error/stack trace in full first (it usually names the `file:line` and often the fix), reproduce consistently before proposing a fix, and in multi-component systems instrument each boundary and run once to locate the break before changing anything; a fix isn't done until the original symptom is re-run and gone.
- **`/ward` — TDD hardening:** the RED test must fail *for the reason under test* (a wrong-reason failure is a false RED → back to RED); delete implementation written before its test and re-derive from the test.
- **`/blueprint` — plan hardening:** a verbatim **Global Constraints** header every task inherits (subagents carry project-wide rules without re-deriving) + a task right-sizing heuristic (smallest unit worth its own test cycle and a reviewer's gate).

## [4.4.0] — 2026-07-10

**Real autonomy: turn on Claude Code *auto mode*, and fix the permission/gate UX.** A live run was still prompting for everything (skills, tests, MCP, branch-compares) despite the plugin claiming "autonomous execution." Root cause: a plugin can't switch the permission mode from a skill, and the session sat in `acceptEdits` — which only auto-approves file edits, so every Bash/MCP/skill call still prompts. The fix is to enable Claude Code's **auto mode** and sharpen the gates.

### Added
- **`magician-ui automode [--off|--available]`** — enables Claude Code **auto** permission mode: sets `permissions.defaultMode: auto` + `env.CLAUDE_CODE_ENABLE_AUTO_MODE=1` (required on Vertex/Bedrock/Foundry). Auto mode's classifier auto-approves reads + request-aligned work and **gates** writes/deploys/force-push/mass-deletion — honoring "don't push"-style boundaries you state in chat. This is the real "reads proceed, writes gate." A plugin can't switch a running session's mode → **restart** to enter it. `reconcile` makes auto mode available (sets the env var) and announces it; making it the default is opt-in via the command (`--off` reverts).

### Changed
- **`jira raw` no longer truncates output at 6000 chars** — the full resource is returned (opt-in `JIRA_RAW_MAX=<N>` if you ever want a cap).
- **Allow-list refined:** added test/typecheck/lint/build runners; **narrowed `Bash(jira:*)`/`Bash(confluence:*)` to read subcommands** so Jira/Confluence *writes* gate in every mode (stale broad grants are stripped on merge).
- **Approval/decision gates → `AskUserQuestion`:** `blueprint`, `manifest`, `conjure`, `deploy`, `scrutinize`, `seal`, `orchestrate`, `autopsy`, `unravel` now present plan/spec/report/ship/scope gates as structured choices instead of a prose "end turn and wait" (`divine`/`transmute`/`magic` already did). Free-text clarifications stay prose. `AskUserQuestion` added to each affected skill's `allowed-tools`.
- **Docs** (`lore/autonomy.md`, statusline): auto mode is the real autonomy mechanism; the read-only allow-list is the `acceptEdits` fallback; the plugin *configures* the mode and the user *restarts* into it.

### Note
Nothing here changes a **running** session — hooks, skill guidance, and the permission mode all load at session start. **Restart Claude Code** to come up in Auto mode.

## [4.3.0] — 2026-07-09

**Plan-auto consistency — every pipeline now says "approve the plan, then run."** An audit (one auditor per skill) found the plan→approve→execute-autonomously posture was only fully wired into `manifest` and `weave`; 13 other pipelines had a plan/requirements gate but no "execute autonomously after the gate" language, so a run could still drift into per-read/per-step prompting. This wires the doctrine uniformly (no existing gate weakened).

### Changed
- **Autonomy stanza in 14 skills** — `accelerate`, `autopsy`, `blueprint`, `certify`, `conjure`, `deploy`, `divine`, `magic`, `orchestrate`, `scrutinize`, `seal`, `transmute`, `unravel`, `ward` each gained a short **"Autonomy — approve the plan, then run"** block: after the skill's existing approval gate, reads / searches / `kg` / read-only git run without pausing; re-gate **only** on that skill's real side effects (writes, commit/push, PR, tickets, deploy). Each links [lore/autonomy.md](lore/autonomy.md).
- **Batched up-front gates** where they were drip-fed: `magic` asks source + depth in one `AskUserQuestion` (was two); `seal` presents a single consolidated ship-summary (changed files + commit message + PR title/body + merge strategy) before the first outward command instead of a bare PR-title prompt; `deploy` presents a one-shot pipeline plan before writing the workflow file.

## [4.2.1] — 2026-07-09

**Steer Jira/Confluence off ambient MCPs onto the bundled MCP-free CLIs — follow-up to 4.2.0.** Re-inspecting the same prompt-heavy run showed the remaining approvals were *not* the reads 4.2.0 fixed: the pipeline hand-rolled `Workflow` scripts that grabbed an **ambient Atlassian MCP** (`mcp__…jira…`) instead of ever invoking `/jira`. Magician is MCP-free by design — it ships `jira`/`confluence` HTTP CLIs (on PATH, already allowed, with shared throttle/cache + bulk ops) — so the fix is to route work back to them, not to bless the MCP.

### Added
- **MCP-steer nudge** — a `PreToolUse` hook on `mcp__…(jira|confluence|atlassian)…` tools injects a one-line reminder to use the bundled `jira`/`confluence` CLI instead (which never prompts per call). Non-blocking, throttled (≤2×/session/service), opt-out aware (`integration-prefs` `jira`/`confluence` = `disabled`), and silent when the bundled CLI isn't present. Fires inside hand-rolled workflows too.

### Changed
- **Broader read-only allow-list:** more read-only git verbs (`rev-list`, `shortlog`, `for-each-ref`, `show-ref`, `ls-tree`, `cat-file`, `merge-base`, `name-rev`, `worktree list`, `stash list`), more `gh` read verbs (`pr list`, `issue view/list`, `repo view`, `search`), and `TaskOutput`.
- **`/jira` + `/confluence` skills, `lore/autonomy.md`:** explicit "do not use an ambient Atlassian MCP even if it appears in the tool list — including in `Workflow` subagents; use the CLI (on PATH for subagents too)."

### Note
Ambient MCP tools carry a **user-specific server name**, so magician does not (and cannot) auto-allow them — nor should it, since the CLI is the intended, hygienic path. Arbitrary `Bash` (ad-hoc `python3` / `cd &&` analysis) is likewise **not** auto-approved (it can write); the durable fix is kg-first retrieval + the bundled CLIs, which take effect on a session **restart**.

## [4.2.0] — 2026-07-09

**Autonomy overhaul — approve the plan, not a thousand file reads.** From a live pipeline run that bombarded the owner with per-read / per-grep / per-git approvals and never touched the knowledge graph, two core promises are restored: kg-first retrieval and gate-at-decisions autonomy.

### Added
- **Read-only auto-approve (`magician-ui allow`).** Magician merges a **safe read-only allow-list** into `settings.json` — `Read`/`Grep`/`Glob`/`LS` + read-only git (status/diff/log/show/rev-parse/branch/ls-files/blame/remote/fetch) + the `kg`/`jira`/`confluence`/`ctx` CLIs + `gh` read verbs — so autonomous runs stop prompting per file. **Writes, commit/push, PRs, ticket-creates, and deletes still gate.** Applied on install/upgrade (announced; opt-out with `magician-ui allow --off`); never removes your own rules; safe backup→validate→atomic edit. Raw `Bash` `grep`/`cat`/`find` are deliberately excluded (redirection / `-delete` can write) — kg-first steers agents to the *allowed* Grep/kg tools instead.
- **`lore/autonomy.md`** — the doctrine: **gather → plan → memorize → execute autonomously**; reads/searches are never a gate; re-gate only on side effects. Wired into `/manifest` and `/weave`.

### Changed
- **kg-first, enforced where the habit forms.** The kg nudge now also catches **raw `Bash` searches** (`grep`/`rg`/`find`/`cat`/`head`/`tail`) — not just the Read/Grep/Glob tools, which is how hand-rolled workflows slipped past it — and when a repo is **unindexed** it nudges `kg init` (was silent), so runs stop grinding grep/read. New **multi-repo** guidance (kg is per-repo — `cd <repo> && kg init` each; cross-repo greps are the wrong tool) across the knowledge-graph, weave, and manifest skills; hand-rolled Workflow scripts must ground via kg too.

## [4.1.2] — 2026-07-09

**A style gate, model currency, and completion notifications.**

### Added
- **Completion-notify hook.** A fail-safe `Notification` handler (`scripts/notify.sh`) reacts to Claude Code's `agent_completed` / `agent_needs_input` events (2.1.198), so a long `/weave`, `/orchestrate`, `/loop`, or `/goal` run tells you when it finishes or needs you. Silent for permission/idle notifications; one concise line by default — set `MAGICIAN_NOTIFY=desktop` for an OS notification (macOS/Linux), `MAGICIAN_NOTIFY=off` to mute. Never blocks the session.

### Changed
- **Style gate — match the project's conventions before review, not after.** New `lore/code-standards.md`: discover + read a repo's own standards (`CLAUDE.md`, `code-review.md` / `CONTRIBUTING` / `STYLEGUIDE`, linter/formatter config) **before** implementing, and run the project's formatter + linter as a **commit gate**. `/ward`, `/certify`, `/seal`, and `/weave` now hold to it — a convention a reviewer would flag (e.g. async/await vs `.then`, import order) is a failing gate caught during implementation instead of bouncing back from PR review round after round.
- **Model currency.** `lore/models.md` updated for **Sonnet 5** — Claude Code's default since 2.1.197 with a **1M-token context window** — alongside Opus 4.8 (top tier for hard coding), Fable 5, and Haiku 4.5.

## [4.1.1] — 2026-07-07

**Hardening for large bulk-Jira and gold-mirror deliveries.** Two avoidable failure modes are now guided against: bulk Jira work routed through a *hardcoded, stale* `jira` helper that lacked throttling (→ HTTP 429 + a stall), and a `/weave` mirror pass green-lighting "folded" stories that then needed a corrective second run.

### Changed
- **`/jira` — version & bulk hygiene (the fix that matters).** Call `jira` on `PATH` (current version) and **never hardcode a `~/.claude/plugins/cache/<version>/bin/jira` path** — a pinned pre-3.6.0 helper lacks the throttle/backoff/pacing and will 429 and hang on bulk work; **restart after a plugin upgrade** so every skill/bin resolves to one version. Reinforced the existing "never `import`/`exec` `bin/jira` to loop `api()` directly" rule (it bypasses the throttle). Mirrored into the Codex jira adapter.
- **`/weave` — parity/mirror evaluator rubric.** For deliveries where units must mirror a gold standard 1:1 (e.g. one platform's stories mirroring another's), the template now ships a `PARITY` evaluator schema asserting `single_purpose` (no folding of several gold items into one), `mirrors_gold`, `correct_id`, and `deviations_justified` — folded output **fails back for a split** instead of passing. A generic FINDINGS pass only checks "covers the purpose," which silently lets folding through and forces a corrective second run. Cross-referenced `/transmute` for full comprehend→parity jobs.

## [4.1.0] — 2026-07-06

**`/transmute` — magician can now comprehend an existing feature and either port it or transform it in place.** A new headline skill that turns Claude into a product-architect-engineer for *brownfield* work: understand something that already exists, then recreate it elsewhere or change it precisely where it lives. One skill, a routing gate, three modes — reusing the existing skills rather than adding a CLI or a data store.

### Added
- **`/transmute` skill (25th skill).** Routes to **PORT** (recreate a feature in another app, optionally upgrading the vendor/library), **INTEGRATE** (change it in place — redesign · swap the 3rd-party behind the scenes preserving the exact UX · add a capability), or **AUDIT** ("just be a user", walk a flow, recommend work). `disable-model-invocation` — invoke it explicitly; the intent hook nudges toward it.
- **Comprehension engine (Phase A).** Tiered by what exists — live URL / +docs / +codebase / pure black-box — and fans out (Tier A/B) or runs sequential (small features) across four layers: **usage** (claude-in-chrome, observation-only), **network** (endpoints/IO shapes/auth/**vendor** hosts/timing), **code** (`kg` on the source repo), **docs** (`/magic` + context7). Produces a confidence/source-tagged XML **dossier** + a **golden parity baseline** split into *behavioral* (portable) vs *environmental* (source-only), in `.workspace/shared/research/`.
- **Parity contract + gateway checklist.** Phase B authors a `<parity_contract>` (behavioral parity + UX invariants + perf/cost/security/a11y budgets + upgrade decision + rollback) — hard-gated before any code. Phase D refuses "done" until **parity · performance · cost · security · a11y/UX · rollback · sanity · toggle-debt** are green, each mapped to an existing skill (`/certify` `/accelerate` `/sentinel` `/conjure` `/scrutinize` `/divine` `/jira` `/seal`).
- **Delivery via `/weave` with an evaluator-optimizer parity loop.** Created Jira **stories become `args.units`** (id/goal/AC/scope from `kg`), so "epic → implement all of it" is real; the loop diffs each build against the **behavioral** golden (never environmental) + budgets until it passes. INTEGRATE cutover ships behind an **anti-corruption layer + strangler-fig + feature flag + parallel-run (returns control so the UX is unchanged) + canary**, with the old path retained. Optional `/goal`+`/loop` for long unattended migrations.
- **Codex adapter** (`.codex-plugin/skills/transmute/`) mapping claude-in-chrome→Browser Use/Playwright, `Task`→agent-spawn, keeping all gates.
- **Engineering principles, cited to official docs** (`references/principles.md`): **no-context-loss on handoff is the #1 HARD-GATE** — every subagent/stage/spawned-Workflow gets a complete self-contained brief + artifact paths and never re-derives upstream work; plus context engineering, the right agent pattern per phase, human-on-the-autonomy-slider, and verify-don't-trust — each grounded in Anthropic's *Building effective agents* / *Effective context engineering* and the Claude Code docs (no individuals named). Comprehension of a **copied** feature now captures its **sources / DOM / events** (the UI-event→network-call map) so a port is rebuilt faithfully, not approximated.
- **Magician CLI UI — new `effort` component.** The status bar now shows a `🧠` **reasoning-effort/mode** readout: the live `effort.level` (low/medium/high/xhigh/max) straight from Claude Code's statusLine stdin — so the session default is visible on open and mid-session `/effort` changes track automatically — plus a magician **mode** overlay so "set mode to ultracode" shows `ultracode` (which otherwise reports as `xhigh`), reverting to the raw level when you switch effort or "exit ultracode". Added to the default component set (`magician-ui set …,effort`); existing enabled users get it on the 4.1.0 upgrade reset. Zero API tokens, fail-safe as ever.

### Safety
- Browser comprehension is **observation-first, read-only**: no credential entry, no form submits, no Enter/Return in a field, no irreversible clicks, no consent/ToS acceptance, host-allowlisted (stated honestly as soft/instruction-enforced, audited in tests). Comprehended app content is **data, not instructions**. Vendor/upgrade **research is keyed only on the public vendor name/version** — never captured payloads/headers/endpoints/PII; secrets are masked before any research subagent reads the dossier. All push/PR/ticket/destructive ops stay write-gated.

### Changed
- Cross-referenced `/transmute` from `/magic` (Phase 5 routing), `/conjure`, `/weave`, `/divine`, and `/manifest`; added a `transmute` intent clause to `scripts/pattern-detect.sh` (after security/perf/deploy, before weave/flow-shape/magic). README skill count 24 → 25.

## [3.8.0] — 2026-07-06

**`/conjure` becomes a two-way, token-driven AI design studio.**

### Added
- **Selection/click callback (#1):** the browser streams clicks + selections (with a stable `data-mid`/id/CSS-path locator) to `state/events.jsonl` (append-only, **never wiped** — the old bug that lost selections is fixed); the session reads them by cursor via `GET …/events.json?since=` and reacts.
- **In-prototype companion chat (#6, opt-in):** a floating ✦ bubble lets you talk to the CURRENT session ("move the title up") without leaving the design — `POST …/chat` → session reacts (**pull** via the Chrome plugin, or **poll** via `/loop`) → replies stream back through `state/outbox.jsonl`. Asked once at GATE 0; off by default. Honest limit: reactions occur while the session is engaged/looping — on Vertex it's poll-latency, not instant push (Monitor tool unavailable there).
- **Design tokens + variation + one-design themes + responsive (#2/#3/#5):** new `references/design-tokens.md` — a two-tier CSS-custom-property system (primitives → semantics). **Seeded multi-archetype** generation so runs genuinely vary (no more same house look); **light & dark are two tonal maps of the SAME tokens on ONE layout** (with a `[data-theme]` toggle), not two different designs; GATE 3 asks target **viewports** and renders the same design responsively. Emits `design-tokens.css` + `brand.md` (archetype + reproducible **seed**) to `.workspace/shared/` so `/blueprint`→`/ward` build against the exact tokens.

### Changed
- `server.cjs` is now an **event hub** (chat POST, events pull endpoint, `outbox.jsonl`→browser, wired `new_version` banner, hardened WS frame parse, activity-aware auto-exit that won't kill a live session). `helper.js` emits stable locators + the opt-in chat widget. GATE 3 rewritten around the token system; the old "vary light/dark across sessions" line (which produced two different designs) is gone.

## [3.7.3] — 2026-07-06

**Magician CLI UI: reliable + fast, via an opt-out model.** The 3.7.0–3.7.2 attempts to *ask* at startup didn't work — a plugin hook can't force Claude to pop an interactive prompt, so Claude just answered the user's first message and skipped the offer (proven from real session transcripts). The bar now auto-enables instead of asking.

### Changed
- **Auto-enable on install and on version upgrade (opt-out).** First run enables the status bar (all components) via a safe `settings.json` edit — guaranteed visible, no reliance on Claude asking. A **version upgrade** re-asserts the default (resets to all components, refreshes the renderer so new parts show). It never clobbers a `statusLine` you set yourself, and `magician-ui disable` is respected across upgrades. New **`magician-ui default`** resets to enabled + all components ("back to default"); `magician-ui set <parts>` tunes which components show (persists within a version).
- **Startup performance.** SessionStart uses a cheap **bash fast-path** and only spawns the (python) `reconcile` when there's real work — first run, version upgrade, or a missing renderer; steady-state startups no longer pay for it (~0.45s → ~0.37s). The renderer **caches the git branch** (5s TTL). Removed the earlier SessionStart/pattern-detect "offer" machinery.

### Fixed
- The token-flow sparkline no longer shows a lone low tick (`▁`, which reads like `_`) at session start — it appears once there are ≥2 data points (an actual trend).

## [3.7.2] — 2026-07-06

**The CLI-UI first-run offer now actually reaches the user** — a second post-restart test showed it still silent in the **desktop app**, where a SessionStart hook's stderr isn't surfaced.

### Fixed
- **The offer is an interactive question now, not a passive hint.** SessionStart's `additionalContext` instructs Claude to proactively call **AskUserQuestion** on first run (enable the bar? which components?) — client-agnostic, so it works in the desktop app too (3.7.1's stderr line only reached the terminal CLI).
- **It re-offers until you decide, instead of burning the one-shot state on emit.** `reconcile` previously set `asked` the moment it emitted, so an offer Claude never surfaced was lost forever. It now re-offers for up to 3 sessions and only goes silent once you enable/disable (or the cap is reached).

## [3.7.1] — 2026-07-06

**Fixes to the v3.7.0 Magician CLI UI rollout**, caught by a real post-restart test.

### Fixed
- **The one-time "enable Magician CLI UI" nudge is now shown on the terminal (stderr).** On the first session after install it was emitted only via `additionalContext` — a Claude-facing hint that isn't guaranteed to surface — *and* the one-time `asked` state was burned on emit, so the suggestion could be silently consumed without the user ever seeing it. SessionStart now prints the nudge to stderr next to the magician banner (guaranteed visible); `additionalContext` still carries it for Claude, and it's still shown only once.
- **"enable magician ui" / "status line" / "status bar" now route to `/statusline`.** There was no pattern-detect trigger for the CLI UI, so the phrasing fell through to skill-description matching and could be hijacked into `/magic` research (e.g. "tell me about the magician ui" contains the research phrase "tell me about"). Added a `statusline` intent trigger, routed **before** `/magic`.

## [3.7.0] — 2026-07-06

**Loops currency pass** — grounded in Anthropic's "Getting started with loops" (ClaudeDevs) and the Week-15 Monitor-tool + self-pacing `/loop` docs. A verified audit (7 skill-groups, 32 agents, every gap adversarially checked) found magician already used loops widely but lagged the newest mechanisms in two systematic ways; both are closed here. Also adds an opt-in **Magician CLI UI** status line.

### Added
- **Magician CLI UI — a lightweight, always-on status line** for context-rot visibility. A native Claude Code `statusLine` (renders locally, **zero API tokens**) showing a color-coded context bar + %, a ⚠/🔴 rot warning at magician's bands, a `▁▂▃▅▇` token-flow sparkline, model · git · cost, and the active skill/workflow/loop. **User-configurable** — pick any subset of `context,rot,spark,meta,skill`. Managed by a new **`bin/magician-ui`** (`enable [--all|--only …]` · `set` · `disable` · `status` · `reconcile`) that edits `~/.claude/settings.json` **safely** (timestamped backup → JSON-validate → atomic write; only the `statusLine` key, and `disable` removes only *magician's* entry). The renderer **`bin/magician-statusline`** reads Claude Code's `context_window` JSON on stdin and is bulletproof — any error prints an empty line and exits 0, so it can never break the REPL. SessionStart **suggests it once** (then records the choice and never re-nudges; declines are honored, re-enable on request) and, when enabled, keeps the installed renderer fresh across updates. New `/statusline` skill (+ Codex adapter); active-skill marker written by the pattern-detect hook.

### Changed
- **`/weave`'s evaluator-optimizer loop now actually runs by default.** The shipped Workflow template previously did Implement → Certify → Review → one adversarial-refute pass → **report** confirmed Critical/High (a to-do list handed to `/seal`). It now adds a bounded **Remediate** phase — fix each confirmed finding with TDD → re-certify the touched unit → re-review + re-verify only those units → repeat — looping until clean or a `MAX_ROUNDS` cap / `budget.remaining()` floor (override via `args.maxRounds`; set `1` for a single-pass report). Still write-gated (never pushes). The managed pipeline now delivers a clean changeset, not a punch list. Same explicit-loop framing added to `/scrutinize` (re-review after remediation), `/certify` (loop, not checklist), `/accelerate` (bounded — stop on negligible marginal gain / budget), and `/orchestrate` (fix → re-certify before "done").
- **Monitor tool + `/loop` self-pacing adopted across watch/poll skills.** Replaces turn-blocking `gh … --watch` / fixed-interval polling with the **Monitor tool** (event-streaming, reacts the instant CI/PR/log state changes) where it improves the outcome — `/seal` (CI), `/deploy` (pipelines), `/divine` monitor mode (PR/commit/CI events + SHA idempotency guard), `/certify` (dev-server/console errors), `/accelerate` (long benchmarks), `/unravel` (intermittent/async repros). `/divine` monitor mode and CI waits now document **self-paced `/loop`** (omit the interval → `ScheduleWakeup`; automatic fixed-interval fallback on Bedrock/Vertex) and **`/goal`** for long unattended "until green" waits. `Monitor` added to the relevant skills' `allowed-tools`.

### Fixed
- **kg-nudge no longer misfires on a ranged read starting at `offset: 0`.** The Read gate tested `ti.get('offset') or ti.get('limit')`, which is falsy when `offset == 0`, so a targeted read from the top of a file was misclassified as a whole-file read and nudged — contradicting the documented rule that ranged reads stay silent. Now tests key presence (`is not None`). Surfaced independently by both arms of the v3.7.0 A/B and by the diff self-review.
- **`/weave` remediate loop can no longer report a false "clean" convergence.** If one unit's fix re-certified while another's failed, the still-open Critical/High findings for the failed unit were dropped (the open set was rebuilt only from re-reviewed/touched units). The loop now carries forward unresolved findings for units that didn't re-certify, so they still count against convergence and appear in `openFindings`. (Caught by the adversarial self-review.)

## [3.6.0] — 2026-07-03

**Adoption + currency release** — grounded in real magician sessions and the code.claude.com what's-new digest (W19–W26).

### Changed
- **kg enforced on file reads, not just search.** The PreToolUse nudge now also fires on whole-file **Read** of code — it skips ranged reads (`offset`/`limit`, the good kg-driven pattern) and non-code files, and steers Claude to `kg query`/`kg blast` at the moment it would otherwise slurp a whole file. Effort-aware cap (`$CLAUDE_EFFORT`: quieter at low, firmer at xhigh) with escalating wording. (Real sessions showed the graph built once then ignored — 3 queries vs 100+ reads.)
- **Global CLI allow-rules.** Added `Bash(kg:*|jira:*|confluence:*|ctx:*|magician-scan:*)` so the bundled CLIs never prompt when called outside their owning skill (e.g. `/magic` running `kg`, `/weave` stages, the kg nudge) — a source of the permission friction users hit.
- **Latest Claude Code capabilities folded in.** `lore/subagent-context.md` + `/orchestrate` + `/weave` now reflect **background-by-default subagents** (keep working; prompts surface in the main session) and **nested subagents (~5 deep)**; pointers added to **`/goal`** (unattended cross-turn runs — `/weave`, `/manifest`), **`/usage`** (limit breakdown by skill/subagent/plugin — `/chronicle` context-mgmt), and **Artifacts** (shareable live pages — `/conjure`, `/divine`).
- **Context-passing hardened between pipelined agents.** `/orchestrate` and `/weave` spawn prompts now require reading `.workspace/local/session-state.md` first and keep it current between waves/phases, so a mid-run compaction loses nothing.

## [3.5.2] — 2026-06-30

### Fixed
- **Jira & Confluence CLIs are now throttle-aware and bulk-safe.** After a bulk epic/story/dependency-link session hit Jira's rate limits, the agent hand-rolled `urllib` loops that re-introduced corporate-CA TLS failures *and* hammered the API. Both `bin/jira` and `bin/confluence` now: retry **429/503 with bounded exponential backoff** then emit a clear **STOP** message (no tight-loop retries); cache **GET** responses briefly (cleared on any write) so repeated identical queries are free and fresh-after-writes; **self-pace bulk loops** across separate calls; and add a **connect-timeout** so a throttled endpoint can't hang the session. New **`jira create`** / **`jira link`** bulk helpers so loops use the CLI instead of hand-rolled HTTP. Skill guidance hardened: never hand-roll `urllib`/MCP — use the CLI; on 429 stop and pace; re-query before retrying an interrupted write. Env knobs: `JIRA_*`/`CONFLUENCE_*` `TIMEOUT`, `RETRIES`, `CACHE_TTL`, `MIN_INTERVAL_MS`.

## [3.5.1] — 2026-06-30

### Added
- **Flow-shape detector** — when you *describe* a multi-step delivery (numbered steps, "first/then/finally", "here's the flow/steps/plan", "for each …") rather than naming an explicit batch, magician now injects a soft analysis nudge to **decide the engine**: `/weave` if it's N similar units, `/manifest` if it's distinct SDLC stages — instead of hand-rolling ad-hoc agents. Fires only when no specific action trigger matched and the prompt is substantial (keeps over-firing low); the decision stays Claude's.

## [3.5.0] — 2026-06-30

**Adoption release** — make magician actually *drive* the behaviors it ships: own large pipelines, push the knowledge graph, and track context for real. Diagnosed from a real 5,000-line session where Claude hand-rolled a Workflow + 42 agents (bypassing magician), reused the graph 3× against 105 reads, and never surfaced a single context warning.

### Added
- **`/weave`** — composes and runs a large delivery as **one native Workflow** with magician's guardrails, instead of hand-rolling dozens of agents. Picks the structure adaptively (per-item `pipeline` / `parallel` barrier / orchestrator-worker / evaluator-optimizer) but always keeps the non-negotiables: **TDD per unit, kg grounding, certify before done, multi-lens review + adversarial verify, write gates, no context loss**. Auto-suggested on big multi-item intent ("implement these N tickets/features", "migrate X across the codebase", batch/sweep). Ships a copy-and-adapt Workflow template; `/orchestrate` and `/manifest` point to it; Codex adapter included.
- **Always-on kg push** — a `PreToolUse(Grep|Glob)` hook (`kg-nudge.sh`) nudges toward `kg query`/`kg blast`/`kg neighbors` at the moment Claude reaches for grep (throttled, only when an index exists); SessionStart now reinforces "prefer kg over grep" when the repo is indexed; `/magic`, `/divine`, `/unravel`, `/accelerate`, and `lore/subagent-context.md` lead with kg as the default for code lookups, not a conditional.
- Natural-language routing gained the big-delivery trigger (→ `/weave`); the debug trigger now matches plurals ("these bugs").

### Fixed
- **Context tracking never fired.** Root cause: the `ctx` hook got no usable `transcript_path` in some host apps, so it silently no-op'd all session. `ctx` now **discovers** the session log itself (newest JSONL for the cwd) when the host doesn't pass one, parses usage schema-tolerantly, and **auto-detects the context window** (200K vs the 1M extended window) so the percentage is right — band warnings (60/80/92%) actually fire now.

## [3.4.0] — 2026-06-28

**Context efficiency release** — a code **knowledge-graph** for targeted retrieval and a **self-managed context system** that keeps conversations small and lossless.

### Added
- `/knowledge-graph` + bundled **`kg` CLI** (`bin/kg`, on PATH when the plugin is enabled): a local, global, per-repo **code knowledge graph + cache** at `~/.claude/magician/knowledge-graph/` so skills/agents retrieve a ranked set of `file:line` ranges (BM25 + Personalized PageRank over a SQLite/FTS5 graph of symbols and their import/reference edges) instead of grepping and reading whole files — fewer tokens, faster search, and a durable shared map that survives hand-offs between agents/pipelines/teams with **no context loss**. Commands: `check · init · refresh · status [--json] · query · neighbors · blast · stale · cache · daemon · reset`. Pre-allowed via `allowed-tools: Bash(kg:*)` — no per-request prompts.
- **Tiered performance, lightweight by default.** Tier 0 is pure stdlib (`sqlite3`+FTS5, regex parser, in-memory CSR traversal, content-addressed cache, fast hashing; optional `KG_JOBS` parallel parsing for very large trees). Tier 1 auto-uses native accelerators *iff already installed* (`tree-sitter` parsing, `numpy` PageRank, `ctags`) with silent fallback. Tier 2 is opt-in: a resident daemon (`kg daemon`) that keeps the graph in RAM to skip the per-call graph load (win grows with graph size) and a pluggable `KG_BACKEND` (cozo/kuzu/duckdb) escape hatch for million-node monorepos. No required network calls or dependencies; embeddings are opt-in only.
- **Auto-suggestion for existing repos**: a throttled, opt-out-aware SessionStart nudge offers to build an index on unindexed git repos (>150 files, once per repo per 7 days) — never auto-builds. Opt-out via `integration-prefs.json` key `knowledge-graph`.

- **Self-managed context system** + bundled **`ctx` CLI** (`bin/ctx`): the plugin now tracks context size every prompt and keeps it small, lossless, and shared. (1) **Size tracking** — parses the transcript's latest assistant `usage` (real occupancy, not a guess) and warns once per band (60/80/92%) before it balloons. (2) **Lossless compaction** — `PreCompact` captures a structured resume capsule (goal, open threads, decisions, changed files, **knowledge-graph blast radius of the changed files**, artifact paths, learnings) to `~/.local/share/magician/projects/<hash>/`; it's re-injected on the next prompt after a mid-session compaction and on `--resume`. (3) **Offload** — `lore/subagent-context.md` + a one-time large-read nudge steer toward `kg query`/`file:line` over whole-file pastes. (4) **Shared memory** — the capsule doubles as `.workspace/local/session-state.md`; every subagent/teammate is told to read it (`/orchestrate` refreshes it per wave) → no context loss across actors. (5) **Self-learning** — commit-derived learnings captured at `Stop`, surfaced at SessionStart, promoted to global with confirmation via `/chronicle`. Exposed through `/chronicle status | resume | learn | consolidate`. **Honest limits (designed around, never overclaimed):** a plugin can't read a live token count (we parse the transcript) and can't force or steer compaction (`PreCompact` only blocks) — so we warn early and make loss impossible via the capsule. *(A/B: a resumed agent with the capsule used ~55% fewer tool calls and oriented more accurately than one reconstructing from git state alone.)*
- **Natural-language skill invocation, expanded.** Describe a situation and the right skill auto-activates — now covering **`/unravel`** (debug: "I have a bug / it's broken / not working / production issue / crash / stack trace"), **`/sentinel`** (security: "scan for vulnerabilities / exposed secrets / is this secure"), **`/accelerate`** (perf: "it's slow / high latency / optimize performance"), **`/deploy`** (CI/CD: "set up a pipeline / the build is failing"), and **`/autopsy`** (post-mortem / RCA), joining the existing review/jira/confluence/research triggers. All routed in **strict first-match precedence with negation guards — exactly one skill ever triggers** (no multi-skill conflicts); the context note rides along independently. `/unravel` debug grounds comprehensively via `/magic` + the knowledge graph.

### Changed
- `/magic` now queries the knowledge graph (`kg query`) as a first-class **internal codebase source** before broad greps; `/divine` uses `kg blast` to establish change **blast-radius** for reviewers. Both degrade gracefully when no index exists and respect the opt-out. Codex adapter included.
- `/chronicle` is now the **memory & context steward** (session history + global references + live context/learnings). The `UserPromptSubmit`, `PreCompact`, `Stop`, and `SessionStart` hooks gained context-management duties; `pre-compact.sh` now captures a full capsule globally (previously only inside a `.workspace/`).

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
