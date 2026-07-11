# Design tokens, variation, theming & responsive (v3.8.0)

The single source of truth for how `/conjure` generates mockups. GATE 3 reads this on demand.
Three requirements ride on ONE architecture — a two-tier design-token system:

- **Variation** — every run seeds a *distinct* archetype so mockups don't converge on one house look.
- **Light/dark = ONE design** — light and dark are two *tonal maps of the same semantic tokens* on the *same* layout, never two different designs.
- **Responsive** — ask the target viewports up front; render the *same* token-driven design across breakpoints.

---

## 1. Two-tier tokens (CSS custom properties)

**Tier 1 — primitives** (raw scales, theme-agnostic, named by value; components NEVER consume these directly):
```css
:root{
  /* color ramps (0=lightest … 900=darkest), one per hue the archetype uses */
  --c-neutral-0:#fff; --c-neutral-50:#f8fafc; /* … */ --c-neutral-900:#0b0b12;
  --c-accent-100: …; --c-accent-500: …; --c-accent-700: …;
  /* type, space, radius, shadow, motion — chosen by the archetype/seed */
  --font-sans:"…"; --font-display:"…"; --font-mono:"…";
  --step--1:.833rem; --step-0:1rem; --step-1:1.2rem; --step-2:1.44rem; --step-3:1.728rem; --step-4:2.07rem;
  --space-1:.25rem; --space-2:.5rem; --space-3:1rem; --space-4:1.5rem; --space-6:2.5rem; --space-8:4rem;
  --radius-sm:6px; --radius-md:12px; --radius-lg:20px; --radius-pill:999px;
  --ease:cubic-bezier(.2,.7,.2,1); --dur:180ms;
}
```

**Tier 2 — semantics** (role-based; the ONLY thing component CSS references, always via `var(--…)`):
```css
:root{ /* light map */
  --bg:var(--c-neutral-50); --surface:var(--c-neutral-0); --surface-2:var(--c-neutral-100);
  --text:var(--c-neutral-900); --text-muted:var(--c-neutral-500); --border:var(--c-neutral-200);
  --accent:var(--c-accent-500); --accent-text:#fff; --focus:var(--c-accent-500);
  --elev-1:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.10);
  --elev-2:0 4px 12px rgba(16,24,40,.10);
}
[data-theme="dark"]{ /* SAME names, tonal remap — see §3 */
  --bg:var(--c-neutral-900); --surface:#14141c; --surface-2:#1c1c26;
  --text:var(--c-neutral-50); --text-muted:#94a3b8; --border:rgba(255,255,255,.10);
  --accent:var(--c-accent-400); --accent-text:#0b0b12; --focus:var(--c-accent-400);
  --elev-1:0 1px 2px rgba(0,0,0,.4); --elev-2:0 8px 28px rgba(0,0,0,.55);
}
```

**Hard rule (self-check before serving):** component CSS references only `var(--<semantic>)` — never a `--c-*` primitive and never a raw hex/rgb. Grep the mockup for `#[0-9a-fA-F]{3,6}` or `rgb(` outside the `:root`/`[data-theme]` token blocks; if found, it's a bug (breaks theming + variation).

---

## 2. Variation — seeded, multi-archetype (ask #2)

1. **Seed** each run: `SEED=$(openssl rand -hex 4)` (or `date +%s`); record it in `.workspace/shared/brand.md` so a run is reproducible/regenerable ("re-roll" = new seed).
2. **Archetype pool** — pick directions that differ on **≥2 axes simultaneously** (font FAMILY, layout SKELETON, density, base personality, motion). Don't reuse the same two fonts + purple every time. Seed → distinct pool selection. A non-exhaustive pool:
   - *Editorial* — serif display, generous whitespace, asymmetric grid, restrained accent.
   - *Neo-brutalist* — mono/grotesk, hard borders, high contrast, flat blocks, no shadow.
   - *Soft-SaaS* — humanist sans, rounded-lg, tinted elevation, pastel accent (the prior house look — keep it, labelled, as one option, not the default).
   - *Dense-utility* — compact scale, data-first tables, thin borders, small radius.
   - *Expressive-gradient* — bold display, gradient mesh bg, large radius, motion-forward.
   - *Minimal-mono* — one hue, type-led hierarchy, near-zero chrome.
3. When showing **3 directions** at GATE 3, enforce they differ on font family AND layout skeleton AND base tone — reject a set where two look like siblings; re-roll one.
4. Each direction is a **token set + one representative layout** (not 3 full apps). Only the chosen direction expands.

---

## 3. Light + dark = ONE design (ask #5)

Not two designs. Same layout, same spacing/type/radii/shapes/motion — only color & elevation tokens remap.

- **Structure is theme-agnostic:** all layout/spacing/type/component-shape rules live outside the token blocks and never change between themes.
- **Dark is a tonal remap, not an inversion:** avoid pure `#000`. Base surfaces `#0b0b12 → #1c1c26`; **elevation by tint** (lighter surface = higher), since shadows barely read on dark. **Desaturate/brighten accents** one step for dark (`--c-accent-400` vs `-500`). **Borders** become low-alpha light (`rgba(255,255,255,.08–.12)`).
- **Contrast:** verify text/bg ≥ WCAG AA (4.5:1 body, 3:1 large) in **both** maps.
- **Toggle:** ship a `[data-theme]` switch in the preview so the user flips light↔dark on the *same* screen and sees it's the same design. Respect `prefers-color-scheme` for the initial value.

---

## 4. Responsive (ask #3)

1. **Ask targets first** — at GATE 3, `AskUserQuestion` (multiSelect): *"Which viewports should this design target?"* → Phone / Tablet / Desktop / Wide (default Phone + Desktop). Record in `brand.md`.
2. **Breakpoints** (mobile-first; `min-width`):
   `--bp-phone:0 · --bp-tablet:640px · --bp-desktop:1024px · --bp-wide:1440px`.
   Frame widths for preview: phone 390 · tablet 834 · desktop 1280 · wide 1600.
3. **Same design across breakpoints** — one token-driven layout that reflows (grid `auto-fit`/`minmax`, fluid `--step-*` via `clamp()`), not separate designs per size. Mobile-first base + `@media (min-width:…)` enhancements.
4. **Preview** each chosen viewport (multi-iframe harness or Playwright `browser_resize` captures); wait for fonts/animation before capture.

---

## 5. What lands in `.workspace/shared/` (handoff)

- `brand.md` — chosen archetype, **seed**, token values (both themes), target viewports, breakpoints.
- `design-tokens.css` — the emitted Tier-1 + Tier-2 token blocks (importable by real code).
- `spec.md` — references the above so `/blueprint` → `/weave`/`/ward` build against the exact tokens (no re-inventing colors downstream).
