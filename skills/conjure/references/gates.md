# Explore, Clarify, GATE 1 and GATE 2 — the full procedures

Read this once the mode is chosen (GATE 0, [design-mode.md](design-mode.md)). The placeholders `<design-dir>`, `<state-dir>` and `<url-base>` are defined there. Each gate is one turn. End the turn at the question and wait for the reply.

## Step 1 — Explore

Read relevant files, recent git log, existing specs in `.workspace/shared/specs/`, and any prior research in `.workspace/shared/research/` (from `/magic`, or a `/transmute` comprehension dossier when redesigning an existing feature — design against its recorded UX contract). Note detected stack and archetype from session additionalContext. Do this silently before asking anything. If a design decision hinges on external evidence you don't have (library choice, prior art, API capabilities), suggest running `/magic` first — it returns a research artifact you then design from.

## Step 2 — Clarify (one question per turn)

Ask one clarifying question. End your turn. Wait for the answer. Repeat until you understand purpose, constraints, success criteria, and edge cases. Skip stack questions the inspector already answered. Use multiple choice when possible.

## GATE 1 — Approach Selection

Present 2–3 approaches.

**In every mode, first write the comparison to disk:** `<design-dir>/screens/v1/approaches.html` (the fragment template in [visual-companion.md](visual-companion.md)). This file is the durable record of the options. It outlives both the companion server and any artifact.

**Surface B (companion):** the server serves that file. Tell the user the URL and a one-sentence summary of each approach. End your turn. On the next turn read new events from `<state-dir>/events.jsonl` (by cursor — see the live loop in [design-mode.md](design-mode.md)) for their click choice plus their terminal message.

**Surface A (artboards):** show the same three cards as one artboard each in the `/design` artifact. Tell the user the link and a one-sentence summary of each approach. End your turn. On the next turn read their terminal reply or artifact comment for the choice.

**Text mode (C):** present the approaches in text, then call `AskUserQuestion` — *"Which approach would you like to go with?"* — with one option per approach (2–3 concrete options). End your turn at the call; act on the chosen approach.

**Do not present architecture until the user confirms an approach.**

## GATE 2 — Architecture Review

Present the architecture for the chosen approach only.

**In every mode, first write the architecture as code:** `<design-dir>/screens/v1/architecture.mmd` (a C4-style component diagram and a sequence diagram for the main flow) and the companion screen `<design-dir>/screens/v1/architecture.html` that embeds it, following [architecture.md](architecture.md). Render `architecture.svg` only when `mmdc` is on PATH; never install it.

**Surface B (companion):** the server serves `architecture.html`. Tell the user the URL and describe the diagram in 2 sentences. End your turn. Wait for their feedback.

**Surface A (artboards):** show the component diagram and the sequence diagram as two artboards. Paste the rendered SVG when it exists, else the box diagram from `architecture.html`. Tell the user the link and describe the diagram in 2 sentences. End your turn. Wait for their feedback.

**Text mode (C):** present the architecture (file structure, data flow, component responsibilities — the Mermaid source from the `.mmd` file can be shown inline), then call `AskUserQuestion` — *"Does this architecture work?"* — with options **Approve** / **Request changes**. End your turn at the call; treat free-form feedback (e.g. "change X") as Request changes.

Iterate on changes if requested. A revision is a new `architecture-v2.mmd` + `.html` pair, never an overwrite. Only advance when the user explicitly approves.
