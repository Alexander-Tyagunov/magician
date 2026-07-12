# langchain — Chains, agents & RAG

Verified against **LangChain 1.x** (`langchain` 1.3, `langchain-core` 1.4, `langchain-openai`/`-anthropic` 1.x, `langgraph` 1.x; `langchain-community` 0.4). Python **3.10+**. Assumes separate python foundation lore. State your versions — the API split changed hard across generations.

```python
import langchain, langchain_core; print(langchain.__version__, langchain_core.__version__)
```

## Package layout (the 0.3→1.x split)

DO install only what you use — integrations live in **independent partner packages**:
- `langchain-core` — `Runnable`/LCEL, messages, prompts, base tool/vectorstore/embeddings abstractions. No heavy deps.
- `langchain-openai`, `langchain-anthropic`, `langchain-chroma`, … — one provider per package.
- `langchain` — `init_chat_model`, `@tool`, and `create_agent` (the agent harness).
- `langgraph` — stateful runtime (checkpointers, persistence) that `create_agent` is built on.
- `langchain-community` — long tail of community integrations (still 0.x; pin it).
- `langchain-text-splitters` — splitters.

DON'T `from langchain.chat_models import ChatOpenAI` (0.0.x monolith path) — it's gone. Import providers from their package: `from langchain_openai import ChatOpenAI`.
DON'T mix a 0.2/0.3 tutorial with 1.x code. Migration ladder: **0.0.x monolith → 0.1/0.2 (core+community split) → 0.3 (Pydantic v2 only) → 1.x (`create_agent`, langgraph runtime, `content_blocks`)**. Legacy `LLMChain`, `initialize_agent`, `AgentExecutor`, `ConversationChain` are removed/deprecated — use LCEL for chains, `create_agent` for agents.

## Models & keys

```python
from langchain.chat_models import init_chat_model
model = init_chat_model("anthropic:claude-...")   # "provider:model"; see models lore for IDs
# or explicit: from langchain_anthropic import ChatAnthropic; ChatAnthropic(model="claude-...")
```

- DON'T hardcode keys. SDKs read env (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`); use a secret manager in prod, not literals or committed `.env`.
- DO use the uniform runtime: `.invoke/.stream/.batch` (+ async `.ainvoke/.astream/.abatch`). `.batch` runs concurrently — cheap parallelism.
- DO cap spend with `rate_limiter=InMemoryRateLimiter(...)` (`from langchain_core.rate_limiters`). Handle 429s: models take `max_retries=`; any Runnable has `.with_retry(...)`.

## LCEL — chains (`Runnable`, `|`)

Still the composition layer in 1.x. Build declarative pipelines with `|`; every stage is a `Runnable` and inherits invoke/stream/batch + async for free.

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_messages([("system","Answer tersely."),("user","{q}")])
chain = prompt | model | StrOutputParser()          # prompt → model → text
chain.invoke({"q": "why is the sky blue?"})
for tok in chain.stream({"q": "..."}): print(tok, end="")   # streams end-to-end
```

- DO fan out with `RunnableParallel` (dict of runnables), adapt with `RunnableLambda`, thread state with `RunnablePassthrough.assign(...)`.
- DON'T use LCEL for a tool-calling *loop* — that's `create_agent`. LCEL = fixed DAG; agents = model-driven control flow.

## Structured output

```python
from pydantic import BaseModel, Field
class Movie(BaseModel):
    title: str; year: int = Field(description="release year")
model.with_structured_output(Movie).invoke("Details for Inception")   # -> Movie instance
```

- DO define schemas with **Pydantic v2** (`BaseModel`) — 0.3+ dropped v1. Add `Field(description=...)`; the model uses it.
- DON'T regex-parse free text. `with_structured_output` auto-picks provider-native JSON/tool-calling. Validate before use.

## Agents (`create_agent` on LangGraph)

Agent = model + tools looped until done. Prefer this over the removed `AgentExecutor`.

```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get weather for a city."""       # docstring + type hints = the tool schema
    return f"sunny in {city}"

agent = create_agent(model="anthropic:claude-...", tools=[get_weather],
                     system_prompt="Be concise.")
agent.invoke({"messages": [{"role":"user","content":"weather in SF?"}]})
```

- DO give tools precise names, typed args, and a real docstring — that's what the model sees.
- DO persist memory with a checkpointer + `thread_id` (don't stuff history into the prompt yourself):
```python
from langgraph.checkpoint.memory import InMemorySaver
agent = create_agent(model=..., tools=[...], checkpointer=InMemorySaver())
cfg = {"configurable": {"thread_id": "user-42"}}
agent.invoke({"messages":[...]}, config=cfg)   # reuse thread_id for follow-ups
```
  Use a Postgres/SQLite checkpointer in prod (`InMemorySaver` is ephemeral).
- DO structured agent output via `create_agent(..., response_format=Movie)` → read `result["structured_response"]`.
- DO stream for UX: `agent.stream(payload, stream_mode="updates")` (per-step state) or `"messages"` (LLM tokens); `"values"` = full state each step.
- DON'T let tool loops run unbounded — cap recursion (`config={"recursion_limit": N}`), set timeouts, and make tools idempotent + input-validated (they run with your creds).

## RAG (retrieval)

Pipeline: **load → split → embed → store → retrieve → generate.** Components are swappable.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore   # or langchain_chroma.Chroma (persistent)

splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200,
                                        add_start_index=True).split_documents(docs)
store  = InMemoryVectorStore(OpenAIEmbeddings(model="text-embedding-3-large"))
store.add_documents(splits)
retriever = store.as_retriever(search_type="similarity", search_kwargs={"k": 4})
```

- DO chunk with overlap; `add_start_index=True` keeps provenance in `metadata`. Match embedding model to your domain; keep embed model consistent between index and query.
- DO wire retrieval into a chain (`{"context": retriever, "q": RunnablePassthrough()} | prompt | model`) **or** as an agent tool (**agentic RAG** — the model decides when/what to fetch, can re-query):
```python
@tool
def search_docs(query: str) -> str:
    """Search the knowledge base."""
    return "\n\n".join(d.page_content for d in retriever.invoke(query))
```
- DO cite/quote retrieved snippets; pass only top-k into the prompt (token cost). `search_type="mmr"` for diversity; `"similarity_score_threshold"` to drop weak hits.
- DON'T embed secrets/PII into a shared store. DON'T trust similarity blindly — inspect scores; empty/low-score results should short-circuit, not hallucinate.
- **Alternative:** for retrieval-first apps, **LlamaIndex** is the more focused RAG framework (richer indexing/query engines); use LangChain when you also need agents/orchestration.

## Sources
- https://docs.langchain.com/oss/python/langchain/overview
- https://docs.langchain.com/oss/python/langchain/install
- https://docs.langchain.com/oss/python/langchain/models
- https://docs.langchain.com/oss/python/langchain/agents
- https://docs.langchain.com/oss/python/langchain/retrieval
- https://docs.langchain.com/oss/python/langchain/knowledge-base
- https://docs.langchain.com/oss/python/langchain/structured-output
- https://docs.langchain.com/oss/python/langchain/streaming
- https://pypi.org/project/langchain/ (versions: langchain 1.3, langchain-core 1.4, langgraph 1.x)
