# LangGraph RAG Chatbot

An agentic LLM chat assistant that decides on its own whether to search the web, fetch a live stock
price, do arithmetic, or read your uploaded PDF — and remembers every conversation across restarts.

## Features (working today)

- **Agentic tool routing** — a LangGraph `StateGraph` with a conditional tool-execution loop
  (`chat_node` ⇄ `tools`), not a single fixed call.
- **4 tools:** DuckDuckGo web search, Alpha Vantage stock price lookup, a calculator, and per-thread
  PDF retrieval (RAG).
- **Per-document RAG** — PDFs are chunked (`RecursiveCharacterTextSplitter`, 1000/200) and embedded
  with `sentence-transformers/all-MiniLM-L6-v2` into a FAISS retriever, scoped per chat thread.
- **Persistent multi-thread memory** — conversations survive restarts via a LangGraph SQLite
  checkpointer; a sidebar thread switcher reloads any past chat.
- **Streaming UI** — token-by-token responses in Streamlit, with a live "using tool…" status
  indicator.

## Tech stack

`langgraph` · `langchain` + `langchain-community` + `langchain-huggingface` · HuggingFace
`Qwen/Qwen2.5-7B-Instruct` (remote inference) · `sentence-transformers` (MiniLM embeddings) ·
`faiss-cpu` · `pypdf` · `streamlit` · SQLite (`langgraph-checkpoint-sqlite`)

## Status

This project is under active restructuring. See:
- [`docs/implementation_plan.md`](docs/implementation_plan.md) — the active roadmap (Qdrant + Neon +
  LangSmith + Modal deploy + eval harness).
- [`docs/structure-plan.md`](docs/structure-plan.md) — the target folder layout and the mapping of
  existing code into it.

## Setup

```bash
python -m venv myenv
myenv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your own keys (HuggingFace token, Alpha Vantage key,
LangSmith keys if using tracing). Then run:

```bash
python -m streamlit run src/client/app.py
```

Run it with `python -m streamlit`, not the bare `streamlit` command, and from the project root
(`ChatBot/`) — the `-m` flag adds the project root to Python's import path, which is what lets the
`from src.backend...` imports in `app.py` resolve.

## Roadmap

See `docs/implementation_plan.md` for the full plan: upgrading the data layer to Qdrant (vectors) and
Neon Postgres (memory), adding LangSmith tracing, splitting the backend onto Modal with a thin
Streamlit client, and adding an evaluation harness.
