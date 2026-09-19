# Claude-side quality gates

These are the plugin's self-tests: the bar a Magician change must clear before it ships. They are
**dependency-free** (Python stdlib `unittest` only — no pytest, no PyYAML) so any team that clones the
plugin can run them with nothing installed. Run the whole gate with:

```bash
scripts/gate.sh            # offline tiers: Claude gates + Codex gates
scripts/gate.sh --evals    # also run the behavioral `claude plugin eval` suite (spends API budget)
```

Or run this tier alone:

```bash
python3 -m unittest discover -s tests/claude -p 'test_*.py'
```

## What each gate proves

| File | Contract |
|------|----------|
| `test_hooks.py` | Every hook is wired to a real lifecycle event, resolves to an executable script, and uses a valid matcher. The destructive guard is a `PreToolUse(Bash)` hook; compaction capture is on `PreCompact`; the subagent lifecycle is wired both ends. |
| `test_agents.py` | Every `agents/*.md` is a spawnable subagent: required frontmatter, name matches filename, least-privilege tools, review lenses are read-only, each declares the fresh-context contract, and the skill→agent wiring resolves (no skill dispatches a `magician:<name>` that does not exist; the parallel-review skill dispatches the real review-lens agents). |
| `test_skills.py` | Every `skills/*/SKILL.md` has a routable name+description, valid `allowed-tools`, and no dangling relative links. |
| `test_manifest.py` | `plugin.json` / `marketplace.json` are well-formed, the version is semver and synchronized across every release surface, and declared component dirs exist. |
| `test_destructive_guard.py` | The catastrophic-command hard gate blocks root/device/critical-file destruction, fork bombs, and pipe-to-shell; soft-blocks secret reads and the lethal trifecta; and lets benign neighbours through. |
| `test_compaction.py` | Compaction is a continuity boundary: the `PreCompact` hook fails open, captures a resume capsule, and a negative constraint survives capture **and** re-injection. |
| `test_evals.py` | The `evals/` behavioral suite is well-formed and honest: valid grader types, compiling patterns, and every asserted skill/agent actually exists. |
| `test_guardrails.py` | Plugin-wide security posture: no hardcoded secrets in the shipped surface, credentialed CLIs read from the environment, no unbounded tool grants, and the guard's fail-open + injection floor hold. |

## Behavioral eval tier (`evals/`, opt-in)

`scripts/gate.sh --evals` runs the plugin end-to-end through `claude plugin eval` — a real model,
in a sandbox, graded on what actually happened. It spends API budget and needs the network, so it is
opt-in; CI runs it on a schedule (see `.github/workflows/gate.yml`). The suite gates the behavior that
is **reliably observable** in the eval sandbox:

| Case | Proves |
|------|--------|
| `security-scan-routes-to-sentinel` | A "run a security scan" request invokes the `sentinel` **skill** (Skill tool) **and** the scan catches the planted SQL injection and XSS. |
| `code-review-routes-to-review-skill` | A code-review request invokes the `divine` review **skill** **and** the review catches the planted correctness defects in a money-transfer diff. |
| `destructive-command-is-blocked` | A prompt that asks to run `rm -rf /` is stopped by the `PreToolUse(Bash)` guard **hook** — the command never executes and the model does not claim it did. |

**Why agent-spawning is not in this tier.** Whether the model spins up a `Task` subagent for a small
review is model-discretionary — it (correctly) reviews a five-line diff inline rather than paying the
overhead of a subagent, even when told to delegate. That is not reproducible enough to hang a green
gate on. Agent *dispatchability* is therefore gated **structurally** in `test_agents.py`: every agent
is well-formed and least-privileged (a malformed one can't be spun), and the parallel-review skill's
`magician:<name>` dispatch targets are proven to resolve to real agents. That is the deterministic
proof the agents are registered and wired to be spawned; the eval tier proves the skill and hook
enforcement that a model *does* exercise on every relevant turn.

## Design principle

Every gate reads declarative config and the filesystem, or invokes a script exactly as the hook does —
**none of them execute a catastrophic command or a real network call.** A guardrail without a test is
unverified; these tests are how the plugin verifies its own guardrails.
