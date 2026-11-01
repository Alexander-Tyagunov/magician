# design-principles — deep dive

> On-demand companion to `lore/design-principles.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Material 3](#material-3) · [Apple HIG](#apple-hig) · [Fluent 2](#fluent-2) · [Design systems](#design-systems) · [Review checklist](#review-checklist)

Paraphrased from the public guidelines. Units: Material dp/sp, Apple pt, Fluent px; all density-independent, so 1dp = 1pt = 1px when translating a mockup. The host app's existing design wins over any of them unless the user asked for a redesign.

## Material 3 <a id="material-3"></a>

**Apply when** the target is Android (Views or Jetpack Compose), Flutter's default theme, Material Web components, Angular Material, or MUI. Default choice for Android-first products and for cross-platform apps whose primary audience is Android. Do not apply to an iOS-only app or a Windows desktop app.

Pillars: tonal colour (every colour is a role derived from a palette), one 4dp grid, one type scale with named roles, adaptive layout by window size class, and expressive motion.

### DO — foundations

- **Colour roles, not hex.** Key colours (primary, secondary, tertiary, error, neutral, neutral-variant) each become a tonal palette (tones 0-100). Roles pick a tone: light theme uses tone 40 for `primary`, 90 for `primary-container`, 10 for `on-primary-container`, white for `on-primary`. Dark theme flips to 80 / 30 / 90 / 20. Surfaces: `surface` is neutral 98 (light) or 6 (dark); `on-surface` 10 / 90. `outline` is neutral-variant 50 (light) / 60 (dark).
- **Surface container tiers carry elevation.** `surface-container-lowest`, `-low`, `-container`, `-high`, `-highest` step neutral tones 100/96/94/92/90 in light and 4/10/12/17/22 in dark. Higher tier = more prominent. Shadows exist (levels 0-5 = 0/1/3/6/8/12dp) but tonal tiers are the primary cue, especially in dark mode.
- **Dynamic colour.** On Android 12+ the scheme can derive from wallpaper or a seed colour. Design against roles so this works; never assume the brand hue is fixed. Contrast control (standard / medium / high) re-tones the same roles.
- **Type scale: 15 roles.** display L/M/S 57/45/36sp, headline L/M/S 32/28/24sp, title L/M/S 22/16/14sp, body L/M/S 16/14/12sp, label L/M/S 14/12/11sp. Display, headline and body are regular weight; title (except Title Large) and label are medium. Default face is Roboto; a brand face swaps in per role. Body Medium 14sp is the default reading size; Label Large 14sp medium is the button label.
- **Spacing on a 4dp grid.** Common steps 4/8/12/16/24/32/48. Screen margins 16dp on compact, 24dp on medium and wider. Pane spacers 24dp. Touch targets 48x48dp minimum even when the visual is smaller (icon buttons 40dp visual inside 48dp target).
- **Window size classes.** Width: compact < 600dp, medium 600-839, expanded 840-1199, large 1200-1599, extra-large >= 1600. Height: compact < 480, medium 480-899, expanded >= 900. Layout decisions key off width; height matters for landscape phones.
- **Canonical layouts.** List-detail (two panes from medium up), supporting pane (main + side pane), feed (responsive grid). Compact gets a single pane; medium and expanded show two.
- **Shape scale.** none 0, extra-small 4, small 8, medium 12, large 16, extra-large 28dp, full = pill. Cards and dialogs use medium-to-extra-large; chips and small buttons use small or full; FAB uses large.

### DON'T — foundations

- Don't paint elevation with drop shadows alone in dark mode; they vanish. Use the surface-container tier.
- Don't put text on `primary-container` without `on-primary-container`; the "on-" pair is what guarantees contrast.
- Don't use `outline` for text or `surface-variant` for primary surfaces; roles have one meaning.
- Don't build a 14-column desktop grid on compact; the grid is 4 columns under 600dp, 8 for medium, 12 from expanded up.

### DO — components

- **Buttons.** Five emphasis levels: filled (highest, the one final action), filled tonal (medium), elevated (only over patterned backgrounds), outlined (secondary action next to a filled one), text (lowest, dialogs and inline). Container 40dp tall, 24dp horizontal padding (16 with a leading icon), 18dp icon, 8dp icon-label gap, full-pill shape by default. One filled button per view.
- **FAB.** The single primary action of a screen. Sizes small 40dp, regular 56dp, large 96dp; extended FAB adds a label. Bottom-trailing on compact; in the rail on medium and wider. Never two FABs.
- **Navigation bar** (bottom, compact windows): 3-5 destinations, 80dp tall (64dp in the expressive variant), active indicator pill 56x32dp, labels on every item when 3 or fewer. **Navigation rail** (medium and expanded): 80dp wide, same destinations, optional FAB at top. **Navigation drawer** (expanded and wider, or modal on compact): 360dp wide, grouped destinations with headlines and dividers. Switch between them by window class, never by device type.
- **Top app bar.** Four sizes: center-aligned 64dp, small 64dp, medium 112dp, large 152dp; the large/medium forms collapse on scroll. Leading nav icon, title, up to three trailing actions, overflow menu for the rest.
- **Lists.** One-line 56dp, two-line 72dp, three-line 88dp rows; 16dp horizontal padding; leading avatar/icon/image and trailing meta or control. Dividers are inset to the text start.
- **Cards.** Elevated, filled, outlined. 12dp corner (medium), 16dp inner padding, one card = one coherent object; make the whole card tappable or none of it.
- **Dialogs** (basic and full-screen): 280-560dp wide, 28dp corner, headline, supporting text, actions right-aligned with the confirming action last. **Bottom sheets** (standard and modal): drag handle 32x4dp, top corners 28dp, modal sheets scrim the content.
- **Text fields.** Filled or outlined, 56dp tall, label floats into the top edge, supporting text 12sp below, error state recolours label/outline/supporting text to `error` and adds an icon.
- **Menus.** 48dp items, 112-280dp wide, 4dp corner, elevation level 2, leading icon optional and aligned.
- **Snackbar** for transient confirmation (one optional action), **banner** for persistent, **chips** (assist/filter/input/suggestion) 32dp tall with 8dp corner.

### DON'T — components

- Don't add a third navigation pattern; one of bar / rail / drawer per window class.
- Don't put destructive actions in a FAB or in the nav bar.
- Don't stack more than three actions in a dialog; move to a full-screen dialog.
- Don't shrink list rows below 48dp; the row is the touch target.

### DO — interaction and motion

- **State layers.** An overlay in the content colour on top of the container: hover 8%, focus 10%, pressed 10%, dragged 16%. Disabled: container at 12% and content at 38% of `on-surface`. Selected items swap to the `secondary-container` / `on-secondary-container` pair.
- **Focus** uses the same 10% layer plus a visible 3dp ring in `secondary` on keyboard/TV; never remove it.
- **Durations.** short1-4 = 50/100/150/200ms (small components, selection, state layers); medium1-4 = 250/300/350/400ms (sheets, menus, cards expanding); long1-4 = 450-600ms (full-screen transitions); extra-long 700-1000ms (ambient only). Longer distance = longer duration.
- **Easing.** Emphasized (default for on-screen moves), emphasized-decelerate (0.05, 0.7, 0.1, 1) for entering, emphasized-accelerate (0.3, 0, 0.8, 0.15) for exiting; standard (0.2, 0, 0, 1) for simple utility moves; standard-decelerate (0, 0, 0, 1); standard-accelerate (0.3, 0, 1, 1); linear only for opacity-only fades.
- **Transition patterns.** Container transform (card/FAB expands into its detail), shared axis x/y/z (sibling and parent-child navigation), fade through (unrelated destinations), fade (dialogs, menus, snackbars).
- **Spring motion** (expressive): spatial springs may overshoot (damping ~0.9), effect springs (colour, opacity) never do. Three speeds: fast, default, slow.

### DON'T — interaction and motion

- Don't exceed 400ms for anything the user triggered directly.
- Don't animate colour with an overshooting spring.
- Don't fade-through between a list and its detail; that pair is a container transform.

### DO — accessibility

- 48x48dp targets, 8dp between adjacent targets.
- Text contrast 4.5:1, large text (>= 24px regular or 18.7px bold, WCAG 18pt / 14pt bold) and UI 3:1; the tonal roles already meet this when the "on-" pair is used.
- Honour font scaling: use sp for text and let containers grow; test at 200%.
- TalkBack: every icon button has a `contentDescription`; decorative images are null; group a list row as one node with one label; announce state changes (selected, expanded) through semantics, not visuals only.
- Keyboard and D-pad: logical focus order, visible focus ring, Escape dismisses sheets and dialogs.
- Reduce-motion: replace container transforms with fades when the system setting is on.

### Concrete numbers

| Item | Value |
|---|---|
| Grid / touch target | 4dp / 48x48dp |
| Button height / padding | 40dp / 24dp |
| FAB sizes | 40 / 56 / 96dp |
| Nav bar / rail / drawer | 80dp tall / 80dp wide / 360dp wide |
| List rows | 56 / 72 / 88dp |
| Type: body M / label L / headline S | 14sp / 14sp medium / 24sp |
| Shape scale | 0 / 4 / 8 / 12 / 16 / 28dp / pill |
| State layers | hover 8%, focus 10%, pressed 10%, drag 16% |
| Disabled | container 12%, content 38% |
| Durations | 50-200 short, 250-400 medium, 450-600 long |
| Window classes (width) | <600, <840, <1200, <1600, >=1600dp |
| Elevation levels | 0, 1, 3, 6, 8, 12dp |

## Apple HIG <a id="apple-hig"></a>

**Apply when** the target is iOS, iPadOS, macOS, watchOS, tvOS or visionOS: SwiftUI, UIKit, AppKit, Mac Catalyst, and React Native or Flutter apps whose primary audience is iPhone. Also the right reference for web apps that want to feel native in Safari on iPhone. Do not apply its tab bar or sheet idioms on Android or Windows.

Pillars the HIG keeps repeating: clarity (legible text, precise icons, focus on content), deference (chrome yields to content, translucency hints at what is behind), depth (layers and realistic motion convey hierarchy). The current material system is Liquid Glass: a translucent, refractive layer reserved for navigation and controls that float above content.

### DO — foundations

- **Semantic system colours.** iOS: `label`, `secondaryLabel`, `tertiaryLabel`, `quaternaryLabel`, `placeholderText`, `separator`, `opaqueSeparator`, `link`. Backgrounds in two sets with three tiers each: `systemBackground` / `secondary` / `tertiary` for plain views, `systemGroupedBackground` tiers for grouped lists. Primary = whole view, secondary = grouping, tertiary = grouping inside secondary. macOS adds `windowBackground`, `controlBackground`, `controlAccent`, `selectedContentBackground`, `keyboardFocusIndicator`. All adapt to light, dark and Increase Contrast automatically.
- **Accent colour.** One app tint for interactive elements; on macOS the user's accent setting can override it. Use it for the single prominent action (the Done button) and for the selected tab, not for every control.
- **System colours** (red, orange, yellow, green, mint, teal, cyan, blue, indigo, purple, pink, brown, gray 1-6) each have light, dark and increased-contrast variants. Never hard-code their RGB; they shift between releases.
- **Typography.** SF Pro (SF Compact on watch, SF Mono for code, New York for serif). Text styles at the default Large size on iOS: Large Title 34/41, Title 1 28/34, Title 2 22/28, Title 3 20/25, Headline 17 semibold/22, Body 17/22, Callout 16/21, Subhead 15/20, Footnote 13/18, Caption 1 12/16, Caption 2 11/13 (pt size/leading). Default 17pt, minimum 11pt. macOS: Body 13pt, min 10pt, no Dynamic Type. watchOS 16/12, visionOS 17/12, tvOS 29/23.
- **Dynamic Type.** Seven standard sizes (xSmall to xxxLarge) plus five accessibility sizes (AX1-AX5, Body up to 53pt). Layout must reflow: stack inline items vertically, drop columns, grow icons (SF Symbols scale with text), avoid truncation. Keep tab titles and chrome fixed; scale content.
- **Weights.** Prefer Regular, Medium, Semibold, Bold. Avoid Ultralight, Thin, Light below ~20pt.
- **Layout.** Keep content inside the safe area (Dynamic Island, home indicator, rounded corners). Standard margins 16pt on iPhone, 20pt on iPad; readable content width guide for long text. Size classes: iPhone portrait is compact width + regular height; most iPhones landscape are compact height; iPad full screen is regular + regular, a 1/3 split is compact width. Put the primary content and action in the top half near the leading edge.
- **Materials.** Liquid Glass applies to the navigation layer (tab bars, toolbars, sidebars, sheets, popovers, menus, prominent buttons). It has no colour of its own; it takes colour from what is behind. Content stays opaque beneath it. Older system materials (ultra-thin to thick) remain for custom panels; vibrancy keeps text legible on them.
- **Shape.** Corners are concentric with the device and container: nested radius = outer radius minus inset. Sheets and windows gained larger radii; controls are rounder and come in an extra-large size. Full-width buttons on iPhone sit inset, rounded, above the bottom safe area.
- **Depth.** Hierarchy comes from layering (glass over content), blur and scale, not from stacked drop shadows. Flat chrome, dimensional content.

### DON'T — foundations

- Don't give controls custom opaque backgrounds that fight the system material; remove custom bar backgrounds.
- Don't stack glass on glass or apply glass to content (cards, list rows, images).
- Don't tint every toolbar button; one tinted prominent action per bar.
- Don't redefine semantic colours (separator as text, secondaryLabel as a background).
- Don't use a Material FAB, a hamburger drawer as primary nav, or Android-style snackbars.

### DO — components

- **Navigation.** iPhone: tab bar with 3-5 tabs for top-level sections, each a flat `NavigationStack`; the search tab is marked with the search role and sits at the trailing end; the bar may minimise on scroll. iPad and Mac: sidebar (`NavigationSplitView`, two or three columns), tab bar adapts into a sidebar when `sidebarAdaptable`. Back is always the leading item in the navigation bar; large titles collapse on scroll.
- **Toolbars.** Group related items that share one glass background; use a fixed spacer between groups; icons rather than text for common actions, never mixed within one group; every icon carries an accessibility label.
- **Buttons.** Styles: plain (text, inline), bordered (gray capsule), bordered-prominent (filled accent), glass and glass-prominent on bars. Sizes mini/small/regular/large/extra-large; minimum 44x44pt hit area; capsule or rounded-rect shape following container radius. Verb labels in title case, destructive role in red, cancel role on the leading side of a row of alert buttons (or at the bottom of a stacked layout).
- **Lists and tables.** Plain or inset-grouped (`.insetGrouped` is the default for settings-style screens). Row height grows with Dynamic Type (44pt base); section headers in title case; swipe actions mirror the top of the context menu; disclosure chevron means push, no chevron means toggle or action.
- **Sheets.** Modal task that keeps context: detents medium (half) and large; half sheets are inset from the edges and show content behind; include an explicit Done/Cancel in a navigation bar; use a full-screen cover only for immersive tasks. Popovers on iPad/Mac for the same role.
- **Alerts and action sheets.** Alert = title + at most two lines of message + 2-3 buttons (destructive in red, cancel last on the bottom-stack layout). Action sheet (confirmation dialog) anchors to its source control and lists 2-6 choices with Cancel at the end.
- **Menus.** Context menu on long-press/right-click, pull-down menu from a bar button; standard actions (Cut, Copy, Paste, Share, Delete) use their standard SF Symbols; destructive items last and red; submenus sparingly.
- **Text fields.** Rounded border on iOS, bezelled on macOS; placeholder hints, label above or inline in forms; clear button; keyboard type and content type set per field; validation inline below the field, not in an alert.
- **Search.** iPhone: search field in the bottom toolbar or search tab; iPad/Mac: upper trailing toolbar. It slides up with the keyboard.
- **Segmented control** for 2-5 mutually exclusive views; **toggle** for on/off; **stepper** for small ranges; **slider** for continuous values; **picker** (wheel, menu, inline) for lists; **progress** indicators determinate when the length is known.
- **Windows (iPad/Mac).** Support any size; split views reflow continuously; keep critical controls away from the bottom of a Mac window.

### DON'T — components

- Don't show more than five tabs on iPhone; the sixth becomes "More", which hides features.
- Don't use a sheet for a one-line confirmation (use an alert) or an alert for anything with input beyond one field.
- Don't put a back button inside content; navigation chrome owns it.
- Don't add custom visual-effect views behind popovers and sheets; the system supplies the material.
- Don't render section headers in all caps; the system now title-cases them.

### DO — interaction and motion

- **Feedback is physical.** Pressed controls dim or scale slightly; sliders and toggle knobs turn into glass while dragging; buttons morph into the menus or popovers they open; sheets rise with spring motion.
- **Durations.** System transitions run roughly 0.2-0.35s (push/pop ~0.35s, modal present ~0.4s, button highlight ~0.1s). Prefer SwiftUI springs (`.smooth`, `.snappy`, `.bouncy`) with 0.3-0.5s response; interruptible and driven by gesture velocity.
- **Scroll edge effect.** Content blurs/fades as it passes under bars so controls stay legible; custom bars register for it rather than painting a background.
- **Focus (tvOS, keyboard, Full Keyboard Access).** Focused items lift and scale with a glass highlight; keep focusable items spaced so the enlarged state does not collide. On macOS the focus ring uses `keyboardFocusIndicatorColor`.
- **Gestures.** Edge swipe = back, pull-down = refresh or dismiss, long press = context menu. Never override a system gesture; keep controls off the bottom edge where the home indicator lives.
- **Haptics** confirm success, warning and selection changes on iPhone and Watch; pair with visual feedback, never alone.
- **Reduce Motion.** Replace slides and zooms with cross-fades; stop auto-playing and parallax effects. Reduce Transparency and Increase Contrast make glass more opaque and colours stronger; test all three together.

### DON'T — interaction and motion

- Don't animate for decoration longer than ~0.5s or loop ambient animation near reading content.
- Don't block interaction while a transition plays; the system makes animations interruptible and so should custom ones.
- Don't use colour alone to show focus on tvOS; scale and highlight do it.

### DO — accessibility

- 44x44pt minimum hit area everywhere, even if the glyph is 24pt.
- Contrast 4.5:1 for text, 3:1 for large text and interactive or state-bearing elements; verify in light, dark, Increase Contrast and over translucent materials.
- Dynamic Type at every size incl. AX5; Bold Text respected; custom fonts must scale the same way.
- VoiceOver: accessibility label (what), value (state), hint (result), traits (button, header, selected); group compound rows into one element; mark decorative images hidden; headings for navigation by rotor.
- Switch Control and Voice Control need visible labels that match spoken names.
- Button Shapes setting adds underline/outline to plain buttons; don't rely on colour to mark text as tappable.
- Right-to-left: the system mirrors layout, navigation direction and most symbols; keep numerals, media controls and logos unmirrored.

### Concrete numbers

| Item | Value |
|---|---|
| Hit target | 44x44pt |
| Body / default / min text | 17pt / 17pt / 11pt (iOS); 13 / 10pt (macOS) |
| Large Title / Title 1 / Headline | 34 / 28 / 17pt semibold |
| Margins | 16pt iPhone, 20pt iPad |
| Tab bar items | 3-5 |
| List row base height | 44pt |
| Alert buttons | 2-3 |
| Sheet detents | medium, large |
| System transition | ~0.2-0.35s, spring-based |
| Contrast | 4.5:1 text, 3:1 UI and large text |
| Dynamic Type sizes | 7 standard + 5 accessibility |

## Fluent 2 <a id="fluent-2"></a>

**Apply when** the target is Windows (WinUI 3, Windows App SDK, WPF with Fluent theme), Microsoft 365 add-ins and Teams apps, Fluent UI React v9 web apps, Fluent UI iOS/Android for Microsoft-branded mobile, Power Apps, or any web product whose users live in Microsoft tools. Do not apply its square geometry and Segoe type on an iOS consumer app.

Pillars: tokens first (global -> alias, themed per light/dark/high-contrast/brand), layered surfaces (Mica base, content layer, flyout layer), three densities, restrained motion, and inclusive design (the system is designed to WCAG 2.x AA).

### DO — foundations

- **Two-tier tokens.** Global tokens hold raw values (`colorPaletteBlueForeground2`, `fontSizeBase300`, `durationFast`); alias tokens give them a role (`colorNeutralForeground1`, `colorBrandBackgroundHover`, `shadow8`). Components consume alias tokens only. Theme = a different alias map over the same globals.
- **Colour ramps.** Neutral grey ramp (grey 2-98, plus white/black and alpha variants) and a brand ramp (brand 10-160). Alias roles: `colorNeutralForeground1-4` (grey 14/26/38/44 in light: strongest to weakest text), `colorNeutralBackground1-6` (white, grey 98/96/94/92/90), `colorNeutralStroke1/2` (grey 82/88), `colorBrandBackground` (brand 80; hover 70, pressed 40, selected 60), `colorBrandForeground1/2` and `colorBrandForegroundLink`, `colorNeutralForegroundDisabled` (grey 74), `colorStrokeFocus1/2` (white/black double ring), `colorSubtleBackground` (transparent at rest, grey on hover/pressed), `colorCompoundBrandStroke` for checked controls. Status families: success (green), warning (yellow), danger (red), severe (dark orange), important (brand), informative (grey).
- **State suffixes.** `Hover`, `Pressed`, `Selected`, `Disabled` on backgrounds, strokes and foregrounds; hover is one step, pressed two steps along the ramp.
- **Typography.** Segoe UI (Segoe UI Variable on Windows 11), system-ui fallback, Consolas for mono. Ramp: caption2 10/14, caption1 12/16, body1 14/20 (default), body1Strong 14/20 semibold, body2 16/22, subtitle2 16/22 semibold, subtitle1 20/28 semibold, title3 24/32, title2 28/36, title1 32/40, largeTitle 40/52, display 68/92 (px size/line height; titles semibold). Weights 400/500/600/700.
- **Spacing on a 4px grid.** Tokens None 0, XXS 2, XS 4, SNudge 6, S 8, MNudge 10, M 12, L 16, XL 20, XXL 24, XXXL 32, each in horizontal and vertical form. Components pad 8-12px; page gutters 16-24px; section gaps 24-32px.
- **Density.** Three sizes on most controls: small (24px tall), medium (32px, default), large (40px). Dense data grids use the extra-small (24px) or small (34px) DataGrid rows; forms use medium.
- **Shape.** The Fluent 2 site lists corner radii None 0, Small 2, Medium 4 (default control corner), Large 8 (cards, dialogs, flyouts on Windows), X-Large 12, Circle (pills and avatars). The Fluent UI React v9 code tokens differ slightly: `borderRadiusNone/Small/Medium/Large/XLarge/Circular` = 0/2/4/6/8/circular; the numbers table below follows the site values. Windows 11: 4px controls, 8px windows and popups. Stroke widths 1px (thin, default), 2px (thick, focus), 3px (thicker), 4px (thickest).
- **Layering and elevation.** Windows: Mica is the base layer painted once per window (tinted by wallpaper, falls back to solid when inactive or on battery saver); Mica Alt gives stronger tint for tabbed title bars; a content layer (`LayerFillColorDefault`) sits on top as a contiguous surface or separate cards; Acrylic is for transient surfaces only (flyouts, menus, context menus). Web: shadows `shadow2/4/8/16/28/64` map to resting cards (2-4), hover and popovers (8-16), dialogs (28), and teaching callouts (64); brand shadows carry the brand tint.
- **Layout.** Fluent web breakpoints: small under 480px, medium 480-639, large 640-1023, x-large 1024-1365, xx-large 1366-1919, xxx-large 1920 up. Windows apps: 4-column grid up to 640px, 6 columns for 641-1007px, 12 columns at 1008px+; left nav collapses from expanded (320px) to compact (48px) to minimal.
- **Iconography.** Fluent UI System Icons (web, mobile) or Segoe Fluent Icons (Windows); regular and filled variants, sizes 12-48; filled marks the active state.

### DON'T — foundations

- Don't reference global tokens (`colorPaletteRedBackground1`, grey ramp values) in components; alias only.
- Don't apply Mica or Acrylic to individual controls; one material per window, on the base layer.
- Don't invent a fourth density; pick small/medium/large and stay there across a surface.
- Don't skip the high-contrast theme; it is a first-class alias map on Windows and the tokens already carry it.

### DO — components

- **Button.** Appearances: primary (brand fill, one per surface), secondary (default, neutral outline), subtle (transparent until hover), outline, transparent. Sizes small/medium/large (24/32/40px), 4px corner, icon-only buttons square, menu button and split button for grouped commands. Toggle button for stateful commands.
- **Navigation.** Windows: NavigationView with left pane (expanded, compact, minimal modes) and top mode; the back button sits in the title bar; settings at the pane bottom. Web (Fluent UI React v9): `Nav` sidebar with category groups, `TabList` for in-page sections, `Breadcrumb` for hierarchy, `Toolbar` for commands, command bar / `Menu` overflow for the rest. Tab bars on mobile Fluent follow each OS: tab bar on iOS, navigation bar on Android.
- **Lists and data.** `DataGrid`/`Table` with extra-small 24px, small 34px or medium 44px rows (Fluent UI React v9), header sorting, row selection via checkbox column; `List` for simple vertical collections; `Tree` for hierarchy; virtualise above ~100 rows.
- **Cards.** `Card` with header/preview/footer slots, 4-8px corner, `shadow4` at rest and `shadow8`/`shadow16` on hover when interactive; selectable cards use a checkbox and a brand stroke.
- **Dialog and drawer.** `Dialog` (modal or non-modal, alert type for destructive confirms) with title, body, and actions aligned to the trailing edge, primary last; `Drawer` (overlay or inline) for side panels; Windows `ContentDialog` for the same role; `Teaching popover` for coach marks.
- **Inputs.** `Input`/`Textarea` with label above, 32px tall, `Field` wrapper carries label, hint, validation message and required marker; `Combobox`/`Dropdown`, `Checkbox`, `Radio group`, `Switch`, `Slider`, `SpinButton`, `DatePicker`; validation state recolours the stroke to danger and shows a message below.
- **Menus and flyouts.** `Menu` with `MenuItem`, checkable and radio items, submenus, dividers; 32px items; Acrylic background on Windows; `Popover` for lightweight content; `Tooltip` after ~250ms hover.
- **Feedback.** `MessageBar` (inline status, intents info/success/warning/error), `Toast` (transient, bottom-end by default, dismissible), `ProgressBar` and `Spinner`, `Skeleton` for loading layouts, `Badge` for counts and status.

### DON'T — components

- Don't use more than one primary button on a surface.
- Don't place destructive actions as the default/primary in a dialog; secondary styling plus danger colour.
- Don't open a dialog from a dialog; use a drawer or a multi-step surface.
- Don't rely on toasts for errors the user must act on; use a MessageBar or inline Field validation.

### DO — interaction and motion

- **Durations.** `durationUltraFast` 50ms, `Faster` 100, `Fast` 150, `Normal` 200 (default for most state changes), `Gentle` 250, `Slow` 300, `Slower` 400, `UltraSlow` 500. Small elements fast, large surfaces slow; page transitions 300-400ms.
- **Curves.** `curveAccelerateMax/Mid/Min` for exits (0.9,0.1,1,0.2 / 1,0,1,1 / 0.8,0,0.78,1), `curveDecelerateMax/Mid/Min` for entrances (0.1,0.9,0.2,1 / 0,0,0,1 / 0.33,0,0.1,1), `curveEasyEase` (0.33,0,0.67,1) and `curveEasyEaseMax` (0.8,0,0.2,1) for on-screen moves, `curveLinear` for opacity.
- **States.** Rest, hover (background one ramp step), pressed (two steps, slight scale on Windows), selected (brand stroke or `colorNeutralBackground1Selected`), focus (2px double ring: `colorStrokeFocus2` inside, `colorStrokeFocus1` outside), disabled (grey 74 text on grey 94 background, no hover).
- **Windows motion.** Connected animations between pages, implicit show/hide and reposition, directional page transitions (drill-in, slide); 150-300ms.
- **Mobile.** Fluent iOS and Android follow the host OS gesture and motion model; tokens and icons carry the Fluent identity.

### DON'T — interaction and motion

- Don't use an accelerate curve for an entrance or a decelerate curve for an exit.
- Don't exceed 500ms on anything user-triggered.
- Don't animate layout on every keystroke in dense data UIs.

### DO — accessibility

- Target WCAG 2.x AA: 4.5:1 text, 3:1 large text and UI parts; the alias tokens are tuned so that foreground1-3 on background1-6 pass.
- Minimum pointer target 24x24px on desktop (WCAG 2.2 AA), 44px on touch; keep 32px controls spaced at least 4px apart.
- Keyboard: Tab order follows reading order, arrow keys within composite widgets (menus, tabs, grids), Escape closes flyouts, focus returns to the trigger, visible double focus ring on every interactive element.
- Narrator and other screen readers: every control has an accessible name (label, `aria-label`, or `AutomationProperties.Name`), roles via native components, live regions for toasts and progress, headings for sections.
- High contrast: Windows high-contrast themes replace colours with system colours; keep borders on all controls so they survive the swap, never encode state in fill only.
- Text scaling: Windows text scaling up to 225% and browser zoom to 400% without horizontal scroll at 320px.
- Reduced motion: honour `prefers-reduced-motion` and the Windows animation setting; swap slides for fades.

### Concrete numbers

| Item | Value |
|---|---|
| Grid | 4px; spacing 2/4/6/8/10/12/16/20/24/32 |
| Control heights | 24 / 32 / 40px (small/medium/large) |
| Corner radius (site values) | 0 / 2 / 4 (controls) / 8 (dialogs, windows) / 12 / circle |
| Stroke | 1px default, 2px focus/thick |
| Type: body1 / subtitle1 / title1 | 14/20 / 20/28 / 32/40px |
| Durations | 50 / 100 / 150 / 200 / 250 / 300 / 400 / 500ms |
| Shadows | 2 / 4 / 8 / 16 / 28 / 64 |
| Grey ramp for text | 14 / 26 / 38 / 44 (foreground1-4), 74 disabled |
| Targets | 24px pointer min, 44px touch |
| Contrast | 4.5:1 text, 3:1 UI |

## Design systems <a id="design-systems"></a>

What a design system is, according to Figma's design-system examples article: a shared source of truth made of reusable UI kits (buttons, forms, icons), design tokens (colour, spacing, type values), patterns (how composed elements behave: navigation bars, modals, forms) and documentation on when and how to use each. The article's examples each note which teams they fit; it does not cover governance, contribution or versioning, so the governance notes below are magician's own.

Examples the article names: Material Design 3 (Google; open source, dynamic colour, Android and adaptive web), Apple Human Interface Guidelines (native Apple platforms), Polaris (Shopify; admin, POS and mobile commerce, accessibility-focused), Carbon (IBM; large enterprise, strong accessibility standards), Atlassian Design System (Jira, Confluence, Trello coherence), Base (Uber; one framework across rides, delivery and more), Arco (ByteDance; enterprise theming lab), TapTap, Dialect, Finesse UI, and two Figma Community templates (Simple Design System, Wanted). Fluent is not on that list; it is covered above because the plugin targets Windows too.

### What the good ones share

- **Layered:** tokens -> components -> patterns -> documentation. Each layer references only the one below it. Material's colour roles, Apple's semantic colours and Fluent's alias tokens are the same idea with different names.
- **Semantic, not literal, names.** `surface`, `on-surface`, `label`, `colorNeutralForeground1` say where a value goes; `blue-500` says what it is. Components read semantic names only.
- **Theming is a second value map,** not a second component set: light, dark, high contrast, brand variants all swap the alias layer.
- **Named states on every component:** rest, hover, focus, pressed, selected, disabled, error, loading, empty.
- **Accessibility built into the tokens** (contrast-tested pairs, focus colours, minimum targets) rather than audited per screen.
- **Documentation with do/don't pairs and usage rules** ("one primary button per view", "3-5 tabs"), plus platform-specific adaptations (Fluent iOS, Material on Compose, Polaris mobile).
- **Governance (magician guidance):** one owner, a contribution path, semantic versioning of the token package, a change log, and a deprecation window. A project's `design-tokens.css` is its tiny design system; treat it that way.

### Structuring a project's token file

Follow the two-tier model in `skills/conjure/references/design-tokens.md`; it maps one-to-one onto the platform systems:

| Tier | magician name | Material | Apple | Fluent |
|---|---|---|---|---|
| 1 primitives | `--c-HUE-STEP`, `--step-N`, `--space-N`, `--radius-*`, `--dur`, `--ease` | tonal palettes (tone 0-100), type scale, shape scale | system colour values, text styles | global tokens (ramps, `fontSizeBase300`, `durationFast`) |
| 2 semantics | `--bg`, `--surface`, `--surface-2`, `--text`, `--text-muted`, `--border`, `--accent`, `--accent-text`, `--focus`, `--elev-1/2` | colour roles (`surface-container`, `on-surface`, `primary`) | `systemBackground`, `label`, `separator`, accent | alias tokens (`colorNeutralBackground1`, `colorNeutralForeground1`, `colorBrandBackground`) |

Rules that follow from all three systems:

- **Tier 1 is named by value, tier 2 by role.** Components reference only `var(--semantic-name)`; a raw hex or `--c-*` inside component CSS is a bug (the self-check grep in design-tokens.md).
- **Dark mode is the second map of tier 2** on `[data-theme="dark"]`: same names, re-pointed to other primitives. Surfaces get lighter as they rise (Material tiers, Fluent background1-6 reversed), accents go one step lighter and less saturated (Material tone 40 -> 80, the `--c-accent-400` rule), borders become low-alpha light, shadows give way to tint.
- **Add role groups as the mockup needs them,** in this order and with these names so later skills can rely on them: status (`--success`, `--warning`, `--danger`, `--info` and their `-bg` variants), state layers (`--hover`, `--pressed` as alpha overlays of `--text` at 8%/10%), `--focus` ring colour plus `--focus-ring-width` 2px, `--radius-control` / `--radius-container`, `--dur-fast/normal/slow` (100/200/300ms) and `--ease-in/out/standard`.
- **Type roles are tokens too:** `--font-display`, `--font-sans`, `--font-mono` plus the fluid `--step-*` scale; map them to platform role names in the spec (e.g. `--step-3` = Material headline-small = Apple Title 2 = Fluent title3).
- **Spacing stays on one grid:** 4px (Material, Fluent) or 8pt rhythm with 4pt half-steps (Apple); `--space-N` values must be multiples of it.
- **Density and viewport are parameters, not themes:** breakpoints (`--bp-tablet` 640, `--bp-desktop` 1024, `--bp-wide` 1440) and an optional `[data-density="compact"]` map that only shrinks `--space-*` and control heights.
- **Emit the file** to `.workspace/shared/design-tokens.css` and reference it from `brand.md` and `spec.md` so `/blueprint`, `/weave` and `/ward` build against the exact names.

## Review checklist <a id="review-checklist"></a>

Run before a mockup or design proposal is shown. Each item is pass/fail; note the failing number in the gate message. Items 1-2 are gates: if they fail, stop and fix before judging the rest.

1. **Existing-app consistency.** The mockup reuses the host app's tokens, components, typography and navigation. New tokens appear only when none exist, or a visual rework was requested explicitly.
2. **Platform idiom match.** Navigation, modals, buttons and lists follow the target's system (Material 3 / Apple HIG / Fluent 2 per the sections above); no cross-platform borrowing (FAB on iOS, iOS tab bar on Windows, hamburger drawer as primary nav on iPhone).
3. **Token discipline.** Component CSS references semantic tokens only; no raw hex/rgb or tier-1 names outside the token blocks.
4. **Text contrast >= 4.5:1** for body text in both light and dark maps; large text (>= 24px regular / 18.7px bold) >= 3:1.
5. **UI contrast >= 3:1** for control boundaries, icons, focus rings and state indicators against adjacent colours.
6. **Target sizes:** 44x44pt (Apple), 48x48dp (Material), 24px pointer / 44px touch (Fluent); >= 8px between adjacent targets.
7. **Type scale uses named roles** (display/headline/title/body/label, or the HIG/Fluent equivalents), body at the platform default (17pt / 14-16sp / 14px), nothing below the platform minimum (11pt / 12sp / 10px), weights no lighter than Regular for small text.
8. **Spacing on the grid:** every margin, gap and padding is a multiple of 4 (or the app's own base); page margins match the platform (16/24dp, 16/20pt, 16-24px).
9. **Every interactive element shows all states:** default, hover, focus, pressed, selected, disabled; forms add error; async views add loading, empty and error screens.
10. **Focus is visible** (ring >= 2px, 3:1 against background) and never removed; Tab order matches reading order.
11. **Responsive classes covered** for each target viewport chosen at GATE 3 (phone 390 / tablet 834 / desktop 1280 / wide 1600) and the navigation component changes with window class, not device.
12. **Dark mode parity:** the dark map is the same layout with re-pointed tokens; surfaces rise by tint, accents one step lighter, no pure #000, contrast re-verified.
13. **Motion durations** within the platform range (Material 50-400ms user-triggered, Apple ~0.2-0.35s springs, Fluent 100-500ms with page transitions 300-400ms, never above 500ms), entrances decelerate, exits accelerate.
14. **Reduced motion honoured:** slides, zooms and container transforms degrade to fades; no auto-playing loops.
15. **RTL and localisation:** layout mirrors (leading/trailing, not left/right); labels tolerate ~30% longer strings and German/Finnish compound words without truncating critical text; numerals and media controls stay unmirrored.
16. **Font scaling:** layout reflows at 200% (Dynamic Type AX sizes, Android font scale 2.0, Windows 225%) with no clipped or overlapping text.
17. **Accessibility names:** every icon-only control, image and form field has a label; decorative images are marked hidden; compound rows read as one element with state.
18. **Keyboard navigation:** all actions reachable by keyboard, Escape closes transient surfaces and returns focus to the trigger, arrow keys work inside menus/tabs/grids.
19. **One primary action per view** (one filled/prominent/primary button, one FAB at most); destructive actions styled as such and never the default.
20. **Navigation limits:** 3-5 top-level destinations; back/up is where the platform puts it; deep links land on a screen with a way back.
21. **Dialog hygiene:** titles are questions or statements of the action, 2-3 buttons, confirming action in the platform's position, cancel always present and reachable.
22. **Colour is never the only carrier** of status, selection or interactivity; icon, text or shape backs it up.
23. **Material/elevation sanity:** no glass-on-glass (Apple), no shadow-only elevation in dark mode (Material), Mica/Acrylic once per window and only on the right layer (Fluent).
24. **Density consistent** across the surface (one of compact/default/comfortable or Fluent small/medium/large).
25. **Handoff artefacts present:** `brand.md` (archetype, seed, viewports), `design-tokens.css` (both maps), and the spec references the exact token and component names used in the mockup.
