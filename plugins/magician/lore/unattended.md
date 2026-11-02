Unattended runs: six rules for work that runs with no human present (`/loop` ticks, `/goal` drives, scheduled tasks, cloud sessions with `CLAUDE_CODE_REMOTE` set, CI watchers). A tick cannot ask a question. So each rule below replaces a question with a file, a check or a limit.

1. **Bookmark the last processed item.**
   - Keep one bookmark file per loop under `.workspace/local/`, for example `.workspace/local/bookmarks/<loop-name>.json`.
   - Store the timestamp or the head SHA of the last item you processed. Store the item key with it (`owner/repo#12`, a run ID).
   - Read the bookmark at the start of each tick. Process only items newer than the bookmark.
   - An absent bookmark means a first run. Record a baseline and act on nothing older.
   - A skill that already has a state file keeps it. `/divine` monitor mode uses `${MAGICIAN_DATA:-$HOME/.local/share/magician}/divine-monitor.json` as its bookmark.

2. **A failed read is not "quiet".**
   - Every tick report has one line per source that you could not read: `could not read <source>: <error>`.
   - "Nothing new" is a valid result only when every read succeeded.
   - Do not move the bookmark past a source you could not read.

3. **Re-check live state before every outward action.**
   - Before a post, a comment, a push or a merge, read the target again in the same tick.
   - Stop the action when the state changed since the read that triggered it. Examples: the PR closed, the head SHA moved, a human already replied, a check went green.

4. **Record only after the platform confirms.**
   - Update the bookmark or the state file after the platform returns success (exit 0, an ID, a URL).
   - On a failed or unconfirmed write, leave the record unchanged. The next tick then retries.

5. **Re-read preferences each tick.**
   - Read `.workspace/local/prefs.md` at the start of every tick. Do not cache it from the first tick.
   - A preference the user changed mid-loop (`disableGit`, a paused integration) applies from the next tick.

6. **Least privilege and a spend cap.**
   - Use a read-only token when the loop only reads. Use a write token only for the one write the loop exists for.
   - Cap spend at 3 to 5 times the cost of one normal run. Use `--max-budget-usd <amount>` for `claude -p`, or the platform budget for a scheduled task.
   - A capped run pauses, and a paused run looks like silence. Say in the loop setup message that a cap exists and what it is. When a tick stops at the cap, write `stopped: spend cap <amount> reached` as its last line.

Where this applies: [divine monitor mode](../skills/divine/references/monitor-mode.md), the [/seal CI loop](../skills/seal/references/ci-loop.md), the [/deploy CI watch](../skills/deploy/SKILL.md) and the [maintenance bands](../skills/deploy/references/control-bands.md). Verification still applies to every tick: [verification.md](verification.md).
