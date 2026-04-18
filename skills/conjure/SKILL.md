---
name: conjure
description: Structured design dialogue with visual companion — produces an approved spec and design artifacts before any implementation begins
keep-coding-instructions: true
---

# /conjure — Design Dialogue

Run a structured design dialogue before writing any code. Produce an approved spec and optional visual design artifacts.

<HARD-GATE>
Do NOT write any code, scaffold any project, or take any implementation action until the user has approved the spec. This applies regardless of perceived simplicity.
</HARD-GATE>

---

## Process — Gated Dialogue

**Core rule: each gate is one turn. End your turn after each gate. Do NOT advance to the next gate until the user replies. Never collapse two gates into one message.**

### Step 1 — Explore
Read relevant files, recent git log, existing specs in `.workspace/shared/specs/`. Note detected stack and archetype from session additionalContext. Do this silently before asking anything.

### Step 2 — Clarify (one question per turn)
Ask one clarifying question. End your turn. Wait for the answer. Repeat until you understand purpose, constraints, success criteria, and edge cases. Skip stack questions the inspector already answered. Use multiple choice when possible.

---
### GATE 0 — Design Mode
Present the design mode options as its own message (see Design Mode section below). End your turn. **Do not propose approaches until the user picks a mode.**

If visual mode chosen: start the visual companion server now (see Visual Companion → Starting). Open the browser. Tell user the URL. Then proceed to GATE 1.

---
### GATE 1 — Approach Selection

Present 2–3 approaches.

**If visual mode:** write the approach comparison screen (`$VC_SCREENS/v1/approaches.html`), tell user the URL and a one-sentence summary of each approach. End your turn. On the next turn read `$VC_STATE/events` for their click choice plus their terminal message.

**If text mode:** present the approaches in text. End with: *"Which approach would you like to go with?"* End your turn.

**Do not present architecture until the user confirms an approach.**

---
### GATE 2 — Architecture Review

Present the architecture for the chosen approach only.

**If visual mode:** write the architecture diagram screen (`$VC_SCREENS/v1/architecture.html`). Tell user the URL and describe the diagram in 2 sentences. End your turn. Wait for their feedback.

**If text mode:** present the architecture (file structure, data flow, component responsibilities). End with: *"Does this architecture make sense, or do you want to change anything?"* End your turn.

Iterate on changes if requested. Only advance when user explicitly approves.

---
### GATE 3 — UI Design (skip if no UI involved)

If the feature has a UI, present a mockup.

**If visual mode:** write the mockup screen (`$VC_SCREENS/v1/mockup.html`) as a full-document design applying frontend-design quality rules. Tell user the URL. End your turn. Iterate on versions if requested. Capture a Playwright screenshot when approved.

**If text mode:** describe the UI layout and key interactions. End with: *"Does this design direction look right?"* End your turn.

Only advance when user explicitly approves the design.

---
### GATE 4 — Spec Approval

Write the full spec to `.workspace/shared/specs/YYYY-MM-DD-<feature>.md`. Then say:

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
> **A — Visual + Strict** — I open a design companion in your browser. I show approach options, architecture diagrams, and UI mockups as interactive screens you can click. Approved designs become binding implementation targets — forge tasks must match them exactly.
>
> **B — Visual + Reference** — Same visual companion, but designs are advisory. Implementation can deviate with good reason.
>
> **C — Text only** — Skip the browser companion. Everything happens here in the terminal.

End your turn. Wait for their reply before doing anything else.

Map reply to mode:
- `VISUAL_STRICT` → visual companion active, designs are binding in forge
- `VISUAL_REFERENCE` → visual companion active, designs are advisory in forge
- `TEXT_ONLY` → no visual companion

If the user says "skip" at any point during the session: immediately switch to TEXT_ONLY, stop the companion server if running, continue text-only.

### Permission Setup (Visual modes only)

Immediately after the user picks A or B, before starting the server, check whether `.workspace/**` permissions already exist:

```bash
python3 -c "
import json, os
s = json.load(open('.claude/settings.json')) if os.path.exists('.claude/settings.json') else {}
allows = s.get('permissions', {}).get('allow', [])
print('ok' if any('.workspace' in a for a in allows) else 'missing')
"
```

If `missing`, send this message — and nothing else. Do not start the server yet:

> **Quick setup:** The visual companion writes design screens and reads click events inside `.workspace/shared/designs/`. Without permission rules, Claude Code will ask for approval on every file operation during the session — that's a lot of interruptions.
>
> I can add these wildcard rules to `.claude/settings.json` now so the companion runs uninterrupted:
> - `Write(.workspace/**)` — writing design screens to disk
> - `Read(.workspace/**)` — reading click events and server state
> - `Bash(> .workspace/**)` — resetting event log between screens
> - `Bash(mkdir* .workspace/**)` — creating version directories
> - `Bash(bash *conjure/scripts/vc-*.sh*)` — companion server lifecycle
> - `Bash(node *conjure/scripts/server.cjs*)` — Node.js server process
> - `Bash(open http://localhost:*)` — opening browser to companion URL
>
> **Add these? (yes / no)**
> If no, the companion still works — you'll just see approval prompts for each operation.

**End your turn. Wait for their reply before starting the companion server.**

If **yes**: write or merge the rules into `.claude/settings.json`:

```python
import json, os

path = ".claude/settings.json"
s = json.load(open(path)) if os.path.exists(path) else {}
s.setdefault("permissions", {}).setdefault("allow", [])

new_rules = [
    "Write(.workspace/**)",
    "Read(.workspace/**)",
    "Bash(> .workspace/**)",
    "Bash(mkdir* .workspace/**)",
    "Bash(bash *conjure/scripts/vc-*.sh*)",
    "Bash(node *conjure/scripts/server.cjs*)",
    "Bash(open http://localhost:*)",
]
for r in new_rules:
    if r not in s["permissions"]["allow"]:
        s["permissions"]["allow"].append(r)

os.makedirs(".claude", exist_ok=True)
json.dump(s, open(path, "w"), indent=2)
print("Permissions added.")
```

Then say: "Permissions saved. Starting the companion..." and proceed immediately to start the server.

If **no** (or if rules already existed): proceed to start the server without any further permission discussion. The user has made their choice; do not ask again.

---

## Visual Companion

The visual companion is a local Node.js WebSocket server that serves interactive HTML design screens in the user's browser. Each screen is a file Claude writes to disk; the server auto-reloads the browser on every new file.

**URL format:** `http://localhost:{PORT}/magician/{project}/v{n}/`

- `{project}` — derived from the project directory name or feature name
- `v{n}` — prototype version, starting at 1; increment when you meaningfully revise a complete design (not every tweak)
- Each version has its own directory: `.workspace/shared/designs/{date}-{feature}/screens/v{n}/`

### Starting the Companion

```bash
DESIGN_DIR=".workspace/shared/designs/$(date +%Y-%m-%d)-<feature>"
mkdir -p "$DESIGN_DIR"
SERVER_JSON=$(bash "${CLAUDE_PLUGIN_ROOT}/skills/conjure/scripts/vc-start.sh" "$DESIGN_DIR" "<project-name>")
VC_URL=$(echo "$SERVER_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['url_base'])")
VC_STATE="$DESIGN_DIR/state"
VC_SCREENS="$DESIGN_DIR/screens"
```

Then open the browser automatically:
```bash
open "${VC_URL}/v1/" 2>/dev/null || xdg-open "${VC_URL}/v1/" 2>/dev/null || true
```

Tell the user: "Design companion open at `{VC_URL}/v1/` — take a look while I explain the options."
Do NOT add further ceremony. One line.

### The Interaction Loop

After writing each screen file:
1. Tell user the current URL + a 1–2 sentence text summary of what's on screen
2. End your turn — let the user look, click choices, and respond
3. On your next turn: read `$VC_STATE/events` — one JSON line per click, last line = final selection
4. Read their terminal message for textual feedback
5. **Iterating same screen:** write `screen-v2.html`, `screen-v3.html` etc. (always a new filename — the server reloads on any new file)
6. **Moving to next design step:** write a semantically different filename
7. **Major revision (new prototype):** increment version: write to `$VC_SCREENS/v2/approaches.html`, tell user the new URL

Clear `events` file yourself before each new screen write so previous clicks don't pollute next reads:
```bash
> "$VC_STATE/events"
```

### Stopping the Companion

```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/conjure/scripts/vc-stop.sh" "$DESIGN_DIR"
```

Call this at the end of conjure (after spec commit) or if user switches to TEXT_ONLY.

---

## Screen Types

### 1. Approach Comparison

Write as a **fragment** (no `<!DOCTYPE>`) to `$VC_SCREENS/v1/approaches.html`.
The server wraps it in the Magician frame template.

```html
<h1 class="page-title">Choose Your Approach</h1>
<p class="page-subtitle">Click a card to select. Your choice appears in the bar above.</p>

<div class="approaches">

  <div class="approach-card" data-choice="a" data-text="[Name of approach A]">
    <span class="badge badge-simple">Option A</span>
    <h3 class="card-title">[Approach A name]</h3>
    <p class="card-desc">[2 sentences: what it is and the core tradeoff]</p>
    <div class="pros-cons">
      <ul class="pros">
        <div class="pros-label">Pros</div>
        <li>[strength 1]</li>
        <li>[strength 2]</li>
      </ul>
      <ul class="cons">
        <div class="cons-label">Cons</div>
        <li>[weakness 1]</li>
        <li>[weakness 2]</li>
      </ul>
    </div>
    <div class="complexity">
      <span class="complexity-label">Complexity</span>
      <div class="complexity-dot filled"></div>
      <div class="complexity-dot"></div>
      <div class="complexity-dot"></div>
    </div>
  </div>

  <div class="approach-card recommended" data-choice="b" data-text="[Name of recommended approach]">
    <span class="badge badge-recommended">★ Recommended</span>
    <h3 class="card-title">[Approach B name]</h3>
    <p class="card-desc">[2 sentences]</p>
    <div class="pros-cons">
      <ul class="pros"><div class="pros-label">Pros</div><li>[strength 1]</li><li>[strength 2]</li><li>[strength 3]</li></ul>
      <ul class="cons"><div class="cons-label">Cons</div><li>[weakness 1]</li></ul>
    </div>
    <div class="complexity">
      <span class="complexity-label">Complexity</span>
      <div class="complexity-dot filled"></div>
      <div class="complexity-dot filled"></div>
      <div class="complexity-dot"></div>
    </div>
  </div>

  <div class="approach-card" data-choice="c" data-text="[Name of approach C]">
    <span class="badge badge-complex">Option C — Advanced</span>
    <h3 class="card-title">[Approach C name]</h3>
    <p class="card-desc">[2 sentences]</p>
    <div class="pros-cons">
      <ul class="pros"><div class="pros-label">Pros</div><li>[strength 1]</li></ul>
      <ul class="cons"><div class="cons-label">Cons</div><li>[weakness 1]</li><li>[weakness 2]</li></ul>
    </div>
    <div class="complexity">
      <span class="complexity-label">Complexity</span>
      <div class="complexity-dot filled"></div>
      <div class="complexity-dot filled"></div>
      <div class="complexity-dot filled"></div>
    </div>
  </div>

</div>

<div class="approve-strip">
  <p>Click your preferred approach above, then tell me in the terminal. I'll explain the architecture in detail.</p>
</div>
```

### 2. Architecture Diagram

Write as a fragment to `$VC_SCREENS/v1/architecture.html`. Use real Mermaid syntax.

```html
<h1 class="page-title">[Feature] Architecture</h1>
<p class="page-subtitle">[One sentence describing the design]</p>

<div class="arch-container">
  <div class="arch-title">System Overview</div>
  <div class="mermaid">
graph TD
    A([Client / Browser]) --> B[API Gateway]
    B --> C[Auth Middleware]
    C --> D[Feature Service]
    D --> E[(PostgreSQL)]
    D --> F[(Redis Cache)]
    F -.->|cache miss| E
    style D fill:#7c3aed,color:#fff
    style E fill:#1a1a2e,color:#e2e8f0
    style F fill:#1a1a2e,color:#e2e8f0
  </div>
</div>

<hr>

<div class="section-label">Component Responsibilities</div>
<div class="approaches">
  <div class="approach-card" style="cursor:default">
    <span class="badge badge-neutral">Gateway</span>
    <h3 class="card-title">[Component]</h3>
    <p class="card-desc">[What it does and why it's separate]</p>
  </div>
  <div class="approach-card" style="cursor:default">
    <span class="badge badge-neutral">Service</span>
    <h3 class="card-title">[Component]</h3>
    <p class="card-desc">[What it does and why it's separate]</p>
  </div>
</div>

<div class="approve-strip">
  <p>Does this architecture match your mental model? Tell me what to change or say <strong>"approve architecture"</strong>.</p>
</div>
```

### 3. UI Mockup — Full Document

For UI features, write a **full HTML document** (starts with `<!DOCTYPE html>`) to `$VC_SCREENS/v1/mockup.html`.
The server serves it as-is and injects only the helper + connection bar.

Apply frontend-design quality rules — these are not optional:

**Typography:** Always pair two fonts. Pick one display font (Playfair Display, Fraunces, Syne, Bebas Neue, Clash Display) and one body font (Space Grotesk, DM Sans, Inter only if combined with a strong display). Load from Google Fonts.

**Color:** Define a dominant color + accent as CSS variables at `:root`. Never use plain white + purple gradients. Use dramatic palettes: near-black with electric accents, warm cream with deep ink, desaturated blue-grey with gold.

**Composition:** Break the grid. Use asymmetry: offset headings, elements that overlap, diagonal flow, elements that bleed off-screen. Never a centered column with equal padding on all sides.

**Depth:** Background must have depth — gradient mesh, subtle radial gradient, or noise texture. Use box-shadows with color tint (not grey). Layer surfaces with slightly different background values.

**Motion:** Add at least one CSS animation — entrance fade-up for hero text, subtle float on cards, gradient shift on backgrounds.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>[Feature] Mockup v1</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,700;1,9..144,400&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg:      #0c0c14;
      --surface: #13131f;
      --border:  #1e1e32;
      --accent:  #7c3aed;
      --accent2: #06b6d4;
      --text:    #f0f0f8;
      --muted:   #6b7280;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'DM Sans', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100dvh;
      /* Radial gradient for depth */
      background-image:
        radial-gradient(ellipse 80% 50% at 20% 20%, rgba(124,58,237,0.15), transparent),
        radial-gradient(ellipse 60% 40% at 80% 80%, rgba(6,182,212,0.08), transparent);
    }

    /* Noise grain */
    body::after {
      content: ''; position: fixed; inset: 0; pointer-events: none; z-index: 999;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='0.03'/%3E%3C/svg%3E");
    }

    nav {
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      padding: 18px 48px;
      display: flex; align-items: center; gap: 32px;
      background: rgba(12,12,20,0.75); backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--border);
    }

    .nav-logo { font-family: 'Fraunces', serif; font-size: 22px; font-weight: 700; }
    .nav-links { display: flex; gap: 24px; margin-left: auto; }
    .nav-links a { font-size: 14px; color: var(--muted); text-decoration: none; transition: color 0.2s; }
    .nav-links a:hover { color: var(--text); }
    .nav-cta {
      padding: 8px 20px; border-radius: 100px;
      background: var(--accent); color: #fff;
      font-size: 14px; font-weight: 600; text-decoration: none;
      transition: opacity 0.2s;
    }

    /* Asymmetric hero */
    .hero {
      padding: 160px 48px 80px;
      display: grid; grid-template-columns: 1fr 0.9fr; gap: 60px; align-items: center;
      max-width: 1280px; margin: 0 auto;
    }

    .hero-eyebrow {
      font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
      color: var(--accent2); font-weight: 600; margin-bottom: 20px;
      display: flex; align-items: center; gap: 8px;
    }
    .hero-eyebrow::before { content: ''; width: 24px; height: 1px; background: var(--accent2); }

    .hero-title {
      font-family: 'Fraunces', serif;
      font-size: clamp(40px, 5vw, 70px);
      font-weight: 700; line-height: 1.05; letter-spacing: -2px;
      margin-bottom: 24px;
      animation: fadeUp 0.7s ease both;
    }

    .hero-title em { font-style: italic; color: var(--accent2); }

    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(20px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .hero-body { font-size: 17px; color: var(--muted); line-height: 1.7; margin-bottom: 36px; }

    .hero-ctas { display: flex; gap: 14px; flex-wrap: wrap; }
    .btn-primary {
      padding: 14px 28px; border-radius: 12px; font-size: 15px; font-weight: 600;
      background: var(--accent); color: #fff; text-decoration: none;
      box-shadow: 0 4px 24px rgba(124,58,237,0.4);
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(124,58,237,0.5); }
    .btn-ghost {
      padding: 14px 28px; border-radius: 12px; font-size: 15px; font-weight: 600;
      border: 1px solid var(--border); color: var(--muted); text-decoration: none;
      transition: border-color 0.2s, color 0.2s;
    }
    .btn-ghost:hover { border-color: var(--accent); color: var(--text); }

    /* Visual panel — overlapping cards */
    .hero-visual {
      position: relative; height: 420px;
    }
    .card-float {
      position: absolute;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 20px; padding: 24px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      animation: floatCard 6s ease-in-out infinite;
    }
    .card-float:nth-child(1) { top: 0; left: 0; width: 68%; animation-delay: 0s; }
    .card-float:nth-child(2) { bottom: 0; right: 0; width: 62%; animation-delay: -2s; }
    .card-float:nth-child(3) { top: 40%; left: 30%; width: 50%; animation-delay: -4s; z-index: 2; }

    @keyframes floatCard {
      0%,100% { transform: translateY(0); }
      50%      { transform: translateY(-10px); }
    }

    .card-label { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }
    .card-value { font-size: 28px; font-weight: 700; }
    .card-delta { font-size: 12px; color: var(--accent2); margin-top: 4px; }
  </style>
</head>
<body>
  <nav>
    <span class="nav-logo">[Product Name]</span>
    <div class="nav-links">
      <a href="#">Features</a>
      <a href="#">Pricing</a>
      <a href="#">Docs</a>
    </div>
    <a class="nav-cta" href="#">Get Started</a>
  </nav>

  <section class="hero">
    <div>
      <div class="hero-eyebrow">[Category / Tagline]</div>
      <h1 class="hero-title">[Primary headline with<br><em>italic accent word]</em></h1>
      <p class="hero-body">[2–3 sentence value proposition. Be specific — no buzzwords.]</p>
      <div class="hero-ctas">
        <a class="btn-primary" href="#">[Primary CTA]</a>
        <a class="btn-ghost" href="#">[Secondary CTA]</a>
      </div>
    </div>
    <div class="hero-visual">
      <div class="card-float" data-choice="layout-a" style="cursor:pointer">
        <div class="card-label">[Metric Label]</div>
        <div class="card-value">[Value]</div>
        <div class="card-delta">↑ [Change]</div>
      </div>
      <div class="card-float">
        <div class="card-label">[Metric Label]</div>
        <div class="card-value">[Value]</div>
        <div class="card-delta">↑ [Change]</div>
      </div>
      <div class="card-float" style="background:linear-gradient(135deg,var(--accent),#5b21b6)">
        <div class="card-label" style="color:rgba(255,255,255,0.6)">[Key Stat]</div>
        <div class="card-value">[Value]</div>
      </div>
    </div>
  </section>
</body>
</html>
```

**Adapt this template to the actual feature.** Replace every placeholder with real content. The floating card visual is a starting point — use it for dashboards, data-heavy features, or SaaS products. For simpler features, simplify accordingly, but keep the font pairing, color depth, and asymmetric layout.

### 4. Design Iteration

When user requests changes to a screen, write a new file (`mockup-v2.html`, `approaches-v2.html`) — never overwrite. The server auto-reloads.

Add an iteration badge at the top of revised screens so the user sees the version:

```html
<div class="iteration-badge">✦ Revision 2 — incorporating your feedback</div>
```

To compare two versions side by side, write a comparison screen:

```html
<h1 class="page-title">Version Comparison</h1>
<p class="page-subtitle">Click the version you prefer.</p>
<div class="compare-grid">
  <div class="compare-pane" data-choice="v1" data-text="Version 1" style="cursor:pointer">
    <div class="compare-label">Version 1 — [description]</div>
    <div class="compare-content">
      <!-- Embed a scaled-down summary of v1 -->
    </div>
  </div>
  <div class="compare-pane" data-choice="v2" data-text="Version 2" style="cursor:pointer">
    <div class="compare-label">Version 2 — [description]</div>
    <div class="compare-content">
      <!-- Embed a scaled-down summary of v2 -->
    </div>
  </div>
</div>
```

### 5. Bumping to a New Prototype Version

Bump from `v1` to `v2` when you are making a fundamentally different design (not just tweaks). Create the new version directory and tell the user the new URL:

```bash
mkdir -p "$VC_SCREENS/v2"
# write screens to $VC_SCREENS/v2/
open "${VC_URL}/v2/" 2>/dev/null || true
```

Tell user: "Prototype v2 ready at `{VC_URL}/v2/` — opening it now."

---

## Capturing Approved Designs (Playwright)

When the user approves a design screen, capture it as a screenshot for spec embedding.

1. Navigate Playwright to the current URL:
   ```
   mcp__playwright__browser_navigate({ url: "{VC_URL}/v{n}/" })
   ```
2. Wait for Mermaid/animations to complete:
   ```
   mcp__playwright__browser_wait_for({ time: 800 })
   ```
3. Take screenshot:
   ```
   mcp__playwright__browser_take_screenshot({ fullPage: false })
   ```
4. Note what was captured for the spec. The approved HTML file in `$VC_SCREENS/v{n}/` is the persistent design artifact — reference it in the spec.

---

## Design Artifacts in the Spec

When writing the spec file, add a Design Artifacts section:

```markdown
## Design Artifacts

**Mode:** [Visual + Strict | Visual + Reference | Text only]
**Screens:** `.workspace/shared/designs/YYYY-MM-DD-<feature>/screens/`
**Approved:** `v{n}/mockup-v{m}.html`

> Forge tasks MUST reproduce this design exactly. [if VISUAL_STRICT]
> Use the approved screens as reference. Deviation with justification is acceptable. [if VISUAL_REFERENCE]
```

In blueprint/forge phases, when implementing UI tasks, Claude reads the approved HTML file to understand the expected layout, typography, and components.

---

## Design Principles

- Each unit has one responsibility and a clear interface
- Prefer smaller focused files over large ones that do too much
- YAGNI: no features the user did not request
- Design for testability: every component independently verifiable

---

## Spec File Format

```markdown
# <Feature> Spec

**Goal:** <one sentence>
**Archetype:** <from inspector>
**Stack:** <from inspector>

## Requirements
- <requirement 1>
- <requirement 2>

## Architecture
<2-3 paragraphs>

## Components
- `path/to/file.ts` — responsibility

## Error Handling
<approach>

## Testing Strategy
<approach>

## Design Artifacts

**Mode:** <Visual + Strict | Visual + Reference | Text only>
**Screens:** `.workspace/shared/designs/YYYY-MM-DD-<feature>/screens/`
**Approved:** `v1/mockup-v2.html`
```

---

## After Approval

Stop the visual companion, commit the spec, then say:

> "Spec approved and committed. Designs saved to `.workspace/shared/designs/`. Run `/magician:blueprint` to create the implementation plan."
