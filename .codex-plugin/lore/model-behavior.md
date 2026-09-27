# Codex prompting guidance for GPT-5.6

This Codex-only guide overrides the provider-specific `lore/model-behavior.md` in the generated
Codex package. Preserve the source skills' requirements, safety gates, test discipline, and output
contracts, but translate provider-specific model claims through this file.

## Keep prompts lean

- State each instruction once. Do not repeat the same approval, verification, or style rule in
  several sections.
- Expose only tools relevant to the task, with concise input, output, and error descriptions.
- Keep examples that encode a product requirement or fix a measured failure. Remove decorative or
  redundant examples one group at a time and rerun the same tests or evals.
- Watch prompt growth in long workflows. Repeated instructions and tool descriptions compound over
  time.

Do not mechanically shorten a working skill. Simplify one behavior at a time and retain every human
gate, safety boundary, completion criterion, and evidence requirement.

## Define authority once

GPT-5.6 can continue multi-step work proactively. Give it one compact authorization policy:

- Answer, explain, review, diagnose, and plan requests authorize inspection and reporting, not
  implementation.
- Change, build, and fix requests authorize in-scope local edits plus relevant non-destructive
  validation.
- External writes, destructive actions, purchases, and material scope expansion require
  confirmation.

Do not scatter repeated "ask first" language through a skill; that can create needless pauses for
safe local reads, edits, and tests. A single clear boundary plus the workflow's real side-effect
gates is enough.

## Ask for outcomes, constraints, and evidence

Provide the goal, relevant context, hard constraints, success criteria, required evidence, and
output shape. Do not add ritual instructions to "think harder" or narrate hidden reasoning. Increase
the supported reasoning setting when the task actually warrants more depth.

GPT-5.6 is concise by default. Avoid stacking broad brevity instructions. When output must be short,
say which facts, decisions, caveats, evidence, and next actions must remain, then trim repetition and
optional background first.

## Verification remains external and observable

Do not replace runnable tests, type checks, linters, builds, browser checks, or fresh-context review
with self-reassurance. Magician's verification gates are observable tool evidence, not repeated
instructions for one model to praise or re-read its own answer.

## Delegate only by task shape

Use Ultra or explicit subagents only when the work has substantial, independent lanes that can run
in parallel. Keep small or tightly coupled work in one context. Set a model or effort override only
when the host exposes it and the source workflow explicitly calls for task-specific routing.

## Provider override rule

When an immutable source skill names provider-specific tiers, aliases, effort commands, safety
fallbacks, or prompting behavior, translate the intent using this guide and `models.md`. Never carry
those literal names or settings into Codex instructions, configuration, or spawned-agent prompts.

Official references:

- https://developers.openai.com/api/docs/guides/latest-model
- https://learn.chatgpt.com/docs/models
