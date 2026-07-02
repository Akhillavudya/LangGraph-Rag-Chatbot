# Phase B Step 3 Explanation — The thin HTTP client (`src/client/app.py`)

> Companion to `docs/explanation/structure_explanation.md`, `phase_b_step1_explanation.md`, and
> `phase_b_step2_explanation.md`. Step 2 put the whole agent on Modal as web endpoints. This step
> rewrites the Streamlit app so it **no longer contains any AI code** — it just talks to those
> endpoints over HTTP. After this, the "split" Phase B is about is complete: heavy brain on Modal,
> feather-light UI anywhere.

---

## 1. The Big Picture — why this step exists

Before this step, `app.py` imported the agent directly (`from src.backend.graph import chatbot`) and
ran it *inside* the Streamlit process. That means the UI machine also had to load LangGraph, LangChain,
the embedding model, and connect to Neon/Qdrant — heavy, slow to start, and impossible to host on a
lightweight platform.

A **thin client** flips that: the UI knows *nothing* about how answers are made. It only knows four
URLs on the backend and how to send/receive HTTP. All the intelligence lives on Modal (Step 2). The
benefit: the client now installs in seconds (`streamlit` + `requests` only), starts instantly, and can
be deployed to a free UI host like Streamlit Community Cloud.

This is the standard **client/server** shape of real software: a small front end, a separate back end,
a well-defined contract between them.

---

## 2. Core concepts, explained simply

### 2.1 Thin client vs. fat client
A *fat* client does the work itself. A *thin* client delegates the work to a server and just shows the
result. Our old app was fat (ran the agent); the new one is thin (asks Modal to run the agent).

### 2.2 HTTP request/response
Talking to the backend = sending an HTTP request and reading the response. We use the `requests`
library:
- `requests.get(url, ...)` — "give me data" (used for `/threads`, `/history`).
- `requests.post(url, ...)` — "here's data, do something" (used for `/ingest`, `/chat`).
- `resp.raise_for_status()` — turn an error HTTP status (401, 500…) into a Python exception so failures
  are loud, not silent.

### 2.3 The bearer token, from the client side
Step 2's backend rejects any request without the right token. So every call sends the header
`Authorization: Bearer <token>` (our `AUTH` dict). Same token string that's stored in the Modal Secret —
the two sides must match, or you get `401 Unauthorized`.

### 2.4 `st.secrets`
The client needs the backend URL and the token, but those must **not** be hard-coded (the token is a
secret; the URL changes between dev and prod). `st.secrets` reads them from `.streamlit/secrets.toml`
locally (git-ignored) or from the "Secrets" box on Streamlit Community Cloud when deployed. Same code,
different source — that's the point.

### 2.5 Multipart upload (`/ingest`)
HTTP can't send a Python file object, only bytes. `requests.post(files={"file": (name, bytes, type)},
data={"thread_id": ...})` packs the PDF bytes and the thread id into a `multipart/form-data` body —
exactly the shape the backend's `File(...)` + `Form(...)` expect.

### 2.6 Streaming responses (`/chat`)
For a live "typing" feel, we don't wait for the whole answer:
- `requests.post(..., stream=True)` — don't download the whole body up front.
- `resp.iter_content(chunk_size=None, decode_unicode=True)` — yield text chunks **as they arrive**.
- Because `stream_chat` is a generator that `yield`s those chunks, `st.write_stream(...)` renders them
  live and returns the final joined string to save into history.

### 2.7 Dev URL vs. deployed URL
`modal serve` gives a temporary URL ending in `-dev` that only lives while that terminal is open.
`modal deploy` gives a **permanent** URL (same, minus `-dev`) that stays up on its own. The client's
`MODAL_ENDPOINT_URL` points at the deployed one so it works without us babysitting a terminal.

---

## 3. File-by-file — what changed and why

### `src/client/app.py` — rewritten
- **Removed** every `from src.backend...`, `langgraph`, and `langchain` import. The UI no longer knows
  the agent exists.
- **Added** four small HTTP helpers, each replacing an old in-process call:
  | Old (in-process) | New (HTTP) |
  |---|---|
  | `chatbot.stream(...)` | `stream_chat()` → `POST /chat` |
  | `ingest_pdf(bytes, ...)` | `ingest_pdf()` → `POST /ingest` |
  | `retrieve_all_threads()` | `get_threads()` → `GET /threads` |
  | `chatbot.get_state(...)` | `get_history()` → `GET /history` |
- **Kept** all the UI from the restyle: dark theme, "Sage" name, avatars, centered column, chat-input
  PDF attach, and the 📎 doc caption.
- **CSS note:** on the narrow `centered` layout Streamlit kept collapsing the sidebar off-screen, so the
  CSS block force-pins it open (`transform: none; margin-left: 0; fixed width`) — see the "Issues" section.

### `src/client/requirements.txt` — new
Only `streamlit` + `requests`. This is what the UI host installs — no torch, no langchain, no qdrant.
Proof that the client is truly thin. (The backend still uses the full root `requirements.txt`.)
It lives **next to `app.py`** on purpose: Streamlit Community Cloud searches the entrypoint file's
directory *before* the repo root and only recognizes the exact name `requirements.txt`, so placing it
here makes the thin file win and the heavy root one get ignored. (An earlier attempt named it
`requirements-client.txt` at the root — Streamlit Cloud would have skipped it and installed the heavy
backend deps instead.)

### `.streamlit/secrets.toml.example` — new (committed)
Placeholder names for `MODAL_ENDPOINT_URL` and `CHATBOT_API_TOKEN`, so anyone cloning the repo knows
which secrets to provide. The real `.streamlit/secrets.toml` is git-ignored.

### `.gitignore` — updated
Added `.streamlit/secrets.toml` so the real token can never be committed by accident.

---

## 4. Issues hit while building

### 4.1 `ImportError: cannot import name 'delete_thread'`
- **What happened:** the app imported a `delete_thread` that didn't exist yet in `src/backend/memory.py`.
- **Why:** Python found the module fine, but not that *name* inside it — a mirror of the earlier
  `No module named 'src'` bug (that one was the module missing; this one the attribute).
- **Fix:** added the function. **Lesson:** "cannot import name X" ≠ "no module" — the file loaded, the
  symbol is what's missing.

### 4.2 Raw JSON leaked into the chat on revisiting a session
- **What happened:** clicking an old thread dumped raw tool JSON and blank bubbles into the transcript.
- **Why:** the checkpointer stores the agent's *full* trail (human msg, an empty tool-call AI msg, the
  tool's raw JSON, then the real answer). The loader printed all of them.
- **Fix:** filter by message type — skip `ToolMessage` and empty-content messages. The backend's
  `/history` now returns only user + non-empty assistant turns, so the client gets clean data. **Lesson:**
  stored conversation state is richer than what a user should see; always filter for display.

### 4.3 Sidebar not visible after the rewrite
- **What happened:** the sidebar didn't render even after refreshing.
- **Why:** on a narrow `centered` layout Streamlit auto-collapses the sidebar (slides it off-screen with
  a CSS `transform`/negative margin); it wasn't deleted, just hidden.
- **Fix:** `initial_sidebar_state="expanded"` **plus** a CSS override that cancels the slide-away and pins
  a fixed width. **Lesson:** "invisible" in a web UI often means moved/collapsed, not absent — inspect the
  DOM before assuming the element is missing.

### 4.4 `'charmap' codec can't encode character '✓'` during `modal deploy`
- **What happened:** `modal deploy` crashed while printing a `✓` checkmark.
- **Why:** the Windows console's default code page can't encode that Unicode glyph — it failed on
  *output*, not on the deploy itself.
- **Fix:** run with `PYTHONIOENCODING=utf-8` (in bash: `PYTHONIOENCODING=utf-8 modal deploy ...`).
  **Lesson:** encoding errors on Windows terminals are display-layer problems; force UTF-8 output rather
  than assuming the command is broken.

### 4.5 `$env:...` failed under the `!` prefix
- **What happened:** `$env:PYTHONIOENCODING=...` gave `command not found`.
- **Why:** the `!` inline-command prefix runs in **bash**, not PowerShell — so PowerShell's `$env:`
  syntax is meaningless there. In bash you prefix the var inline: `VAR=value command`.
- **Lesson:** know which shell you're actually in; the same env-var assignment has different syntax in
  bash vs. PowerShell.

---

## 5. Where things stand + what's next

The backend is deployed to a permanent Modal URL, and the client is a genuinely thin Streamlit app that
reaches it over HTTP with a bearer token — verified end-to-end (chat, PDF ingest, thread list, history).
The remaining piece is hosting the client itself on **Streamlit Community Cloud** (point it at this repo,
main file `src/client/app.py`, deps `requirements-client.txt`, and paste the two secrets). After that,
Phase B is done and Phase C (the evaluation harness) begins.
