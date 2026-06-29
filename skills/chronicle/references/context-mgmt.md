# Context self-management — internals & honest limits

Magician treats the conversation context as a finite resource (per Anthropic's context-engineering guidance): track it, keep it small, and make compaction lossless. This is driven by the bundled **`ctx`** CLI and the existing hooks — mostly automatic; `/chronicle` exposes the manual surface.

## What runs automatically (no command needed)

- **Size tracking** — the `UserPromptSubmit` hook (`pattern-detect.sh`) calls `ctx hook`, which parses the transcript's **latest assistant `usage`** (`input + cache_read + cache_creation` = the real occupancy the model just saw) and warns once per band: **60%** (soft — offload soon), **80%** (firm — consider `/compact` or offload), **92%** (urgent). One warning per band per session, so no per-turn spam.
- **Resume capsule** — the `PreCompact` hook (`pre-compact.sh`) calls `ctx capsule`, writing a structured capsule (active goal, open threads, recent commits/decisions, changed files, `.workspace/shared/` artifact **paths**, recent learnings) to `~/.local/share/magician/projects/<project-hash>/capsule.md` and arming re-injection. The **next prompt** (`pattern-detect.sh` → `ctx hook`) re-injects it after a mid-session compaction; **SessionStart** re-injects it on `--resume`/`--continue` (fresh < 30 min, same cwd), then marks it consumed.
- **Learning capture** — the `Stop` hook (`chronicle-stop.sh`) calls `ctx learn --from-git`, distilling decision-phrased commit subjects into the per-project learnings store. SessionStart surfaces the last 3 under a `PROJECT MEMORY` header.
- **Offload nudges** — `access-tracker.sh` nudges once on a large code read (use `kg query` for the lines); `lore/subagent-context.md` carries the standing rule (pointers over pastes).

## The `ctx` CLI (what `/chronicle` calls)

```
ctx pct --transcript <path>                  # current context % (real tokens; ~approx fallback)
ctx capsule --session <id> --transcript <p>  # build+save capsule, arm re-injection  (hooks use this)
ctx resume [--on-start] [--keep]             # print the capsule (--keep = don't consume)
ctx learn --from-git                         # extract decisions from commits → project store
ctx learn --list [--n 3]                     # recent project learnings
ctx learn --add "<fact>" [--global]          # record a learning (project, or promote to references.md)
ctx consolidate                              # show recurring learnings → promotion candidates
```

Storage: `~/.local/share/magician/projects/<project-hash>/` (capsule + `learnings.jsonl`); band state at `~/.local/share/magician/ctx/<session>.json`. `project-hash` = md5 of cwd (matches `session-start.sh`). Override the root with `MAGICIAN_HOME`; the context window assumption with `CTX_MAX` (default 200000).

## Honest limits (designed around — never claim otherwise)

1. **No live token count** via any plugin API. We parse the transcript's latest `usage` — accurate but one turn stale. If parsing fails, we fall back to `bytes/4`, tagged `~approx`.
2. **Cannot force, schedule, or steer compaction.** `PreCompact` can only *block*; it cannot inject or add context. Only the user (`/compact`) or the auto-threshold compacts. We warn early and capture a capsule so loss is impossible — we do not claim to compact for you.
3. **Cannot know the exact auto-compact threshold** (undocumented). We warn conservatively (60/80/92%) so you act before the harness does.
4. **Cannot inject context into a running subagent.** Subagents get only their spawn prompt — so the capsule doubles as `.workspace/local/session-state.md`, and the spawn template ([lore/subagent-context.md](../../../lore/subagent-context.md)) tells every actor to read it first. Pointer, not push.

## Keeping context small (the standing playbook)

- Prefer `kg query` + `Read(file:line)` over pasting whole files.
- Persist durable facts via `/chronicle learn` (or `.workspace/shared/decisions/`), not the transcript.
- Offload heavy exploration to subagents (clean context windows; they return distilled summaries).
- When a band warning fires, offload to an artifact and/or run `/compact` (with a focus instruction) before the next big step.
- Add a `# Compact instructions` section to your project `CLAUDE.md` so the built-in compaction always preserves what matters (it survives compaction; `PreCompact` hooks cannot steer it).
