---
name: conjure
description: Structured design dialogue with a visual companion — produces an approved spec and design artifacts before any implementation begins. Use at the start of a feature, before writing code.
allowed-tools: Read, Write, Edit, AskUserQuestion, Bash, mcp__playwright__browser_navigate, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_snapshot, mcp__playwright__browser_wait_for, mcp__playwright__browser_close
argument-hint: [feature or what you want to design]
---

# /conjure — Design Dialogue

Run a structured design dialogue before writing any code. Produce an approved spec and optional visual design artifacts. When a visual mock or the spec is worth sharing, you can publish it as a Claude Code **Artifact** (a live page on claude.ai) so stakeholders can view/comment as it evolves — offer it, don't create it unprompted.

<HARD-GATE>
Do NOT write any code, scaffold any project, or take any implementation action until the user has approved the spec. This applies regardless of perceived simplicity.
</HARD-GATE>

**Reference files (read on demand, do not inline):**
- Visual modes (A/B/D) — permission setup, companion server, screen templates, Playwright capture: [references/visual-companion.md](references/visual-companion.md)
- Brand book template (GATE 3, first-time setup): [references/brand-book.md](references/brand-book.md)
- Spec file format (GATE 4): [references/spec-format.md](references/spec-format.md)

---

## Process — Gated Dialogue

**Core rule: each gate is one turn. End your turn after each gate. Do NOT advance to the next gate until the user replies. Never collapse two gates into one message.**

### Step 1 — Explore
Read relevant files, recent git log, existing specs in `.workspace/shared/specs/`, and any prior research in `.workspace/shared/research/` (from `/magic`). Note detected stack and archetype from session additionalContext. Do this silently before asking anything. If a design decision hinges on external evidence you don't have (library choice, prior art, API capabilities), suggest running `/magic` first — it returns a research artifact you then design from.

### Step 2 — Clarify (one question per turn)
Ask one clarifying question. End your turn. Wait for the answer. Repeat until you understand purpose, constraints, success criteria, and edge cases. Skip stack questions the inspector already answered. Use multiple choice when possible.

---
### GATE 0 — Design Mode
Present the design mode options as its own message (see Design Mode section below). End your turn. **Do not propose approaches until the user picks a mode.**

If visual mode chosen: read [references/visual-companion.md](references/visual-companion.md), run permission setup, start the companion server, open the browser, and tell user the URL. Then proceed to GATE 1.

---
### GATE 1 — Approach Selection

Present 2–3 approaches.

**If visual mode:** write the approach comparison screen (`$VC_SCREENS/v1/approaches.html` — see [references/visual-companion.md](references/visual-companion.md)), tell user the URL and a one-sentence summary of each approach. End your turn. On the next turn read `$VC_STATE/events` for their click choice plus their terminal message.

**If text mode:** present the approaches in text. End with: *"Which approach would you like to go with?"* End your turn.

**Do not present architecture until the user confirms an approach.**

---
### GATE 2 — Architecture Review

Present the architecture for the chosen approach only.

**If visual mode:** write the architecture diagram screen (`$VC_SCREENS/v1/architecture.html` — see [references/visual-companion.md](references/visual-companion.md)). Tell user the URL and describe the diagram in 2 sentences. End your turn. Wait for their feedback.

**If text mode:** present the architecture (file structure, data flow, component responsibilities). End with: *"Does this architecture make sense, or do you want to change anything?"* End your turn.

Iterate on changes if requested. Only advance when user explicitly approves.

---
### GATE 3 — UI Design (skip if no UI involved)

If the feature has a UI:

**Design personality gate — BEFORE any CSS or mockup:**

This step prevents all mockups from looking the same. Do it every time, without exception.

1. **Research context** — silently scan: existing CSS/Tailwind config, any brand assets, README, the product's name and purpose, target audience from spec. Note the tone: serious B2B tool? Playful consumer app? Developer utility? Financial product?

2. **Commit to a bold aesthetic direction** — choose ONE from this list (or derive your own that fits the project):
   - Brutally minimal — extreme whitespace, monochrome, single accent, nothing decorative
   - Editorial / magazine — strong typographic hierarchy, oversized headlines, asymmetric layouts
   - Luxury / refined — muted palette, serif headlines, subtle shadows, controlled density
   - Retro-futuristic — geometric shapes, high contrast, bold angles, neon accent on dark
   - Playful / toy-like — rounded everything, saturated pastels, bouncy micro-animations
   - Industrial / utilitarian — dense layout, monospace type, low chrome, data-forward
   - Organic / natural — earthy tones, fluid shapes, soft textures, warm neutrals
   - Brutalist / raw — clashing fonts, visible structure, unexpected color collisions
   - Art deco / geometric — symmetry, ornamental borders, gold/black, structured grids

   **NEVER default to:** Inter/Roboto/system fonts, purple gradients on white, generic card layouts, Space Grotesk, "clean modern SaaS look." These produce identical output across every project.

3. **Vary light/dark** — alternate between light and dark base themes across sessions. Do not always choose dark.

4. **State your direction** — tell the user in one sentence: "I'm going with [direction] — [one-line rationale tied to the product]." Do not ask for approval; move forward. If they want something different they'll say so.

**Brand book (first-time setup):** After committing to a direction, check whether `.workspace/shared/brand.md` exists. If not, create it now using the template in [references/brand-book.md](references/brand-book.md) — the brand book must capture the *chosen aesthetic personality*, not just mechanical values. All subsequent mockup CSS must stay consistent with this brand book.

**Present a mockup.**

**If visual mode:** write two files for every mockup — `$VC_SCREENS/v1/mockup.css` (all styles) first, then `$VC_SCREENS/v1/mockup.html` (HTML only, linking to it via `<link rel="stylesheet" href="mockup.css">`). No `<style>` blocks in the HTML. Apply the frontend-design quality rules and templates in [references/visual-companion.md](references/visual-companion.md). Tell user the URL. End your turn. Iterate on versions if requested (keep paired naming: `mockup-v2.css` + `mockup-v2.html`). Capture a Playwright screenshot when approved.

**If text mode:** describe the UI layout and key interactions. End with: *"Does this design direction look right?"* End your turn.

Only advance when user explicitly approves the design.

---
### GATE 3.5 — Design-Only Close (mode D only)

**Skip GATE 4 entirely when mode is `DESIGN_ONLY`.**

After the user approves the mockup:

1. Write `$DESIGN_DIR/design-notes.md`:

```markdown
# [Feature] Design Notes

**Date:** YYYY-MM-DD
**Approach chosen:** [approach name]
**Screens:** screens/v{n}/
**Approved mockup:** screens/v{n}/mockup[-v{m}].html + .css

To reuse this design in a future session, reference this folder when running /conjure.
```

2. Stop the visual companion:
```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/conjure/scripts/vc-stop.sh" "$DESIGN_DIR"
```

3. Say:
> "Mockup saved to `[DESIGN_DIR]`. Open `screens/v{n}/mockup.html` directly in your browser to review it — CSS is in the sibling `.css` file. Run `/conjure` in a future session and reference this folder to continue."

Do **not** write a spec file. Do **not** invoke writing-plans or blueprint.

---

### GATE 4 — Spec Approval

Write the full spec to `.workspace/shared/specs/YYYY-MM-DD-<feature>.md` using the format in [references/spec-format.md](references/spec-format.md). Then say:

> "Spec written to `[path]`. Please review it and let me know if anything needs to change before we lock it in."

End your turn. Wait for explicit approval — "yes", "looks good", "approved", etc. Do NOT commit until this arrives.

---
### Step 3 — Commit and close

```bash
git add .workspace/shared/specs/
git commit -m "docs: add spec for <feature>"
```

Stop the visual companion if running. Then say: *"Spec approved and committed. Run `/magician:blueprint` to create the implementation plan."*

---

## Design Mode

At GATE 0, send this message — and nothing else. Do not add clarifying questions. Do not preview approaches. Just this:

> **How would you like to work through the design?**
>
> **A — Visual + Strict** — I open a design companion in your browser. I show approach options, architecture diagrams, and UI mockups as interactive screens you can click. Approved designs become binding implementation targets — ward tasks must match them exactly.
>
> **B — Visual + Reference** — Same visual companion, but designs are advisory. Implementation can deviate with good reason.
>
> **C — Text only** — Skip the browser companion. Everything happens here in the terminal.
>
> **D — Design Only (Visual)** — Full visual dialogue (approaches → architecture → mockup) with no spec and no implementation plan. Artifacts saved to `.workspace/shared/mockups/YYYY-MM-DD-<feature>/` for reuse across sessions.

End your turn. Wait for their reply before doing anything else.

Map reply to mode:
- `VISUAL_STRICT` → visual companion active, designs are binding in ward
- `VISUAL_REFERENCE` → visual companion active, designs are advisory in ward
- `TEXT_ONLY` → no visual companion
- `DESIGN_ONLY` → visual companion active, output saved to `.workspace/shared/mockups/`, no spec written, no writing-plans invoked

If the user says "skip" at any point during the session: immediately switch to TEXT_ONLY, stop the companion server if running, continue text-only.

For visual modes (A/B/D), the permission setup, companion server lifecycle, interaction loop, all screen-type templates, and Playwright capture live in [references/visual-companion.md](references/visual-companion.md). Read it before starting the companion.

---

## Design Principles

- Each unit has one responsibility and a clear interface
- Prefer smaller focused files over large ones that do too much
- YAGNI: no features the user did not request
- Design for testability: every component independently verifiable

---

## Design Artifacts in the Spec

When a UI was designed, the spec's Design Artifacts section binds implementation to the approved screens (full format and STRICT/REFERENCE wording in [references/spec-format.md](references/spec-format.md)). In blueprint/ward phases, when implementing UI tasks, Claude reads the approved HTML file in `$VC_SCREENS/v{n}/` to understand the expected layout, typography, and components.

---

## After Approval

Stop the visual companion, commit the spec, then say:

> "Spec approved and committed. Designs saved to `.workspace/shared/designs/`. Run `/magician:blueprint` to create the implementation plan."
