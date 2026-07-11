# /magic — Phase 5 "What's Next" navigation

Read this when you reach **Phase 5 (navigate & suggest)**. Every block below MUST be
delivered via the AskUserQuestion tool. Adapt the question text to reflect the actual
topic researched — these are templates, not literal copy. Always keep "Dig deeper" and
"Done" as the last two options.

---

### Academic / scientific

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

### Financial / business

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

### Technical feature / API

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

### Bug / incident

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

### Security

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

### Architecture / design

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
