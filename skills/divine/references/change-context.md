# Change context — what changed and why

A review is only as good as its grasp of the change. Establish full context before dispatching any reviewer. Never review a diff in isolation from its intent.

## 1. Resolve the target

From `$ARGUMENTS` or the user's message, determine what to review:

| Target | Signal | How to fetch |
|---|---|---|
| **GitHub PR** | a `github.com/.../pull/N` URL, "PR #N", "this PR" | `gh` (below) |
| **GitLab MR** | a `gitlab.*/.../merge_requests/N` URL, "MR !N", "this MR" | `glab` (below) |
| **Branch / range** | a branch name, "review my branch", "since main" | `git diff <base>...HEAD` |
| **Working tree** | "my changes", "what I just did", nothing committed yet | `git diff` (+ `git diff --staged`) |

If ambiguous, default to: open PR/MR for the current branch if one exists, else the branch diff vs the default base, else the working tree. State which you chose.

### Account note
For a **GitHub/GitLab repo, use the account that owns it** — follow whatever org/account conventions the user has configured. Check `gh auth status` / the active account first and switch if needed; restore afterward. Reads are safe; any *write* (posting) needs the explicit gate in Phase 5.

## 2. Pull the change

**GitHub (gh):**
```bash
gh pr view <N|url> --json title,body,baseRefName,headRefName,additions,deletions,changedFiles,files,labels,url
gh pr diff <N|url>                              # full diff
gh pr checks <N|url>                            # CI / merge-gate status  ← critical for "merge gates"
gh pr view <N|url> --json reviews,comments      # prior review context (don't repeat resolved points)
```
**GitLab (glab):**
```bash
glab mr view <N|url>
glab mr diff <N|url>
glab ci status            # or: glab mr view --json | jq '.pipeline'
```
**Branch / working tree:**
```bash
git merge-base --fork-point <base> HEAD   # find the true base
git diff <base>...HEAD --stat && git diff <base>...HEAD
git diff && git diff --staged            # working tree
```

For very large diffs, also read the **full current contents** of the most-changed files (a diff hides surrounding code that a finding may depend on).

## 3. Capture the intent

The PR/MR **description** and **linked tickets** tell you what the change is *supposed* to do — without them you can only check the code against itself, not against requirements. Gather:

- PR/MR **title + body**; any "what/why/testing" sections.
- **Linked issues / tickets** (issue keys like `ABC-123`, `Closes #N`). Pull the acceptance criteria / DoD via the **`magician:jira`** skill (or an issue-tracker MCP / `gh issue` / `glab issue`); pull linked specs / design docs via **`magician:confluence`**. Both run one-time setup if not configured — but **skip a service the user has opted out of** ([lore/integration-prefs.md](../../../lore/integration-prefs.md)); don't suggest setup for it. The AC/DoD become **traceability targets** in the report (does the code satisfy each AC?). If none is reachable, ask the user to paste the AC/DoD or derive provisional ones from the PR/MR body, and note in the report where traceability couldn't be grounded rather than omitting it.
- In-repo intent: `.workspace/shared/specs/`, `.workspace/shared/research/` (from `/magic`), design docs, ADRs, RFCs, `CHANGELOG`.

## 4. CI / merge gates

Read CI status (commands above). A failing required check is a **🔴 Merge gate** in the report. Distinguish a real blocker (schema check needs approval, failing test) from an infra flake (auth/checkout failure) — say which, and don't present a flake as a code defect.

## 5. Conventions

Skim `CLAUDE.md`, linter/formatter config, and a couple of neighboring files so findings match house style rather than your defaults. Pass the relevant conventions into each reviewer's context (Phase 2).

## 6. Blast radius — affected services & infrastructure (Deep/Exhaustive)

A change is rarely contained to its diff. For deeper reviews, map what it can break **downstream**:
- **Contract / API changes** — if a public interface, schema, API response, event, or shared type changed, find its **consumers** (grep the repo and, if available, sibling repos / a monorepo for the symbol, endpoint, topic, or field). Flag breaking changes and missing versioning/backward-compat.
- **Data & migrations** — schema migrations, data backfills, or storage-format changes: check reversibility, ordering vs deploy, and read/write compatibility during rollout.
- **Infrastructure & config** — touched IaC, CI/CD, Dockerfiles, k8s/manifests, feature flags, env/secrets, queues, cron: note deploy/rollback impact and blast radius.
- **Cross-cutting** — auth, rate limits, observability (logs/metrics/traces), and shared libraries many call sites depend on.
Pass the affected-surface list into the relevant lenses, and summarize it in the report's **Blast radius** section. Use `/magic` when the downstream surface spans systems you can't see from this repo alone.
