# Status, visualization, and reset

## `kg status` — the default text view

Compact, ~12 lines: repo + hash, index version + freshness + parser, counts (files / symbols / edges / communities), FTS + accelerators, staleness, cache hit/miss + rate, and the most central symbols. Example:

```
knowledge-graph · magician (c7b5e4219e76)
  index v3 · 2h ago · parser=ctags · daemon
  240 files · 3,110 symbols · 5,400 edges · 28 communities
  fts=True · accel=numpy,blake3 · stale=2
  cache: 41 hit / 12 miss (77.4%)
  central:
    api (function) — bin/jira
    …
  ⚠ 2 files changed — run `kg refresh`
```

This is the answer to "show me the state of the graph + caches + optimizations." Read it; don't auto-render a graphic.

## The visual widget — only when asked

If the user asks to *see / visualize / draw* the graph, get the machine view and render it:

1. `kg status --json` → counts, central nodes, communities, cache stats, accel flags.
2. Build an SVG/HTML with `mcp__visualize__show_widget`: community clusters sized by node count, central symbols highlighted, a small panel for index freshness + cache hit-rate. Keep it readable; this is a summary, not a full node-link dump of thousands of nodes.

Default to text. The widget is opt-in so status stays cheap and quiet.

## `kg cache stats|clear`

`stats` shows entry count and hit/miss. `clear` drops the derived-result cache (safe — it's rebuilt on demand). The cache auto-invalidates whenever `index_version` bumps (any `init`/`refresh`).

## `kg daemon start|stop|status`

Tier-2, opt-in. `start` launches a resident process that keeps the graph in RAM so queries skip the per-call graph load (socket round-trip ~1 ms; the win grows with graph size — negligible on small repos, real on large ones, where rebuilding the in-memory graph per call would otherwise cost 100s of ms). `status` reports running/stopped; `stop` shuts it down. It auto-exits after idle and refuses a stale index. Everything works without it.

## `kg reset` — gated

Destroys this repo's index + cache (`repos/<hash>/`). Per the skill's HARD-GATE, confirm first. It only removes the rebuildable store under `~/.claude/magician/knowledge-graph/` — never the user's code. Rebuild with `kg init`. Use it to clear a corrupted index or to honor a "forget this repo" request.
