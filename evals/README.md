# Behavioral evals

This folder is magician's behavioral suite for `claude plugin eval`. Each case runs a real model in a sandbox with the plugin loaded, then runs it again without the plugin (the baseline arm), and grades what happened. The suite gates behavior that a static test cannot see: which skill a prompt routes to, whether a review finds a planted defect, whether TDD runs red before green.

A run spends API credit. `scripts/gate.sh` runs the suite only on request:

```bash
bash scripts/gate.sh --evals                    # offline tiers, then this suite and the flip check
bash scripts/gate.sh --evals --update-baseline  # the same, then record this run as the baseline
```

The offline gate (`tests/claude/test_evals.py`) checks the shape of every case on each commit, at no cost.

## The cases

| Case | Proves | Graders | Pair |
|------|--------|---------|------|
| `security-scan-routes-to-sentinel` | A named security scan invokes `sentinel` and catches the planted SQL injection and XSS. | `tool_used` Skill, `llm` | `plain-question-loads-no-skill` |
| `code-review-routes-to-review-skill` | A named code review invokes `divine` and catches the money-transfer defects. | `tool_used` Skill, `llm` | `plain-question-loads-no-skill` |
| `destructive-command-is-blocked` | A filesystem-root wipe never runs and is never reported as done. | `llm` | — |
| `ste-spec-writing` | With STE-lite on, a short spec keeps the checkable STE-lite rules. | `regex` ×3, `llm` | — |
| `tdd-red-before-green` | A test run comes before the first edit of the implementation, the new test fails first, and the suite ends green. | `tool_order`, `llm` | — |
| `blueprint-emits-plan-folder` | `/blueprint` writes `plan.json` and renders `plan.md` (with `### Task 1:`) and `plan.html` with `plan-render`. | `file_exists` ×2, `regex` (file), `tool_used` Bash | `planning-negative-control` |
| `planning-negative-control` | A one-line typo fix does not route to `/manifest`, `/conjure`, `/blueprint` or `/orchestrate`, and the typo is fixed. | `tool_used` Skill (max 0), `regex` (file) ×2 | `blueprint-emits-plan-folder` |
| `scrutinize-fixes-seeded-bug` | `/scrutinize` fixes a seeded off-by-one and adds a regression test that pins the boundary. | `regex` (file), `llm` (file) ×2, `file_exists` | — |
| `obstacles-on-missing-input` | A dispatched implementer with a missing spec returns `STATUS: NEEDS_CONTEXT` and builds nothing. | `regex` ×2, `file_exists` (absent), `llm` | — |
| `session-state-before-wave` | `/orchestrate` writes `.workspace/local/session-state.md` before its first wave. | `file_exists`, `llm` (trace) | — |
| `review-uses-tags-and-count-line` | A deep `/divine` review opens with the count line, tags and locates every finding, and each lens finds its planted defect. | `regex`, `llm` ×4 | — |
| `small-diff-stays-inline` | A quick review of a five-line diff spawns no subagent and still finds the bug. **Expected to fail** until batch 6 (below). | `tool_used` Agent (max 0), `llm` | `large-plan-fans-out` |
| `large-plan-fans-out` | `/orchestrate` on a plan with four independent tasks fans the first wave out to subagents dispatched together. | `tool_used` Agent (min 2), `llm` (trace) | `small-diff-stays-inline` |
| `plain-question-loads-no-skill` | A plain question gets a plain answer and loads no workflow skill. | `tool_used` Skill (max 0), `llm` | the two routing cases |

### Fold-first routing and the expected failure

`small-diff-stays-inline` and `large-plan-fans-out` (tags `routing`, `fold-first`) grade the fold-first rule in [`lore/fold-first.md`](../lore/fold-first.md), which batch 6 wired into `/divine`, `/scrutinize`, `/orchestrate` and `/weave`. A diff of 3 files or fewer and 300 changed lines or fewer stays in the main loop, with each lens file read as a checklist. A Quick review of such a diff makes no `Agent` call, and its verification runs in the main loop. Two or more independent `Parallel: YES` tasks in a wave still fan out. `small-diff-stays-inline` keeps its `expected-fail` tag until a paid eval run confirms that it passes, so the flip check leaves it out until then. Remove the tag after that run.

`session-state-before-wave` grades the order with an `llm` rubric over the trace, not with `tool_order`. A `tool_order` grader can only name one `after` tool. Before batch 6 the first wave goes to an `Agent` call, after it a two-task wave may run inline with `Write` and `Edit`, and one grader cannot cover both paths.

### Sign-in for eval runs

`claude plugin eval` starts a separate `claude` process for every run. That process must be able to sign in on its own. If the report says `partial: true` with `partialReason: auth_failed` and the run error is `Not logged in · Please run /login`, the judge still ran, because it runs in your main process, but the case did not run. `flip.py` and `lens-ab/summarize.py` report such a result as partial and fail. Check that a fresh non-interactive process can sign in from the same shell: `claude -p "reply ok" --model haiku`. If that also fails, fix the sign-in first.

## Layout and format

Each case is one folder:

- `prompt.md`: the frontmatter (`name`, `description`, `tags`, `runs`, `max_turns`, `timeout_seconds`, `expected_outcome`, `allowed_tools`) and the prompt as the body.
- `graders/<name>.md`: one grader per file. The four original cases use this form.
- `case.yaml`: `schema_version`, `name`, `context.scaffold_script` and the inline `graders` list. The newer cases use this form. It is written as JSON, which is valid YAML, so the offline gate reads it with the Python standard library. One file for all graders also keeps the repository under the plugin directory's 512-file limit.
- `scaffold.sh`: stages the fixture (files, a git repository) in the run's working folder. The runner starts it as `bash scaffold.sh` only with `--scaffold`, which the gate passes.

Rules that come from the runner, not from taste:

- `file_exists` and the `files` target see only files the run **created**. A file the scaffold staged and the run changed counts as absent. To grade its content, use a `{source: file, path: …}` target.
- A `tool_used` grader on `Skill` is a display-only indicator under `--ablation with-without`. A must-not-call grader sets `min: 0`, `max: 0` and `arm: both`, so it counts.
- Every case has at least one outcome grader (`regex`, `file_exists` or `llm`), not only `tool_used` or `tool_order`.
- Tools follow graders. A grader that needs a call of a tool, or a created file, only passes if `allowed_tools` names that tool. Write tools are granted at run time with `--allow-tools` (the gate grants `Bash Edit Write`; set `MAGICIAN_EVAL_ALLOW_TOOLS` to change that). A granted shell tool needs the OS sandbox backend; without it the runner refuses the run.
- The subagent tool is `Agent`. `Monitor` and the worktree tools never run inside an eval.
- An unknown frontmatter or grader key makes the runner refuse the case. `test_evals.py` holds the accepted key sets.

## How cases are sourced

1. Start from real failures: an incident, a revert, a bug report, a review finding that a skill missed. Each incident becomes a permanent regression case.
2. Then hand-write golden cases for the behavior each skill promises. Ten golden cases is the floor for a useful set. This suite has fourteen.
3. Add synthetic cases from the codebase last, to fill gaps.
4. Pair every routing positive with a negative control: a prompt where the skill must **not** fire.
5. Do not build the suite only from the failures of the current model. A suite like that measures one model's blind spots, not the plugin.
6. A case must look like real use: a realistic prompt, a small realistic fixture, no hints that only an eval would give.

Write `llm` rubrics as checkable claims ("PASS only if all of these hold: 1. … 2. …"), not as impressions. A stronger model or more reasoning must score higher. If it does not, suspect the task, the grader or the setup.

## Runs and the flip check

Every case sets `runs: 3` (2 is the minimum the offline gate accepts). A regression often shows in only one run of several, so a single run cannot gate a change.

After the suite runs, `scripts/gate.sh` calls `evals/flip.py`. It reads the run result (`.gate-evals.json`) and the tracked baseline `evals/results/last.json`, and for each case:

- **flipped**: the case passed every run in the baseline and fails at least one run now. The tier fails, whatever the aggregate score.
- **below threshold**: the case score is under `--threshold` (default 0.8). The tier fails.
- **new** or **improved**: reported, never a failure.
- **expected-fail**: a case tagged `expected-fail` is left out until the baseline records it as passing every run. After that it counts like any other case.

`claude plugin eval` exits 1 when any case is under the threshold, expected-fail cases included. `flip.py` gets that exit status and accepts it only when excused expected-fail cases explain it. A load error, an API-error run, a partial run (exit 2, the cost ceiling) or an interrupted run (130, 143) always fails the tier.

`flip.py` reads two result shapes, because the per-case shape of `--json` is not in the public documentation:

- `{"cases": [{"name", "score", "pass_rate", "runs": [{"score", "graders", "error"}]}]}`: what the CLI writes. A run passes when its `score` is 1 (every scored grader passed) and it has no `error`.
- `{"results": [{"case", "score"}]}`: a flat shape. A case passed every run only when `score` is 1.

The baseline shape is `{"schema": 1, "recorded_at", "cases": {"<name>": {"runs", "passed", "pass_rate", "score"}}}`. Record a new baseline with `--update-baseline` (or `MAGICIAN_EVAL_UPDATE_BASELINE=1`) only after you inspected the run, and commit `last.json` with the change it measures.

### Inspect the flipped cases, not the aggregate

An aggregate can hold steady while one case breaks. For each flipped case:

1. Open the run report under `evals/results/<timestamp>/` and read the failed run's trace and grader verdicts.
2. Find the root cause: the agent, the skill instructions, the harness, the grader, or the eval itself.
3. Fix that cause with one change, then run the case again (`claude plugin eval . --case <name> --runs 3 --no-publish`).

## Improving a skill description against the suite

Use the `/claude-api build-eval` and `hillclimb` skills for trigger accuracy of skill descriptions, with these rules:

- **Held-out split.** Split the trigger cases (the `routing` and `negative-control` tags, plus prompts from real traffic) into a train set and a held-out set, about two to one. The optimizer sees train failures only, never held-out answers.
- **One change per round.** Inspect the failures, find one root cause, make one patch, run both sets, and keep or revert.
- **Revert** when the held-out score drops, or when the train score rises while the held-out score stays flat (overfitting).
- **Noise.** Never merge a gain smaller than the run-to-run spread. Add cases or runs until the noise is smaller than the smallest gain that matters.
- **Never paste failure content into a skill or a prompt.** Fix the cause. A pasted model output or an eval answer in a skill is a leak that inflates the score and helps no user.
- **Keep headroom.** When a case passes every run, release after release, at about 95% or more, add a harder case or optimize cost and latency instead.
- **The judge is never the evaluated model.** Pass `--judge-model` with a model other than the one under test (the default judge is a small model; use a sonnet-tier judge for nuanced rubrics). Spot-check the judge against your own verdict on a sample.

## Lens-model A/B

`evals/lens-ab/run.sh` compares models for the `simplifier` and `verifier` lenses (proposal L2). For each model (default `haiku` and `sonnet`) it copies the plugin to a scratch folder, sets the `model:` line of the copied lens agents, and runs the cases tagged `lens-ab` against the copy with `--ablation none`. The main loop keeps one model (`--main-model`, else the CLI default), so only the lens model changes. `evals/lens-ab/summarize.py` then prints findings recall per lens per model: the share of graded runs in which the graders named after that lens (`reviewer-…`, `simplifier-…`, `verifier-…`) passed. Adopt the cheaper model only if its recall holds.

```bash
evals/lens-ab/run.sh --dry-run                      # print the commands, spend nothing
evals/lens-ab/run.sh --main-model opus --runs 3     # spends API credit
```

## Not in the suite, and why

- **Lazy lore on a stack mention** (a prompt that names React in a repository with `package.json` uses a fact only `lore/react.md` holds): skipped. Every fact in the React core is public react.dev content that current models already know, so no regex can tell an injected core from prior knowledge, and the two arms would score the same. `tests/claude/test_hook_scripts.py` runs `pattern-detect.sh` for real and proves the injection deterministically.
- **STE-lite off allows normal prose** (the negative twin of `ste-spec-writing`): skipped. With STE-lite off nothing constrains the prose, so every answer passes and the case measures nothing.
