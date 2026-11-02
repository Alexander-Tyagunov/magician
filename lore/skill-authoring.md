Skill authoring — write every new or edited `SKILL.md` so the spec-only consumers (claude.ai upload, Skills API, Codex/ChatGPT plugins) accept it, and Claude Code still gets its extensions.

## Frontmatter: standard keys vs Claude Code extensions

Agent Skills is an open standard (agentskills.io, donated to the Agentic AI Foundation under the Linux Foundation; 70+ platforms, ChatGPT/Cursor/Copilot/VS Code included). The portable key set is:

| Standard (AAIF) | Claude Code extensions (hard-error on claude.ai upload / Skills API / `package_skill.py`) |
|---|---|
| `name`, `description`, `license`, `compatibility` (≤ 500 chars), `metadata`, `allowed-tools` | `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `disallowed-tools`, `model`, `effort`, `context`, `agent`, `background`, `hooks`, `paths`, `shell` |

Rules:
- Put behaviour that must survive a port in the **body**, not in an extension key. `effort`, `context: fork`, `paths`, `hooks` are Claude Code conveniences; the Codex build strips them, so the body must still say when the skill runs and what it must not do.
- `allowed-tools` is standard but its *values* are Claude Code permission specifiers; keep them least-privilege (`Bash(kg query *)`, `Edit(./.workspace/shared/**)`) — never bare `Bash`/`Edit`/`Write`.
- `license` and `compatibility` are accepted and not acted on in Claude Code; `metadata` is free-form.

## Description = the router, in every ecosystem

`name` + `description` decide invocation on both sides. `description` + `when_to_use` are truncated at **1,536 chars** in the Claude Code listing and sit in context every turn; **Codex truncates descriptions when many skills are installed**, so lead with the trigger and keep one "use when / not when" sentence (negative triggers raised Glean's triggering accuracy ~20%). Keep descriptions ≤ ~250 chars; move trigger-phrase lists into the body — the model reads the body only after selection. Codex budgets ~2% of context (~8k chars) for the whole skill list.

## Provider-neutral wording

Skills should read correctly under any agent: say **"the agent"**, not "Claude", where it is not a product reference; name Claude Code features (`Workflow`, `/goal`, Artifacts, hooks) only where the feature is the point, and give the portable alternative (Codex: `codex exec`, `AGENTS.md`, `.agents/skills/`). Claude live artifacts are unsupported on the OpenAI side — return regular content when they are absent. Non-portable per OpenAI's conversion guide: `outputStyles`, `lspServers`, themes/monitors, channels, `dependencies`, `bin/`, `settings.json`, `CLAUDE.md`, `.mcpb` bundles.

## Shape

- SKILL.md is a **short router** (≤ ~8k chars) pointing to `references/` and `scripts/`; after compaction Claude Code re-injects at most 5,000 tokens per invoked skill, keeping the start of the file — so the completion signal and the Obstacles pointer go near the top, not the tail.
- Goals + constraints + completion criteria beat step-by-step itineraries; newer models over-constrain on recipes.
- Instruction-only by default; `scripts/` only for deterministic work. State how to verify (commands + expected evidence).
- Obstacles: the two-line pointer to [obstacles.md](obstacles.md), never the pasted block.
- Evaluate with 10–20 prompts per skill including negative controls (`claude plugin eval`, or `codex exec --json --output-schema` headless), and track token usage per skill version.

## On Codex

`scripts/build-codex.sh` makes the Codex and ChatGPT package from this tree (default `dist/codex/magician/`, gitignored). Each generated skill ends with an "On Codex" section. That section lists only the rows below that the skill uses.

| Claude Code | Codex / ChatGPT |
|---|---|
| `/goal` | `/goal`, the same name. The goal text holds the outcome, the constraints and how to verify. One goal per chat, and a goal never widens the sandbox. |
| `Workflow` fan-out | One `codex exec --worktree` per independent unit, or `/worktree` for parallel chats. |
| Subagents (`Task`, `Agent`, `agents/*.md`) | `.codex/agents/*.toml` with `name`, `description`, `developer_instructions`. They are not part of the public plugin format, so the build turns each agent into a `<agent>-lens` skill. |
| Hooks | None in the package: the public directory does not accept hooks. Local Codex hooks live in `hooks.json` under `~/.codex/` or `<repo>/.codex/`, use the same event names, block with exit 2, and need trust through `/hooks`. |
| `Monitor` | None. Poll the file or the command. |
| `AskUserQuestion` | No question tool. Ask in prose with the same options and wait. `/plan` mode also asks clarifying questions. |
| `codex exec --full-auto` | Removed. Use `--sandbox workspace-write`. |
| `CLAUDE.md` | `AGENTS.md`, read from the repository root down to the current folder. `/almanac` can write one and import it from `CLAUDE.md`. |
| `/skill` | `$skill` in Codex, `@skill` in ChatGPT. |
| `userConfig` | None. The `jira` and `confluence` helpers read `MAGICIAN_JIRA_*` and `MAGICIAN_CONFLUENCE_*` environment variables. |

The build keeps only the Agent Skills keys in the frontmatter. It moves every other key into `metadata` as a `claude-code.<key>` string, because `metadata` is a flat string map. It rewrites the `CLAUDE_PLUGIN_ROOT` and `CLAUDE_SKILL_DIR` variables to paths relative to the file, and the `CLAUDE_PLUGIN_DATA` folder to `$MAGICIAN_DATA` (default `~/.local/share/magician`). It drops `hooks/`, `monitors/`, `output-styles/`, `mods/`, `evals/` and `scripts/`.

Sources: code.claude.com/docs/en/skills (frontmatter reference; spec-only consumers) · anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation · learn.chatgpt.com/docs (Codex skills, plugin conversion guide) · learn.chatgpt.com/docs (long-running-work, developer-commands, agent-configuration/subagents, hooks, non-interactive-mode, agent-configuration/agents-md) · developers.openai.com/plugins (build/plugins, guides/submit-claude-plugin) · developers.openai.com/blog (skill evaluation).
