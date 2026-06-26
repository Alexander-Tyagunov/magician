---
name: magic
description: Use when the user asks to research, investigate, analyze, find out, explore, examine, audit, or evaluate something — structured multi-source research with consulting, library-doc search, web search, and guided output delivery.
allowed-tools: WebSearch, WebFetch, Read, Write, AskUserQuestion, mcp__context7__resolve-library-id, mcp__context7__query-docs
argument-hint: [topic or research question]
---

# /magic — Research, Analysis & Consulting

Structured research and consulting workflow. Uses web search, document analysis, and library documentation. Every decision point uses `AskUserQuestion` so the user explicitly drives the process via action-reaction UI.

<HARD-GATE>
EVERY consultation, clarification, and decision MUST use the AskUserQuestion tool. Do NOT ask questions in plain prose — always invoke AskUserQuestion so the user sees the structured prompt UI. This applies to every gate in this skill without exception.
</HARD-GATE>

## Standalone & pipeline use

`/magic` is a **standalone** skill — run it any time to research, analyze, or consult; no pipeline required, nothing changes about the flow below when used alone.

It also plugs into the SDLC chain without losing context:
- **Feeds the pipeline:** inside a magician workspace (`.workspace/` present), saved research goes to `.workspace/shared/research/<topic>-<date>.md` — a first-class artifact, like specs and plans. Phase 5 hands that **path** (not just a summary) to the next stage, so design/planning/debugging start informed.
- **Fed by the pipeline:** `/conjure`, `/blueprint`, `/unravel`, and `/manifest` read `.workspace/shared/research/` and suggest `/magic` when a decision needs external evidence.
- **Internal sources:** for the user's own Jira tickets/epics/boards or Confluence pages, use the `magician:jira` / `magician:confluence` skills (direct HTTP REST, no MCP; they run one-time setup if not configured) instead of web search. Fold what they return into the findings like any other source. **Skip a source the user has opted out of** ([lore/integration-prefs.md](../../lore/integration-prefs.md)) — don't suggest setting it up.

## Auto-Invocation

This skill is auto-triggered by the `UserPromptSubmit` hook when the user's message contains research-intent keywords: **research, investigate, analyze, analyse, find out, explore, examine, assess, evaluate, discover, look into, audit, study, probe**.

When auto-triggered, announce before any other action:
> "Auto-activating /magic for structured research. Let me gather a few inputs before diving in."

---

## Phase 0 — Scope & Sources

### Step 0.1 — Understand the goal

Read the user's original message carefully. Silently classify the research into one of these types — this determines which sources and output formats to offer:

| Type | Signals | Notes |
|---|---|---|
| **Academic / scientific** | thesis, diploma, dissertation, paper, study, hypothesis, literature review, citation, journal, research question, scientific, university, course | Target academic databases in web search; offer citation-aware output formats |
| **Software / tech library** | library name, version, API, framework, npm, Maven, pip, compatibility, SDK | context7 may be relevant |
| **Financial / business** | revenue, Q1–Q4, KPI, margins, market share, P&L, report | Read tool for files; structured financial output |
| **Document / file analysis** | file path mentioned, .xlsx/.pdf/.docx, "this report", "this article" | Read tool; context7 NOT relevant |
| **General / strategic** | anything else | Web search; broad output options |

Do NOT ask for anything already clear from the message.

### Step 0.2 — Source selection (AskUserQuestion)

Read [references/questions.md](references/questions.md) → "Phase 0 — Source selection". Pick the variant matching the Step 0.1 classification and deliver it via AskUserQuestion. Wait for the response before proceeding.

### Step 0.3 — Research depth (AskUserQuestion)

Read [references/questions.md](references/questions.md) → "Phase 0 — Research depth" and deliver that block via AskUserQuestion.

> **Model & effort:** the depth choice maps onto reasoning effort — Quick overview ≈ `/effort low`, Standard depth ≈ `/effort medium`, Deep dive ≈ `/effort high` (`xhigh` for exhaustive sweeps). If the session is on an older model than ideal, suggest an upgrade rather than switching silently. See [lore/models.md](../../lore/models.md).

---

## Phase 1 — Tool Availability Check

### Step 1.1 — Check context7

**Only proceed with this step if both conditions are true:**
1. User selected "Tech Library Docs (context7)"
2. The research topic is genuinely about a software library, framework, package, or version compatibility

If the topic is a business document, financial report, article, spreadsheet, or anything that is not a software library/framework — **skip this step entirely** and go to Step 1.2.

If user selected "Tech Library Docs (context7)", check availability:

```bash
python3 -c "
import subprocess
try:
    result = subprocess.run(['claude', 'mcp', 'list'], capture_output=True, text=True, timeout=5)
    print('found' if 'context7' in result.stdout.lower() else 'missing')
except Exception:
    print('missing')
" 2>/dev/null || echo "missing"
```

If output is `missing`, read [references/questions.md](references/questions.md) → "Phase 1 — context7 not installed" and deliver that block via AskUserQuestion. On "Yes" run the `claude mcp add` command and confirm; on "Skip" continue and note the limitation in findings.

### Step 1.2 — Document paths (if selected)

If user selected "My Documents / Files", read [references/questions.md](references/questions.md) → "Phase 1 — Document source" and deliver that block via AskUserQuestion. Wait for file paths if the user chose to type them; extract paths from the next message. Reading local documents uses the built-in Read tool — no external service required.

---

## Phase 2 — Research Execution

Execute research in parallel where possible. Take structured notes as you go.

### Step 2.1 — Web Search (if selected)

Use WebSearch with 2–4 targeted queries. Tailor queries to the research type:

**Academic/scientific topic** — prefix queries to target academic sources:
- `site:scholar.google.com <topic>` or `"<topic>" filetype:pdf journal`
- `arXiv <topic>` for STEM/CS/physics/math
- `PubMed <topic>` for biomedical/life sciences
- `IEEE "<topic>"` for engineering/electronics
- `ACM "<topic>"` for computer science
- Include the research question as a direct search query too

**General/business topic** — standard targeted queries:
- Use specific terms, dates, and named entities
- Include news sources, industry reports, official publications

For each query:
1. Formulate the query (academic-targeted or general as above)
2. Call WebSearch tool
3. Extract key facts, quotes, and sources — **note author, title, year, URL** for every source (essential for citations in academic work)
4. Assess source credibility: peer-reviewed > institutional > reputable press > general web

Synthesize web findings into a running outline.

### Step 2.2 — Tech Library Docs via context7 (if selected and topic is software/tech)

For each library or framework relevant to the topic:
1. Resolve the library ID: call `mcp__context7__resolve-library-id` with the library name
2. Query the docs: call `mcp__context7__query-docs` with the resolved ID and a focused query
3. Extract relevant sections and cross-reference with other findings

**Only use this step for genuine software library/framework questions** — e.g. "what Spring Boot version supports Java 21?", "what's the correct Axios API for interceptors?". Do NOT invoke context7 for business reports, financial documents, articles, or any non-library topic.

### Step 2.3 — Document / File Analysis (if selected)

Uses the **Read tool** — no external service. For each provided file path:
1. Call the Read tool on the file path
2. For **financial documents** (reports, P&L, balance sheets): extract key metrics, dates, figures, YoY comparisons, notable trends, risks, executive summary
3. For **spreadsheets / data files** (.xlsx, .csv): extract headers, key rows, totals, trends, anomalies
4. For **articles / research papers**: extract thesis, main arguments, evidence, conclusions, citations
5. For **technical documents** (architecture docs, RFCs, specs): extract decisions, constraints, APIs, versions, dependencies
6. For **general business documents** (reports, memos, meeting notes): extract main points, action items, decisions made

### Step 2.4 — Synthesis

Cross-reference all findings. Identify:
- Consensus points (multiple sources agree)
- Contradictions or gaps
- Key numbers, dates, or facts
- Actionable insights or recommendations

---

## Phase 3 — Output Format Consultation

### Step 3.1 — Choose output format (AskUserQuestion)

Read [references/questions.md](references/questions.md) → "Phase 3 — Output format". Pick the academic or all-other-topics variant (and the citation-style follow-up when an academic format is chosen) and deliver it via AskUserQuestion. If the user selects "Visual design via /conjure", invoke `/conjure` with the topic and findings outline, then return here.

### Step 3.2 — Persistence decision (AskUserQuestion)

Read [references/questions.md](references/questions.md) → "Phase 3 — Persistence decision" and deliver that block via AskUserQuestion. If saving: determine an appropriate filename from the topic. **Inside a magician workspace (`.workspace/` exists), default to `.workspace/shared/research/<topic>-<date>.md`** (creating the dir if needed) so the findings become a pipeline artifact; otherwise save to the cwd or a path the user gives.

---

## Phase 4 — Deliver & Persist

### Step 4.1 — Present findings

Write the findings in the format chosen in Phase 3. Include:
- Source attribution for web content
- File references for local documents
- Clear headings and structure
- A summary/conclusion section

### Step 4.2 — Save to file (if requested)

Write findings to the agreed filename using the Write tool.

### Step 4.3 — Commit (if requested)

Read [references/questions.md](references/questions.md) → "Phase 4 — Commit message", deliver that block via AskUserQuestion, then run the `git add`/`git commit` it specifies with the confirmed message.

---

## Phase 5 — Navigate & Suggest

### Step 5.1 — Assess the research silently

Before asking anything, look at what was just researched and classify it:

| Research type | Signals | Best next skills |
|---|---|---|
| Academic / scientific | thesis, paper, literature review, citation, study, diploma | /conjure (research poster or slides), /magic again (next research angle) |
| Financial / business | revenue, Q1–Q4, KPIs, margins, market share | /conjure (dashboard), /blueprint (action plan) |
| Technical feature / API | endpoints, SDK, library, integration | /blueprint (plan), /conjure (design), /ward (implement) |
| Bug / incident | error, failure, crash, regression, issue | /unravel (debug), /sentinel (security angle) |
| Security / vulnerability | CVE, injection, auth, permissions, exposure | /sentinel (full scan) |
| Performance / scalability | latency, throughput, memory, profiling | /accelerate (profile) |
| Architecture / system design | components, services, data flow, schema | /conjure (visual spec), /blueprint (plan) |
| General knowledge / comparison | options, alternatives, pros/cons, landscape | /conjure (visual comparison), /magic again |

Select the 2 most contextually relevant skills. Always include "Dig deeper" and "Done" as the last two options.

### Step 5.2 — Propose next steps (AskUserQuestion)

Read [references/next-steps.md](references/next-steps.md). Pick the template matching the research type, adapt the question text to reflect what was actually found (not generic), and deliver it via AskUserQuestion.

### Step 5.3 — Act on selection

When handing off, pass the **saved research artifact path** (if saved, e.g. `.workspace/shared/research/<topic>-<date>.md`) plus a 2–3 sentence summary, so the next stage reads the full findings with zero context loss (see [lore/subagent-context.md](../../lore/subagent-context.md)).

| Selection | Action |
|---|---|
| /conjure | Invoke `/conjure` — pass the research artifact path + topic + a 2–3 sentence summary so design starts informed |
| /blueprint | Invoke `/blueprint` — pass the research artifact path as spec/requirements input |
| /unravel | Invoke `/unravel` — pass the identified bug/incident and the research artifact path as the starting point |
| /sentinel | Invoke `/sentinel` — no extra context needed, it scans the codebase |
| /accelerate | Invoke `/accelerate` — pass performance concerns from findings (and the artifact path) as focus areas |
| Dig deeper | Use AskUserQuestion to ask which area, then return to Phase 2 with a focused query |
| Done | Go to Step 5.4 |

### Step 5.4 — Graceful exit

When the user selects "Done", close with:

1. One sentence summarising what was accomplished (topic + output location if saved)
2. A warm sign-off that reflects the work done, e.g.:

> "That's a solid research session on [topic] — findings saved to [file] if you need them later. Have a great day!"

or if nothing was saved:

> "Good investigation on [topic]. Hope the findings give you what you needed — have a great day!"

Keep it brief. No bullet lists. No meta-commentary. Just a clean, friendly close.
