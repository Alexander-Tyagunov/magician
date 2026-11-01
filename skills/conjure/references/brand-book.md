# Brand Book Template

Used at **GATE 3 (UI Design)** when `.workspace/shared/brand.md` does not yet exist. After committing to an aesthetic direction, create the brand book — it must capture the *chosen aesthetic personality*, not just mechanical values.

```markdown
# Brand Book

## Personality
[One sentence: the aesthetic direction and why it fits this product]

## Colors
- Primary: #<hex>
- Secondary: #<hex>
- Background: #<hex>
- Surface: #<hex>
- Text: #<hex>
- Accent: #<hex>
- Error: #<hex>

## Typography
- Display font: <name + source — must be distinctive, not Inter/Roboto>
- Body font: <name + source>
- Heading scale: <sizes>
- Body: <size/line-height>

## Spatial style
[Dense | Airy | Extreme whitespace | Controlled density]

## Spacing scale
Base: 4px — 4 / 8 / 16 / 24 / 32 / 48 / 64

## Border radius: <value — 0px for sharp/brutalist, 4px for refined, 24px for playful>

## Shadows: <none | subtle | dramatic>

## Motion character
[None | Subtle fades | Bouncy | Staggered reveals | Dramatic]

## Component character
- Button: <shape, weight, hover behavior>
- Input: <border style, focus treatment>
- Card: <elevation, border, background>

## Guidelines applied
- Set: <Material 3 | Apple HIG | Fluent 2 | app's own system (<name>)> — chosen because <target platform / existing system>
- Sections consulted: <deep-lore anchors and live page URLs, one per component>
- Current design: <followed | rework requested on YYYY-MM-DD | greenfield>
- Deviations: <component or rule> — <what differs> — <why> (one line each; "none" if none)
- Checklist: <passed | items not satisfied: ...> (from the deep-lore review checklist)
```

Derive from existing design tokens if present. Otherwise build from the chosen personality direction. Tell the user: "Brand book created at `.workspace/shared/brand.md` — all future mockups for this project reference it." All subsequent mockup CSS must stay consistent with this brand book.

**v3.8.0 — also record (see [design-tokens.md](design-tokens.md)):** the run **style seed** (so the direction is reproducible / re-rollable) — only when variation ran (greenfield or rework); otherwise write `seed: n/a (followed current design)` — the chosen **archetype**, the **target viewports**, and the actual **token values for BOTH light and dark** maps. Additionally emit `.workspace/shared/design-tokens.css` (the Tier-1 primitives + Tier-2 semantics blocks) so `/blueprint` → `/ward` build real components against the exact tokens instead of re-inventing colors.

**v4.17.0 — Guidelines applied (see [design-principles.md](design-principles.md)):** record which guideline set the design follows (chosen by target platform), the deep-lore sections and live pages consulted, whether the current design was followed or a rework requested, and every deliberate deviation with its reason.
