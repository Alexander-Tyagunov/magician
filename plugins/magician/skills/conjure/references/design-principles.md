# Design Principles & Platform Guidelines

Read at **GATE 3, before the directions step**. Two rules: the app's **current design comes first**, and every new decision is **grounded in a public guideline set** chosen by target platform. The paraphrased guidance lives in [lore/design-principles.md](../../../lore/design-principles.md) (core) and [lore/deep/design-principles.md](../../../lore/deep/design-principles.md) (deep dive, one `## ` section per set — Grep `^## ` then Read offset/limit).

**Read the core first** ([lore/design-principles.md](../../../lore/design-principles.md), one screen of DO/DON'T for all three sets); Read a deep section only when you design against that set or run the checklist.

## Target → guideline set

| Target | Guideline set | URL | Deep-lore anchor |
|---|---|---|---|
| Android, Material web, Flutter | Material 3 | https://m3.material.io/ | [#material-3](../../../lore/deep/design-principles.md#material-3) |
| iOS, iPadOS, macOS, watchOS, visionOS | Apple Human Interface Guidelines | https://developer.apple.com/design/human-interface-guidelines | [#apple-hig](../../../lore/deep/design-principles.md#apple-hig) |
| Windows, Microsoft 365, Fluent UI | Microsoft Fluent 2 | https://fluent2.microsoft.design/ | [#fluent-2](../../../lore/deep/design-principles.md#fluent-2) |
| Neutral web (no platform idiom) | The app's own design system; else pick one of the above and say which | https://www.figma.com/resource-library/design-system-examples/ | [#design-systems](../../../lore/deep/design-principles.md#design-systems) |
| Every target | Review checklist (run before any mockup is shown) | — | [#review-checklist](../../../lore/deep/design-principles.md#review-checklist) |

Cross-platform apps (Flutter, React Native, Electron) follow the platform the user names as primary; note the secondary platform's differences in brand.md rather than designing twice.

## Current design first

Before proposing a direction, inventory what the app already looks like and treat it as the constraint:

- `.workspace/shared/brand.md` — personality, seed, archetype, viewports, earlier **Guidelines applied**.
- `.workspace/shared/design-tokens.css` — the Tier-1/Tier-2 token maps.
- The app's own stylesheets, theme files and token sources (`theme.*`, `tailwind.config.*`, `tokens.json`, SCSS variables, Compose/SwiftUI theme objects).
- The component library in use (its buttons, inputs, cards, navigation) and how the app already composes them.
- Screenshots or saved mockups in `.workspace/shared/designs/` and `.workspace/shared/mockups/`.
- README, marketing copy and audience notes for tone.

Follow what you find: reuse tokens, components and spacing; add only what the feature needs. The three directions in GATE 3 step 1 vary **inside** these constraints (layout skeleton, density, component choice), not the brand: same fonts, palette and personality, no style seed. The brand/typography variation rule and the "never default to system fonts" rule in [design-tokens.md](design-tokens.md) apply only to the two exceptions below, and a platform system font (Roboto, SF Pro, Segoe UI) is always allowed when the chosen guideline set prescribes it.

Two exceptions, and only these:

1. **The user asks for a rework** (or says to ignore the current design). Then the full seed/variation rule in [design-tokens.md](design-tokens.md) applies and the directions may differ on fonts, palette and personality. Record in brand.md that a rework was requested.
2. **Greenfield app with no design yet** — no brand.md, no tokens, no stylesheets, no screenshots. Choose the guideline set by platform from the table, say which one you chose and why, and build the design system on it.

## Consulting a live guideline page

When online, consult the live page for each **specific component** you are designing (a date picker, a navigation rail, a sheet), not the whole site:

- `WebFetch` the component's own page (for example the Material 3 "Date pickers" page) and ask for its anatomy, states, sizing and accessibility rules. For a wider question ("how should onboarding work on watchOS?") run `/magic` and design from its research artifact.
- **Paraphrase.** Carry the rule into your design decision in your own words; never paste guideline text, token tables or imagery into a mockup, a screen file or the spec.
- **Cite the URL** of each page you consulted in brand.md under Guidelines applied, so the next session can re-check it.
- Offline, or when the fetch fails, design from the deep-lore section alone and say so in brand.md.

Live pages are read, never written to, and the fetch is the only side effect.

## brand.md — Guidelines applied

Add this section to `.workspace/shared/brand.md` (template in [brand-book.md](brand-book.md)) and keep it current across sessions:

```markdown
## Guidelines applied
- Set: <Material 3 | Apple HIG | Fluent 2 | app's own system (<name>)> — chosen because <target platform / existing system>
- Sections consulted: <deep-lore anchors and live page URLs, one per component>
- Current design: <followed | rework requested on YYYY-MM-DD | greenfield>
- Deviations: <component or rule> — <what differs> — <why> (one line each; "none" if none)
- Checklist: <passed | items not satisfied: ...> (from the deep-lore review checklist)
```

A deviation is deliberate only when it is written here with its reason; an unrecorded difference from the guideline set is a defect the review checklist should catch.

## Review checklist

Before any mockup is presented, run every item in the [review checklist](../../../lore/deep/design-principles.md#review-checklist) against the screen and fix what fails. Items you cannot satisfy go into the mockup description and the **Checklist** line above — never silently.
