# Architecture — what the graph and cache actually are

## The problem it solves

Finding code the default way is expensive: broad greps and whole-file reads, re-paid every session and re-paid again by every subagent/teammate that spawns. The knowledge graph replaces *exhaustive* exploration with *targeted* retrieval — a ranked set of `file:line` ranges from a pre-built map — and shares that map on disk so nobody re-derives it.

## On-disk layout (global, per-repo)

Default root `~/.claude/magician/knowledge-graph/` (override with `MAGICIAN_HOME`). Stored at the **main-Claude level** on purpose — stable across marketplaces, readable by every session/agent.

```
knowledge-graph/
  repos/<repohash>/          # repohash = sha256(realpath(repo root))[:12]
    graph.db                 # SQLite: files, nodes (symbols), edges, FTS5
    meta.json                # index_version, counts, parser, accel, cache stats
    cache/<key>.json         # content-addressed derived results (TTL + LRU)
    suggest.json             # SessionStart nudge throttle marker
    daemon.sock              # present only while the Tier-2 daemon runs
```

**Graph contents.** `files` (path, content_hash, lang, pagerank, community); `nodes` (symbol name, kind, file, line span, signature); `edges` (file→file: `imports`, `references`); plus `entities`/`entity_edges` for external modules and remembered references. PageRank ranks central files; label-propagation groups modules.

## The honest caching story

A plugin **cannot** inject `cache_control` into Claude Code's API requests, so this does **not** literally extend Anthropic's server-side prompt cache. What it really does, all local:

1. **Cuts volume** — retrieve targeted ranges instead of whole files / blind greps (the big saving).
2. **Content-addressed derived cache** — `query`/`blast` results keyed on `index_version` + inputs, stored on disk and shared across sessions/agents, so repeats are near-free. The fastest query is the one you don't run.
3. **Cache-friendly structure** — a stable graph snapshot pulled once per task, stable-content-first, so what *is* sent lands on the prompt cache naturally.

Retrieval is **explicit-call only** — nothing is injected per prompt, so the layer can never *raise* per-turn cost.

## No context loss across agents/pipelines/teams

The graph + cache are a durable on-disk artifact. A spawned agent runs `kg query`/`kg neighbors` and gets the same map without the parent re-explaining the codebase — the substrate, not the conversation, carries the knowledge (see [lore/subagent-context.md](../../../lore/subagent-context.md)).

## Performance tiers (lightweight default, faster on opt-in)

- **Tier 0 (default, zero-dep):** stdlib `sqlite3` + FTS5 BM25, regex parser, in-memory CSR traversal, content cache, fast hashing; optional `KG_JOBS` parallel parsing (opt-in; serial is faster for typical repos).
- **Tier 1 (auto, optional wheels, silent fallback):** `tree-sitter` (parse) and `numpy` (PageRank) used iff importable; `ctags` binary used iff present. ~95% of native speed, no shipped binary.
- **Tier 2 (opt-in):** `kg daemon` (resident process keeping the graph in RAM — skips the per-call graph load; ~1 ms socket round-trip, win grows with graph size); `KG_BACKEND=cozo|kuzu|duckdb` for million-node monorepos. Never required.

Why not a Rust/C core or GPU by default? At repo scale this is small data that fits in RAM (a 2-hop traversal is sub-millisecond even at millions of edges) — the bottleneck is parsing, process startup, and repeated work, not the engine. GPU transfer overhead would make typical repos *slower*. So: SQLite + tree-sitter + the daemon + the cache, with native graph DBs as an opt-in escape hatch.

## Env knobs

`MAGICIAN_HOME` (root) · `KG_PARSER` (`treesitter|ctags|regex|auto`) · `KG_JOBS` (parallel parse workers) · `KG_BACKEND` (`sqlite` default) · `KG_EMBEDDINGS` (off) · `KG_MAX_FILE` (skip files larger than N bytes).
