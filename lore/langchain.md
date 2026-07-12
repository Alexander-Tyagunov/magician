# LangChain (Python) — core lore

Current: **v1.0** (Oct 2025, Python 3.10+). v1 slimmed `langchain` to agents/messages/tools/chat_models/embeddings; base is `langchain-core`; legacy → `langchain-classic`. Provider models live in partner pkgs: `langchain-openai`, `langchain-anthropic`, `langchain-google-genai`.

DO init via `from langchain.chat_models import init_chat_model` → `init_chat_model("openai:<model>")`, or class import `ChatOpenAI`/`ChatAnthropic`.
DO use `invoke` / `stream` (yields `AIMessageChunk`) / `batch`; v1 returns `AIMessage`; `.text` is a property (no parens).
DO tool-call: `@tool` (from `langchain.tools`) → `model.bind_tools([...])` → read `resp.tool_calls`.
DO structured output: `model.with_structured_output(PydanticModel)` — not string parsing.
DO build agents with `create_agent` (from `langchain.agents`, on LangGraph): `system_prompt=`, middleware hooks, TypedDict state only.
DO keep keys in env (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)/secret mgr; use `stream`+`batch` to cut latency/cost.

DON'T use moved/removed APIs: `LLMChain`, `ConversationChain`, `initialize_agent`, `create_react_agent`, legacy LCEL chains → now `langchain-classic` or `create_agent`.
DON'T hardcode keys; DON'T call `.text()`; DON'T pass Pydantic/dataclass agent state.
DON'T assume 0.0.x monolith imports — provider classes are in partner packages.

Deep dive when writing non-trivial langchain — read lore/langchain/{chains-agents-rag}.md

Sources: docs.langchain.com/oss/python — overview, releases/langchain-v1, migrate/langchain-v1, langchain/models
