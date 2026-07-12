# LLM SDKs (anthropic, openai) — core

Versions: `anthropic` + `openai` Python SDKs v1.x+. Anthropic = Messages API (`client.messages.create`). OpenAI = **Responses API** (`client.responses.create`) primary; Chat Completions (`client.chat.completions.create`) still supported.

DO init once: `from anthropic import Anthropic; c=Anthropic()` / `from openai import OpenAI; c=OpenAI()` — key auto-read from `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`.
DON'T hardcode keys — env var / secret manager only; never commit.
DO set `max_tokens` (required on Anthropic Messages).
DO stream long output: `with c.messages.stream(...) as s:` / `c.responses.create(..., stream=True)`.
DO structured output via tools + `tool_choice` (Anthropic) or `text={"format":{"type":"json_schema",...}}` / `c.responses.parse(text_format=Model)` (OpenAI Pydantic).
DO handle limits: SDKs auto-retry (OpenAI 2x, exp backoff) — tune `max_retries`/`timeout`; catch `RateLimitError`.
DO read `response.usage` for tokens/cost; pre-count with Anthropic `messages.count_tokens`.
DON'T sync-loop bulk — async client / Batches API (50% cheaper).
DON'T pin stale model IDs — check docs for current (Claude `claude-opus-4-*`, OpenAI `gpt-5.*`).

Commands: `pip install anthropic openai`

Deep dive when writing non-trivial llm-sdks — read lore/llm-sdks/{tooluse-structured-rag}.md
Sources: platform.claude.com/docs/en/api · developers.openai.com/api/reference · SDK READMEs (github anthropics/anthropic-sdk-python, openai/openai-python)
