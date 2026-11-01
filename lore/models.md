Model & effort currency — how magician skills should choose models and reasoning effort.

NEVER hardcode a model version in skill output (commit trailers, prompts, docs). Versions go stale. Use tier aliases (`opus`, `sonnet`, `haiku`, `fable`, `best`) which always resolve to the latest of that tier, or describe the capability ("the latest coding-optimal model").

Behavioral guidance for these models — what to stop telling them to do — lives in [model-behavior.md](model-behavior.md). Read it before writing or editing any skill prompt.

## Current tiers (as of 2026-11; verify, don't trust blindly)

| Tier | Model | Context | $/MTok in / out | Cache read / write |
|---|---|---|---|---|
| **fable** | Fable 5.1 (`claude-fable-5-1`) | 1M | 10 / 50 | — |
| **opus** | Opus 5.5 (`claude-opus-5-5`) | 1M | 4 / 20 | 0.20 / 5 |
| **sonnet** | Sonnet 5.5 (`claude-sonnet-5-5`) | 1M | 2 / 10 | 0.10 / 2.50 |
| **haiku** | Haiku 5.5 (`claude-haiku-5-5`) | 1M (API) | 0.10 / 0.50 ≤100k; 0.50 / 2.50 above | 0.01 / 0.125 ≤100k; 0.05 / 0.625 above |

- **opus** — the default on Pro/Max/Team/Enterprise/API (Claude Code v2.1.280+). Near Fable 5.1 quality at ~40% lower cost per task than Opus 5; thinking is **always on and cannot be turned off**; Opus 5.5 at `medium` ≈ Opus 5 at `high`. Works longer autonomously and reads screenshots well. Fast mode (research preview, usage credits) bills $8 / $40.
- **fable** — Fable 5.1 is never a default and bills to usage credits after a one-time consent. **Escalate to Fable only after Opus 5.5 at `xhigh` has failed twice** on the same problem.
- **sonnet** — 30%+ faster than Sonnet 5, ~30% fewer tokens per task, batches tool calls aggressively; 128k max output, June 2026 knowledge cutoff; no fast mode. Thinking cannot be disabled (`between_tools` mode replaces it). **Preserved thinking ties its reasoning to the originating account** — switching accounts mid-session breaks the conversation.
- **haiku** — the documented coding subagent for search, log reading, classification, summarization and compaction. **First Haiku with an effort axis** (`low`…`max`); 1M context on the API but priced higher above 100k tokens, so keep Haiku subagents under 100k. ~75% cheaper than Haiku 4.5 on average (90% for ≤100k requests). Updated tokenizer like Sonnet/Opus 5.5: slightly more tokens per task.
- The whole 5.5 family plus Fable runs adaptive thinking; `MAX_THINKING_TOKENS=0` does not disable it there. Task tools (`TaskCreate`/`TodoWrite`) are absent on Opus 4.8, Sonnet 5, Fable and later unless `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` — the plan file is the checklist.

Legacy but still selectable: Opus 5, Sonnet 5, Opus 4.8 / 4.7 / 4.6, Sonnet 4.6, Haiku 4.5.

### Aliases resolve per provider

`best` → `fable` where the org has it, else `opus`. `fable` → Fable 5.1 (Claude apps gateway still resolves it to Fable 5; the alias retries the previous Fable model when the newest is unavailable). `opusplan` → Opus while planning, Sonnet to execute. `sonnet[1m]` / `opus[1m]` are only needed for the 4.6 models.

Alias resolution is **provider-dependent**: `opus` = Opus 5.5 on the Anthropic API, Claude Platform on AWS, Bedrock and Vertex, but Opus 4.6 on Foundry; `sonnet` = Sonnet 5.5 on the API, Sonnet 4.6 on the AWS platform, Sonnet 4.5 on Bedrock/Vertex; `haiku` = Haiku 5.5 on the API, Haiku 4.5 elsewhere. Pin a newer model with `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU,FABLE}_MODEL`. So: don't assume `sonnet` means Sonnet 5.5 — check the session's actual model before claiming a capability that depends on it.

## Effort (`/effort`) — support differs by model

Effort is a behavioral signal across **all** output tokens (thinking, prose, tool calls), not a token budget.

| Level | Supported on | Default |
|---|---|---|
| `low` / `medium` / `high` / `xhigh` / `max` | Fable, Opus 5.5, Sonnet 5.5, Haiku 5.5, Opus 5, Sonnet 5, Opus 4.8, Opus 4.7 | `medium` on the 5.5 family; `xhigh` on Opus 4.7; `high` elsewhere |
| `low` / `medium` / `high` / `max` (no `xhigh`) | Opus 4.6, Sonnet 4.6 | `high` |

Precedence: `CLAUDE_CODE_EFFORT_LEVEL` / `--effort` / `/effort` > `modelSettings` per model or `effortLevel` > model default. A skill's or subagent's `effort:` frontmatter overrides the session level but never the env var; `maxEffortLevel` (any plan; lowest cap wins) caps everything. `max` is session-only. `CLAUDE_CODE_SUBAGENT_EFFORT` (2.1.316) and `CLAUDE_CODE_SUBAGENT_MODEL` set subagent defaults — frontmatter wins; magician only **suggests** them (see [autonomy.md](autonomy.md)).

### Name the intent, not the level

Skills ask for a **capability intent** and let this table resolve it:

- **`deep`** — `xhigh`. Migrations, whole-repo refactors, deep root-cause hunts, sprawling reviews. Mention `max` only as an opt-in for frontier problems with evals showing headroom: Sonnet 5.5 at `max` over-invoked Claude Code's code-review skill, spawned many subagents and timed out.
- **`standard`** — `high`. Where verification and edge cases matter: brownfield bug fixes, review, security (Terminal-Bench 3.0: effort lifts security pass rates 64→87%). Higher effort fixes missed edge cases, not a wrong approach.
- **`cheap`** — `low` for interactive sketching and mechanical single-file work, `medium` for routine feature and bugfix work.
- Every current tier, Haiku 5.5 included, has the effort axis; only the 4.5 generation lacks it — say so instead of suggesting a level there.

The recommended loop is **spec at high, implement and iterate at low/medium, verify and test at high** — not one level held for the whole run. On low/medium turns add the verification paragraph from [verification.md](verification.md). `ultrathink` anywhere in a prompt runs **that one turn at `xhigh`** on the 5.5 family and Fable 5.1 via the Anthropic API (2.1.311; `CLAUDE_CODE_DISABLE_ULTRATHINK` turns the keyword off) without changing the session level. Other phrases ("think hard") are ordinary text.

### Effort and the prompt cache

Each model has its own cache, and so does each effort level — **except Opus 5.5, Sonnet 5.5, Haiku 5.5 and Fable 5.1 on an API key or subscription, where an effort change keeps the cache**. On Bedrock, Vertex, the Claude apps gateway, HIPAA accounts or with `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` it still invalidates — hold one level for the run there. A model switch, compaction, the first fast-mode turn and an automatic safety fallback all invalidate too.

### `ultracode` is a Claude Code setting, not an API effort level

`/effort ultracode on` sends `xhigh` to the model *and* has Claude orchestrate dynamic workflows for substantive tasks. The status bar reports it as `xhigh` unless magician's own mode marker is set.

## Fast mode

Research preview on Opus 5.5 and Opus 5 (up to 2.5x faster, ~2x price; usage credits on subscriptions); `/fast on|off`. Not on Bedrock/Vertex/Foundry/AWS platform, not on Sonnet 5.5. **Fast mode on Opus 4.8 ends 2026-11-30** (2.1.316) — don't recommend it.

## Deprecations to honor

Fast mode on Opus 4.8 ends **2026-11-30**; standalone Claude Design closes **2026-12-14** (say "`/design` artboards", never "Claude Design"); Task tools need `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` on current models; `/ultraplan` and the `ultraplan` keyword are removed — nothing in magician may reference them; Managed Agents `coordinator` → `multiagent_20261001`; MCP session ids, Roots, Sampling and Logging are deprecated. API-level removals (`thinking: disabled`, forced `tool_choice`, history edits) and the full table: [llm-sdks.md](llm-sdks.md) → `lore/deep/llm-sdks.md#deprecations`.

## Safety classifiers change which model you end up on

Fable 5.1/5, Opus 5.5, Opus 5 and Sonnet 5.5 run cyber/bio classifiers. When one flags a request, Claude Code re-runs it on a fallback model and **the session continues there**: Fable 5.1/5 and Opus 5.5 bio → Opus 5, cyber → Opus 4.8; Opus 5 cyber → Opus 4.8; Sonnet 5.5 cyber → Sonnet 5. Most cyber tasks on Opus 5.5 reroute this way, and the switch invalidates the prompt cache.

Make it visible or stop it: `switchModelsOnFlag: false` asks before switching; `CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK=1` (2.1.312) disables the automatic switch; cloud providers need `ANTHROPIC_DEFAULT_*_MODEL` pins for the fallback targets; `/feedback` reports a wrong flag. Security skills print the active model at start and end so a mid-run switch is visible — see [security.md](security.md).

## Value profile — models differ in *behavior*, not just capability

Anthropic's research on Claude's values across models & languages found the values a model expresses — how cautious vs. accommodating, how rigorous vs. warm, how candid about uncertainty — shift by **model version** in ways not deliberately chosen: frontier tiers push back more, flag risks unprompted and go deeper; lighter tiers lean warmer, more deferential, briefer. So model choice affects *tone and judgment*:

- **Critique / review / security / debugging** ([divine](../skills/divine/SKILL.md), [scrutinize](../skills/scrutinize/SKILL.md), [sentinel](../skills/sentinel/SKILL.md), [unravel](../skills/unravel/SKILL.md)) want the **cautious + candid + thorough** profile — the top tier (`opus`) at `high` for the correctness and security lenses; Haiku 5.5 at `high` is fine for the narrower simplification and test-coverage lenses, with an eval guarding against softened findings.
- **Ideation / design dialogue** ([conjure](../skills/conjure/SKILL.md)) tolerates the warmer, briefer profiles.
- **Re-verify posture after a model bump.** Don't assume a newer model is a drop-in on *behavior*; do not hardcode the research's per-version numbers. (anthropic.com/research/claude-values-models-languages.)

## Currency rule (history/planning/orchestration skills)

When a skill picks a model or spawns subagents and the session is on an older model than the latest available for the task, **suggest the upgrade** ("You're on an older model — Opus 5.5 would handle this better. Switch with `/model`?") and let the user decide. Never switch silently. For spawned subagents, choose the tier that fits the subtask — `haiku` for narrow search/summarize/classify work, `sonnet` for well-scoped implementation, `opus` as the lead and for review — rather than always inheriting.

Sources: code.claude.com/docs/en/{model-config,prompt-caching,fast-mode,sub-agents,changelog} (2.1.296–2.1.316) · anthropic.com/claude-{opus,sonnet,haiku}-5-5 · claude.dev/blog/{spending-your-effort,what-a-task-costs-on-opus-5-5,building-with-claude-sonnet-5-5,getting-the-most-out-of-opus-5-5}.
