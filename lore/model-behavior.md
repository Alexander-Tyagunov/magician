Model behavior — what the Claude 5 generation does differently, and what to stop telling it.

Companion to [models.md](models.md), which covers *which* model and effort level. This file covers *how to prompt it*. Read it before writing or editing any skill prompt, agent definition, or spawn prompt.

The short version: Opus 5, Sonnet 5, and Fable 5 already do several things older models had to be told to do. Instructions that used to add quality now add cost, and a few of them actively subtract quality. Everything below is grounded in Anthropic's per-model prompting guides — re-check them when a new tier lands.

## Anti-patterns — never reintroduce these

**1. Self-verification reminders.** "Double-check your answer", "re-verify before responding", "include a final verification step for any non-trivial task", "use a subagent to verify your own work". Opus 5 and Fable 5 catch and fix their own mistakes without prompting; these compound with the model's own behavior and cause over-verification — real token cost, no quality gain.

*This is not a rule against verification.* Magician's gates stay exactly as they are: [certify](../skills/certify/SKILL.md) demands evidence, [divine](../skills/divine/SKILL.md) and [scrutinize](../skills/scrutinize/SKILL.md) run a **fresh-context verifier subagent** against the findings, [ward](../skills/ward/SKILL.md) requires a red test before green. Those are independent checks with their own context, which Anthropic explicitly recommends over self-critique for long runs. The anti-pattern is telling *one* model to re-check *itself*.

**2. Severity pre-filters in review prompts.** "Only report high-severity issues", "be conservative", "don't nitpick". Opus 5 and Sonnet 5 follow this literally: they investigate just as deeply, find the bugs, then decline to report them. Precision rises, recall falls, and the drop looks like a capability regression when it is a prompt problem. Ask the finder stage for **coverage** with confidence and severity attached, and filter in a separate pass.

**3. Reasoning-echo instructions.** Anything telling the model to echo, transcribe, reproduce, or explain its internal reasoning as response text. On Fable 5 this triggers the `reasoning_extraction` refusal category and elevated fallbacks to another model. If a workflow needs reasoning visibility, read the structured `thinking` blocks.

**4. Forced interim-status scaffolding.** "After every 3 tool calls, summarize progress." Opus 5 and Sonnet 5 narrate progress well on their own — often more than wanted. Describe the cadence and shape you want instead of forcing a counter.

**5. Surfacing a remaining-token countdown *to the model*.** Fable 5 responds to it by suggesting a new session, offering to hand off, or trimming its own work. Magician's status bar is safe — it renders locally and never enters the model's context. Anything that writes a context percentage *into a prompt* is not.

**6. Over-prescriptive skill bodies.** Skills written for the 4.x generation are often too prescriptive for Fable 5 and measurably degrade its output. When a skill enumerates behaviors the model now gets right by default, cut the enumeration and keep the intent.

## Behaviors that now need explicit steering

**Length is prompted, not dialed.** On Opus 5, lowering effort reduces *thinking*, not the visible answer — and default responses run longer than on 4.8. Files written to disk (reports, plans, specs in `.workspace/`) run longer too. Where a skill produces a written deliverable, calibrate it: cover the substance, no filler sections, no redundant summaries. Magician's voice setting (`warrior`/`scribe`/`bard`, see [statusline](../skills/statusline/SKILL.md)) is the user-facing lever for the same thing.

**Delegation needs a ceiling.** Opus 5 and Fable 5 dispatch subagents far more readily than earlier models. That pays off on genuinely independent, sizeable tracks and multiplies cost and wall-clock on small ones. Any skill that can fan out ([orchestrate](../skills/orchestrate/SKILL.md), [weave](../skills/weave/SKILL.md), [divine](../skills/divine/SKILL.md)) should state when delegation is warranted and cap the count — and never spawn an agent to double-check work the model just did itself.

**Scope needs a boundary.** Opus 5 can widen a task, adding steps that weren't requested. Fable 5 at higher effort can tidy or refactor around the change. For narrow work, say so: deliver what was asked at the scope intended, make routine judgment calls, flag a better approach in a sentence and continue rather than quietly transforming the task.

**Sonnet 5 is literal.** It does not generalize an instruction from one item to the next and does not infer requests you didn't make. State the scope ("apply this to every section, not just the first"). Good for pipelines and structured extraction; a trap for loosely worded skill steps.

**Corrections get narrated.** Opus 5 announces its own corrections more than earlier models. Limit that to corrections that change the user's code, conclusions, or decisions; silent fixes for slips that change nothing.

## Long autonomous runs (Fable 5 especially)

- **Turns run long.** A single request on a hard task can run many minutes; autonomous runs extend for hours. Prefer async check-ins (Monitor, background tasks, scheduled wake-ups) over blocking the turn.
- **Ground every progress claim.** Before reporting progress, audit each claim against a tool result from *this session*. Report failures with the output; say plainly when a step was skipped. This is already magician doctrine in [verification.md](verification.md) — it matters more here because Fable 5 is trusted with longer unsupervised stretches.
- **Don't end a turn on a promise.** Deep into a long session Fable 5 occasionally ends with "I'll now run X" and no tool call. If the last paragraph is a plan, a question, or a promise, do the work now.
- **Give the reason, not only the request.** Fable 5 connects a task to relevant context when it knows why the task exists. Spawn prompts that carry intent outperform ones that carry only instructions — see [subagent-context.md](subagent-context.md).

## When the model is older

Everything above is safe on Opus 4.8 and earlier: removing a self-recheck instruction doesn't disable a gate, capping delegation doesn't remove parallelism, and prompting for length works on every tier. Nothing in this file should be turned into a hard requirement on a Claude 5 feature. If a skill needs a genuinely new capability, feature-detect it and no-op when it's absent.
