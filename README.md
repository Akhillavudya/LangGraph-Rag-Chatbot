# Sage — Agentic RAG Chatbot

An agentic LLM assistant that decides on its own whether to search the web, fetch a live stock price,
do arithmetic, or read your uploaded PDF — and remembers every conversation across restarts. Built as a
**deployed, industry-structured** project: a serverless agent on Modal behind a thin web UI.

> **Live demo:** https://langgraph-rag-chatbot-ugm9xtvqqpggvo8vpcv9vf.streamlit.app/ &nbsp;·&nbsp; **Backend:** serverless on Modal

## Architecture

```
  Browser
     │  HTTPS + bearer token
     ▼
  Thin Streamlit client  ──────►  Modal FastAPI backend  ──►  Qdrant   (PDF vectors, per-thread)
  (streamlit + requests)   HTTP   (LangGraph agent)       ──►  Neon PG  (conversation memory)
  on Streamlit Cloud                                       ──►  Groq API (Llama-3.1-8B LLM)
                                                           ──►  LangSmith (tracing)
```

The UI holds **no AI code** — it only knows five HTTP endpoints (`/health`, `/threads`, `/history`,
`/ingest`, `/chat`). All intelligence (the agent, retrieval, memory) lives in the Modal backend, which
scales to zero when idle. A shared bearer token protects every endpoint.

## Features

- **Agentic tool routing** — a LangGraph `StateGraph` with a conditional tool-execution loop
  (`chat_node` ⇄ `tools`), not a single fixed call.
- **4 tools:** DuckDuckGo web search, Alpha Vantage stock lookup, a calculator, and per-thread PDF
  retrieval (RAG).
- **Per-document RAG** — PDFs are chunked (`RecursiveCharacterTextSplitter`, 1000/200), embedded with
  `sentence-transformers/all-MiniLM-L6-v2`, and stored in **Qdrant** with a per-thread payload filter so
  each chat only sees its own document.
- **Persistent multi-thread memory** — conversations survive restarts via a LangGraph **Neon Postgres**
  checkpointer; the sidebar reloads any past chat.
- **Streaming UI** — token-by-token responses in Streamlit, resilient to Modal cold starts.
- **Tracing** — every run is captured in **LangSmith**.

## Tech stack

`langgraph` · `langchain` (+ `-community`, `-groq`, `-huggingface`, `-qdrant`) · **Groq**
`llama-3.1-8b-instant` (LLM inference) · `sentence-transformers` (local MiniLM embeddings) ·
**Qdrant** (vectors) · **Neon Postgres** (memory) · **LangSmith** (tracing) · **Modal** (serverless
backend) · **Streamlit** + `requests` (thin client, on Streamlit Community Cloud).

## Repo layout

```
src/backend/     the LangGraph agent, tools, RAG (Qdrant), memory (Neon)   ← runs on Modal
src/client/      the thin Streamlit UI (HTTP only) + its own requirements.txt
modal_app.py     wraps the backend as 5 FastAPI endpoints on Modal
eval/            reproducible benchmark: retrieval hit-rate/MRR + latency p50/p95
assets/          the fixed sample PDF the eval runs against (+ its generator)
requirements.txt          full backend deps (installed into the Modal image)
docs/explanation/         per-step beginner explainers
docs/implementation_plan.md   the authoritative roadmap
```

## Running it

**Backend (Modal).** Store your keys in a Modal secret named `chatbot-secrets` (Neon, Qdrant, HF,
LangSmith, and a `CHATBOT_API_TOKEN`), then:

```bash
modal deploy modal_app.py     # permanent URL
# or: modal serve modal_app.py   # temporary dev URL while the terminal is open
```

**Client (Streamlit).** The client only needs the backend URL + token. Locally, copy
`.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` (git-ignored) and fill in
`MODAL_ENDPOINT_URL` and `CHATBOT_API_TOKEN`, then:

```bash
python -m streamlit run src/client/app.py
```

On Streamlit Community Cloud: set the main file to `src/client/app.py` (its neighboring
`requirements.txt` keeps the deploy thin) and paste the same two secrets into the app's **Secrets** box.

## Evaluation

A reproducible benchmark lives in [`eval/`](eval/): 13 questions over the fixed `assets/sample.pdf`,
each with a known answer. It reports **retrieval** hit-rate@1 / hit-rate@4 / MRR and **latency**
p50/p95 (time-to-first-token and total), with the timed turns traced in LangSmith. Run it from the
project root:

```bash
python -m eval.run_eval            # retrieval + latency  → writes eval/README.md
python -m eval.run_eval --no-latency   # retrieval only (no LLM calls)
```

## Roadmap

All three phases are complete: **A** (managed data layer: Qdrant + Neon + LangSmith), **B** (split onto
Modal + thin deployed client), and **C** (this eval harness). See
[`docs/implementation_plan.md`](docs/implementation_plan.md) for the full plan and
[`docs/explanation/`](docs/explanation/) for the per-step teaching write-ups.
