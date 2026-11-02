# LLM SDKs (anthropic, openai) — core

Versions: `anthropic` + `openai` Python SDKs v1.x+. Anthropic = Messages API (`client.messages.create`, API version `2026-10-21`). OpenAI = **Responses API** (`client.responses.create`) primary; Chat Completions still supported.

DO init once: `from anthropic import Anthropic; c=Anthropic()` / `from openai import OpenAI; c=OpenAI()` — key auto-read from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`.
DON'T hardcode keys — env var / secret manager only; never commit.
DO set `max_tokens` (required on Anthropic Messages).
DO stream long output: `with c.messages.stream(...) as s:` / `c.responses.create(..., stream=True)`.
DO on current Claude models: adaptive thinking or `between_tools` (never `thinking: disabled` — 400), `tool_choice: auto` + `strict: true` tools (forced `any`/`tool` — 400), append-only histories (preserved thinking), check `stop_reason == "refusal"` + `stop_details`.
DO structured output via `strict` tools / `output_config.format` (Anthropic) or `text={"format":{"type":"json_schema",...}}` / `c.responses.parse(text_format=Model)` (OpenAI).
DO handle limits: SDKs auto-retry (2x, exp backoff) — tune `max_retries`/`timeout`; catch `RateLimitError`.
DO read `response.usage`; pre-count with Anthropic `messages.count_tokens`.
DON'T sync-loop bulk — async client / Batches API (50% cheaper).
DON'T pin stale model IDs — use tier aliases or check docs (lore/models.md).
DON'T ask the model to echo or move its thinking blocks (lore/model-behavior.md).
MCP: target spec 2026-07-28 (stateless, `server/discover`, MRTR, `subscriptions/listen`); Roots/Sampling/Logging deprecated.

Commands: `pip install anthropic openai`

Deep dive when writing non-trivial llm-sdks — read lore/deep/llm-sdks.md#{tooluse-structured-rag,claude-api-2026,mcp-2026-07-28,openai-2026,deprecations}
Sources: platform.claude.com/docs/en/api · developers.openai.com/api/reference · modelcontextprotocol.io/specification/2026-07-28 · SDK READMEs (github anthropics/anthropic-sdk-python, openai/openai-python)
