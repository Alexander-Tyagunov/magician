<div align="center">

```
         *        
        /|\       
       / | \      
      /  *  \     
    /_________\   
   /\  o   o  /\   ---- * . * . * .
  /   ~~~~~~~   \   . * . * . * .
  /  ( ~~~~~ )  \  * . * . * . *
  \_____________/
    |   | |   |  
```

# magician

**Full-stack SDLC plugin for Claude Code**

Inspects your project, assembles the right knowledge automatically, orchestrates parallel agents, learns from every session, and ships clean code — from idea to merged PR, autonomously.

[![Version](https://img.shields.io/badge/version-1.2.0-6c63ff)](https://github.com/Alexander-Tyagunov/magician/releases)
[![License](https://img.shields.io/badge/license-MIT-43e97b)](LICENSE)
[![Sponsor](https://img.shields.io/badge/sponsor-%E2%9D%A4-ff6584)](https://github.com/sponsors/Alexander-Tyagunov)

</div>

---

## What it does

Most AI coding tools require you to describe your stack, pick templates, and manage context manually. Magician inspects your project on every session start, assembles targeted knowledge for every technology it finds, and gets smarter with every session.

One command to go from idea to PR:

```
/manifest
```

---

## How it works

### The manifest flow — full autonomous SDLC

```mermaid
flowchart TD
    A["/manifest"] --> B{"scope OK?"}
    B -- too large --> C["decompose\ninto sub-projects"]
    B -- ok --> D["/conjure\ndesign dialogue"]
    D --> E["approved spec"]
    E --> F["/blueprint\nimpl plan + parallelism map"]
    F --> G["/portal\ngit worktree isolation"]
    G --> H["/orchestrate\nparallel agents"]
    H --> I["/ward\nTDD throughout"]
    I --> J["/certify\nverify: tests + browser"]
    J --> K{all green?}
    K -- no --> H
    K -- yes --> L["/scrutinize\nmulti-agent review"]
    L --> M["/absorb\nintegrate findings"]
    M --> N["/seal\nPR + loop until merged"]

    style A fill:#6c63ff,color:#fff
    style D fill:#6c63ff,color:#fff
    style F fill:#6c63ff,color:#fff
    style H fill:#43e97b,color:#000
    style I fill:#43e97b,color:#000
    style J fill:#43e97b,color:#000
    style L fill:#43e97b,color:#000
    style N fill:#4facfe,color:#000
```

Human gates (4 only): scope confirm → spec approval → plan approval → PR title. Everything else: autonomous.

---

### Dynamic project inspector — no manual stack selection

```mermaid
flowchart LR
    A["session start"] --> B["scan project files"]
    B --> C{"detect markers"}

    C --> D["package.json\ntsconfig.json\nnext.config.*"]
    C --> E["pom.xml\nbuild.gradle\n*.xcodeproj"]
    C --> F["go.mod\nCargo.toml\npyproject.toml"]
    C --> G["pubspec.yaml\ncapacitor.config.*\nproject.godot"]

    D --> H["assemble lore\nweb/ fragments"]
    E --> I["assemble lore\nbackend/ fragments"]
    F --> J["assemble lore\nbackend/ fragments"]
    G --> K["assemble lore\nmobile/ craft/ fragments"]

    H --> L["assign archetype\n+ inject context"]
    I --> L
    J --> L
    K --> L

    L --> M["session ready\nin < 2 seconds"]

    style A fill:#0d1117,color:#ccc,stroke:#555
    style M fill:#43e97b,color:#000
```

Polyglot stacks (Next.js + FastAPI + Go) get full coverage automatically. No pack selection needed.

---

### Self-learning — intelligence grows each session

```mermaid
flowchart TD
    A["session ends"] --> B["chronicle-stop.sh\nStop hook"]
    B --> C["git log + diff\nobservable data only"]
    C --> D["write chronicle entry\nCLAUDE_PLUGIN_DATA/chronicle/"]
    D --> E["update patterns.json"]

    E --> F{"pattern seen 3x?"}
    F -- yes --> G["offer: create skill\nvia /inscribe"]
    F -- no --> H[" "]

    G --> I["next session start"]
    H --> I

    I --> J["load last 3 entries\nas additionalContext"]
    J --> K["cumulative intelligence\ngrows without replay"]

    style B fill:#f7971e,color:#000
    style D fill:#f7971e,color:#000
    style G fill:#43e97b,color:#000
    style K fill:#6c63ff,color:#fff
```

---

## Skills

| Skill | Purpose | Category |
|---|---|---|
| `/conjure` | Structured design dialogue with visual browser companion — 4 modes (Visual+Strict, Visual+Reference, Text-only, Design-Only); HARD-GATE: no code until spec approved | Core SDLC |
| `/blueprint` | Converts an approved spec into a TDD task plan with parallelism map (PARALLEL vs SEQUENTIAL tasks) saved to `.workspace/shared/plans/` | Core SDLC |
| `/forge` | Executes one task from a blueprint using strict TDD — failing test first, minimum implementation, lint+type-check, refactor, full suite, commit | Core SDLC |
| `/ward` | Enforces red→green→refactor discipline — one behavior at a time; blocks progress if a failing test cannot be written first | Core SDLC |
| `/unravel` | Systematic debugging with mandatory hypothesis preflight — no code changes before evidence; one change at a time, then regression test | Core SDLC |
| `/certify` | Full verification loop — tests, types, lint, build, and Playwright browser check for UI projects; collects evidence before any success claim | Core SDLC |
| `/summon` | Spawns parallel subagents seeded with the full skill registry; collects STATUS: DONE / BLOCKED / NEEDS_CONTEXT from each | Orchestration |
| `/orchestrate` | Drives full multi-agent execution from a blueprint — groups parallel tasks into waves, dispatches via `/summon`, resolves conflicts, runs `/certify` at end | Orchestration |
| `/scrutinize` | Dispatches 3 specialist reviewers in parallel (correctness, security, simplification); deduplicates and delivers a prioritized consolidated report | Orchestration |
| `/absorb` | Processes scrutiny findings by severity — fixes Critical and High, evaluates Medium, documents declined findings; never skips Critical/High without user sign-off | Orchestration |
| `/portal` | Creates a git worktree for isolated feature work; includes cleanup steps post-merge; respects `disableGit` preference | Orchestration |
| `/seal` | Ships a feature — simplifier pass, `/certify`, commit, push, PR via `gh pr create`, CI monitoring, review loop, merge | Orchestration |
| `/almanac` | One-time workspace init — creates `.workspace/` structure, generates lean `CLAUDE.md`, configures `.gitignore`, suggests relevant MCPs | Workspace |
| `/chronicle` | Views and manages session learning entries from the Stop hook; supports filtering by recency, branch, or date; can clear old entries | Intelligence |
| `/magic` | Research, analysis & consulting — auto-invokes on keywords (research, investigate, analyze…); web search with academic DB targeting (Google Scholar, arXiv, PubMed, IEEE); context7 for tech library docs; local document analysis (PDF, Excel, reports); citation-aware outputs (literature review, APA/MLA/IEEE); context-sensitive next-skill navigation with graceful exit | Research |
| `/sentinel` | Security scan — OWASP Top 10, credential detection, injection surfaces, dependency audit, git history secret scan, auth middleware spot-check | Security |
| `/accelerate` | Performance profiling with mandatory baseline-first discipline — measures before optimizing, re-measures after; uses wrk/lighthouse/cProfile/pprof by stack | Quality |
| `/deploy` | CI/CD pipeline management — creates, updates, and monitors GitHub Actions, GitLab CI, and CircleCI pipelines | Quality |
| `/inscribe` | Creates a new reusable skill; auto-triggered by the pattern detector at 3 repetitions (offer) and 5 repetitions (auto-draft) | Meta |
| `/manifest` | Full autonomous SDLC — 4 human gates (scope, spec, plan, PR title); runs conjure → blueprint → portal → orchestrate → certify → scrutinize → absorb → seal | Full flow |
| `/autopsy` | Blameless post-mortem — timeline from git log/CI, 5-Whys root cause, action items with owner/deadline; saved to `.workspace/shared/postmortems/` | Quality |

---

## Installation

### Add the marketplace and install

```bash
/plugin marketplace add https://github.com/Alexander-Tyagunov/magician
/plugin install magician@magician-marketplace
```

### Or install directly

```bash
/plugin install github:Alexander-Tyagunov/magician
```

### After install — initialize your workspace

```
/almanac
```

This detects your stack, creates `.workspace/`, generates a lean `CLAUDE.md`, and suggests relevant MCPs.

---

## Workspace — team memory

```
.workspace/
├── shared/           ← git committed (team sees this)
│   ├── context.md    team state, open decisions
│   ├── roadmap.md    cross-session priorities
│   ├── decisions/    architecture decision records
│   ├── specs/        design specs from /conjure (full SDLC flow)
│   ├── mockups/      visual-only designs from /conjure Design-Only mode
│   ├── plans/        implementation plans from /blueprint
│   └── postmortems/  /autopsy outputs
└── local/            ← always gitignored (your machine only)
    ├── prefs.md      personal preferences
    └── session.md    last session state (saved before compaction)
```

Multiple developers on the same repo share `.workspace/shared/` via git. Each machine keeps its own `.workspace/local/`. Context flows automatically — no manual sync.

---

## Security

Security is infrastructure, not advice.

- **Hard deny rules** in `settings.json` — blocks pipe-to-shell, eval, credential file access before any prompt sees them
- **PreToolUse hook** — `sentinel-guard.sh` scans every Bash command for injection patterns and lethal trifecta (private data + network + execution)
- **`magician-scan`** — standalone CLI for CI pipelines: `./bin/magician-scan .`
- **Workspace isolation** — `.workspace/local/` is always gitignored; per-machine secrets never reach git

---

## Support this work

If magician saves you time, consider sponsoring its development.

**[❤ Sponsor on GitHub →](https://github.com/sponsors/Alexander-Tyagunov)**

Sponsorship funds continued development: new skills, lore coverage for additional frameworks, Windows compatibility improvements, and community support.

---

## License

MIT © [Alexander Tyagunov](https://github.com/Alexander-Tyagunov)
