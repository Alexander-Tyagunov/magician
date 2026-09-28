# INTEGRATE mode delta

Change a comprehended feature **in place**: redesign it, **swap the 3rd-party behind it while
preserving the exact UX**, or add a capability — then integrate it precisely into the existing
processes. Read [comprehension.md](comprehension.md) (Phase A) and [delivery.md](delivery.md)
(Phase C) first; this is the INTEGRATE-specific delta. Mental model: **transmute the substance,
conserve the essence** — the user shouldn't notice the machinery changed.

## B1 (INTEGRATE) — pick the variant  (AskUserQuestion)

- **(a) redesign, preserve behavior** — new UI/UX, same functional contract. Behavior golden must
  still pass; `/conjure` drives the redesign.
- **(b) swap the vendor/3rd-party, preserve UX** — new provider behind the scenes; the user-facing
  experience is provably identical. The headline case.
- **(c) add a capability** — extend the feature; existing behavior is a regression baseline.

## The boundary — anti-corruption layer + strangler-fig

The safe way to change a live feature's internals is to isolate the change behind a seam:
- **Anti-corruption layer (ACL) / adapter** — introduce an interface that both the old and new
  implementation satisfy; call sites depend on the interface, not the vendor. For a vendor swap, the
  new provider is a new adapter behind the same interface; **call sites stay untouched** (that's how
  the UX is preserved by construction).
- **Strangler-fig** — route through the facade, migrate incrementally, keep the old path alive until
  the new one is proven, then retire the old path (a later, separate step — not in the cutover PR).
- **Expand-contract** for data/schema/config changes: add the new shape, migrate, then remove the old.

Use `kg blast` on the feature's files to scope the blast radius before touching anything; record the
seam in the parity contract's `<boundary>`.

## Cutover safety (G6) — flag + parallel-run + canary

- **Feature flag** gates old vs new; the new path ships **off**.
- **Parallel-run / shadow**: run the new provider **alongside** the old for real traffic, compare
  outputs against the old (the source golden is valid here — same app), but **return the old (control)
  result** so the UX is unchanged while you build confidence. Log mismatches.
- **Canary ramp**: enable the new path for a small cohort, watch the gateways, ramp up.
- **Rollback**: the flag is the kill-switch; the old path and strangler facade are retained; revert
  steps are documented. The removal of the old path is a **separate** follow-up, tracked (G8).

## Delivery (INTEGRATE) — worked example: a transactional-email provider swap

A common case: change which provider sends the app's transactional email (sign-up confirmation,
password reset, order receipt) behind the scenes, keep every message users receive unchanged, then
produce the whole delivery.

1. **Comprehend** (Phase A): drive the current flows read-only, capture the provider calls (network
   layer), fingerprint the current provider SDK, `kg` the send sites, mask secrets → dossier +
   behavioral golden of the messages users receive today.
2. **Contract** (Phase B, variant b): parity contract = *messages identical*, behavioral golden = the
   rendered subject/body/recipients and the delivery outcomes (sent, bounced, retried);
   `<boundary>` = an ACL (a `MailSender` interface) in front of sending; upgrade decision = the new
   provider; cost gate on per-message pricing × volume; rollback via flag.
3. **Tickets** (C3): `/jira` epic ("Transactional email provider migration") + stories (ACL
   interface, new-provider adapter, parallel-run harness, flag + config, cutover, old-path removal
   follow-up), linked to any existing epic.
4. **Design** (C1, if any UI shifts): `/conjure` — usually none for a pure backend swap (UX preserved).
5. **Build** (C4): `/weave` with the created **stories as `args.units`**; the parity loop diffs the new
   adapter's rendered messages against the golden; the ACL keeps send sites unchanged.
6. **Cutover**: flag + parallel-run (shadow-send to a sink, compare) + canary.
7. **Gateways** (Phase D): parity, perf, **cost** (provider pricing delta), **security** (new creds /
   recipient addresses crossing the ACL — `/sentinel`), UX-identical (G5), rollback (G6),
   toggle-removal filed (G8).
8. **Ship** (`/seal`, gated).

## Gateways (INTEGRATE emphasis)

All of Phase D, with **G5 UX-parity** (the change must be invisible to users), **G6 rollback/kill-
switch**, and **G8 toggle-debt** as first-class — these are what make an in-place change to a live
system safe.
