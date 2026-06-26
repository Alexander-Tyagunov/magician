# Monitor mode — unattended review via /loop

Polls one or more repos on an interval and reviews new open PRs/MRs **without a human in the loop**. Because no one is there to answer gates, depth and post-policy are pre-set when the loop starts, the run is idempotent, and it never changes code.

## Setup (the user starts a loop)

Natural language:
> `/loop 1h review open PRs in acme/api at standard depth and post a comment`

Explicit:
> `/loop 1h /divine monitor acme/api --depth standard --post`

Parse from the loop prompt and remember for every tick:
- **repo(s)** — one or more `owner/repo`.
- **depth** — Quick / Standard / Deep / Exhaustive (default **Standard**).
- **post policy** — post the review to the PR/MR, or report only (default **report only**; posting happens only if the user asked for it when starting the loop — that is the pre-authorization).

## Each tick

1. **List open PRs/MRs** for each repo:
   - GitHub: `gh pr list --repo <owner/repo> --state open --json number,headRefOid,title,url,isDraft,updatedAt`
   - GitLab: `glab mr list -R <owner/repo> --output json` (fields: iid, sha, title, web_url, draft)
2. **Skip** drafts and anything already reviewed at its current head. Track state in `$CLAUDE_PLUGIN_DATA/divine-monitor.json` — a map `"owner/repo#number" -> last-reviewed head SHA`. Review only when the entry is missing or the head SHA changed (new commits since last review).
3. For each new/updated PR/MR, run the normal **Phases 0, 2, 3, 4** at the pre-set depth. Do **not** call AskUserQuestion (unattended) — use the pre-set depth. If grounding genuinely needs the user, note the gap and proceed best-effort.
4. **Deliver per policy:** if posting is enabled, post the review (Phase 5 commands, with the correct account for the repo's org); otherwise collect the report into the loop's output.
5. **Record** the reviewed head SHA in the state file.

## Hard rules in monitor mode

- **Never implement or push fixes** (Phase 6 is interactive only). Monitor mode reviews — and at most posts review comments — nothing else.
- **Idempotent:** the SHA map prevents duplicate reviews/comments on an unchanged PR. Re-review only on new commits.
- **Correct account** per repo org for any read or post.
- **Bounded output:** end each tick with a short summary — repos polled, PRs found, reviewed (verdict + link), skipped (already current) — so the loop log stays readable.

## Stopping

Monitor mode runs as long as the `/loop` runs; the user stops it by ending the loop. Nothing persists beyond the SHA state file, which is safe to delete to force a full re-review.
