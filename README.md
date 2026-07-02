<div align="center">

# 🧭 Sage — Agentic RAG Chatbot

**A production-style, agentic Retrieval-Augmented-Generation assistant** that reasons about *which* tool to use, answers questions over your uploaded PDFs, and remembers every conversation across restarts.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://langgraph-rag-chatbot-ugm9xtvqqpggvo8vpcv9vf.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent-1C3C3C?logo=langchain&logoColor=white)
![Modal](https://img.shields.io/badge/Modal-Serverless-7C5CFC?logo=modal&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLM-F55036?logo=groq&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-Vectors-DC244C?logo=qdrant&logoColor=white)

**[▶ Try the live app](https://langgraph-rag-chatbot-ugm9xtvqqpggvo8vpcv9vf.streamlit.app/)** &nbsp;·&nbsp; *first message may take ~30s while the serverless backend cold-starts*

</div>

---

## Overview

**Sage** is an LLM assistant built as a **deployed, industry-structured** system rather than a local script. Instead of hard-coding a single call, it runs an **agent**: on each turn the model decides for itself whether to answer directly or reach for a tool — web search, a live stock quote, a calculator, or semantic retrieval over a PDF you uploaded to *that specific chat*.

The project is deliberately split into a **thin client** and a **serverless backend**:

- The **Streamlit UI** contains *no AI logic* — it only makes HTTP calls to five endpoints.
- The **LangGraph agent** runs on **Modal**, scales to zero when idle, and connects to fully managed data services (Qdrant, Neon, LangSmith).

This mirrors how real AI products are structured — a lightweight front end talking to an independently deployable, observable, stateful backend.

## Architecture

```
   Browser
      │  HTTPS + bearer token
      ▼
 ┌─────────────────────┐        ┌──────────────────────────┐      ┌───────────────────────────────┐
 │  Thin Streamlit UI  │  HTTP  │   Modal FastAPI backend  │ ───► │  Qdrant     — PDF vectors      │
 │  streamlit + requests│ ─────► │   (LangGraph agent)      │ ───► │  Neon PG    — chat memory      │
 │  on Streamlit Cloud │        │   scales to zero on idle │ ───► │  Groq       — Llama-3.1-8B LLM │
 └─────────────────────┘        └──────────────────────────┘ ───► │  LangSmith  — tracing          │
                                                                   └───────────────────────────────┘
```

The UI knows only the endpoints `/health`, `/threads`, `/history`, `/ingest`, and `/chat`. All intelligence — the agent graph, tool routing, retrieval, and memory — lives in the Modal backend, guarded by a shared bearer token.

## Features

| | |
|---|---|
| 🧠 **Agentic tool routing** | A LangGraph `StateGraph` with a conditional `chat_node ⇄ tools` loop — the model chooses the tool, it isn't hard-wired. |
| 📄 **Per-document RAG** | Upload a PDF inside a chat; it's chunked, embedded, and stored in Qdrant behind a **per-thread payload filter**, so each conversation only ever retrieves its own document. |
| 🛠️ **Four tools** | DuckDuckGo web search · Alpha Vantage stock quotes · a safe calculator · per-thread PDF retrieval. |
| 💾 **Persistent memory** | Conversations survive restarts via a LangGraph **Neon Postgres** checkpointer; any past thread reloads from the sidebar. |
| ⚡ **Streaming responses** | Token-by-token output in the UI, resilient to Modal cold starts. |
| 🔭 **Full observability** | Every run is traced in **LangSmith**. |
| 📊 **Reproducible eval** | A benchmark harness scores retrieval quality (hit-rate / MRR) against a fixed document. |

## Tech stack

| Layer | Technology |
|---|---|
| **Agent framework** | LangGraph (`StateGraph`, `ToolNode`, `tools_condition`) + LangChain |
| **LLM** | **Groq** — `llama-3.1-8b-instant` (fast, tool-calling, free-tier inference) |
| **Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` (runs locally, in-process) |
| **Vector store** | **Qdrant Cloud** — per-thread payload-filtered PDF chunks |
| **Conversation memory** | **Neon** serverless Postgres via LangGraph checkpointer |
| **Serverless backend** | **Modal** — FastAPI app exposed with `@modal.asgi_app()`, scales to zero |
| **Frontend** | **Streamlit** (Community Cloud) — thin client, `streamlit` + `requests` only |
| **Observability** | **LangSmith** tracing |
| **Language / tooling** | Python 3.11, pinned `requirements.txt` |

## How a request flows

1. You type a message (optionally attaching a PDF) in the Streamlit UI.
2. The client `POST`s to the Modal backend's `/chat` (or `/ingest`) with a bearer token.
3. The **LangGraph agent** runs: `chat_node` asks the LLM what to do; if it requests a tool, the `tools` node executes it and loops back with the result.
4. For document questions, the `rag_tool` runs a semantic search in Qdrant **scoped to this thread's PDF**.
5. The final answer streams back token-by-token; the full turn is checkpointed to Neon and traced in LangSmith.

## API

All endpoints except `/health` require an `Authorization: Bearer <token>` header.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check (open, no auth) |
| `GET` | `/threads` | List all past conversation thread IDs |
| `GET` | `/history?thread_id=…` | Fetch one thread's message history |
| `POST` | `/ingest` | Upload a PDF (multipart) → chunk + embed into Qdrant |
| `POST` | `/chat` | Run the agent for a message and stream the reply |

## Project structure

```
src/backend/     LangGraph agent, tools, RAG (Qdrant), memory (Neon)   ← runs on Modal
src/client/      thin Streamlit UI (HTTP only) + its own requirements.txt
modal_app.py     wraps the backend as 5 FastAPI endpoints on Modal
eval/            reproducible benchmark: retrieval hit-rate / MRR (+ optional latency)
assets/          the fixed sample PDF the eval runs against (+ its generator)
requirements.txt              full backend deps (installed into the Modal image)
docs/explanation/             per-step teaching write-ups
docs/implementation_plan.md   the project roadmap
```

## Getting started

### Prerequisites
Accounts/keys for: **Groq**, **Qdrant Cloud**, **Neon**, **LangSmith**, and (optional) **Alpha Vantage**. Python 3.11.

### 1. Backend on Modal
Store your keys in a Modal secret named `chatbot-secrets` (`GROQ_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `NEON_URL`, `LANGCHAIN_*`, and a self-chosen `CHATBOT_API_TOKEN`), then:

```bash
modal deploy modal_app.py        # permanent URL
# or: modal serve modal_app.py   # temporary dev URL while the terminal stays open
```

### 2. Client (Streamlit)
The client only needs the backend URL and token. Locally, copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` (git-ignored) and set `MODAL_ENDPOINT_URL` and `CHATBOT_API_TOKEN`, then:

```bash
python -m streamlit run src/client/app.py
```

On **Streamlit Community Cloud**: set the main file to `src/client/app.py` (its neighbouring `requirements.txt` keeps the deploy thin) and paste the same two secrets into the app's **Secrets** box.

## Evaluation

A reproducible benchmark in [`eval/`](eval/) scores retrieval against a fixed document (`assets/sample.pdf`) with 13 questions whose answers each live in exactly one place — so a correct chunk either contains the known answer or it doesn't, no human grading needed.

```bash
python -m eval.run_eval               # writes eval/README.md
python -m eval.run_eval --no-latency  # retrieval only (no LLM calls)
```

**Latest results** — retrieval over 13 questions at top-4:

| Metric | Score |
|---|---|
| Hit-rate@1 | **100%** |
| Hit-rate@4 | **100%** |
| MRR | **1.000** |

> Latency (TTFT / total p50/p95) is supported by the harness and traced in LangSmith, but is left *skipped* on the free tier: bursting the benchmark's turns through Groq's free 6,000-tokens-per-minute limit trips a rate cap that real, one-message-at-a-time usage never hits.

## Project phases

| Phase | Focus | Status |
|---|---|---|
| **A** | Upgrade the data layer in place — Qdrant vectors, Neon memory, LangSmith tracing | ✅ Complete |
| **B** | Split into a serverless Modal backend behind a thin deployed client | ✅ Complete |
| **C** | Reproducible evaluation harness | ✅ Complete |

See [`docs/implementation_plan.md`](docs/implementation_plan.md) for the full roadmap and [`docs/explanation/`](docs/explanation/) for the per-step teaching write-ups covering vector databases, agents, RAG, deployment, and secrets management.

---

<div align="center">

Built as a hands-on learning project to go from a local prototype to a deployed, observable, industry-structured AI application.

</div>
