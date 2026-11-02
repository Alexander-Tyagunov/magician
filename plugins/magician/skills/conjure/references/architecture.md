# Architecture as code — the `.mmd` + HTML convention

Read this at GATE 2 ([gates.md](gates.md)). Write the architecture as text first and render it second. Text diagrams diff, review on GitHub and in Confluence, and pass through `tools/ste-lint`. The same convention serves `/magic` research artifacts and `/transmute` comprehension dossiers (last section).

## Files, in order

All files go under `<design-dir>/screens/v<n>/` (defined in [design-mode.md](design-mode.md)).

1. **`architecture.mmd`** — the source of truth. Put two diagrams in one file, each in its own fenced block with a one-line heading comment.
   - A **C4-style component diagram** (`graph TD` or `flowchart LR`). Show the containers and components of the chosen approach, with their responsibilities as node labels. Draw data stores as cylinders and external systems as rounded nodes. Label the edges for the main dependencies. Keep it to the components the feature touches. This is not a map of the whole system.
   - A **sequence diagram** (`sequenceDiagram`) of the main flow. Show the user action, each component in call order, the data store, and the response. Use one diagram per primary flow. A second flow goes in `architecture-flow-2.mmd`.
   Write plain Mermaid. Do not add `style` lines with hardcoded colours. The frame template and the SVG renderer apply the theme.
2. **`architecture.svg`** — render it only when `mmdc` (the Mermaid CLI) is already on PATH. Check with `command -v mmdc`. The check goes through Claude Code's normal permission prompt. When `mmdc` is found, run `mmdc -q -i architecture.mmd -o architecture.svg` in the screens folder. **Never install `mmdc`** or any package to get it. A missing renderer is the normal case, not an error. `mmdc` renders one diagram per file. When the sequence diagram is in the same `.mmd`, split a copy into `architecture-components.mmd` and `architecture-sequence.mmd` for rendering, and keep the combined file as the source. Add a `.png` only when the user asks for an image to paste elsewhere.
3. **`architecture.html`** — the companion screen fragment (template in [visual-companion.md](visual-companion.md), screen type 2). It embeds the diagram in one of two ways.
   - When `architecture.svg` exists, paste the `<svg>…</svg>` inline inside `<div class="arch-container">`. Use no `<img>`, no external file and no CDN, so the page renders offline and from `file://`.
   - Else draw a **pre-rendered box diagram** the way `tools/plan-render` draws its wave graph. Write an inline `<svg viewBox="0 0 W H">` by hand: one `<rect>` + `<text>` per component, laid out in columns by layer (client → API → services → stores), `<path>` edges with a `marker-end` arrow for the dependencies, and a `<title>`/`<desc>` pair for screen readers. No library, no network.
   Keep the `<div class="mermaid">` block with the component diagram source under the SVG as well. The frame template draws it when the browser is online, and it stays readable as text when it is not.

The `.mmd` file is what the spec links (Design Artifacts section, [spec-format.md](spec-format.md)). It is also what `/blueprint` reads for the dependency map, and what a reviewer diffs between v<n> and v<n+1>.

## The same convention elsewhere

`/magic` research artifacts and `/transmute` comprehension dossiers follow the same rule when they describe a system or a flow. A Mermaid block in the Markdown document is the source: a component diagram for structure, a sequence diagram for a flow. An SVG next to it is rendered only when `mmdc` is already on PATH, and is never installed. The Markdown stays complete without the SVG. For `/magic`, put the block in the research file under `.workspace/shared/research/`. For `/transmute`, put it in the dossier's structure section and in the parity contract's flow section. Diagrams are text first so they diff, lint and render on GitHub.
