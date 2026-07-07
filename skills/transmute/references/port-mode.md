# PORT mode delta

Recreate a comprehended feature in **another app**, optionally **upgrading** the vendor/library on
the way. Read [comprehension.md](comprehension.md) (Phase A) and [delivery.md](delivery.md) (Phase C)
first — this file is only the PORT-specific delta. Mental model: **graft** the feature onto a new host,
conserving its behavior, not its environment.

## B1 (PORT) — target-app fit

Point `kg` at the **target** repo (`kg check`/`kg init` there, then `kg query`/`kg neighbors` for the
insertion area). Map the **target seam**: where the feature plugs in (routes/screens, data layer,
config, auth), what already exists to reuse, and what conventions the target imposes (stack, patterns,
design tokens). Record it in `<change_plan_seed><weave_shape>` and the parity contract's `<boundary>`.

## B2 (PORT) — upgrade decision  (AskUserQuestion)

The source feature may be built on an old vendor/library version — porting is the moment to consider
upgrading. Via `/magic` + context7 (queries keyed on the **public vendor name/version only**):
- current version-in-use vs **latest available** vs a **better alternative** vendor/library;
- breaking changes / migration cost / API deltas between them;
- a recommendation with the trade-off (parity-fast vs upgraded-but-more-work).

Present it — **don't silently default to parity**. Record the choice in `<upgrade_decision>`. If the
user upgrades, the behavioral golden still defines "correct" (the feature must behave the same for the
user even on the newer vendor), and the migration notes go into the blueprint.

## Parity for a port — behavioral only

A port lands in a different environment: different domain, data, IDs, styling. So:
- the evaluator loop asserts **behavioral parity** (input → output **semantics/shapes**, state
  machine, business rules) against `<f>-golden/behavioral/`;
- **environmental** captures (`<f>-golden/environmental/`) are reference-only and **never asserted** —
  otherwise parity can never converge.
State this split in `<parity_contract>` so the loop terminates.

## Delivery (PORT)

Follow [delivery.md](delivery.md): `/conjure` if the port needs its own UI (else reuse the target's
design system), `/blueprint`, optional `/jira`, then `/weave` with the parity loop. There is no
strangler/cutover here (nothing to replace in the target) — but G6 rollback still applies: the ported
feature ships behind a flag so it can be disabled cleanly.

## Gateways (PORT emphasis)

All of Phase D. Emphasis: **G1 parity** (behavioral golden), **G2 perf** in the target's budget (the
new environment may perform differently — re-baseline with `/accelerate`, don't assume the source's
numbers), **G3 cost** if an upgrade changes the vendor's pricing, **G7 sanity** in the target repo.
