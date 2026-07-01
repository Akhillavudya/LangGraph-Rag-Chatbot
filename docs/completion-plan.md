# Completion Plan — LangGraph Multi-Tool RAG Chatbot

> **Honest status:** ~65–70% of the *code* is built and runs (the SQLite DB proves it has been
> used). It is **0% deployed and 0% documented**, has a hardcoded API key, and ships two
> duplicate copies of the app. The remaining work is mostly "ship + clean up," not new features.
>
> **Primary target role: SDE** (backend / GenAI-application engineering). Secondary pitch:
> "AI/LLM application engineer." **Not** a Data Analyst project; only a weak Data Scientist fit.

---

## 1. Current State (verified from code)

### What works right now
- **Agentic LangGraph loop** (`Langraph_backend.py`): `chat_node ↔ tools` with `tools_condition`
  conditional routing and a real ToolNode execution cycle. Compiles and runs.
- **LLM**: HuggingFace serverless inference (`Qwen/Qwen2.5-7B-Instruct`) via `ChatHuggingFace`.
  Remote inference — **no local GPU required**, so this *is* deployable.
- **4 tools**: DuckDuckGo web search, Alpha Vantage stock price, calculator, and a per-thread
  `rag_tool` over an uploaded PDF.
- **Per-conversation PDF RAG**: `ingest_pdf()` loads a PDF, splits it (1000/200), embeds with
  `all-MiniLM-L6-v2`, stores in FAISS, and exposes a retriever keyed by `thread_id`.
- **Persistent memory**: `SqliteSaver` checkpointer (`chatbot.db`) — conversations survive restarts
  and are listed in the sidebar via `retrieve_all_threads()`.
- **Streaming UI** (`app_2.py`): token-by-token streaming with a live "🔧 Using `tool`…" status box,
  new-chat button, thread switcher, PDF uploader.

### What's stubbed / broken / incomplete
- **Hardcoded Alpha Vantage API key** in source (`Langraph_backend.py:139`, `Langraph_backend_app.py:78`).
  Security problem and a recruiter red flag. Must move to env var.
- **`st.set_page_config` called twice** in `app_2.py` (lines 57 and 97), and *after* other `st.`
  calls — Streamlit requires it to be the first command. Will throw/warn.
- **RAG retrievers live in an in-memory dict** (`_THREAD_RETRIEVERS`) — lost on restart and not
  shared across server workers. Fine for a single-session demo; must be documented as a known limit.
- **`rag_tool` depends on the LLM passing `thread_id`** correctly via a system-prompt instruction —
  fragile; a 7B model may forget it.
- **No README, no `.gitignore`, no git repo at all.**

### What's completely missing
- Any deployment (no public URL, no `Procfile`/`runtime`/Spaces config).
- Documentation, screenshots/GIF, sample PDF to demo with.
- Tests or even a smoke-test script.
- `.env.example` for safe key handling.

---

## 2. Definition of "CV-Ready Done" for THIS project

This project is **done** (everything past this is optional) when:

1. **One** clean app (the RAG version) runs end-to-end locally on a fresh clone via documented steps.
2. **Deployed at a public URL** that a recruiter can click — chat works, a tool fires, and a PDF
   upload + question works in the live demo.
3. **No secrets in source.** All keys via env / platform secrets; `.env` git-ignored; `.env.example` present.
4. **README** with: one-paragraph what/why, architecture diagram or bullet of the agent graph,
   setup steps, the live link, and **at least one screenshot + one GIF** of a tool call and a RAG answer.
5. **Repo is clean**: git-initialized, `myenv/`, `chatbot.db`, `__pycache__/`, `.env` ignored; the
   duplicate app removed.

---

## 3. MUST-DO (to reach CV-ready)

Ordered. Only what's genuinely required for the bar above.

| # | Task | Files | Effort | Why it matters |
|---|------|-------|--------|----------------|
| 1 | **Pick one app, delete the duplicate.** Keep `app_2.py` + `Langraph_backend.py` (the RAG version). Delete `app_1.py` + `Langraph_backend_app.py`. Rename keepers to `app.py` + `backend.py` and fix the import. | all 4 .py | S | Two near-identical apps screams "unfinished" to a reviewer. One clean entry point. |
| 2 | **Remove the hardcoded Alpha Vantage key.** Read it from `os.getenv("ALPHAVANTAGE_API_KEY")`; return a clear error if unset. | `backend.py` | S | Hardcoded keys are an instant credibility hit in a code review. **Also rotate that key** — it's already exposed. |
| 3 | **Add `.gitignore` + `.env.example` + `git init`.** Ignore `myenv/`, `chatbot.db`, `__pycache__/`, `.env`. Commit a clean tree. | new files | S | A 200MB venv or a leaked `.env` in the repo is disqualifying. Recruiters open the GitHub repo first. |
| 4 | **Fix the `set_page_config` bug.** Single call, first Streamlit command in the file. | `app.py` | S | A visible crash/warning on launch ruins a live demo. |
| 5 | **Harden the tool loop for the demo.** Wrap `get_stock_price`/search in try/except so an API hiccup returns a friendly message instead of a stack trace; pass `thread_id` into `rag_tool` reliably (inject via the graph/config rather than trusting the LLM to echo it). | `backend.py` | M | Live demos fail on flaky external APIs. Graceful degradation = "this person thinks about reliability." |
| 6 | **Write the README** (what/why, architecture bullets of the LangGraph flow, tools list, setup, live link, screenshot + GIF). | `README.md` | M | This is the artifact the recruiter actually reads. Without it the project is invisible. |
| 7 | **Capture demo media + a sample PDF.** One screenshot, one short GIF (tool call + RAG answer), and commit a small sample PDF so the demo is reproducible. | `assets/` | S | Proof it works without them running anything. Also gives you the metric for the resume bullet. |
| 8 | **Deploy (see section 4) and verify the live URL end-to-end.** | config | M | "Deployed" is the single biggest differentiator vs. every other half-built repo. |

**Realistic must-do total: see section 8.**

---

## 4. Deployment Plan (required)

### Recommended host: **Hugging Face Spaces (Streamlit SDK)** — free
Why HF Spaces over Streamlit Community Cloud:
- The **LLM and embeddings are already HuggingFace-hosted**, so your inference token lives natively
  there and latency to the inference endpoint is good.
- Free CPU tier is enough — inference is **remote**, embeddings (MiniLM ~90MB) + FAISS run fine on CPU.
- Built-in **Secrets** UI for the token. Dead-simple Streamlit support.
- (Streamlit Community Cloud is an equally valid free fallback if you prefer GitHub-based deploys.)

### Exact steps (HF Spaces)
1. Create a Space → SDK: **Streamlit**, hardware: **CPU basic (free)**.
2. Add files: `app.py`, `backend.py`, `requirements.txt`, `README.md`, `assets/`.
   - Pin versions in `requirements.txt` before deploying (avoid surprise breakage) and add
     `huggingface_hub` if not pulled transitively.
   - Rename entry file to `app.py` (Spaces expects it) — already covered by must-do #1.
3. In **Space → Settings → Secrets**, add:
   - `HUGGINGFACEHUB_API_TOKEN`
   - `ALPHAVANTAGE_API_KEY`
   - (LangSmith keys optional — only if you want tracing; otherwise drop them.)
4. Push. Spaces builds and serves a public URL.
5. **Verify live:** ask a normal question, trigger the stock tool ("price of AAPL"), upload the sample
   PDF and ask a question about it. Confirm the status box and streaming work.

### Secrets handling (do NOT hardcode)
- Local: `.env` (git-ignored) loaded by `python-dotenv`; ship `.env.example` with empty placeholders.
- Deployed: platform **Secrets** (HF Spaces / Streamlit secrets) → read via `os.getenv`.
- **Rotate the Alpha Vantage key** that's currently in source before going public.

### Known-limitation note for the README (be upfront)
- **RAG retrievers are in-memory and session-scoped** (`_THREAD_RETRIEVERS`). On the free tier the
  filesystem is ephemeral and there's effectively one worker, so this works for a demo but a PDF
  uploaded in one session isn't persisted. State it honestly; it's a reasonable scope choice.
- HF free inference is **rate-limited** — fine for a demo, not for traffic.

### Cost
- **$0** on free tiers (HF Spaces CPU basic, HF serverless inference free tier, Alpha Vantage free
  key, DuckDuckGo free). Nothing here requires paid hosting or a GPU. Flag: heavy demo traffic could
  hit HF rate limits — acceptable for a portfolio piece.

> This project **can** be deployed live (no GPU needed). No video-only fallback required — but still
> record the GIF as backup in case the free inference endpoint is briefly rate-limited during a demo.

---

## 5. NICE-TO-HAVE (only after must-do + deployment ship)

Ranked by impact-per-effort. **Do not start these until the live URL works.**

1. **Persist RAG across restarts** — save/load the FAISS index to disk (or a small vector store)
   keyed by thread, so uploaded PDFs survive. *Adds:* real durability. *Impresses:* SDE. *Effort:* M.
2. **Source citations in RAG answers** — surface the page/source for each retrieved chunk in the UI.
   *Adds:* trust + a polished feel. *Impresses:* SDE / DS. *Effort:* S–M.
3. **Basic eval / smoke-test script** — a tiny script that runs 3–4 canned prompts (one per tool) and
   asserts non-empty/typed output. *Adds:* engineering maturity. *Impresses:* SDE. *Effort:* S.
4. **Pluggable model selector** — dropdown to swap HF models, or fall back to a smaller model on rate
   limit. *Adds:* robustness story. *Impresses:* SDE / ML-eng. *Effort:* M.

---

## 6. What to CUT or DESCOPE

- **CUT the entire `app_1.py` + `Langraph_backend_app.py` pair.** It's a strictly inferior duplicate
  of the RAG version. Delete it; don't maintain two.
- **CUT LangSmith/LangChain tracing env vars** unless you actively use tracing — they add 4 secrets and
  config surface for zero demo value. Drop them or make them optional.
- **DESCOPE the stock tool if it's flaky** — the free Alpha Vantage key rate-limits hard. If it
  misbehaves in the live demo, keep search + calculator + RAG and hide the stock tool. Three reliable
  tools beat four where one breaks on stage.
- **Do NOT** build auth, user accounts, or a database beyond the existing SQLite checkpointer — out of
  scope for a portfolio demo and a time sink.

---

## 7. Resume Bullet Preview (primary role: SDE)

> **Built and deployed an agentic LLM chatbot (LangGraph + Streamlit, HuggingFace Qwen2.5-7B) that
> autonomously routes between web search, a finance API, a calculator, and per-conversation PDF
> retrieval (FAISS + MiniLM embeddings), with persistent multi-thread memory via a SQLite checkpointer;
> live demo answers document questions in ~[X]s and retains [N] persisted conversations.**

**Metrics to instrument while building:** average end-to-end response latency `[X]s` (time first→last
token for a tool-using turn), and `[N]` = number of persisted threads / or chunks indexed per PDF.
Capture these during the demo-recording step (must-do #7).

---

## 8. Total Effort Estimate

| Bucket | Effort |
|--------|--------|
| Must-do #1–4 (cleanup, key, gitignore, bug) | ~2–3 h |
| Must-do #5 (harden tool loop) | ~2–3 h |
| Must-do #6–7 (README + demo media) | ~2–3 h |
| Must-do #8 (deploy + verify) | ~2–3 h |
| **Total to CV-ready** | **~8–12 focused hours (1–1.5 days)** |

**Verdict: worth finishing — clearly.** The expensive, hard part (the agent graph, tooling, RAG,
persistence, streaming) is already built and working. You're paying ~1–1.5 days of cleanup + ship to
convert a hidden half-project into a clickable, deployed, agentic-AI portfolio piece — one of the most
in-demand topics for SDE/AI-engineering roles right now. The ROI here is high; this is exactly the kind
of project to finish rather than drop.
