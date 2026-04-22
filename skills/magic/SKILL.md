---
name: magic
description: Use when user asks to research, investigate, analyze, find out, explore, examine, audit, or evaluate something — structured multi-source research with consulting, doc search, web search, and guided output delivery
keep-coding-instructions: true
---

# /magic — Research, Analysis & Consulting

Structured research and consulting workflow. Uses web search, document analysis, and library documentation. Every decision point uses `AskUserQuestion` so the user explicitly drives the process via action-reaction UI.

<HARD-GATE>
EVERY consultation, clarification, and decision MUST use the AskUserQuestion tool. Do NOT ask questions in plain prose — always invoke AskUserQuestion so the user sees the structured prompt UI. This applies to every gate in this skill without exception.
</HARD-GATE>

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

**Before showing this question**, apply these rules based on Step 0.1 classification:
- **Academic/scientific** → pre-select Web Search; hide "Tech Library Docs"; description should mention academic databases
- **Document/file/business** → hide "Tech Library Docs" entirely — it would only confuse
- **Software/tech library** → show all three options
- **General/strategic** → show Web Search and My Documents/Files; show Tech Library Docs only if topic could plausibly involve a framework

**For academic/scientific topics**, use this configuration (Web Search description targets academic databases):

```json
{
  "questions": [
    {
      "question": "Which sources should I search?",
      "header": "Research Sources",
      "multiSelect": true,
      "options": [
        {
          "label": "Academic & Web Search",
          "description": "Search Google Scholar, arXiv, PubMed, IEEE Xplore, ACM Digital Library, ResearchGate, and general web — for papers, journals, studies, and references"
        },
        {
          "label": "My Documents / Files",
          "description": "Read and analyze files you provide — existing papers, notes, drafts, datasets. Uses the Read tool, no external service needed."
        }
      ]
    }
  ]
}
```

**For financial / business / document / file topics** (no software library involved), use this configuration — Tech Library Docs is absent:

```json
{
  "questions": [
    {
      "question": "Which sources should I search?",
      "header": "Research Sources",
      "multiSelect": true,
      "options": [
        {
          "label": "Web Search",
          "description": "Search the internet for current articles, news, reports, and documentation"
        },
        {
          "label": "My Documents / Files",
          "description": "Read and analyze files you provide — Excel, PDF, Word, CSV, reports, articles, any text-based file. Uses the Read tool, no external service needed."
        }
      ]
    }
  ]
}
```

**For software / tech library topics and general/strategic topics** where a framework could plausibly be involved, use this configuration (all three options):

```json
{
  "questions": [
    {
      "question": "Which sources should I search?",
      "header": "Research Sources",
      "multiSelect": true,
      "options": [
        {
          "label": "Web Search",
          "description": "Search the internet for current articles, news, reports, and documentation"
        },
        {
          "label": "Tech Library Docs (context7)",
          "description": "For software questions only — search official docs for npm packages, Java/Spring/Maven libraries, Python modules, framework APIs, version compatibility. NOT for business documents or general research."
        },
        {
          "label": "My Documents / Files",
          "description": "Read and analyze files you provide — Excel, PDF, Word, CSV, reports, articles, any text-based file. Uses the Read tool, no external service needed."
        }
      ]
    }
  ]
}
```

Wait for the response before proceeding.

### Step 0.3 — Research depth (AskUserQuestion)

Use AskUserQuestion with this configuration:

```json
{
  "questions": [
    {
      "question": "How thorough should the research be?",
      "header": "Research Depth",
      "multiSelect": false,
      "options": [
        {
          "label": "Quick overview",
          "description": "Fast scan of top sources — best for time-sensitive needs or initial exploration"
        },
        {
          "label": "Standard depth",
          "description": "Thorough research across selected sources with cross-referenced synthesis"
        },
        {
          "label": "Deep dive",
          "description": "Exhaustive multi-angle analysis with gap identification — takes longer"
        }
      ]
    }
  ]
}
```

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

If output is `missing`, use AskUserQuestion:

```json
{
  "questions": [
    {
      "question": "context7 MCP is not installed. It enables searching official library and framework documentation. Install it?",
      "header": "Install context7?",
      "multiSelect": false,
      "options": [
        {
          "label": "Yes — install context7",
          "description": "Adds context7 to Claude Code: claude mcp add --transport http context7 https://mcp.context7.com/mcp"
        },
        {
          "label": "Skip for now",
          "description": "Continue without library documentation search"
        }
      ]
    }
  ]
}
```

If user selects "Yes — install context7", run:
```bash
claude mcp add --transport http context7 https://mcp.context7.com/mcp
```
Then confirm: "context7 installed — library docs now available."

If "Skip": continue without context7, note the limitation in findings.

### Step 1.2 — Document paths (if selected)

If user selected "My Documents / Files", use AskUserQuestion:

```json
{
  "questions": [
    {
      "question": "How would you like to provide the documents?",
      "header": "Document Source",
      "multiSelect": false,
      "options": [
        {
          "label": "I'll type the paths in the terminal",
          "description": "Paste or type file paths in your next message — I'll read them with the Read tool"
        },
        {
          "label": "Paths are already in my request",
          "description": "Use the file paths or filenames I already referenced above"
        }
      ]
    }
  ]
}
```

Wait for file paths if user chose the first option. Extract paths from the user's next message.

> **Note:** Reading local documents uses the built-in Read tool — no external service or MCP required. This works for any text-readable file: `.pdf`, `.xlsx`, `.csv`, `.docx`, `.md`, `.txt`, financial reports, articles, meeting notes, etc.

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
1. Resolve the library ID: call `mcp__context7-global__resolve-library-id` with the library name
2. Query the docs: call `mcp__context7-global__query-docs` with the resolved ID and a focused query
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

**For academic/scientific topics**, use this configuration (citation-aware formats surfaced first):

```json
{
  "questions": [
    {
      "question": "How should I present the findings?",
      "header": "Output Format",
      "multiSelect": false,
      "options": [
        {
          "label": "Literature review",
          "description": "Structured academic review: Introduction, thematic sections, synthesis of sources, gaps identified, conclusion — with in-text citations and reference list"
        },
        {
          "label": "Annotated bibliography",
          "description": "Each source listed with full citation + 2–3 sentence annotation on relevance, methodology, and key findings"
        },
        {
          "label": "Research outline",
          "description": "Structured outline for a thesis chapter, paper, or report — with section headings, key points per section, and source assignments"
        },
        {
          "label": "Summary with citations",
          "description": "Concise findings summary with properly formatted citations (ask for citation style: APA, MLA, IEEE, Harvard, Chicago)"
        },
        {
          "label": "Visual design via /conjure",
          "description": "Invoke /conjure for a research poster, presentation slides, or visual summary design"
        }
      ]
    }
  ]
}
```

If academic format chosen, also ask for citation style via AskUserQuestion:

```json
{
  "questions": [
    {
      "question": "Which citation style should I use?",
      "header": "Citation Style",
      "multiSelect": false,
      "options": [
        {
          "label": "APA (7th edition)",
          "description": "Common in social sciences, psychology, education"
        },
        {
          "label": "MLA",
          "description": "Common in humanities, literature, language studies"
        },
        {
          "label": "IEEE",
          "description": "Common in engineering, electronics, computer science"
        },
        {
          "label": "Harvard",
          "description": "Common in UK universities and natural sciences"
        },
        {
          "label": "Chicago / Turabian",
          "description": "Common in history, arts, some social sciences"
        },
        {
          "label": "No formal citation needed",
          "description": "Include source URLs and titles informally"
        }
      ]
    }
  ]
}
```

**For all other topics**, use this configuration:

```json
{
  "questions": [
    {
      "question": "How should I present the findings?",
      "header": "Output Format",
      "multiSelect": false,
      "options": [
        {
          "label": "Markdown report",
          "description": "Structured document with sections: Executive Summary, Key Findings, Details, Sources"
        },
        {
          "label": "Executive summary",
          "description": "Concise 1-page overview of the most important findings and recommendations"
        },
        {
          "label": "Data tables",
          "description": "Tabular format — ideal for metrics, financial figures, feature comparisons"
        },
        {
          "label": "Visual design via /conjure",
          "description": "Invoke /conjure for an interactive visual presentation or dashboard design"
        },
        {
          "label": "Bullet notes",
          "description": "Fast, unformatted key points — best for quick handoff or further processing"
        }
      ]
    }
  ]
}
```

If user selects "Visual design via /conjure" in either config: invoke `/conjure` now, passing context about the research topic and findings outline so conjure starts informed. Return here after spec approval.

### Step 3.2 — Persistence decision (AskUserQuestion)

```json
{
  "questions": [
    {
      "question": "What should happen with the output?",
      "header": "Save & Commit",
      "multiSelect": false,
      "options": [
        {
          "label": "Show here only",
          "description": "Display findings in the terminal — no file created"
        },
        {
          "label": "Save to file",
          "description": "Write findings to a markdown file in the current directory"
        },
        {
          "label": "Save and commit to git",
          "description": "Write to file and create a git commit with a descriptive message"
        }
      ]
    }
  ]
}
```

If saving: determine an appropriate filename from the topic (e.g., `research-q3-results-2026-04-21.md`).

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

Use AskUserQuestion to confirm commit message:

```json
{
  "questions": [
    {
      "question": "Confirm the git commit message for this research output:",
      "header": "Commit Message",
      "multiSelect": false,
      "options": [
        {
          "label": "docs: add research findings",
          "description": "Standard docs commit — appropriate for research outputs and reports"
        },
        {
          "label": "I'll provide a custom message",
          "description": "Type your preferred commit message in the terminal"
        }
      ]
    }
  ]
}
```

After confirmation (using the chosen or user-provided message):
```bash
git add {filename}
git commit -m "{confirmed message}

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 5 — Navigate & Suggest

### Step 5.1 — Assess the research silently

Before asking anything, look at what was just researched and classify it:

| Research type | Signals | Best next skills |
|---|---|---|
| Academic / scientific | thesis, paper, literature review, citation, study, diploma | /conjure (research poster or slides), /magic again (next research angle) |
| Financial / business | revenue, Q1–Q4, KPIs, margins, market share | /conjure (dashboard), /blueprint (action plan) |
| Technical feature / API | endpoints, SDK, library, integration | /blueprint (plan), /conjure (design), /forge (implement) |
| Bug / incident | error, failure, crash, regression, issue | /unravel (debug), /sentinel (security angle) |
| Security / vulnerability | CVE, injection, auth, permissions, exposure | /sentinel (full scan) |
| Performance / scalability | latency, throughput, memory, profiling | /accelerate (profile) |
| Architecture / system design | components, services, data flow, schema | /conjure (visual spec), /blueprint (plan) |
| General knowledge / comparison | options, alternatives, pros/cons, landscape | /conjure (visual comparison), /magic again |

Select the 2 most contextually relevant skills. Always include "Dig deeper" and "Done" as the last two options.

### Step 5.2 — Propose next steps (AskUserQuestion)

Construct and call AskUserQuestion with context-aware options. The question text should reflect what was actually found — not generic. Examples:

**For academic/scientific research:**
```json
{
  "questions": [
    {
      "question": "Good foundation of sources. What's the next step for your work?",
      "header": "What's Next?",
      "multiSelect": false,
      "options": [
        {
          "label": "Research another angle or topic",
          "description": "Continue building the literature base — start a new /magic search on a related aspect"
        },
        {
          "label": "Design a presentation or poster with /conjure",
          "description": "Turn findings into a visual research poster, slide deck, or summary design"
        },
        {
          "label": "Dig deeper into one source or claim",
          "description": "Focus on a specific paper, finding, or gap identified in the research"
        },
        {
          "label": "Done — that's what I needed",
          "description": "End the session"
        }
      ]
    }
  ]
}
```

**For financial/business research:**
```json
{
  "questions": [
    {
      "question": "Solid analysis — Q3 numbers are in. What's the next move?",
      "header": "What's Next?",
      "multiSelect": false,
      "options": [
        {
          "label": "Visualize with /conjure",
          "description": "Design an executive dashboard or slide deck from these findings"
        },
        {
          "label": "Build an action plan with /blueprint",
          "description": "Turn key findings into a prioritized implementation plan"
        },
        {
          "label": "Dig deeper into one area",
          "description": "Focus the research on a specific metric, risk, or segment"
        },
        {
          "label": "Done — that's what I needed",
          "description": "End the session"
        }
      ]
    }
  ]
}
```

**For technical feature/API research:**
```json
{
  "questions": [
    {
      "question": "Research complete. Ready to move from investigation to action?",
      "header": "What's Next?",
      "multiSelect": false,
      "options": [
        {
          "label": "Plan implementation with /blueprint",
          "description": "Convert findings into a TDD task plan with parallelism map"
        },
        {
          "label": "Design the UI/API with /conjure",
          "description": "Run a structured design dialogue to produce an approved spec"
        },
        {
          "label": "Dig deeper into one area",
          "description": "Investigate a specific part of the findings further"
        },
        {
          "label": "Done — that's what I needed",
          "description": "End the session"
        }
      ]
    }
  ]
}
```

**For bug/incident research:**
```json
{
  "questions": [
    {
      "question": "Root cause identified. Ready to dig in?",
      "header": "What's Next?",
      "multiSelect": false,
      "options": [
        {
          "label": "Debug systematically with /unravel",
          "description": "Run hypothesis-driven debugging with mandatory preflight — no random code changes"
        },
        {
          "label": "Security scan with /sentinel",
          "description": "Check if this bug has security implications across the codebase"
        },
        {
          "label": "Dig deeper into one area",
          "description": "Investigate a specific aspect of the findings further"
        },
        {
          "label": "Done — that's what I needed",
          "description": "End the session"
        }
      ]
    }
  ]
}
```

**For security research:**
```json
{
  "questions": [
    {
      "question": "Security findings noted. Want a full scan?",
      "header": "What's Next?",
      "multiSelect": false,
      "options": [
        {
          "label": "Full security scan with /sentinel",
          "description": "OWASP Top 10, credential detection, injection surface — full codebase sweep"
        },
        {
          "label": "Plan the remediation with /blueprint",
          "description": "Create a prioritized fix plan from the identified vulnerabilities"
        },
        {
          "label": "Dig deeper into one area",
          "description": "Investigate a specific vulnerability or surface area further"
        },
        {
          "label": "Done — that's what I needed",
          "description": "End the session"
        }
      ]
    }
  ]
}
```

**For architecture/design research:**
```json
{
  "questions": [
    {
      "question": "Good picture of the landscape. Time to make it concrete?",
      "header": "What's Next?",
      "multiSelect": false,
      "options": [
        {
          "label": "Design with /conjure",
          "description": "Structured design dialogue with visual companion — produces an approved spec"
        },
        {
          "label": "Plan the build with /blueprint",
          "description": "Turn the architecture findings into a TDD task plan"
        },
        {
          "label": "Dig deeper into one area",
          "description": "Investigate a specific component or decision further"
        },
        {
          "label": "Done — that's what I needed",
          "description": "End the session"
        }
      ]
    }
  ]
}
```

Use these as templates — adapt the question text to reflect the actual topic researched.

### Step 5.3 — Act on selection

| Selection | Action |
|---|---|
| /conjure | Invoke `/conjure` — pass the research topic and a 2–3 sentence findings summary as context so conjure starts informed |
| /blueprint | Invoke `/blueprint` — pass findings as the feature spec/requirements input |
| /unravel | Invoke `/unravel` — pass the identified bug/incident as the starting point |
| /sentinel | Invoke `/sentinel` — no extra context needed, it scans the codebase |
| /accelerate | Invoke `/accelerate` — pass performance concerns identified in findings as focus areas |
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
