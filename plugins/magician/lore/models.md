Model & effort currency — how magician skills should choose models and reasoning effort.

NEVER hardcode a model version in skill output (commit trailers, prompts, docs). Versions go stale. Use tier aliases (`opus`, `sonnet`, `haiku`, `fable`, `best`) which always resolve to the latest of that tier, or describe the capability ("the latest coding-optimal model").

Behavioral guidance for these models — what to stop telling them to do — lives in [model-behavior.md](model-behavior.md). Read it before writing or editing any skill prompt.

## Current tiers (as of 2026-08; verify, don't trust blindly)

| Tier | Model | Context | Max out | $/MTok | Knowledge cutoff |
|---|---|---|---|---|---|
| **fable** | Fable 5 (`claude-fable-5`) | 1M | 128k | 10 / 50 | Jan 2026 |
| **opus** | Opus 5 (`claude-opus-5`) | 1M | 128k | 5 / 25 | **May 2026** |
| **sonnet** | Sonnet 5 (`claude-sonnet-5`) | 1M | 128k | 2 / 10 | Jan 2026 |
| **haiku** | Haiku 4.5 (`claude-haiku-4-5`) | 200k | 64k | 1 / 5 | Feb 2025 |

- **opus** — the daily driver and the default Opus in Claude Code. Step-change over 4.8 on agentic coding, long-horizon work, and code review; converts extra effort into results more reliably than any earlier Opus. Thinking is **on by default**. Has the freshest knowledge of the family (May 2026), so it is the tier to prefer when the task turns on recent library or platform behavior.
- **fable** — Mythos-class, above Opus. For work larger than a single sitting: multiday autonomous runs, ambiguous root-cause hunts, architecture decisions. Adaptive thinking is **always on and cannot be disabled**. Twice the price of Opus 5 and can bill to usage credits; not the default, select with `/model fable`. Not available under zero data retention.
- **sonnet** — best balance of speed and intelligence, and more agentic than Sonnet 4.6. Uses a **new tokenizer: the same text is ≈30% more tokens**, so token budgets measured on 4.6 no longer transfer.
- **haiku** — fast and cheap for simple, well-scoped subagent tasks. **No adaptive thinking and no effort axis at all** — don't suggest an effort level for a Haiku subagent.

Legacy but still selectable: Opus 4.8 / 4.7 / 4.6, Sonnet 4.6, Sonnet 4.5, Opus 4.5.

### Aliases resolve per provider

`best` → Fable 5 where the org has it, else the latest Opus. `opusplan` → opus while planning, sonnet to execute. `sonnet[1m]` / `opus[1m]` request the 1M window explicitly (a no-op where the tier is already natively 1M).

Alias resolution is **provider-dependent** — on Microsoft Foundry `opus` is still Opus 4.6 and `sonnet` is Sonnet 4.5; on Bedrock and Google Cloud `sonnet` is Sonnet 4.5. Where an alias lands on an older model, the newer one is reachable by full model name or via `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL`. So: don't assume `sonnet` means Sonnet 5 — check the session's actual model before claiming a capability that depends on it.

## Effort (`/effort`) — support differs by model

Effort is a behavioral signal across **all** output tokens (thinking, prose, and tool calls), not a token budget. The default is `high` on every model that supports it, except Opus 4.7 (`xhigh`).

| Level | Supported on |
|---|---|
| `low` / `medium` / `high` | every effort-capable model |
| `xhigh` | Fable 5, Opus 5, Opus 4.8, Opus 4.7, Sonnet 5 — **not** Opus 4.6, **not** Sonnet 4.6 |
| `max` | all of the above **plus** Opus 4.6 and Sonnet 4.6 |
| *(none)* | Haiku 4.5, Sonnet 4.5, Opus 4.5 |

Claude Code silently clamps an unsupported level down to the highest supported one (`xhigh` runs as `high` on Opus 4.6), so a bad recommendation degrades quietly rather than erroring — which is exactly why skills must not name a bare level.

### Name the intent, not the level

Skills should ask for a **capability intent** and let this table resolve it:

- **`deep`** — the deepest level this model supports: `xhigh` on Fable 5 / Opus 5 / Sonnet 5 / Opus 4.8 / Opus 4.7, `max` on Opus 4.6 / Sonnet 4.6. For migrations, whole-repo refactors, deep root-cause hunts, sprawling reviews.
- **`standard`** — `high`. The default; large changesets, multi-component design, normal review.
- **`cheap`** — `low` for mechanical/single-file work, `medium` for ordinary feature and bugfix work.
- If the session's model has **no effort axis** (Haiku, the 4.5 generation), say so instead of suggesting a level.

`max` is genuinely unbounded and prone to overthinking on structured-output tasks — reserve it for frontier problems, and only when evals show headroom at `deep`. When running at `xhigh` or `max`, leave a large `max_tokens`; thinking counts against it.

Effort shapes the rendered prompt, so **changing it mid-conversation invalidates the prompt cache**. Pick a level at the start of a long run and hold it.

### `ultracode` is a Claude Code setting, not an API effort level

It sends `xhigh` to the model *and* has Claude orchestrate dynamic workflows for substantive tasks. Session-only: the persisted `effortLevel` setting and `CLAUDE_CODE_EFFORT_LEVEL` reject it. The status bar reports it as `xhigh` unless magician's own mode marker is set.

`ultrathink` anywhere in a prompt still requests deeper reasoning for that one turn without changing the session level. Other phrases ("think hard", "think more") are ordinary prompt text and do nothing.

## What no longer exists

Do not emit these in generated code, migration advice, or SDK examples for current models:

- `thinking: {type: "enabled", budget_tokens: N}` — **400** on Opus 5, Sonnet 5, Fable 5, Opus 4.8, Opus 4.7. Use adaptive thinking plus effort.
- `temperature` / `top_p` / `top_k` at non-default values — **400** on Opus 4.7+ and Sonnet 5. Steer with the system prompt instead.
- Assistant message prefill — **400** on Sonnet 4.6+ and Fable 5. Use structured outputs or `output_config.format`.
- `thinking: {type: "disabled"}` — always **400** on Fable 5; on Opus 5 only valid at effort `high` or below (`xhigh`/`max` + disabled → 400).

## Safety classifiers change which model you end up on

Fable 5 **and** Opus 5 run cybersecurity and biology classifiers. When one flags a request, Claude Code re-runs it on a fallback model and **the session continues there**: Fable 5 bio → Opus 5, Fable 5 cyber → Opus 4.8, Opus 5 cyber → Opus 4.8 (Opus 5 bio is a hard refusal). This can fire on the very first request from CLAUDE.md and git context alone.

So a long security sweep can quietly change tier mid-run. Set `switchModelsOnFlag: false` to be asked instead of switched, and use `claude --safe-mode` to test whether local customizations are the trigger. Details for the security skills are in [security.md](security.md).

## Value profile — models differ in *behavior*, not just capability

Anthropic's research on Claude's values across models & languages found the values a model expresses —
how cautious vs. accommodating, how rigorous vs. warm, how candid about uncertainty, how thorough —
shift by **model version** in ways not deliberately chosen: newer frontier models tend to push back
more, flag risks unprompted, hedge, and go deeper; lighter tiers lean warmer, more deferential, and
briefer. So model choice affects *tone and judgment*, not only correctness:

- **Critique / review / security / debugging** ([divine](../source-skills/divine/SKILL.md), [scrutinize](../source-skills/scrutinize/SKILL.md), [sentinel](../source-skills/sentinel/SKILL.md), [unravel](../source-skills/unravel/SKILL.md)) want the **cautious + candid + thorough** profile — prefer the top tier (`opus`), which leans that way, over a lighter tier that may soften findings.
- **Ideation / design dialogue** ([conjure](../source-skills/conjure/SKILL.md)) tolerates the warmer, briefer profiles.
- **Re-verify posture after a model bump.** A new version can shift these values, so when this file's default changes, re-check that the review/verification skills still push back as hard — don't assume a newer model is a drop-in on *behavior*. **Do NOT hardcode the research's per-version numbers** (they go stale); keep the principle. (Anthropic research: anthropic.com/research/claude-values-models-languages.)

## Currency rule (history/planning/orchestration skills)

When a skill picks a model or spawns subagents, and the session is on an older model than the latest available for the task, **suggest the upgrade** (e.g. "You're on an older model — Opus 5 or Fable 5 would handle this better. Switch with `/model`?") and let the user decide. Never switch silently. For spawned subagents, choose the tier that fits the subtask (cheap tier for narrow tasks, top tier for code/review) rather than always inheriting.
