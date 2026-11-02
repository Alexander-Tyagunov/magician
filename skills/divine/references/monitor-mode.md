# Monitor mode — unattended review via /loop

Watches one or more repos and reviews new open PRs/MRs **without a human in the loop**, on a `/loop` schedule. No one is there to answer gates. So depth and post policy are pre-set when the loop starts, the run is idempotent, and it never changes code.

## Setup (the user starts a loop)

Natural language:
> `/loop 1h review open PRs in acme/api at standard depth and post a comment`

Explicit:
> `/loop 1h /divine monitor acme/api --depth standard --post`

**Omit the interval** to self-pace (`/loop /divine monitor acme/api …`): Claude picks the next tick — wider on quiet repos, tighter on active ones (between 1 min and 1 h). A tick runs at an interval, so a new PR is reviewed on the next tick rather than the moment it opens.

Parse from the loop prompt and remember for every tick:
- **repo(s)** — one or more `owner/repo`.
- **depth** — Quick / Standard / Deep / Exhaustive (default **Standard**).
- **post policy** — post the review to the PR/MR, or report only (default **report only**). A post happens only if the user asked for it when the loop started. That is the pre-authorization, and later ticks post without a further question.

## Each tick

1. **List open PRs/MRs** for each repo:
   - GitHub: `gh pr list --repo <owner/repo> --state open --json number,headRefOid,title,url,isDraft,updatedAt`
   - GitLab: `glab mr list -R <owner/repo> --output json` (fields: `iid`, `sha`, `title`, `web_url`, `draft`)
2. **Skip** drafts and anything already reviewed at its current head. Track state in the monitor-mode state file `${CLAUDE_PLUGIN_DATA}/divine-monitor.json` (magician's plugin data folder): a map `"owner/repo#number" -> last-reviewed head SHA`. Read it at the start of the tick. An absent file means nothing was reviewed yet. Review only when the entry is absent or the head SHA changed (new commits since the last review).
3. For each new or updated PR/MR, run the normal **Phases 0, 2, 3, 4** at the pre-set depth. Read `REVIEW.md` first when the repository has one. Dispatch the lenses fresh, because a loop tick has no diff in context to fork from. Do **not** call AskUserQuestion (unattended). Use the pre-set depth. If grounding needs the user, note the gap and proceed best-effort.
4. **Deliver per policy:** if the post policy is on, post the review (Phase 5 commands, with the correct account for the repo's org). Otherwise collect the report into the loop's output. The post commands are not pre-approved. Claude Code shows its normal permission prompt for them unless the session's permission mode allows them.
5. **Record** the reviewed head SHA in the state file. Edit the JSON map, and create the file if it is absent.

## Hard rules in monitor mode

Monitor mode follows the six unattended rules in [lore/unattended.md](../../../lore/unattended.md). In this mode they mean:
- The SHA state file is the bookmark.
- A repo that `gh` or `glab` could not list gets a `could not read <owner/repo>: <error>` line. A failed list never counts as "no new PRs".
- Before a post, read the PR again. Skip the post when the PR closed or its head SHA moved since the review.
- Record the head SHA only after the post command returned success, or after the report was collected.
- Re-read `.workspace/local/prefs.md` at the start of each tick.
- Use a read-only token unless the post policy is on. State the spend cap when the loop starts.

- **Never implement or push fixes** (Phase 6 is interactive only). Monitor mode reviews — and at most posts review comments — nothing else.
- **Idempotent:** the SHA map prevents duplicate reviews/comments on an unchanged PR. Re-review only on new commits.
- **Correct account** per repo org for any read or post.
- **Bounded output:** end each tick with a short summary — repos polled, PRs found, reviewed (verdict + link), skipped (already current) — so the loop log stays readable.

## Stopping

Monitor mode runs as long as the `/loop` runs. The user stops it by ending the loop. Nothing persists beyond the SHA state file, which is safe to delete to force a full re-review.
