# Design principles — core (on-demand)

Platform design guidelines for `/conjure` mockups: Material 3 (Android, Compose, Flutter/Material web default), Apple HIG (iOS/iPadOS/macOS/watchOS/visionOS), Fluent 2 (Windows, Microsoft 365, Fluent UI React). Pick the guideline that matches the target; reuse the host app's own tokens/components first unless a rework was asked for.

DO
- Material: 4dp grid, 48dp touch targets, 40dp button height. Tonal palettes (tone 40 accent/90 container light; 80/30 dark); elevation via surface-container tiers, not shadows. Type roles display/headline/title/body/label (57-11sp). State layers hover 8%/focus 10%/pressed 10%. Window classes compact <600dp, medium <840, expanded <1200.
- Apple: 44x44pt targets, SF Pro + Dynamic Type (Body 17pt, min 11pt), safe areas, platform idioms (tab bar/sidebar, sheets, menus), clarity/deference/depth, system materials (Liquid Glass on nav layer only), system semantic colors.
- Fluent 2: 4px grid (spacing 2-32px), global -> alias tokens (`colorNeutralBackground1`, `borderRadiusMedium` 4px), neutral/brand ramps, Mica base + content layer, three densities, durations 50-500ms with accelerate/decelerate curves, WCAG 2.x AA.
- Cross-cutting: contrast >= 4.5:1 text and 3:1 UI/large text; visible focus ring; `prefers-reduced-motion`; RTL mirroring; dark mode = same design, tonal remap.

DON'T
- Mix idioms (Material FAB on iOS, iOS tab bar on Windows). Invent a third look when the app already has one.
- Hard-code hex/px in components; reference semantic tokens only.
- Rely on colour alone for state; ship pure #000 dark mode; shrink targets under 44pt/48dp.
- Animate longer than ~400ms for UI feedback, or ignore reduced-motion.

Deep dive when designing UI — read lore/deep/design-principles.md#{material-3,apple-hig,fluent-2,design-systems,review-checklist}

Sources: m3.material.io, developer.apple.com/design, fluent2.microsoft.design, figma.com/resource-library
