# Implementation Plan — RAG Chatbot Upgrade

**Stack:** Qdrant + Neon + LangSmith + agent on Modal + thin Streamlit client
**Project path:** `C:\Users\91888\OneDrive\Desktop\ChatBot`

## Context

The chatbot's hard engineering is already built and working (LangGraph agent loop, 4 tools,
per-thread PDF RAG, streaming UI, persisted memory). But today it is: 0% deployed, uses an
**in-memory FAISS dict** + a **local SQLite file**, has a **hardcoded Alpha Vantage key**, and
ships a **duplicate app pair**. It needs to earn a 7/10 on *both* the SDE and DS/AI-eng CVs without
colliding with the FastAPI+React lane already owned by Verdex + Materia.

Decision: **no Next.js frontend.** Keep a **thin Streamlit client** and move the intelligence to a
**Modal serverless backend**, upgrading the data layer to managed services. Verdex already carries the
full-stack/React proof, so this project's job is the **AI-engineering story**: agentic RAG + managed
vector DB + persistent memory + tracing + eval + serverless deploy.

### Why the stack is required (not optional)
Running the agent on Modal means **ephemeral, non-shared containers**. Therefore:
- `_THREAD_RETRIEVERS` (in-memory dict, `Langraph_backend.py:43`) **cannot survive** between requests
  → must become **Qdrant** (managed vector DB).
- `SqliteSaver` over a local `chatbot.db` (`Langraph_backend.py:205-206`) **cannot persist** on
  serverless → must become **Neon Postgres** via `PostgresSaver`.
- **LangSmith** is the only visibility into the deployed agent + powers the eval.

Qdrant + Neon + LangSmith fall out of the Modal decision — they make it *correct*, not just fancier.

---

## Target architecture

**Before:** one process — Streamlit imports `Langraph_backend` directly; FAISS in RAM; SQLite on disk.

**After:** two decoupled pieces —
```
Thin Streamlit client (Streamlit Cloud / HF Spaces)
        │  HTTPS (POST /chat streamed, POST /ingest, GET /threads, GET /history)
        ▼
Modal serverless backend  ──►  HuggingFace Qwen2.5-7B (remote inference)
   (LangGraph agent)       ──►  Qdrant Cloud   (per-thread PDF vectors)
                           ──►  Neon Postgres  (LangGraph checkpointer / memory)
                           ──►  LangSmith      (tracing every run)
```
The client holds **no** langchain/langgraph deps — it only does UI + HTTP. All AI logic lives on Modal.

> Note: Modal web endpoints use FastAPI *internally*, but we are not hand-building a FastAPI+React SPA
> — the frontend is Streamlit. No collision with Verdex/Materia.

---

## Build order (3 phases, each independently shippable)

### Phase A — Upgrade the data layer *in place* (still one local Streamlit app)
Swap FAISS→Qdrant, SQLite→Neon, wire LangSmith, clean up — **while the app still runs the current way**
(Streamlit importing the backend). De-risks everything: if Phase B (Modal) proves too hard, Phase A
alone is already a deployable, upgraded, CV-ready project (fallback = HF Spaces).

1. **Cleanup / secrets (do first):**
   - Delete the duplicate pair: `app_1.py`, `Langraph_backend_app.py`.
   - Rename keepers → `app.py` (from `app_2.py`) + `backend.py` (from `Langraph_backend.py`); fix import.
   - **Rotate** the Alpha Vantage key, then read via `os.getenv("ALPHAVANTAGE_API_KEY")`
     (`backend.py`, currently hardcoded at `Langraph_backend.py:139`).
   - Add `.gitignore` (`myenv/`, `chatbot.db`, `__pycache__/`, `.env`, `*.db`) + `.env.example`, then
     `git init`. **Do this before the first commit** — `.env` is not yet ignored and holds live tokens.
   - Fix the double `st.set_page_config` (`app_2.py:57` and `:97`) → single call, first Streamlit command.
2. **FAISS → Qdrant** (`backend.py`): in `ingest_pdf()`, replace `FAISS.from_documents(...)` with a
   `QdrantVectorStore` writing chunks into one collection, tagging each point with `thread_id` in the
   payload. In `rag_tool()`, query Qdrant filtered by `thread_id`. **Delete** the `_THREAD_RETRIEVERS`
   /`_THREAD_METADATA` in-memory dicts.
3. **SQLite → Neon Postgres** (`backend.py`): replace `SqliteSaver(conn=...)` with
   `PostgresSaver.from_conn_string(NEON_URL)` (+ one-time `.setup()`). `retrieve_all_threads()` already
   reads from `checkpointer.list(None)` — no change beyond the swap.
4. **Harden `thread_id` injection** (`backend.py`): stop trusting the 7B LLM to echo `thread_id` into
   `rag_tool`. Inject it from graph config via `InjectedToolArg`/`RunnableConfig` so retrieval is
   reliable (now essential because Qdrant filters on it).
5. **LangSmith tracing:** set `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` in
   `.env`. The existing `CONFIG` in the UI already sets `run_name`/`metadata` — traces will populate.
6. **Pin `requirements.txt`** and add: `qdrant-client`, `langchain-qdrant`,
   `langgraph-checkpoint-postgres`, `psycopg[binary]`, `langsmith`, `modal`.

**Phase A checkpoint:** app runs locally end-to-end on managed services; PDFs and memory survive
restarts. Deployable to HF Spaces as-is if needed.

### Phase B — Split onto Modal + thin client
1. **`modal_app.py`** — a `modal.App`, image with backend deps, mount `backend.py`, expose endpoints
   (via `@modal.asgi_app()` FastAPI or `@modal.fastapi_endpoint`):
   - `POST /chat` `{message, thread_id}` → **streaming** response (wrap the existing
     `chatbot.stream(..., stream_mode="messages")` loop in a `StreamingResponse`).
   - `POST /ingest` `{pdf_bytes, thread_id}` → `ingest_pdf()` → Qdrant.
   - `GET /threads`, `GET /history?thread_id=` → read from the Postgres checkpointer.
   - Secrets (`HUGGINGFACEHUB_API_TOKEN`, `ALPHAVANTAGE_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`,
     `NEON_URL`, LangSmith keys) via `modal.Secret`. Protect endpoints with a shared bearer token.
2. **Rewrite `app.py` as a thin client:** remove all `langgraph`/`langchain` imports. Keep the UI
   (thread sidebar, New Chat, PDF uploader, chat box). Replace direct calls with HTTP:
   - chat → `POST /chat` consumed as a stream, fed to `st.write_stream` (`requests`/`httpx`, `stream=True`).
   - upload → `POST /ingest`; thread list/history → the `GET` endpoints.
   - Read `MODAL_ENDPOINT_URL` + token from `st.secrets` / env.
   - **`requirements-client.txt`** = `streamlit`, `requests` only (no AI deps) — the diversity win.
3. **Deploy:** `modal deploy modal_app.py`; deploy the client to **Streamlit Community Cloud** (or HF
   Spaces) with the Modal URL + token as secrets. Verify live.

### Phase C — Eval harness (earns the DS/AI-eng slot)
`eval/run_eval.py` — a fixed set of ~10–15 Q/A pairs over a known sample PDF + tool prompts. Measure:
- **Retrieval quality:** hit-rate / recall@k against expected source chunks.
- **Latency:** end-to-end p50/p95 (first→last token) per turn, logged to LangSmith.
Emit a small `eval/README.md` table — these numbers convert the weak DS bullet into a real one.

---

## Files

| Action | File | Notes |
|--------|------|-------|
| Delete | `app_1.py`, `Langraph_backend_app.py` | inferior duplicate pair |
| Rename+edit | `Langraph_backend.py` → `backend.py` | Qdrant, Postgres, env key, thread_id injection |
| Rename+edit | `app_2.py` → `app.py` | Phase A: fix config bug; Phase B: gut to thin HTTP client |
| New | `modal_app.py` | Modal endpoints wrapping the agent |
| New | `requirements.txt` (pinned) + `requirements-client.txt` | split backend vs client deps |
| New | `.gitignore`, `.env.example`, `README.md` | repo hygiene + the artifact recruiters read |
| New | `eval/run_eval.py`, `eval/README.md`, `assets/sample.pdf` | DS signal + reproducible demo |

## Secrets / accounts (all free tier)
Qdrant Cloud (`QDRANT_URL`, `QDRANT_API_KEY`) · Neon (`NEON_URL`) · LangSmith (`LANGCHAIN_API_KEY`) ·
Modal account · existing `HUGGINGFACEHUB_API_TOKEN` + **rotated** `ALPHAVANTAGE_API_KEY`.
Local → `.env`; deployed → Modal Secrets + Streamlit secrets.

## Verification (end to end)
1. **Local (Phase A):** run Streamlit; upload `assets/sample.pdf`, ask a doc question (Qdrant hit),
   ask "price of AAPL" (tool), restart the app and confirm the thread + its PDF answers still work
   (proves Neon + Qdrant persistence). Confirm the run appears in the LangSmith project.
2. **Modal (Phase B):** `curl` the `/chat` endpoint for a streamed answer; then drive the deployed thin
   client — chat streams, tool fires, PDF upload+question works, thread switcher loads history from Postgres.
3. **Eval (Phase C):** `python eval/run_eval.py` prints the retrieval + latency table; runs show in LangSmith.

## Effort & fallback
~**2.5–3 focused days**: Phase A ~1 day, Phase B ~1–1.5 days, Phase C ~0.5 day.
**Fallback if Modal streaming proves too hard:** ship **Phase A only** to HF Spaces (fully upgraded app
on Qdrant + Neon + LangSmith + eval) — still a strong, deployed, CV-ready piece; the Modal split becomes
a later stretch. This is why the data-layer upgrade is sequenced first.
