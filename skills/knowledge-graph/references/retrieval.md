# Retrieval — query, neighbors, blast (and how other skills use them)

All three are reads: no confirmation, cached, and they flag any returned file that changed since indexing (`⚠ stale … — kg refresh`). Never assert from a stale result without refreshing.

## `kg query "<text>" [--k N]`

Ranked code for a topic. Combines **BM25** (FTS5 over symbol name/signature/path) with **Personalized PageRank** seeded by those hits and a global-centrality prior:

```
score = 0.55·BM25 + 0.30·PPR(file) + 0.15·pagerank(file)
```

Prints rows ready for a **ranged `Read`**:

```
skills/jira/SKILL.md:23-40  section Commands  (0.91)
bin/jira:27                 function api      (0.74)
```

Use it instead of a broad grep when you need "where is the code for X" or "what's related to X". Then `Read` the exact ranges.

## `kg neighbors <symbol|file> [--depth N]`

Direct graph neighbors — callers/callees/imports — ranked by centrality. Good for "what touches this" before an edit.

## `kg blast <file|symbol> [--depth N]`

Reverse-dependency BFS: everything that transitively depends on the target, with depth and pagerank. This is the **change blast-radius** — the set a reviewer must consider when the target changes.

```
blast radius of bin/jira (2 impacted):
  d1  bin/confluence  (pr=0.075)
  d1  scripts/session-start.sh  (pr=0.009)
```

## How `/magic` uses it

When researching the user's own codebase, `/magic` runs `kg query "<topic>"` as a **first-class internal source** (alongside web/context7/jira/confluence), folds the ranked hits into findings, and `Read`s the top ranges. If there's no index it falls back to grep and may offer to build one once (opt-out aware). Skip if the user opted out.

## How `/divine` uses it

At Deep/Exhaustive depth (or whenever change impact matters), `/divine` runs `kg blast <changed file>` per changed file to build the impact set, then hands those `file:line` lists to the reviewer subagents — the same artifact every agent can read, so there's no context loss and no re-exploration.

## Tier-2 speed

If `kg daemon start` is running, `query`/`neighbors`/`blast` auto-route to a resident process that keeps the graph loaded in RAM, skipping the per-call graph load (the socket round-trip itself is ~1 ms). The client still starts fresh, so per-call Python startup (~50 ms) is the floor — the daemon's real win **grows with graph size**: on a large repo a query no longer rebuilds the in-memory graph each call. It falls back to a direct open if down, validates freshness per call, and refuses a stale index.
