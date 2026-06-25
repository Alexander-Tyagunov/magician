Subagent & handoff context contract — prevent context loss when work passes to another agent.

Subagents and agent-team teammates do NOT inherit the conversation history. They load project files (CLAUDE.md, MCP, skills) and ONLY the prompt you give them. Anything in your head that isn't in the spawn prompt is lost. The same applies when one skill hands off to the next stage.

## Rule: every spawn prompt is self-contained

Before dispatching a subagent (or chaining to the next skill), include everything it needs to do the task without asking:

1. **Goal** — the specific deliverable, in one or two sentences.
2. **Scope** — exact files/paths/modules in play (and what is out of scope).
3. **Inputs** — the spec, plan task, diff, or findings it must act on. Pass the content or an exact readable path (e.g. `.workspace/shared/specs/<feature>.md`, `.workspace/shared/plans/<plan>.md`), never "the spec we discussed".
4. **Constraints** — conventions, tech/lore in use, things it must not touch (deny rules), the definition of done.
5. **Return contract** — the exact STATUS / output format expected back.
6. **Model/effort** — pick the tier and effort that fit the subtask (see [models.md](models.md)).

## Rule: persist shared state, reference it by path

Pipeline stages (conjure → blueprint → orchestrate → certify → scrutinize → seal) communicate through `.workspace/shared/` artifacts, not memory. Each stage writes its output to a known path and the next stage reads it. When a stage completes, state in its handoff message which artifact it produced and where, so the next stage (or a fresh session after compaction) can pick up with zero loss.

## Rule: verify the handoff

If a subagent returns NEEDS_CONTEXT, treat it as a context-completeness bug in your spawn prompt — add the missing input and re-dispatch, don't guess on its behalf.
