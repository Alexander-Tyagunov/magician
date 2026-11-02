# /magic — phase procedures

The full procedure for each phase of the router in [`SKILL.md`](../SKILL.md). Read the phase you are in. Every gate goes through AskUserQuestion. The question blocks are in [`questions.md`](questions.md) and the next-step templates in [`next-steps.md`](next-steps.md).

## Phase 0 — Scope and sources

### Step 0.1 — Understand the goal

Read the user's original message. Classify the research into one of these types without asking. The type selects the sources and the output formats to offer.

| Type | Signals | Notes |
|---|---|---|
| **Academic / scientific** | thesis, diploma, dissertation, paper, study, hypothesis, literature review, citation, journal, research question, scientific, university, course | Target academic databases in web search; offer citation-aware output formats |
| **Software / tech library** | library name, version, API, framework, npm, Maven, pip, compatibility, SDK | context7 may be relevant |
| **Financial / business** | revenue, Q1–Q4, KPI, margins, market share, P&L, report | Read tool for files; structured financial output |
| **Document / file analysis** | file path mentioned, .xlsx/.pdf/.docx, "this report", "this article" | Read tool; context7 is not relevant |
| **General / strategic** | anything else | Web search; broad output options |

Ask for nothing that is already clear from the message.

### Step 0.2 — Scope gate: sources and depth (one batched AskUserQuestion)

Batch both decisions into a **single** AskUserQuestion call, so the user approves the scope once ([`lore/autonomy.md`](../../../lore/autonomy.md): clarify up front, batched). Read [`questions.md`](questions.md) → "Phase 0 — Source selection" (the variant that matches the Step 0.1 type) **and** "Phase 0 — Research depth". Pass **both** question blocks in the `questions` array of one call. Wait for the response.

**Model and effort:** the depth choice maps onto reasoning effort. Quick overview ≈ `/effort low`, Standard depth ≈ `/effort medium`, Deep dive ≈ `/effort high` (`xhigh` for exhaustive sweeps, `max` only as an opt-in for a frontier problem). When the session is on an older model than ideal, suggest an upgrade. Do not switch without saying so ([`lore/models.md`](../../../lore/models.md)).

## Phase 1 — Tool availability

### Step 1.1 — Check context7

Run this step only when both conditions hold:

1. The user selected "Tech Library Docs (context7)".
2. The topic is a software library, framework, package or version-compatibility question.

For a business document, financial report, article, spreadsheet or any other non-library topic, skip this step and go to Step 1.2.

context7 is available when `mcp__context7__resolve-library-id` is in your tool list. When it is not, read [`questions.md`](questions.md) → "Phase 1 — context7 not installed" and deliver that block via AskUserQuestion. Do not add the server yourself: on "Show me the command", print the command for the user to run. Either way, continue without context7 and note the limitation in the findings.

### Step 1.2 — Document paths

When the user selected "My Documents / Files", read [`questions.md`](questions.md) → "Phase 1 — Document source" and deliver that block via AskUserQuestion. When the user chose to type the paths, wait for the next message and extract them from it. Local documents are read with the built-in Read tool. No external service is involved.

## Phase 2 — Research execution

Run the selected sources in parallel where possible. Take structured notes as you go.

### Step 2.1 — Web search

Use WebSearch with 2–4 targeted queries. Each search prompts unless the user already approved web search or runs in auto mode. Build queries from the public topic only: no private file contents, credentials or internal names. Tailor the queries to the research type.

**Academic / scientific topic** — prefix queries to target academic sources:

- `site:scholar.google.com <topic>` or `"<topic>" filetype:pdf journal`
- `arXiv <topic>` for STEM, CS, physics and math
- `PubMed <topic>` for biomedical and life sciences
- `IEEE "<topic>"` for engineering and electronics
- `ACM "<topic>"` for computer science
- The research question itself, as a direct query

**General / business topic** — standard targeted queries with specific terms, dates and named entities. Include news sources, industry reports and official publications.

For each query:

1. Formulate the query (academic-targeted or general, as above).
2. Call the WebSearch tool.
3. Extract key facts, quotes and sources. Note author, title, year and URL for every source, because citations in academic work need them.
4. Assess source credibility: peer-reviewed > institutional > reputable press > general web.

Fold the web findings into a running outline.

### Step 2.2 — Library docs via context7

Only for a software library or framework question (for example "what Spring Boot version supports Java 21?", "what is the current Axios API for interceptors?"). Do not query context7 for business reports, financial documents, articles or any non-library topic. context7 queries go to the context7 service, so use the public library name and a generic question. Use no private code and no internal names.

For each relevant library or framework:

1. Resolve the library id: call `mcp__context7__resolve-library-id` with the library name.
2. Query the docs: call `mcp__context7__query-docs` with the resolved id and a focused query.
3. Extract the relevant sections and cross-reference them with the other findings.

### Step 2.3 — Document and file analysis

This step uses the Read tool and no external service. For each file path, call Read, then extract what the document type calls for:

1. **Financial documents** (reports, P&L, balance sheets): key metrics, dates, figures, YoY comparisons, notable trends, risks, executive summary.
2. **Spreadsheets and data files** (.xlsx, .csv): headers, key rows, totals, trends, anomalies.
3. **Articles and research papers**: thesis, main arguments, evidence, conclusions, citations.
4. **Technical documents** (architecture docs, RFCs, specs): decisions, constraints, APIs, versions, dependencies.
5. **General business documents** (reports, memos, meeting notes): main points, action items, decisions made.

### Step 2.4 — Synthesis

Cross-reference all findings. Identify:

- Consensus points (several sources agree)
- Contradictions or gaps
- Key numbers, dates or facts
- Actionable insights or recommendations

## Phase 3 — Output format

### Step 3.1 — Choose the output format (AskUserQuestion)

Read [`questions.md`](questions.md) → "Phase 3 — Output format". Pick the academic or the all-other-topics variant (and the citation-style follow-up when an academic format is chosen) and deliver it via AskUserQuestion. When the user selects "Visual design via /conjure", invoke `/conjure` with the topic and the findings outline, then return here.

### Step 3.2 — Persistence decision (AskUserQuestion)

Read [`questions.md`](questions.md) → "Phase 3 — Persistence decision" and deliver that block via AskUserQuestion. When saving, derive the filename from the topic. Inside a magician workspace (`.workspace/` exists) the default is `.workspace/shared/research/<topic>-<date>.md` (create the folder when needed), so the findings become a pipeline artifact. Otherwise save to the cwd or to a path the user gives.

## Phase 4 — Deliver and persist

### Step 4.1 — Present the findings

Write the findings in the format chosen in Phase 3. Include:

- Source attribution for web content
- File references for local documents
- Clear headings and structure
- A summary or conclusion section

When the findings describe a system or a flow, add a Mermaid block (component diagram for structure, sequence diagram for a flow) to the research file. An SVG is rendered next to it only when `mmdc` is already on PATH. The Markdown stays complete without it. Convention: [conjure's `architecture.md`](../../conjure/references/architecture.md).

For findings the user wants to circulate, offer a Claude Code **Artifact** (a live page on claude.ai, team-co-editable on Team and Enterprise plans). Do not create it unprompted. A **public** link (anyone with the URL can view it) is an outward sharing action. Confirm it and keep the page account-private by default. Keep proprietary data, secrets and confidential source material off a public link.

### Step 4.2 — Save to file

Write the findings to the agreed filename with the Write tool. A save inside `.workspace/shared/research/` is pre-approved by this skill. Any other path goes through the normal permission prompt.

### Step 4.3 — Commit

Read [`questions.md`](questions.md) → "Phase 4 — Commit message", deliver that block via AskUserQuestion, then run the `git add` and `git commit` it specifies with the confirmed message.

## Phase 5 — Navigate and suggest

### Step 5.1 — Assess the research

Before asking anything, classify what was researched:

| Research type | Signals | Best next skills |
|---|---|---|
| Academic / scientific | thesis, paper, literature review, citation, study, diploma | /conjure (research poster or slides), /magic again (next research angle) |
| Financial / business | revenue, Q1–Q4, KPIs, margins, market share | /conjure (dashboard), /blueprint (action plan) |
| Technical feature / API | endpoints, SDK, library, integration | /blueprint (plan), /conjure (design), /ward (implement) |
| Existing feature to port or change | usage of a live app, vendor or third party, "recreate / clone", "swap the provider", migration | /transmute (comprehend → port or integrate), /blueprint |
| Bug / incident | error, failure, crash, regression, issue | /unravel (debug), /sentinel (security angle) |
| Security / vulnerability | CVE, injection, auth, permissions, exposure | /sentinel (full scan) |
| Performance / scalability | latency, throughput, memory, profiling | /accelerate (profile) |
| Architecture / system design | components, services, data flow, schema | /conjure (visual spec), /blueprint (plan) |
| General knowledge / comparison | options, alternatives, pros and cons, landscape | /conjure (visual comparison), /magic again |

Select the 2 most relevant skills. "Dig deeper" and "Done" are the last two options in every case.

### Step 5.2 — Propose next steps (AskUserQuestion)

Read [`next-steps.md`](next-steps.md). Pick the template that matches the research type. Adapt the question text to what was found, then deliver it via AskUserQuestion.

### Step 5.3 — Act on the selection

On a handoff, pass the saved research artifact path (for example `.workspace/shared/research/<topic>-<date>.md`) plus a 2–3 sentence summary. The next stage then reads the full findings with no context loss ([`lore/subagent-context.md`](../../../lore/subagent-context.md)).

| Selection | Action |
|---|---|
| /conjure | Invoke `/conjure` with the research artifact path, the topic and a 2–3 sentence summary, so the design starts informed |
| /blueprint | Invoke `/blueprint` with the research artifact path as the spec or requirements input |
| /unravel | Invoke `/unravel` with the identified bug or incident and the research artifact path as the starting point |
| /sentinel | Invoke `/sentinel`; it scans the codebase and needs no extra context |
| /accelerate | Invoke `/accelerate` with the performance concerns from the findings (and the artifact path) as focus areas |
| /transmute | Invoke `/transmute` when the research comprehended an existing feature to port elsewhere or change in place; pass the research artifact path as the seed for the dossier |
| Dig deeper | Ask which area via AskUserQuestion, then return to Phase 2 with a focused query |
| Done | Go to Step 5.4 |

### Step 5.4 — Graceful exit

When the user selects "Done", close with:

1. One sentence on what was done (topic, plus the output location when saved).
2. A warm sign-off that reflects the work, for example:

> "That's a solid research session on [topic] — findings saved to [file] if you need them later. Have a great day!"

or, when nothing was saved:

> "Good investigation on [topic]. Hope the findings give you what you needed — have a great day!"

Keep it brief: no bullet lists and no meta-commentary.
