# /magic — AskUserQuestion configurations

Read this when you reach **Phase 0 (source selection)** or **Phase 3 (output format)**.
Every block below MUST be delivered via the AskUserQuestion tool — never in plain prose.

---

## Phase 0 — Source selection

Apply these rules based on the Step 0.1 classification, then use the matching block:
- **Academic/scientific** → pre-select Web Search; hide "Tech Library Docs"; description mentions academic databases
- **Document/file/business** → hide "Tech Library Docs" entirely — it would only confuse
- **Software/tech library** → show all three options
- **General/strategic** → show Web Search and My Documents/Files; show Tech Library Docs only if the topic could plausibly involve a framework

### Academic / scientific (Web Search targets academic databases)

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

### Financial / business / document / file (no software library involved)

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

### Software / tech library and general/strategic where a framework could be involved (all three)

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

---

## Phase 3 — Output format

### Academic / scientific (citation-aware formats surfaced first)

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

If an academic format is chosen, also ask for citation style via AskUserQuestion:

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

### All other topics

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

If the user selects "Visual design via /conjure" in either config: invoke `/conjure` now, passing context about the research topic and findings outline so conjure starts informed. Return to Phase 3 after spec approval.

---

## Phase 0 — Research depth

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

> **Model & effort:** map the chosen depth onto reasoning effort — Quick overview ≈ `/effort low`, Standard depth ≈ `/effort medium`, Deep dive ≈ `/effort high` (raise to `xhigh` for exhaustive, whole-landscape sweeps). If the session is on an older model than ideal for the depth picked, suggest an upgrade rather than switching silently. See [../../../lore/models.md](../../../lore/models.md).

---

## Phase 1 — context7 not installed

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

If "Yes", run `claude mcp add --transport http context7 https://mcp.context7.com/mcp`, then confirm: "context7 installed — library docs now available." If "Skip", continue without context7 and note the limitation in findings.

---

## Phase 1 — Document source

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

Wait for file paths if the user chose the first option; extract paths from the next message. Reading local documents uses the built-in Read tool — no external service or MCP required (`.pdf`, `.xlsx`, `.csv`, `.docx`, `.md`, `.txt`, etc.).

---

## Phase 3 — Persistence decision

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

## Phase 4 — Commit message

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

Co-Authored-By: Claude <noreply@anthropic.com>"
```
