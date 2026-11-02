# Report format

Mirror the structure of a strong human review. First the count line, then a clear verdict, then merge gates, then findings by severity, and last an honest list of candidates you dropped. Each finding has a location, an **impact**, a **fix**, and **traceability** to the requirement it touches.

## In-chat report template

```
## Review — <change title> (<depth> review)

N Important, N Nit, N Pre-existing; N fixed, N closed with reason.

Reviewed the <areas> against <grounding: PRD/spec/stories/docs, or "the diff + repo conventions">.
Findings were cross-checked before reporting; dropped candidates are listed at the end.

**Overall:** <1–3 sentence verdict — is it sound? what's the headline? is it mergeable after fixes?>

Scope: <N files, +adds/−dels, base ← head; skipped per REVIEW.md: <paths or none>>

---

### 🔴 Merge gates / CI
<failing required checks. For each: what fails, whether it's a real blocker or an infra flake, what unblocks it. Omit the section if CI is green.>

### 🔴 Critical
N. **[Important]** <title> — `file:line`
   <what's wrong>. Impact: <consequence / requirement violated>.
   Fix: <concrete remediation>.

### 🟠 High
…

### 🟡 Medium
…

### 🟢 Low / nits
- **[Nit]** `file:line` — <one-liner>
<at most the REVIEW.md nit cap; then "N more nits withheld">

### Pre-existing
- **[Pre-existing]** `file:line` — <one-liner; code the change did not touch, reported once, not counted against the author>

### ✅ Dropped (false positives)
<candidates considered and refuted in verification, one line each + why — e.g. "X looked unguarded but the caller validates at Y.">

### 💥 Blast radius — affected services & infrastructure  (Deep/Exhaustive)
<downstream consumers of changed contracts/APIs, data migrations, infra/config touched, and rollout/rollback risk. State "contained to this repo" if nothing reaches beyond it.>

### Requirement traceability  (Deep/Exhaustive, when ACs/DoD exist)
| Requirement / AC | Status | Note |
|---|---|---|
| <AC / DoD item> | ✅ met / ⚠️ partial / ❌ gap | <finding ref> |
```

Rules:
- The **count line** is the first line of the report, directly under the heading and before the verdict. The Completion Signal at the end repeats it; it never replaces it. The verdict and the findings follow it. Before remediation the second half reads `0 fixed, 0 closed with reason`. Fill it in last: after deduplication and verification, count the findings you actually list under each tag, and make every number match that list. A candidate the verification stage dropped is not counted.
- Every listed finding, each Nit and Low one-liner included, carries exactly one **tag** (Important / Nit / Pre-existing), written first on its line as `**[Important]**`, `**[Nit]**` or `**[Pre-existing]**` per [`lore/review.md`](../../../lore/review.md). A finding without `file:line` is dropped. A coverage gap cites the lines of the untested code (`client/fetch.py:17-24`), never a whole file or nothing.
- **Number** Critical/High/Medium findings continuously so they are easy to reference in discussion and PR comments.
- Every finding states **impact**, not just the defect — *why it matters* is what makes a review actionable.
- Cite **`file:line`** precisely, and link to the requirement (PRD §, AC, DoD line, story key) when one exists.
- Keep Low as terse one-liners. Do not pad the report.
- If you capped coverage (large-PR partition, sampling), say so explicitly under Overall.

## Posting to the PR

Only after the explicit Phase 5 gate (publishing on the user's behalf).

**Step 0 — verify the account before any write** (mirror `change-context.md`): check the active `gh`/`glab` account against the repo's org. Switch if it is wrong (for example the work account for a work-org repo), and restore afterward. The write commands below assume this check passed. Do not skip it because you jumped to the snippet.

**Summary review (body only):** write the report to `.workspace/local/divine-review.md` (gitignored scratch space), then:
```bash
# GitHub — choose ONE event. Prefer COMMENT unless the user asks to approve/request-changes.
gh pr review <N|url> --comment --body-file .workspace/local/divine-review.md
# gh pr review <N|url> --request-changes --body-file .workspace/local/divine-review.md   # only if user says so
```
```bash
# GitLab — pass the report text itself as the message value
glab mr note <N|url> --message "<report text>"
```

**Inline comments** (one per finding, anchored to `file:line`) — GitHub, via the reviews API, batched into one pending review:
```bash
gh api repos/{owner}/{repo}/pulls/{N}/reviews -f event=COMMENT \
  -f body="<overall summary>" \
  -F 'comments[][path]=src/Foo.java' -F 'comments[][line]=42' -F 'comments[][body]=<finding>' \
  # …repeat the three comments[][] fields per finding
```
Show the user the exact body / comment set before sending. Default to a single `--comment` review unless they explicitly want `--request-changes` or `--approve`. Never `--approve` on the user's behalf without an explicit instruction to approve.

After posting, report the review URL.

For a large review the user will want to circulate, you can also publish the severity-ranked report as a Claude Code **Artifact**. That is a live page on claude.ai. It updates in place as findings are remediated, and the team can **co-edit together** (multiplayer, Team/Enterprise plans). Offer it, and do not create it unprompted.

A **public** link (anyone with the URL can view it) is an outward sharing action. **Confirm it explicitly, and keep the report account-private by default. Never expose a review that quotes proprietary code, secrets, or unremediated vulnerability detail to a public link.**
