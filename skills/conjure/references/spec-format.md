# Spec File Format

Used at **GATE 4 (Spec Approval)**. Write the full spec to `.workspace/shared/specs/YYYY-MM-DD-<feature>.md`.

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

## Design Artifacts section (detail)

When a UI was designed, the Design Artifacts section binds implementation to the approved screens:

```markdown
## Design Artifacts

**Mode:** [Visual + Strict | Visual + Reference | Text only]
**Screens:** `.workspace/shared/designs/YYYY-MM-DD-<feature>/screens/`
**Approved:** `v{n}/mockup-v{m}.html`

> Ward tasks MUST reproduce this design exactly. [if VISUAL_STRICT]
> Use the approved screens as reference. Deviation with justification is acceptable. [if VISUAL_REFERENCE]
```

In blueprint/ward phases, when implementing UI tasks, Claude reads the approved HTML file to understand the expected layout, typography, and components.

## Design Principles (apply when writing the spec)

- Each unit has one responsibility and a clear interface
- Prefer smaller focused files over large ones that do too much
- YAGNI: no features the user did not request
- Design for testability: every component independently verifiable
