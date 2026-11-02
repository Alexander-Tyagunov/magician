# GATE 3.5, GATE 4 and the close — the full procedures

Read this after the design is approved (or after GATE 2 when the feature has no UI). The placeholders `<design-dir>` and `<state-dir>` are defined in [design-mode.md](design-mode.md).

## GATE 3.5 — Design-Only Close (`DESIGN_ONLY` flag only)

**Skip GATE 4 entirely when the mode carries the `DESIGN_ONLY` flag.**

After the user approves the mockup:

1. Write `<design-dir>/design-notes.md`:

```markdown
# [Feature] Design Notes

**Date:** YYYY-MM-DD
**Approach chosen:** [approach name]
**Screens:** screens/v{n}/
**Approved mockup:** screens/v{n}/mockup[-v{m}].html + .css
**Screenshots:** .workspace/local/screens/<feature>/v{n}/ (light/dark × viewports)

To reuse this design in a future session, reference this folder when running /conjure.
```

2. Stop the visual companion if it runs:
```bash
../scripts/vc-stop.sh <design-dir>
```

3. Say:
> "Mockup saved to `<design-dir>`. Open `screens/v{n}/mockup.html` directly in your browser to review it — CSS is in the sibling `.css` file. Run `/conjure` in a future session and reference this folder to continue."

Do **not** write a spec file. Do **not** invoke writing-plans or blueprint.

## GATE 4 — Spec Approval

Write the full spec to `.workspace/shared/specs/YYYY-MM-DD-<feature>.md` using the format in [spec-format.md](spec-format.md). Tell the user the spec path, then call `AskUserQuestion` — *"Spec ready — lock it in?"* — with options **Approve** / **Request changes**. End your turn at the call. Treat **Approve** (or any free-form "yes / looks good / approved") as approval; treat **Request changes** or specific feedback as revise. Do NOT commit until the user approves.

### Design Artifacts in the Spec

When a UI was designed, the spec's Design Artifacts section binds implementation to the approved screens (full format and STRICT/REFERENCE wording in [spec-format.md](spec-format.md)). It lists the approved HTML pair in `<design-dir>/screens/v{n}/`, the `architecture.mmd`, and the screenshot paths from [capture.md](capture.md). In blueprint/ward phases, when implementing UI tasks, Claude reads the approved HTML file in `<design-dir>/screens/v{n}/` to understand the expected layout, typography, and components.

## Step 3 — Commit and close

```bash
git add .workspace/shared/specs/YYYY-MM-DD-<feature>.md
git add .workspace/shared/decisions/YYYY-MM-DD-<feature>-<decision>.md
git add .workspace/shared/intents/YYYY-MM-DD-<feature>.md
git commit -m "docs: add spec for <feature>"
```

Run one `git add` per file, and only for a file that exists: `git add` of a missing path fails and stages nothing. Repeat the decisions line once per decision record this session wrote. Run the intents line only when `/manifest` wrote an intent file. Stage only the approved spec, its decision records and its intent file. Claude Code asks before the `git add` (only the commit is pre-approved); if the user declines it, stop without committing.

Stop the visual companion if running (`../scripts/vc-stop.sh <design-dir>`). Then say:

> "Spec approved and committed. Designs saved to `.workspace/shared/designs/`. Run `/magician:blueprint` to create the implementation plan."

## Sharing the result

When a visual mock or the spec is worth sharing, you can publish it as a Claude Code **Artifact** (a live page on claude.ai) that updates as the design evolves and that a team can **co-edit together** (multiplayer, Team/Enterprise plans) — offer it, don't create it unprompted. On the artboard surface the `/design` artifact already exists. Offer to share that one instead of making a second. Publishing to a **public** link (anyone with the URL can view it) is an outward, sharing action: **confirm it explicitly, keep artifacts account-private by default, and never publish anything containing secrets, credentials, or proprietary/internal code or data to a public link.**
