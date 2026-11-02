Review dialect: the shared rules for `/divine`, `/scrutinize` and every lens agent. It follows the pipeline Anthropic describes for Claude Code's own review. `REVIEW.md` at the repository root overrides the defaults here. `/almanac` scaffolds it from `skills/divine/references/review-md-template.md`.

Findings:
- Every finding carries a tag next to its severity: `Important` (fix or close with a reason), `Nit` (never blocks), `Pre-existing` (not caused by this change, report once, do not count it against the author).
- Every finding names `file:line` and its impact. No location, no finding.
- Report at most the nit cap (default 5). Say how many nits you withheld.
- Risk tier comes from what the change touches, never from who wrote it. A High-tier change (auth, payments, migrations, CI files, secrets) gets the Deep depth and a fresh verification stage.
- The count line is the first line of the report summary. The findings follow it: `3 Important, 5 Nit, 2 Pre-existing; 3 fixed, 0 closed with reason.`

Approval:
- An agent's approval never counts as a human approval. A lens verdict, a gatekeeper GO or a `/divine` "Overall: approve" is evidence for the human, not a sign-off.
- An approval binds to one commit, the head SHA it was given on. A new commit after the approval needs a new approval.
- Risk tiers: Low is docs, comments or tests only. Medium is application logic, a shared or public interface, shared data or a dependency bump. High is auth, payments, migrations, CI files, secrets, or a change with no easy rollback. The tiers in `REVIEW.md` win when it exists.
- Human approvals per risk tier: Low 0, Medium 1, High 2. `REVIEW.md` can raise the numbers. It cannot set an agent as an approver.

Rounds:
- Remediation runs at most three rounds. Round 2 and round 3 review only the diff since the previous round.
- Keep a round ledger at `.workspace/shared/diffs/<ref>-rounds.md`. Read it before each round. Never repeat a finding an earlier round fixed or closed.
- Every `Important` finding ends as fixed or as closed with a reason.

Dispatch:
- A small diff (3 files or fewer, 300 changed lines or fewer) dispatches no lens. A High-tier change dispatches its lenses fresh at any size. Each lens runs in the main loop with `agents/<lens>.md` as a checklist (`lore/fold-first.md`).
- Above that, fork the lenses (`subagent_type: "fork"`) when the diff is already in context and small (about 40k tokens or less). Dispatch fresh `magician:<lens>` agents otherwise.
- The verification stage is fresh at Standard depth and deeper. Only a Quick review of a small diff verifies in the main loop, and the report says so. A fork carries the author's framing, and `lore/verification.md` demands fresh evidence.
- A fork does not load the agent file and has no memory, so the fork prompt names the lens and points to `${CLAUDE_PLUGIN_ROOT}/agents/<lens>.md`.

Memory and fixes:
- `reviewer`, `sentinel` and `simplifier` keep project memory. A finding class is recorded only after it recurs twice. The agent proposes a lint rule or a `CLAUDE.md` line through the Obstacles `NEXT` field. The memory folder `.claude/agent-memory/` is tracked by git by default.
- Parallel fixes for several independent `Important` findings run `fixer` with `isolation: "worktree"` on the call and get a branch name back. A single fix runs in place.

Platform surfaces (`/code-review`, `claude ultrareview --trust-workspace`, the `@claude review` GitHub flow) are alternatives `/divine` can recommend. They run under the session's permission settings.

Deep dive for the ledger format, the fork rule, the memory rule, worktree fixes and the platform surfaces — read `lore/deep/review.md#{dialect,round-ledger,fork-or-fresh,review-md,reviewer-memory,fixer-worktree,platform-surfaces}`
