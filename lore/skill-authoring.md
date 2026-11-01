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

Sources: code.claude.com/docs/en/skills (frontmatter reference; spec-only consumers) · anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation · learn.chatgpt.com/docs (Codex skills, plugin conversion guide) · developers.openai.com/blog (skill evaluation).
