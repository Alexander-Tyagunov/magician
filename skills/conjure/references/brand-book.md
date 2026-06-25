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
```

Derive from existing design tokens if present. Otherwise build from the chosen personality direction. Tell the user: "Brand book created at `.workspace/shared/brand.md` — all future mockups for this project reference it." All subsequent mockup CSS must stay consistent with this brand book.
