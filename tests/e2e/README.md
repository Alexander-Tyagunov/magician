# tests/e2e — local-only browser checks

These Playwright scripts drive the real `plan.html` in headless Chromium. They are **local only**:
`scripts/gate.sh` never runs them and CI has no browser. Run them before a release that touches
`tools/plan-render` or `tools/companion`.

```
node tests/e2e/plan_walkthrough.spec.js
```

Needs Node ≥ 18 and `playwright` resolvable from `require('playwright')` with a Chromium build
(`npx playwright install chromium`). Exit code is the number of failed checks capped at 1; each
check prints `ok` or `FAIL — <detail>`.

## `plan_walkthrough.spec.js`

| Part | What it covers | Skips when |
|---|---|---|
| 1 Static (`file://`) | keyboard map (← → Space A C E D H ? Esc), skip link first in the tab order, review tally, the change sheet composing a `T1: …` chat line, plan document dialog, reduced-motion play | never |
| 3 Artifact (mock) | `--transport artifact` with an in-page stand-in for `claude.use("db")`: one `events` document per toolbar action, `state/current` and `plan/current` snapshots driving the revising ring, the v2 hot-swap and the "what changed" panel, `invalid_argument` ⇒ read-only controls, `null` capability ⇒ static with the "Artifact without a database — reply in chat" notice | never (the real capability exists only inside the Artifact host; this part proves the page-side contract) |
| 2 Live (companion) | starts `tools/companion/vc-start.sh <dir> e2e --plan`, opens the served page, posts a change request from the toolbar, writes a `plan.json` v2 + `state.json` revision into the plan dir as `/blueprint` would, asserts the v2 badge and the diff panel, approves the plan, asserts `plan.approved` in `events.jsonl`, stops the server | `tools/companion/vc-start.sh` missing or `node` absent |

Everything runs in a temp dir that is deleted afterwards; the companion listens on 127.0.0.1 only.
