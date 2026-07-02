# Phase B Step 2 Explanation — The Modal backend (`modal_app.py`)

> Companion to `docs/explanation/structure_explanation.md` and `phase_b_step1_explanation.md`. This
> covers building `modal_app.py`: wrapping the existing LangGraph agent as a set of **web endpoints on
> Modal**, secured with a bearer token. After this step, the whole backend runs in the cloud and is
> reachable over HTTPS — the client rewrite (Step 3) comes next.

---

## 1. The Big Picture — why this file exists

Until now the agent only ran *inside* the Streamlit process on your laptop. `modal_app.py` turns it into
a standalone **cloud service**: the same `chatbot`, `ingest_pdf`, and `retrieve_all_threads` from `src/`,
but reachable by any client over HTTP. This is the "split" that Phase B is about — intelligence on
Modal, UI somewhere thin. Crucially, **no `src/` code changed**: we only added a wrapper. That's the
payoff of Phase A's managed data layer — a fresh cloud container just reconnects to Neon/Qdrant.

---

## 2. Core concepts, explained simply

### 2.1 Web endpoint / route
A URL the server answers, tied to a function. `@web.get("/threads")` means "when someone GETs
`/threads`, run this function." FastAPI (bundled into the Modal image) provides this.

### 2.2 `@modal.asgi_app()`
Tells Modal "this function returns a web application; serve it at a URL." Everything inside it runs
**once per container** at boot — which is exactly where we do the expensive backend import (connect to
Neon/Qdrant, load the embedder) so it happens once and is reused across requests, not per request.

### 2.3 `modal.Secret`
The cloud replacement for `.env`. `.env` is git-ignored and never ships to Modal. Instead we stored the
keys in a Modal Secret named `chatbot-secrets`; Modal injects them into the container as environment
variables. Because `src/` already reads keys via `os.getenv(...)`, it works unchanged — `load_dotenv()`
simply finds no file and the Modal env vars are already present.

### 2.4 Bearer token (the cost firewall)
A random string (`CHATBOT_API_TOKEN`, stored in the same Secret). Every protected endpoint depends on
`require_token`, which checks the request's `Authorization: Bearer <token>` header and returns `401`
otherwise — *before* any expensive work runs. This stops strangers from spending your Modal credits even
though the URL is public. `/health` is intentionally left open as a liveness check.

### 2.5 `multipart/form-data` (file upload)
HTTP can't send a Python file object — only bytes. To upload a PDF *plus* a `thread_id`, the client uses
`multipart/form-data`: labeled parts, one holding the raw bytes (`UploadFile`/`File`), one holding the
string (`Form`). `ingest()` reads the bytes and hands them to the existing `ingest_pdf()`.

### 2.6 Streaming with `StreamingResponse`
A normal endpoint computes the whole answer then returns it — slow for an LLM. `StreamingResponse` takes
a **generator** that `yield`s pieces, and FastAPI flushes each piece to the client immediately. Our
`token_stream()` is the HTTP twin of the `ai_only_stream()` generator already in `app.py`: it runs
`chatbot.stream(..., stream_mode="messages")` and yields each `AIMessage` chunk's text as it's produced.

### 2.7 Serializing messages for HTTP
LangChain message objects can't travel over HTTP; only JSON can. `/history` converts them to plain
`{role, content}` dicts (keeping Human + non-empty AI turns, dropping tool stubs). This is also what lets
the client stay dependency-free — it never needs langchain to render a conversation.

---

## 3. File-by-file: what changed and why

### `modal_app.py` (new)
- **`app`, `image`, `secrets`** (module level) — the Modal app namespace; the container spec (Debian +
  Python 3.11 + pinned `requirements.txt` + the `src/` package copied in via `.add_local_python_source`);
  and the Secret reference. Kept lightweight because module-level code also runs *locally* at deploy.
- **`fastapi_app()`** (decorated `@app.function` + `@modal.asgi_app()`) — builds the FastAPI app once per
  container. All heavy backend imports live **inside** it (cloud-only). Contains `require_token` and the
  five routes: `/health`, `/threads`, `/history`, `/ingest`, `/chat`.

### `requirements.txt`
Added `modal==1.5.1`, `fastapi[standard]==0.139.0`, and — critically — `ddgs==9.13.1` (see Issue 1). All
pinned to the exact installed versions.

### Application code (`src/`)
**Unchanged.** The whole point: the agent was wrapped, not rewritten.

---

## 4. Issues hit while building this step

### Issue 1 — `ModuleNotFoundError: No module named 'ddgs'` (works locally, fails in cloud)
- **What happened:** the backend import crashed in the container at `search.py` creating
  `DuckDuckGoSearchRun`, which internally does `from ddgs import DDGS`.
- **Why:** the DuckDuckGo library was renamed `duckduckgo-search` → `ddgs`. `ddgs` was installed on the
  laptop (so local runs worked) but was **missing from `requirements.txt`**, and the Modal image is built
  *only* from that file — a clean room that knows nothing about incidental local installs.
- **Fix:** add `ddgs==9.13.1` to `requirements.txt`.
- **Lesson:** `requirements.txt` is the *only* truth about your environment once you leave your laptop.
  "Works on my machine" but not in a fresh env = an unpinned dependency. Deploying is valuable precisely
  because it forces the dependency list to be honest. (Same family as the earlier `torchvision` bug.)

### Issue 2 — top-level backend import broke the deploy
- **What happened:** the `from src.backend.rag.ingest import ingest_pdf` line was pasted at **module top
  level** instead of inside `fastapi_app`.
- **Why:** module-level code in a Modal file runs **on your laptop** during `modal serve`/`deploy` (to
  build the app graph). A top-level backend import forces a heavy local import (Qdrant/Neon/embedder) at
  the wrong place and can fail the deploy.
- **Fix:** move it inside `fastapi_app` with the other backend imports.
- **Lesson:** in a Modal file, cloud-only work (backend imports) goes **inside** the function; keep
  module scope minimal.

### Issue 3 — ⭐ `modal serve` does NOT live-reload on Windows (the big one)
- **What happened:** repeated `{"detail":"Not Found"}` for newly added routes even though the file on
  disk was correct. The serve log revealed: `Live-reload skipped. This feature is currently unsupported
  on Windows`.
- **Why:** on Windows, `modal serve` watches files but **cannot hot-reload** them. When a reload would be
  needed it keeps serving the code it started with, so new routes never appear. This masqueraded as many
  different bugs.
- **Fix:** after **every** edit to `modal_app.py`, **stop serve (Ctrl+C) and re-run it**. Confirm the new
  route is live by fetching `/openapi.json` (FastAPI's auto-generated list of all routes) before testing.
- **Lesson:** don't trust hot-reload on Windows — restart, then verify the route exists via
  `/openapi.json`. That check turns confusing 404s into a 2-second confirmation.

### Issue 4 — Windows console encoding crash in background (`charmap` codec)
- **What happened:** running `modal serve` with output redirected failed instantly with
  `'charmap' codec can't encode character '✓'`.
- **Why:** Modal prints a `✓`; Windows' default console encoding (cp1252) can't encode it when output
  isn't a real terminal.
- **Fix:** set `PYTHONIOENCODING=utf-8` (and `PYTHONUTF8=1`) before launching.
- **Lesson:** force UTF-8 when a tool's fancy output must go somewhere other than an interactive console.

### Issue 5 — JSON body mangled by PowerShell quoting
- **What happened:** `curl.exe -d "{\"message\":...}"` → `JSON decode error`.
- **Why:** PowerShell re-interprets the escaped quotes, so curl received malformed JSON.
- **Fix:** build the body as a hashtable and `ConvertTo-Json`, then send with `Invoke-RestMethod`
  (or write the JSON to a file and use `curl -d @file.json`).
- **Lesson:** on Windows, prefer `Invoke-RestMethod` + `ConvertTo-Json` over hand-escaping JSON in curl.

---

## 5. Where things stand after this step

- `modal_app.py` exposes the full agent as five endpoints, all verified against the live dev URL:
  `/health`, `/threads`, `/history`, `/ingest` (PDF → Qdrant), and `/chat` (streamed answer). A single
  `/chat` call proved the whole chain end-to-end: token auth → LangGraph → `rag_tool` (injected
  `thread_id`) → Qdrant → HuggingFace → streamed tokens.
- Secrets are delivered via `modal.Secret`; the bearer token guards every non-health endpoint.
- `src/` is untouched — the agent was wrapped, not rewritten.

**Next: Phase B Step 3** — rewrite `src/client/app.py` as a *thin* Streamlit client that calls these
endpoints over HTTP (no langgraph/langchain imports), add `requirements-client.txt` (streamlit +
requests only), then `modal deploy` the backend and deploy the client.
