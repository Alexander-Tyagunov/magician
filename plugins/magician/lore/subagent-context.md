Subagent & handoff context contract — prevent context loss when work passes to another agent.

Subagents and agent-team teammates do NOT inherit the conversation history. They load project files (CLAUDE.md, MCP, skills) and ONLY the prompt you give them. Anything in your head that isn't in the spawn prompt is lost. The same applies when one skill hands off to the next stage.

## Rule: every spawn prompt is self-contained

Before dispatching a subagent (or chaining to the next skill), include everything it needs to do the task without asking:

1. **Goal** — the specific deliverable, in one or two sentences.
2. **Scope** — exact files/paths/modules in play (and what is out of scope).
3. **Inputs** — the spec, plan task, diff, or findings it must act on. Pass the content or an exact readable path (e.g. `.workspace/shared/specs/<feature>.md`, `.workspace/shared/plans/<plan>.md`), never "the spec we discussed". If `.workspace/local/session-state.md` exists, tell the agent to read it first for the current session capsule (goal, decisions, blockers, artifact paths).
4. **Constraints** — conventions, tech/lore in use, things it must not touch (deny rules), the definition of done.
5. **Return contract** — the exact STATUS / output format expected back.
6. **Model/effort** — pick the tier and effort that fit the subtask (see [models.md](models.md)).

## Rule: persist shared state, reference it by path

Pipeline stages (conjure → blueprint → orchestrate → certify → scrutinize → seal) communicate through `.workspace/shared/` artifacts, not memory. Each stage writes its output to a known path and the next stage reads it. When a stage completes, state in its handoff message which artifact it produced and where, so the next stage (or a fresh session after compaction) can pick up with zero loss.

## Rule: keep context small — pointers over content

Context is a finite resource; protect it for yourself and every actor downstream.
- For locating code, **default to `kg query` / `kg blast` / `kg neighbors`** whenever the repo has an index — it returns exact `file:line` in far fewer tokens and is shared across agents. Use broad `grep` / whole-file reads only for non-code or literal-string scans. Never paste whole files into the transcript; reference code by `path:line`.
- Persist durable facts (decisions, user prefs, gotchas) to `.workspace/shared/decisions/` or `/chronicle learn`, not the chat.
- Offload heavy exploration to subagents (clean context windows) and have them return a distilled summary, not raw dumps.
- The plugin warns when context grows (60/80/92%) and captures a resume capsule before any compaction — when warned, offload to an artifact and/or `/compact` before the next big step. See [the chronicle context-mgmt reference](../source-skills/chronicle/references/context-mgmt.md).

## Rule: subagents run in the background — use it, don't fight it

Current Claude Code runs spawned subagents in the **background by default**: you can keep working while they run, and their permission prompts now surface in *your* main session (they no longer auto-deny). So:
- Fan out, then keep doing useful work and collect results as they land. Ask to "run in the foreground" only when the next step genuinely blocks on a subagent's output.
- Subagents can spawn their own subagents (**nested, up to ~5 levels**) — an orchestrator-worker where a wave lead further fans out is fine; keep every level's prompt self-contained per the rules above.
- You rarely need to pre-authorize tools now (prompts surface to you), but the plugin's global `Bash(kg:*|jira:*|confluence:*|ctx:*)` allows keep the common CLIs prompt-free anyway.

## Rule: verify the handoff

If a subagent returns NEEDS_CONTEXT, treat it as a context-completeness bug in your spawn prompt — add the missing input and re-dispatch, don't guess on its behalf.

## Note: Claude Code Artifacts (shareable live pages)

Distinct from the `.workspace/` artifacts above: a Claude Code **Artifact** is a live page published to claude.ai that updates as work proceeds. Current capability — an Artifact can be **shared via a public link** (anyone with the URL can view it), **co-edited by a team** (multiplayer, Team/Enterprise plans), and created from Claude Tag. Skills that produce shareable output (`/conjure`, `/divine`, `/scrutinize`, `/autopsy`, `/magic`, `/accelerate`) **offer** it, never auto-create it, and treat **publishing to a public link as an outward, permission-changing action**: confirm explicitly, keep artifacts account-private by default, and never expose secrets or proprietary/internal content to a public link.
