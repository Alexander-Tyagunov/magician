# Report format

Mirror the structure of a strong human review: a clear verdict, merge gates first, then findings by severity — each with location, **impact**, **fix**, and **traceability** to the requirement it touches — and an honest list of candidates you dropped.

## In-chat report template

```
## Review — <change title> (<depth> review)

Reviewed the <areas> against <grounding: PRD/spec/stories/docs, or "the diff + repo conventions">.
Findings were cross-checked before reporting; dropped candidates are listed at the end.

**Overall:** <1–3 sentence verdict — is it sound? what's the headline? is it mergeable after fixes?>

Scope: <N files, +adds/−dels, base ← head>

---

### 🔴 Merge gates / CI
<failing required checks. For each: what fails, whether it's a real blocker or an infra flake, what unblocks it. Omit the section if CI is green.>

### 🔴 Critical
N. **<title>** — `file:line`
   <what's wrong>. Impact: <consequence / requirement violated>.
   Fix: <concrete remediation>.

### 🟠 High
…

### 🟡 Medium
…

### 🟢 Low / nits
- `file:line` — <one-liner>

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
- **Number** Critical/High/Medium findings continuously so they're easy to reference in discussion and PR comments.
- Every finding states **impact**, not just the defect — *why it matters* is what makes a review actionable.
- Cite **`file:line`** precisely; link to the requirement (PRD §, AC, DoD line, story key) when one exists.
- Keep Low as terse one-liners; don't pad the report.
- If you capped coverage (large-PR partition, sampling), say so explicitly under Overall.

## Posting to the PR

Only after the explicit Phase 5 gate (publishing on the user's behalf).

**Step 0 — verify the account before any write** (mirror change-context.md): check the active `gh`/`glab` account against the repo's org, switch if it's wrong (e.g. the work account for a work-org repo), and restore afterward. The write commands below assume this check has passed — do not skip it just because you jumped to the snippet.

**Summary review (body only):** write the report to a temp file, then:
```bash
# GitHub — choose ONE event. Prefer COMMENT unless the user asks to approve/request-changes.
gh pr review <N|url> --comment --body-file /tmp/divine-review.md
# gh pr review <N|url> --request-changes --body-file /tmp/divine-review.md   # only if user says so
```
```bash
# GitLab
glab mr note <N|url> --message "$(cat /tmp/divine-review.md)"
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

For a large review the user will want to circulate, you can also publish the severity-ranked report as a Claude Code **Artifact** — a live page on claude.ai that updates in place as findings are remediated. Offer it; don't create it unprompted.
