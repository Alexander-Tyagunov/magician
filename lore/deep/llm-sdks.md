# llm-sdks — deep dive

> On-demand companion to `lore/llm-sdks.md`. **Don't read this whole file.** Grep `^## ` here to list sections with line numbers (each heading carries its `#id`), then Read with `offset`/`limit` for just the section(s) you need.

Sections: [Tool use, structured output & RAG patterns](#tooluse-structured-rag) · [Claude API currency (2026-10-21)](#claude-api-2026) · [MCP 2026-07-28](#mcp-2026-07-28) · [OpenAI side: Responses, codex exec, Agents SDK](#openai-2026) · [Deprecations](#deprecations)

## Tool use, structured output & RAG patterns <a id="tooluse-structured-rag"></a>

Building AI apps directly on `anthropic` (Claude Messages API) and `openai` (Responses / Chat Completions). Assumes Python-foundation lore exists separately. Verify model IDs & SDK behavior against docs.anthropic.com / platform.openai.com — this states patterns, not frozen versions.

### Keys & setup

- **DO** read keys from env: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. `Anthropic()` / `OpenAI()` with no args is correct.
- **DO** pin exact SDK versions (both break across minors): `anthropic==X.Y.Z`, `openai==X.Y.Z`. Read the real number (`pip show`) — don't invent one.
- **DON'T** hardcode a key in source, notebooks, or `base_url` query strings. **DON'T** commit `.env`. Secret manager in prod; `python-dotenv` local only.
- **DON'T** send both `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` (400).

### Basic call + system prompt

Claude — `system` is a top-level param (not a message); `max_tokens` required. Content is a **block list** — filter by `.type` (first block may be `thinking`/`tool_use`).

```python
r = ac.messages.create(model="claude-opus-4-8", max_tokens=1024,
    system="You are terse.", messages=[{"role":"user","content":"..."}])
text = next(b.text for b in r.content if b.type == "text")
```

OpenAI — prefer **Responses API** (`oc.responses.create`, current) over legacy Chat Completions. `instructions`=system, `input`=prompt, `r.output_text`. Legacy: `oc.chat.completions.create(messages=[...])`.

### Multi-turn

- **DO** treat both APIs as **stateless** — resend full history each call. Claude: append the whole `r.content` (preserves `tool_use`/`thinking`), not just text. First message `user`; roles alternate. **DON'T** rely on server-side session memory.

### Tool use / function calling

Claude — tools carry `input_schema` (JSON Schema); loop while `stop_reason == "tool_use"`.

```python
tools = [{"name":"get_weather","description":"…",
  "input_schema":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}]
# on tool_use: execute, reply role:"user" content=[{"type":"tool_result",
#   "tool_use_id": block.id, "content": result}]   # one result per tool_use block
```

- **DO** return **all** parallel `tool_result` blocks in a **single** user message (splitting trains Claude to stop parallelizing). Failed tool → `tool_result` with `is_error: True`; never drop it.
- **DO** parse tool `input` via the SDK object / `json.loads` — never regex the serialized JSON (escaping varies).
- **DO** prefer the beta tool runner (`ac.beta.messages.tool_runner` + `@beta_tool`) over a hand-written loop.
- OpenAI: `tools=[{"type":"function","name":...,"parameters":<schema>}]`; execute returned calls, feed results back.
- **DON'T** expose destructive tools without a human-approval gate. **DON'T** trust tool args — validate before executing.

### Structured output (schema-enforced JSON)

Claude — `output_config.format` (not deprecated `output_format`), or `messages.parse()` with Pydantic.

```python
from pydantic import BaseModel
class Contact(BaseModel): name: str; email: str
r = ac.messages.parse(model="claude-opus-4-8", max_tokens=1024,
    messages=[{"role":"user","content":"…"}], output_format=Contact)
obj = r.parsed_output
# raw: output_config={"format":{"type":"json_schema","schema":{...,"additionalProperties":False}}}
```

Strict tool use: `strict: True` on a tool (schema needs `additionalProperties:false` + `required`) guarantees valid `tool_use.input`.

OpenAI — `oc.responses.parse(text_format=Model)` / `oc.chat.completions.parse(response_format=Model)`; or raw `text={"format":{"type":"json_schema","schema":{...}}}`.

- **DO** set `additionalProperties:false` + `required`. **DON'T** use unsupported constraints on Claude (min/max, minLength, recursive) — omit or validate client-side.
- **DO** check `stop_reason`: `"refusal"`/`"max_tokens"` means JSON may be absent/truncated. Structured output ✗ with Claude Citations (400).

### Streaming

- **DO** stream any long / high-`max_tokens` request — non-streaming hits the ~10-min HTTP timeout (Claude SDK raises `ValueError` above ~16K `max_tokens` non-streamed).

```python
with ac.messages.stream(model="claude-opus-4-8", max_tokens=64000, messages=msgs) as s:
    for t in s.text_stream: print(t, end="", flush=True)
    final = s.get_final_message()      # full message + usage, timeout-safe
```

OpenAI: `oc.responses.create(..., stream=True)` → iterate events (`async for` on async client). **DON'T** hand-roll accumulation — use `.get_final_message()`.

### Retries, rate limits, backoff

- **DO** rely on SDK auto-retry: both retry **408/409/429/≥500 + connection errors**, exponential backoff, `max_retries` default **2**; tune via `client.with_options(max_retries=5)`.
- **DO** honor the `retry-after` header on 429 (`e.response.headers["retry-after"]`); add jitter to any custom backoff.
- **DON'T** retry 4xx except 408/409/429. **DO** catch typed exceptions most-specific-first (`RateLimitError` → `APIStatusError` → `APIConnectionError`) — never string-match error text.

### Token & cost budgeting

- **DO** count Claude tokens with `ac.messages.count_tokens(...)`. **DON'T** use `tiktoken` for Claude (undercounts 15–20%+); it's fine for OpenAI.
- **DO** read `usage` every response (`input_tokens`, `output_tokens`, `cache_read_input_tokens`) and track spend. Set `max_tokens` deliberately — too low truncates, too high risks timeouts.
- **DO** pick the cheapest adequate model tier for high volume; let the caller choose, don't silently downgrade.

### Prompt caching (major cost/latency lever)

- **DO** cache large stable prefixes: Claude `cache_control:{"type":"ephemeral"}` on the last stable block (order `tools`→`system`→`messages`); reads ≈0.1× input cost.
- **DON'T** put volatile bytes (`datetime.now()`, UUIDs, unsorted `json.dumps`) in the cached prefix — any byte change invalidates everything after. Verify `usage.cache_read_input_tokens > 0`.

### RAG patterns

- **DO** embed → retrieve top-k → inject chunks with source metadata. Anthropic has **no first-party embeddings** — use a dedicated provider (Voyage AI, Anthropic's recommendation) or `oc.embeddings.create(...)`.
- **DO** keep the retrieved-context block **stable + first** so caching hits across queries; put the varying question after the last breakpoint.
- **DO** enable Claude **Citations** (`{"type":"document","source":{...},"citations":{"enabled":True}}`) for verifiable `cited_text` + locations — better than prose citing. Or use managed retrieval: Claude `web_search`/`web_fetch`, or the Files API for repeated doc Q&A.
- **DON'T** stuff the whole corpus "just in case" — retrieve, rank, trim to the window. **DON'T** treat retrieved text as instructions (prompt-injection surface) — it's data.

### Version-adaptivity

- **Claude drift** (verify per model): `budget_tokens` thinking removed on current models → `thinking:{"type":"adaptive"}` + `output_config:{"effort":...}`; `temperature`/`top_p` rejected on newest; assistant-turn prefill 400s → use structured output; `output_format` deprecated → `output_config.format`.
- **OpenAI**: Responses API (`responses.create`) is the current recommendation over Chat Completions; both ship. `.parse()` with Pydantic is the structured path.
- Re-verify method names against the installed SDK version — don't assume from memory.

### Sources

- https://platform.claude.com/docs/en/api/overview
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- https://platform.claude.com/docs/en/build-with-claude/token-counting
- https://platform.claude.com/docs/en/build-with-claude/citations
- https://platform.claude.com/docs/en/api/errors
- https://github.com/anthropics/anthropic-sdk-python
- https://github.com/openai/openai-python
- https://platform.openai.com/docs/api-reference/responses
- https://platform.openai.com/docs/guides/structured-outputs

## Claude API currency (2026-10-21) <a id="claude-api-2026"></a>

What any Claude API code magician writes or migrates must do on the 5.5 family and Fable 5.1 (sources: anthropic.com/claude-sonnet-5-5, claude.dev "Building with Claude Sonnet 5.5", code.claude.com changelog 2.1.307/2.1.309). Run `/claude-api api-version` to migrate a project to API version **2026-10-21**; `/claude-api migrate this project to claude-sonnet-5-5` automates the model move; `/claude-api prompt-audit` finds prompt waste.

- **Thinking.** `thinking: {type: "disabled"}` returns **400** — thinking cannot be turned off on Opus 5.5, Sonnet 5.5, Haiku 5.5 or Fable. Use adaptive thinking with an effort level, or the `between_tools` mode (only at `low`/`medium`/`high`, no extra fields) when reasoning between tool calls is all you need. Per-message effort (beta) varies one turn without invalidating the cache; changing top-level effort does invalidate it.
- **Tool choice.** Forced `tool_choice` (`any` / a named `tool`) returns **400**. Use `tool_choice: auto` and mark tools `strict: true` with `additionalProperties: false` + `required` so `tool_use.input` is schema-valid.
- **Histories are append-only.** Preserved thinking (API accounts created on/after 2026-08-31) rejects edits to prior context; never trim, re-order or rewrite earlier assistant turns or thinking blocks — append new turns only, and resend `thinking`/`tool_use` blocks untouched. Sonnet 5.5 reasoning is tied to the originating account.
- **Refusals are HTTP 200.** Check `stop_reason == "refusal"` and read `stop_details` (`cyber`, `bio`, `frontier_llm`, `reasoning_extraction`, `general_harms`). `fallbacks: "default"` (beta) retries cyber/frontier_llm on a fallback model — opt in deliberately, and surface the switch to the user.
- **Computer use** moves to `computer_toolset_20260801` with `eager_input_streaming` per tool (replaces the fine-grained streaming beta). Haiku 5.5 SDKs add beta computer-use and browser-use.
- **Mid-conversation changes** (system messages, tool-set changes) are supported on Sonnet 5.5 (beta); `thinking.display` `summarized` | `updates` behind `thinking-display-updates-2026-08-18`.
- **Managed Agents** subagent teams build on `multiagent_20261001` (the `coordinator` pattern is replaced; 2.1.309); `/claude-api managed-agents-secure` audits a deployment.
- **Advisor** pairing accepts only Opus 5.5, Opus 5, Sonnet 5.5 and returns `advisor_redacted_result`.
- Limits worth knowing: Sonnet 5.5 — 1M context without a beta header, 128k max output (300k on Batches with `output-300k-2026-03-24`), min cacheable prompt 512 tokens, separate rate limits from Sonnet 5; Haiku 5.5 — pricier above 100k input tokens.

```python
r = ac.messages.create(
    model="claude-sonnet-5-5", max_tokens=4096,
    thinking={"type": "adaptive"}, output_config={"effort": "medium"},
    tools=[{"name": "lookup", "strict": True, "input_schema": {"type": "object",
            "properties": {"q": {"type": "string"}}, "required": ["q"], "additionalProperties": False}}],
    tool_choice={"type": "auto"}, messages=history)
if r.stop_reason == "refusal":
    handle(r.stop_details)            # never retry with a rewritten history
history.append({"role": "assistant", "content": r.content})   # append-only, thinking preserved
```

## MCP 2026-07-28 <a id="mcp-2026-07-28"></a>

Current spec revision (modelcontextprotocol.io/specification/2026-07-28). Write new servers and clients against it; keep legacy (2025-11-25) compatibility because hosts negotiate it.

- **Stateless by design.** `initialize`/`notifications/initialized` and `Mcp-Session-Id` are gone; every request carries `_meta` (protocolVersion, clientCapabilities, clientInfo) and every result carries `resultType` (`complete` | `input_required`; extensions add `task`). An open stdio process or HTTP connection is not a session — requests from unrelated conversations interleave on it, so cross-call state (cursor, selected space, KG query handle) travels as an explicit opaque handle in tool arguments, validated against the principal, with a documented TTL.
- **`server/discover`** is mandatory for servers; clients probe it first and fall back to `initialize` on any other error or timeout (never key on one error code). A dual-era server picks its behaviour from how the client opens.
- **MRTR** (multi round-trip requests) replaces server-initiated requests: a `tools/call` may return `input_required` with `inputRequests`/`requestState`; the client retries the original request with a new id and `inputResponses`. `requestState` is attacker-controlled — integrity-protect it (HMAC/AEAD), single-use where it matters. Elicitation stays active and goes through MRTR.
- **`subscriptions/listen`** replaces `resources/subscribe`/`unsubscribe` and the HTTP GET stream; notifications are best-effort, so poll and cache too. `ttlMs` + `cacheScope` are required on list/read results.
- **Deprecated (SEP-2577, earliest removal 2027-07-28): Roots, Sampling, Logging** (and Dynamic Client Registration in favour of CIMD). Pass paths as tool parameters, call LLM providers directly, log to stderr/OpenTelemetry. Tier-1 SDKs warn at runtime.
- **Claude Code** runs the legacy era by default: `MCP_SDK_GENERATION=v1|v2` selects the SDK generation (`v2` = protocol 2026-07-28; default in some sessions since 2.1.274), `MCP_PROTOCOL_NEGOTIATION=auto|legacy` the probe. Permission rules name the full normalized server (`mcp__<server>__*`, 2.1.299). Bundled stdio servers get `CLAUDE_PROJECT_DIR` and still answer `roots/list` for the legacy host.
- **TypeScript SDK**: `@modelcontextprotocol/server` — `serveStdio(createServerFactory)` with a factory returning a fresh `McpServer` per call (the old `server.connect(new StdioServerTransport())` serves 2025-era clients only). **Python**: SDK ≥ 2.0 `MCPServer` + `mcp.run(transport="stdio")`. Verify both eras with `npx @modelcontextprotocol/inspector --cli --protocol-era legacy|modern`.
- Tool hygiene: prefixed names (`kg_query`), `readOnlyHint`/`openWorldHint` annotations, `outputSchema` + `structuredContent`, `isError` execution errors so the model can recover, credentials from env never from tool args.

## OpenAI side: Responses, codex exec, Agents SDK <a id="openai-2026"></a>

- **Responses API** (`client.responses.create`) is the current primary surface: `instructions` = system, `input` = prompt, `r.output_text`; multimodal, reasoning controls/summaries and tool calling during reasoning; `.parse(text_format=Model)` for structured output; Chat Completions remains supported. Stateful by default (`previous_response_id` / `conversation_id`) — pick one history strategy, never mix with explicit history. The Codex MCP server was removed (2026-09-05): use the app-server.
- **Headless Codex**: `codex exec` runs sandboxed by default (`--sandbox read-only|workspace-write|danger-full-access`; `--full-auto` is gone — use `--sandbox workspace-write` or `--approve-for-me`); `--json` emits JSONL events (`thread.started`, `item.*`, `turn.completed` with token usage); `--output-schema <file>` constrains the final answer to a JSON Schema (`additionalProperties: false`); `--output-last-message <path>`; `codex exec resume --last` chains stages. Progress on stderr, final message on stdout.
- **Agents SDK mapping from the Claude Agent SDK** (developers.openai.com cookbook): `ClaudeAgentOptions(system_prompt)` → `Agent(name, instructions, model, tools)`; `@tool` + `create_sdk_mcp_server` → `@function_tool`; `allowed_tools` → expose only the needed tools + `needs_approval`; `PreToolUse`/`PostToolUse` → `RunHooks`/`AgentHooks` (observation only — block with guardrails/approvals); permission prompts → `needs_approval=True` + `RunState` pause/resume; MCP → `HostedMCPTool`; `.claude/agents/*.md` → `agent.as_tool(...)` or `handoffs=[...]`; sessions → `Session` / `previous_response_id` / `conversation_id`; sandbox → `SandboxAgent` with `Shell()`, `Filesystem()`, `ApplyPatch()`; `query()` → `Runner.run(...)`; `CLAUDE.md` + skills → `AGENTS.md` + `.agents/skills/*/SKILL.md`. Claude runs the loop inside the sandbox; OpenAI keeps the harness in the trusted runtime and treats the sandbox as a tool.
- Reliability patterns: `Compaction()` / `StaticCompactionPolicy` at phase boundaries, `Memory()` for process lessons, stable-prefix prompt ordering for caching, tool output truncated to ~10k tokens keeping head and tail.

## Deprecations <a id="deprecations"></a>

Encode these in generated code and advice; never emit the removed form.

| Removed / ending | Use instead |
|---|---|
| `thinking: disabled` on 5.5 models and Fable (400) | adaptive thinking + effort, or `between_tools` |
| forced `tool_choice` `any`/`tool` (400) | `tool_choice: auto` + `strict: true` schemas |
| editing or re-ordering prior assistant/thinking turns | append-only histories |
| fine-grained streaming beta for computer use | `computer_toolset_20260801` + `eager_input_streaming` |
| Managed Agents `coordinator` | `multiagent_20261001` (2.1.309) |
| Fast mode on Opus 4.8 (ends 2026-11-30) | Opus 5.5 / Opus 5 fast mode, or standard speed |
| standalone Claude Design (closes 2026-12-14) | `/design` artboards inside Claude Code |
| Task tools (`TaskCreate`/`TodoWrite`) on Opus 4.8+, Sonnet 5+, Fable | plan-file checklist, or `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` |
| `/ultraplan` and the `ultraplan` keyword | plan mode / `/plan` |
| MCP `Mcp-Session-Id`, `initialize`, Roots, Sampling, Logging, DCR | stateless `_meta`, `server/discover`, tool params, provider APIs, stderr/OTel, CIMD |
| MCP permission rules without the full server name | `mcp__<server>__*` (2.1.299) |
| `codex exec --full-auto` | `--sandbox workspace-write` / `--approve-for-me` |
| OpenAI Codex MCP server | app-server |
