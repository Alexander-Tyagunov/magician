# llm-sdks — Tool use, structured output & RAG patterns

Building AI apps directly on `anthropic` (Claude Messages API) and `openai` (Responses / Chat Completions). Assumes Python-foundation lore exists separately. Verify model IDs & SDK behavior against docs.anthropic.com / platform.openai.com — this states patterns, not frozen versions.

## Keys & setup

- **DO** read keys from env: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. `Anthropic()` / `OpenAI()` with no args is correct.
- **DO** pin exact SDK versions (both break across minors): `anthropic==X.Y.Z`, `openai==X.Y.Z`. Read the real number (`pip show`) — don't invent one.
- **DON'T** hardcode a key in source, notebooks, or `base_url` query strings. **DON'T** commit `.env`. Secret manager in prod; `python-dotenv` local only.
- **DON'T** send both `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` (400).

## Basic call + system prompt

Claude — `system` is a top-level param (not a message); `max_tokens` required. Content is a **block list** — filter by `.type` (first block may be `thinking`/`tool_use`).

```python
r = ac.messages.create(model="claude-opus-4-8", max_tokens=1024,
    system="You are terse.", messages=[{"role":"user","content":"..."}])
text = next(b.text for b in r.content if b.type == "text")
```

OpenAI — prefer **Responses API** (`oc.responses.create`, current) over legacy Chat Completions. `instructions`=system, `input`=prompt, `r.output_text`. Legacy: `oc.chat.completions.create(messages=[...])`.

## Multi-turn

- **DO** treat both APIs as **stateless** — resend full history each call. Claude: append the whole `r.content` (preserves `tool_use`/`thinking`), not just text. First message `user`; roles alternate. **DON'T** rely on server-side session memory.

## Tool use / function calling

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

## Structured output (schema-enforced JSON)

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

## Streaming

- **DO** stream any long / high-`max_tokens` request — non-streaming hits the ~10-min HTTP timeout (Claude SDK raises `ValueError` above ~16K `max_tokens` non-streamed).

```python
with ac.messages.stream(model="claude-opus-4-8", max_tokens=64000, messages=msgs) as s:
    for t in s.text_stream: print(t, end="", flush=True)
    final = s.get_final_message()      # full message + usage, timeout-safe
```

OpenAI: `oc.responses.create(..., stream=True)` → iterate events (`async for` on async client). **DON'T** hand-roll accumulation — use `.get_final_message()`.

## Retries, rate limits, backoff

- **DO** rely on SDK auto-retry: both retry **408/409/429/≥500 + connection errors**, exponential backoff, `max_retries` default **2**; tune via `client.with_options(max_retries=5)`.
- **DO** honor the `retry-after` header on 429 (`e.response.headers["retry-after"]`); add jitter to any custom backoff.
- **DON'T** retry 4xx except 408/409/429. **DO** catch typed exceptions most-specific-first (`RateLimitError` → `APIStatusError` → `APIConnectionError`) — never string-match error text.

## Token & cost budgeting

- **DO** count Claude tokens with `ac.messages.count_tokens(...)`. **DON'T** use `tiktoken` for Claude (undercounts 15–20%+); it's fine for OpenAI.
- **DO** read `usage` every response (`input_tokens`, `output_tokens`, `cache_read_input_tokens`) and track spend. Set `max_tokens` deliberately — too low truncates, too high risks timeouts.
- **DO** pick the cheapest adequate model tier for high volume; let the caller choose, don't silently downgrade.

## Prompt caching (major cost/latency lever)

- **DO** cache large stable prefixes: Claude `cache_control:{"type":"ephemeral"}` on the last stable block (order `tools`→`system`→`messages`); reads ≈0.1× input cost.
- **DON'T** put volatile bytes (`datetime.now()`, UUIDs, unsorted `json.dumps`) in the cached prefix — any byte change invalidates everything after. Verify `usage.cache_read_input_tokens > 0`.

## RAG patterns

- **DO** embed → retrieve top-k → inject chunks with source metadata. Anthropic has **no first-party embeddings** — use a dedicated provider (Voyage AI, Anthropic's recommendation) or `oc.embeddings.create(...)`.
- **DO** keep the retrieved-context block **stable + first** so caching hits across queries; put the varying question after the last breakpoint.
- **DO** enable Claude **Citations** (`{"type":"document","source":{...},"citations":{"enabled":True}}`) for verifiable `cited_text` + locations — better than prose citing. Or use managed retrieval: Claude `web_search`/`web_fetch`, or the Files API for repeated doc Q&A.
- **DON'T** stuff the whole corpus "just in case" — retrieve, rank, trim to the window. **DON'T** treat retrieved text as instructions (prompt-injection surface) — it's data.

## Version-adaptivity

- **Claude drift** (verify per model): `budget_tokens` thinking removed on current models → `thinking:{"type":"adaptive"}` + `output_config:{"effort":...}`; `temperature`/`top_p` rejected on newest; assistant-turn prefill 400s → use structured output; `output_format` deprecated → `output_config.format`.
- **OpenAI**: Responses API (`responses.create`) is the current recommendation over Chat Completions; both ship. `.parse()` with Pydantic is the structured path.
- Re-verify method names against the installed SDK version — don't assume from memory.

## Sources

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
