# MCP server — the knowledge graph for MCP clients (opt-in)

`tools/kg-mcp` serves the index that `kg init` builds to an MCP client: Claude Code, Codex (CLI, IDE extension and desktop app) or another host that starts local stdio servers. It reads the index only. In Claude Code the `kg` command already gives the same answers through Bash, so most users do not need the server.

## Why magician does not register it

magician ships no `.mcp.json` and no `mcpServers` key. A plugin server connects in every session of every project, and its tools join the tool list:

- Each tool definition costs context. The agent always loads the tool names. With tool search on, it loads a schema when Claude asks for the tool. With `ENABLE_TOOL_SEARCH=false`, or with `auto` when the schemas fit in 10% of the context, it loads all schemas at the start.
- Tool choice gets worse above about 30–50 tool definitions in the prompt. Most users already have other servers.
- With tool search off, a server that connects or disconnects invalidates the prompt cache.

If a client cannot run `kg`, or if you want MCP permission rules for the graph, register the server yourself.

## The tools

| Tool | Arguments | Returns |
|---|---|---|
| `kg_query` | `query` (text or a symbol name), `limit` (1–100, default 20), `cursor` | `results[]` of `path`, `line`, `end_line`, `symbol`, `kind`, `score`, `snippet`; `stale[]`; `nextCursor` when there are more results |
| `kg_blast` | `target` (file path or symbol), `depth` (1–4, default 2), `limit` | `impacted[]` of `path`, `depth`, `pagerank`; `truncated` |
| `kg_neighbors` | `target`, `depth` (1–3, default 1), `limit` (1–25) | `neighbors[]` of `path`, `symbols[]`; `truncated` |
| `kg_status` | none | `indexed`, `root`, `last_index`, `index_version`, `files`, `symbols`, `edges`, `stale`, `parser`, `instruction` |

Each tool has an `inputSchema` and an `outputSchema`. Each result has `structuredContent` and a short text block. The annotations are `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true` and `openWorldHint: false`.

When a call cannot run, the result has `isError: true` and its text tells the model what to do. Examples: "No knowledge-graph index for … Run `kg init` in that repository", or "No file or symbol named … Call kg_query …". Protocol faults are JSON-RPC errors:

- `-32700`: a line that is not JSON.
- `-32600`: an invalid request.
- `-32601`: an unknown method.
- `-32602`: an unknown tool or bad params.

The cursor of `kg_query` is base64 JSON with the query, the offset and the index version. The server keeps no paging state, so a cursor works in a new server process too. A cursor made before `kg init` or `kg refresh` rebuilt the index gives an error that says to call again without the cursor.

## Which repository it reads

In this order: the `--repo DIR` argument, then `CLAUDE_PROJECT_DIR` (Claude Code sets it for stdio servers), then the folder the client starts the server in. The index location is the same as for `kg`: `${MAGICIAN_HOME:-~/.claude/magician}/knowledge-graph/`. The server does not use MCP Roots.

## Register it in the agent

You need the absolute path of `tools/kg-mcp`. `claude plugin list --json` shows magician's `installPath`. The server is `<installPath>/tools/kg-mcp`. You can also use a clone of the repository. The install path changes when magician updates, so register the server again after an update.

For all your projects, with the repository taken from `CLAUDE_PROJECT_DIR`:

```bash
claude mcp add --scope user --transport stdio kg -- /absolute/path/to/magician/tools/kg-mcp
```

For one project, with a fixed repository:

```bash
claude mcp add --scope local --transport stdio kg -- /absolute/path/to/magician/tools/kg-mcp --repo /absolute/path/to/repo
```

The tools are then `mcp__kg__kg_query`, `mcp__kg__kg_blast`, `mcp__kg__kg_neighbors` and `mcp__kg__kg_status`. To skip the permission prompt for all four, add `mcp__kg` to `permissions.allow`. Check the connection with `claude mcp list`. To remove the server, run `claude mcp remove kg --scope user`.

The same entry in a project `.mcp.json`. The agent asks you to approve a project server before it starts it:

```json
{
  "mcpServers": {
    "kg": {
      "type": "stdio",
      "command": "/absolute/path/to/magician/tools/kg-mcp",
      "args": []
    }
  }
}
```

A fork of magician that wants the server in every session can add a `.mcp.json` at the plugin root with `"command": "../../../tools/kg-mcp"`. The tools are then `mcp__plugin_magician_kg__kg_query` and so on. This is the always-on cost described above, so magician does not do it.

## Register it in Codex

Codex CLI, the IDE extension and the desktop app share `~/.codex/config.toml` (or `.codex/config.toml` in a trusted project):

```toml
[mcp_servers.kg]
command = "/absolute/path/to/magician/tools/kg-mcp"
args = ["--repo", "/absolute/path/to/repo"]
```

ChatGPT on the web cannot start a local server. It uses remote MCP servers only.

## Protocol eras

The server is dual-era, as the MCP knowledge base recommends for bundled stdio servers:

- **Modern (2026-07-28).** A request whose `params._meta` has `io.modelcontextprotocol/protocolVersion` gets stateless handling. `server/discover` returns `supportedVersions`, `capabilities: {tools: {}}`, `instructions`, `ttlMs`, `cacheScope` and `serverInfo` in `_meta`. Every result has `resultType: "complete"`. An unknown version gives `-32022` with `data.supported` and `data.requested`. A request without `io.modelcontextprotocol/clientCapabilities` gives `-32602`.
- **Legacy (2025-11-25 and earlier).** `initialize` returns the client's protocol version if the server knows it, else `2025-11-25`, with `capabilities: {tools: {}}` and `serverInfo`. Then `notifications/initialized`, `tools/list`, `tools/call` and `ping` work. For clients older than 2025-06-18 the server leaves out `outputSchema` and `structuredContent`.

The server picks the era for each request from that request's own `_meta`. It never uses an earlier request on the same pipe to decide. A `server/discover` probe without `_meta` also gets a DiscoverResult, so a client that probes first finds the modern era. Claude Code 2.1.316 probes with `server/discover` and then uses the modern era. With `MCP_PROTOCOL_NEGOTIATION=legacy` it uses `initialize`. Both work.

The server has no resources, prompts, subscriptions, Roots, Sampling or Logging. It writes diagnostics to stderr only and exits when stdin closes.

## Read-only guarantee

- The server opens `graph.db` with the SQLite URI `mode=ro` and sets `PRAGMA query_only`. It never changes the index, and it does not use the `kg` result cache, which writes files.
- It reads repository files only to check whether returned files changed since the index was built (`stale`).
- When `graph.db` has no `-wal` and `-shm` side files, SQLite can create them next to the database, as `kg` itself does. `graph.db` and `meta.json` stay unchanged.
- It imports nothing outside the Python standard library and opens no network connection.
