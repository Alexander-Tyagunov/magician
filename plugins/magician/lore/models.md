# Codex model and reasoning guidance

This is the Codex-only model guide used by Magician's generated Codex package. It overrides the
provider-specific `lore/models.md` that remains the source of truth for Claude Code. Keep the two
files separate.

Current as of 2026-08-12. Model availability is account- and surface-dependent, so verify current
OpenAI documentation before changing defaults, saved agents, scheduled tasks, or API integrations.

## Current GPT-5.6 family

| Role | Model | Use it for |
|---|---|---|
| Frontier | `gpt-5.6-sol` | Complex, ambiguous, high-value coding, review, research, computer use, and security work |
| Balanced | `gpt-5.6-terra` | Everyday implementation and tool-heavy work that does not need Sol's full depth |
| Efficient | `gpt-5.6-luna` | Clear, repeatable, high-volume extraction, classification, transformation, and summaries |

`gpt-5.6` is an alias for `gpt-5.6-sol`. In Codex, the default Power setting uses Sol with medium
reasoning. If the host does not offer a requested tier, inherit the session model or choose from the
models the host actually exposes; never invent an unavailable model override.

When source skills describe a top/coding-optimal tier, resolve it to Sol. Resolve a balanced or
everyday tier to Terra, and a cheap narrow tier to Luna. This is a role mapping, not permission to
switch the user's session silently. Suggest a session-model change and let the user decide. For a
spawned agent, set a model only when the host exposes that model and the source workflow explicitly
requires a task-specific tier.

## Reasoning effort in Codex

Use the lowest effort that produces the required result, then raise it only for measured quality
gains:

- **cheap**: `low` for quick, tightly scoped work.
- **ordinary**: `medium`, the balanced starting point.
- **standard/deep**: `high` for difficult multi-step work; `xhigh` for the hardest single-agent work
  when extra depth is worth the latency and usage.
- **maximum**: Max may be available through an app setting. Use it only for exceptional,
  quality-first work and compare it with `xhigh`; do not assume it is accepted by every Codex config
  surface.

Translate source-skill `/effort` references into the active Codex reasoning selector or supported
Codex configuration. The current `config.toml` reference lists `minimal`, `low`, `medium`, `high`,
and `xhigh` for `model_reasoning_effort`; it does not list `max`. Do not write an undocumented value
to config. The API's `reasoning.effort` schema is broader and is not the same configuration surface.

Max and Ultra are different. Max increases single-model reasoning. Ultra coordinates subagents for
work that divides into meaningful independent parts. Most tasks need neither.

For migrations from an older family, keep the current effort as the baseline and also test one
level lower on representative tasks. Do not assume effort levels map exactly between model families.

## Deprecated Codex model cleanup

With ChatGPT sign-in, `gpt-5.2` and `gpt-5.3-codex` are deprecated. `gpt-5.4` and
`gpt-5.4-mini` retire from Codex on 2026-08-31. Replace saved Codex uses of `gpt-5.4` with
`gpt-5.6-terra`, and `gpt-5.4-mini` with `gpt-5.6-luna`. This retirement does not apply to the
OpenAI API or Codex authenticated with an API key; verify API availability separately.

<a id="safety-classifiers-change-which-model-you-end-up-on"></a>

## Safety classifiers change how a run may complete

GPT-5.6 requests can be paused, blocked, or refused by real-time cyber and biology safeguards,
including on legitimate dual-use work. Keep security prompts defensive, authorized, and focused on
review, diagnosis, remediation, or education. Do not import provider-specific claims about a silent
fallback model into Codex; report the behavior actually shown by the host.

## API-only guidance is not Codex config

For direct API integrations, OpenAI recommends the Responses API for reasoning, tool calling, and
multi-turn workflows. GPT-5.6 API requests support `none`, `low`, `medium`, `high`, `xhigh`, and
`max` reasoning effort. Pro mode is `reasoning.mode: "pro"` on the selected GPT-5.6 model, not a
separate model slug. Apply these fields only when editing an API integration, not when configuring a
Magician skill or Codex plugin.

Official references:

- https://learn.chatgpt.com/docs/models
- https://learn.chatgpt.com/docs/config-file/config-reference
- https://developers.openai.com/api/docs/guides/latest-model
- https://developers.openai.com/api/docs/models/gpt-5.6-sol
