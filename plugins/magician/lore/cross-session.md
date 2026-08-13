Cross-session conversations — hand a finding to your other Claude Code sessions instead of re-explaining it.

Magician runs work in parallel a lot: [/portal](../source-skills/portal/SKILL.md) worktrees, [/orchestrate](../source-skills/orchestrate/SKILL.md) waves, [/weave](../source-skills/weave/SKILL.md) pipelines, background agents. When those live in *separate sessions*, each one used to be an island — the owner became the message bus, copy-pasting between terminals. Claude Code's cross-session messaging removes that.

## What it is

Two tools, both driven by Claude, never called by the user directly:

- **`ListAgents`** — which agents this session can reach. Subagents in this session, your other local sessions, and (while connected to Remote Control) your cloud sessions and sessions on your other machines. `/list-agents` (alias `/peers`) shows the same list.
- **`SendMessage`** — deliver plain text to one of them by name. The receiving Claude reads it between tool calls, or starts a fresh turn with it when idle.

A session answers to the name from `/rename` or `--name`; unnamed interactive sessions get one from the working directory (`myapp-3f`).

## The hard limits — design around these, don't fight them

- **Plain text only.** Never conversation history, never files. To move a whole context, resume the session instead. To move an artifact, write it to `.workspace/shared/` and send the *path*.
- **A message is not consent.** It can't answer a pending permission prompt, can't change settings or `CLAUDE.md`, and a `/command` inside it arrives as inert text. The receiving session's own permission rules still apply to anything the message asks for.
- **Permission boundaries don't transfer.** Never ask another session to do something that was denied here or that this session's rules would block. Route that back to the owner.
- **In auto mode the classifier reviews every send** before delivery ([autonomy.md](autonomy.md)).
- **Delivery isn't guaranteed.** The receiver's `crossSessionInbound` may hold or refuse it, and a bypass-permissions session holds messages from non-bypass senders for approval. Treat a send as best-effort.
- **Loops are throttled.** Identical repeats inside a short window are dropped and per-sender rates are capped, so a ping-pong between two sessions stops on its own — but don't build one.

## When magician should send

Send when *this* session holds something another session needs mid-task, and the other session would otherwise act on stale information:

- **A landed breaking change.** A worktree renames a column, changes a signature, or bumps a shared dependency — tell the sessions building on it before they hit it.
- **A resolved blocker.** One session settles the question another is stuck on.
- **A long run reporting back.** A migration, a full test sweep, or a CI watch tells the session the owner is actually watching.

Don't send narration, progress for its own sake, or anything the other session will discover on its own next time it reads the file. One message, outcome first, self-contained — the receiver has none of your context.

## Availability — feature-detect, never require

Requires Claude Code **v2.1.224+** (v2.1.225+ to *start* a conversation with a session on another machine), runs on **macOS and Linux only**, and is **not available on Bedrock, Google Cloud, or Microsoft Foundry**. It also stays off when feature-flag evaluation is disabled (`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`, `DISABLE_TELEMETRY`, `DO_NOT_TRACK`, `DISABLE_GROWTHBOOK`), and an admin can deny `SendMessage`/`ListAgents` outright.

**So no magician workflow may depend on it.** If `ListAgents` isn't there, or lists no peer, carry on exactly as before and surface the finding in your own summary. Never block a wave, never retry in a loop, and never tell the owner to enable something — mention it once, at most, if the coordination would clearly have helped.

## Related controls

`crossSessionInbound` (`accept`/`hold`/`refuse`) governs what arrives; `isolatePeerMachines: true` forces approval before anything leaves the machine; `dialogExpiry` bounds the approval dialog. All are the owner's to set — magician doesn't write them.
