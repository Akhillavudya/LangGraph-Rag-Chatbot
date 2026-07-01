# Project Profile — Extract for CV & Portfolio

> **Two sources, kept strictly separate.** `[DONE]` = verified in the current code today.
> `[PLANNED]` = only described in `docs/completion-plan.md`, **not yet built**. `NOT FOUND` = could
> not be verified anywhere. **Write CV bullets only from `[DONE]`.**

---

## 1. Identity

- **Project name:** LangGraph Multi-Tool RAG Chatbot (working title — repo folder is `ChatBot`; no official name set yet — `NOT FOUND`)
- **One-line description:** Agentic LLM chatbot that routes between web search, a finance API, a calculator, and PDF retrieval.
- **Type:** Personal project (no hackathon/internship/coursework markers found in code — `NOT FOUND`)
- **Current completion %:** ~65–70% of code built and runs; **0% deployed, 0% documented.**
- **Target completion per plan:** Fully cleaned, documented, and deployed at a public URL (see `docs/completion-plan.md` §2).

---

## 2. The Problem

- **What it solves:** A single chat assistant that can both answer from live external sources (web
  search, stock prices, arithmetic) **and** answer questions about a user's own uploaded PDF, without
  switching tools — the LLM decides which capability to invoke per question. It also remembers every
  past conversation across restarts.
- **Target user/audience:** Anyone needing a do-it-all chat assistant over their own documents — e.g.
  a student querying lecture notes/papers, or a recruiter evaluating an agentic-AI demo.

---

## 3. Technical Stack

### [DONE] — currently wired up in code (exact installed versions)
- **Orchestration:** `langgraph==1.1.6`, `langgraph-checkpoint-sqlite==3.0.3`
- **LLM framework:** `langchain==1.2.15`, `langchain-core==1.2.30`, `langchain-community==0.4.1`, `langchain-huggingface==1.2.1`
- **LLM (remote inference):** `Qwen/Qwen2.5-7B-Instruct` via HuggingFace serverless endpoint (no local GPU)
- **Embeddings:** `sentence-transformers==5.4.1` → `all-MiniLM-L6-v2`
- **Vector store:** `faiss-cpu==1.13.2`
- **PDF parsing:** `pypdf==6.10.2` (PyPDFLoader)
- **Tools/APIs:** DuckDuckGo search (`langchain_community`), Alpha Vantage stock API (`requests==2.33.1`)
- **UI:** `streamlit==1.56.0`
- **Persistence:** SQLite via `SqliteSaver` (`chatbot.db`, ~630KB, contains real checkpoint data → proves it's been run)
- **Config:** `python-dotenv==1.2.2`

### [PLANNED] — to be added per completion-plan.md
- `[PLANNED]` Pinned `requirements.txt` versions for reproducible deploy (plan §4)
- `[PLANNED]` `huggingface_hub` explicitly in requirements if not pulled transitively (plan §4)
- `[PLANNED]` On-disk persisted FAISS index (nice-to-have #1) — currently in-memory only
- `[PLANNED]` Optional LangSmith tracing (currently env vars exist but flagged for removal)

---

## 4. Architecture & Key Decisions

### [DONE] How it's currently built
- **Agent graph** (`Langraph_backend.py:210-221`): a `StateGraph` with two nodes — `chat_node` (the
  LLM) and `tools` (a `ToolNode`). `START → chat_node`, then `tools_condition` conditionally routes to
  `tools`, and `tools → chat_node` loops back. This is a real tool-execution cycle, not a single call.
- **State** (`Langraph_backend.py:173`): `ChatState` with `messages: Annotated[list, add_messages]`.
- **4 tools** (`Langraph_backend.py:104-168`): DuckDuckGo `search_tool`, `get_stock_price` (Alpha
  Vantage), `calculator`, and `rag_tool` (per-thread PDF retrieval). Bound via `llm.bind_tools`.
- **Per-thread RAG** (`Langraph_backend.py:54-98`): `ingest_pdf()` → PyPDFLoader → 
  `RecursiveCharacterTextSplitter(1000/200)` → FAISS from MiniLM embeddings → retriever (k=4), stored
  in an **in-memory dict** `_THREAD_RETRIEVERS` keyed by `thread_id`.
- **Persistent memory** (`Langraph_backend.py:205-206`): `SqliteSaver` checkpointer over `chatbot.db`;
  `retrieve_all_threads()` lists prior conversations.
- **Streaming UI** (`app_2.py:121-158`): token-by-token `st.write_stream`, live "🔧 Using tool…"
  status box, new-chat button, thread switcher, PDF uploader sidebar.

### [PLANNED] Architecture changes/additions in the plan
- `[PLANNED]` Collapse the **two duplicate apps** into one (`app_2.py`+`Langraph_backend.py` kept,
  renamed `app.py`/`backend.py`; delete `app_1.py`+`Langraph_backend_app.py`) — plan §3 #1, §6.
- `[PLANNED]` Move Alpha Vantage key to env var + rotate it — plan §3 #2.
- `[PLANNED]` Reliable `thread_id` injection into `rag_tool` via config (not LLM-echoed) — plan §3 #5.
- `[PLANNED]` Fix duplicate/misordered `st.set_page_config` — plan §3 #4.
- `[PLANNED]` try/except hardening around external API tools — plan §3 #5.
- `[PLANNED]` Persist FAISS to disk; source citations; smoke-test; model selector — plan §5.

### Scale indicators that exist NOW
- **Lines of code (core):** 693 total — `Langraph_backend.py` 236, `app_2.py` 184, `app_1.py` 141,
  `Langraph_backend_app.py` 132.
- **Core source files:** 4 Python files (2 are the to-be-deleted duplicate).
- **Commit count:** 0 — **no git repo initialized yet** (`NOT FOUND`).

---

## 5. Results / Metrics

### [DONE] Real numbers today
- **Nothing is formally measured.** No latency, accuracy, or eval numbers captured.
- Only incidental counts exist: 693 LOC, 4 tools, `chatbot.db` ~630KB of stored checkpoints, RAG chunk
  size 1000 / overlap 200 / top-k 4. None of these are presentable "results."

### [PLANNED] Metrics claimable once the plan is complete — and what to instrument
- `[PLANNED]` **End-to-end response latency** (first→last token for a tool-using turn) — instrument by
  timing around the `chatbot.stream` loop in `app.py`. Unlocked by plan §7/§3 #7.
- `[PLANNED]` **# persisted conversation threads** — already derivable from `retrieve_all_threads()`;
  just surface the count.
- `[PLANNED]` **Chunks indexed per PDF / pages processed** — already returned by `ingest_pdf()`
  summary dict; capture a representative number during demo recording.
- **Start capturing now during the build:** latency per tool type, chunks/PDF, thread count. These are
  cheap to instrument and turn into the resume-bullet placeholders.

---

## 6. CV Material — STRICT

### Resume bullets from [DONE] work only

- **SDE:**
  > Built an agentic LLM chatbot in Python using LangGraph and Streamlit, implementing a conditional
  > tool-execution graph that autonomously routes a HuggingFace Qwen2.5-7B model across 4 tools (web
  > search, finance API, calculator, PDF retrieval) with token streaming and persistent multi-thread
  > memory via a SQLite checkpointer. *(All verifiable in code; add a latency number after plan §3 #7.)*

- **Data Scientist:**
  > Implemented per-document retrieval-augmented generation (RAG) over user-uploaded PDFs using
  > sentence-transformers (all-MiniLM-L6-v2) embeddings and a FAISS vector store with recursive
  > chunking (1000/200, top-k 4), exposed to the agent as a callable tool.
  > *(Honest caveat: this is RAG engineering, not modeling/analysis — a weak DS bullet. Strengthen
  > with citations/eval from plan §5 before leaning on it.)*

- **Data Analyst:**
  > **Not enough built yet for a DA bullet** — this project has no data analysis, dashboards, SQL
  > analytics, or insight generation. Needs a genuine analysis component that is **not in the current
  > plan**. Do not use this project for DA applications.

### Future bullets (DO NOT use yet) — and which task unlocks each
- After **deploy (plan §3 #8 / §4):**
  > Deployed the chatbot to a public URL on HuggingFace Spaces (free CPU tier) with secrets managed via
  > platform config — *unlocks the single biggest differentiator: a clickable live demo.*
- After **latency instrumentation (plan §3 #7):**
  > …answers tool-using and document queries in ~[X]s end-to-end across [N] persisted conversations.
- After **hardening + one clean app (plan §3 #1, #5):**
  > Refactored to a single production entry point with graceful degradation on external-API failures.
- After **smoke-test (plan §5 #3):**
  > Added an automated smoke-test covering each tool path. *(Adds "I test my code" signal.)*

---

## 7. For the Portfolio Website

- **Card title:** "Agentic Multi-Tool RAG Chatbot"
  **Summary:** An LLM chat assistant that decides on its own whether to search the web, fetch a stock
  price, do math, or read your uploaded PDF — and remembers every conversation. Built on LangGraph with
  a HuggingFace model, FAISS retrieval, and a Streamlit UI. *(Note: the first live version will show the
  core chat + tools + PDF flow; advanced extras like persisted RAG and citations are planned, not live.)*
- **Live demo:** `[PLANNED]` HuggingFace Spaces (Streamlit SDK), free CPU tier. **Fully deployable on a
  free tier — no GPU needed** because inference is remote via HuggingFace. (Caveat: free HF inference is
  rate-limited; record a GIF as a fallback.) Not yet deployed today.
- **Screenshot/visual to capture once built:** (1) a tool call in action (the "🔧 Using tool…" status
  box), (2) a RAG answer citing an uploaded PDF, (3) the sidebar thread switcher showing persisted chats.
- **README status:** **`NOT FOUND` — no README exists.** Needs to be written before linking (plan §3 #6).
  Do not link the repo publicly until README + `.gitignore` are in place.

---

## 8. Build Priority Signal

- **High-CV-value vs polish:** The biggest CV payoff items are small/medium effort — **deploy** (live
  URL), **README + demo media**, and **collapsing to one clean app + removing the hardcoded key**.
  Roughly: ~60% of remaining effort is high-CV-value (ship + document + clean), ~40% is polish
  (hardening, persisted RAG, citations, tests).
- **Honest take:** **Worth finishing for placements.** The hard engineering (agent graph, tools, RAG,
  persistence, streaming) already works; you're paying ~1–1.5 days to convert a hidden half-project into
  a deployed, clickable agentic-AI demo — a top-demand topic for SDE/AI-engineer roles. For **SDE** it's
  a strong portfolio piece; for **DS** it's a moderate one; for **DA** it does not apply — prioritize a
  real analysis project for DA applications instead.
- **Effort to first CV-usable state:** ~8–12 focused hours (1–1.5 days), matching `docs/completion-plan.md` §8.

---

## 9. Cleanup / Secrets Check

- 🚨 **URGENT — hardcoded API key in source:** Alpha Vantage key `C9PE94QUEW9VWGFM` appears in:
  - `Langraph_backend.py:139`
  - `Langraph_backend_app.py:78`
  **Action:** rotate the key immediately and move it to `os.getenv("ALPHAVANTAGE_API_KEY")`.
- ⚠️ **Secrets in `.env` (correct location, but unprotected):** `HUGGINGFACEHUB_API_TOKEN`,
  `LANGCHAIN_API_KEY`, plus LangChain tracing vars. `.env` is **not git-ignored** and there is no git
  repo yet — add a `.gitignore` (ignore `.env`, `myenv/`, `chatbot.db`, `__pycache__/`) **before**
  initializing git or pushing, or these will leak in the first commit.
- **To cut / hide (per plan §6):** delete the duplicate `app_1.py` + `Langraph_backend_app.py`; drop the
  LangSmith tracing vars unless used; the ~200MB `myenv/` venv and `chatbot.db` (real chat data) must
  never be committed.

---

*Sources: current code in repo (read directly) and `docs/completion-plan.md`. Anything not verifiable
in code is marked `[PLANNED]` or `NOT FOUND`.*
