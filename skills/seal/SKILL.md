---
name: seal
description: Ships a feature — simplify pass, certify, commit, PR, CI monitoring, review loop, merge
keep-coding-instructions: true
---

# /seal — Ship to Production

Take a certified feature branch through to a merged PR.

## Pre-flight

- Confirm /certify has been run and passed
- Confirm /scrutinize + /absorb cycle is complete (or explicitly skipped by user)

## Process

### 1. Simplifier Pass
Dispatch simplifier agent (`agents/simplifier.md`) for a final simplification sweep. Fix any Important findings. Skip Low suggestions unless trivial.

### 2. Final Certify
Run /certify. All checks must pass before continuing.

### 3. Commit
```bash
git add -A
git commit -m "feat: <feature description>

<bullet list of what was built>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

### 4. Push
```bash
git push -u origin <branch>
```

### 5. Create PR
Ask user to provide the PR title, then:
```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
- <what was built>
- <key decisions>

## Test plan
- [ ] All tests pass
- [ ] Types clean
- [ ] Lint clean
- [ ] Manually verified: <golden path>

Built with magician + Claude Code
EOF
)"
```

### 6. Monitor CI
```bash
gh pr checks --watch
```
Wait for all checks to pass. If any fail: read the failure, fix, push, wait again.

### 7. Review Comments
If reviewers add comments: use /absorb to process them, then /certify, then push.

### 8. Merge (if auto-merge not enabled)
```bash
gh pr merge --squash --delete-branch
```

## disableGit Mode

If `disableGit: true`: skip push/PR/merge steps. Commit locally and report done.

## Completion Signal

"Sealed. PR merged. Run /portal cleanup steps if applicable."
