# Structure Explanation — A Beginner's Guide to This Codebase

> This document explains **how the app works and why it's organized this way** — one level deeper
> than `docs/structure-plan.md` (which just maps old code → new files). Read this if you want to
> understand the *concepts*, not just the file layout.

---

## 1. The Big Picture — what happens when you use the app

Here's the full journey of a single chat message, start to finish:

```
 You type a message in the browser
            │
            ▼
 src/client/app.py (Streamlit UI)
   - reads your text from st.chat_input()
   - wraps it as a HumanMessage
   - calls chatbot.stream({...}, config={"thread_id": ...})
            │
            ▼
 src/backend/graph.py — the compiled `chatbot` graph
            │
            ▼
     ┌─────────────┐
     │  chat_node   │  ← the LLM looks at the conversation
     └─────────────┘
            │
   Does the LLM need a tool (web search / stock price / calculator / PDF)?
            │
     ┌──────┴───────┐
    NO              YES
     │               │
     ▼               ▼
  Answer‑        ┌─────────────┐
  streamed       │    tools    │  ← runs the requested tool function
  back to UI     └─────────────┘
                        │
                 result goes BACK into chat_node
                 (loop continues until the LLM has
                  enough info to give a final answer)
            │
            ▼
 Every step of this is saved to chatbot.db (via the checkpointer)
 so if you reload the page or restart the app, the conversation
 for that thread_id is still there.
```

**The one idea that makes this all work: `thread_id`.** Every conversation ("thread") has a unique
ID (a UUID). It's used for two independent things:
1. **Memory** — the checkpointer saves/loads conversation history keyed by `thread_id`.
2. **RAG scoping** — an uploaded PDF is only searchable within the thread that uploaded it, also
   keyed by `thread_id`.

---

## 2. Core concepts, explained simply

### 2.1 What is "the agent" / LangGraph?
Most simple chatbots do: *user asks → LLM answers*. That's it — one call, done.

This project instead uses **LangGraph**, which turns the conversation into a **graph** — a flowchart
the conversation moves through:
- **Nodes** = steps that do something (e.g. "ask the LLM", "run a tool").
- **Edges** = arrows saying what happens next.
- **Conditional edges** = a fork in the road — "if the LLM asked for a tool, go here; otherwise go
  there."

This project's graph (`src/backend/graph.py`) has exactly two nodes:
- `chat_node` — sends the conversation to the LLM.
- `tools` — actually executes whichever tool the LLM asked for.

And it loops: `chat_node → (maybe) tools → chat_node → (maybe) tools → ...` until the LLM produces a
plain answer with no tool request. This is what makes it an **agent** rather than a plain chatbot —
it can take multiple steps and use tools to gather information before answering.

### 2.2 What is a "tool"?
A tool is just a **regular Python function** with a `@tool` decorator on it and a docstring. The
docstring is not a comment for humans — **the LLM reads it** to decide when to call the function and
what arguments to pass. For example, `calculator`'s docstring says it does "add, sub, mul, div" — the
LLM uses that exact text to decide whether a user's question needs the calculator.

`llm.bind_tools(tools)` (in `graph.py`) tells the LLM "here are 4 functions you're allowed to call."
The LLM never actually executes them — it just replies with *"please call `get_stock_price` with
symbol='AAPL'"*, and LangGraph's `ToolNode` is what actually runs the Python function and feeds the
result back in.

### 2.3 What is RAG (Retrieval-Augmented Generation)?
LLMs can't read your uploaded PDF directly — it's too big to paste into a prompt. RAG solves this in
4 steps (all in `src/backend/rag/ingest.py`):

1. **Load** — `PyPDFLoader` reads the PDF into plain text, one chunk per page.
2. **Split** — `RecursiveCharacterTextSplitter` cuts that text into ~1000-character pieces (with
   200 characters of overlap between pieces, so a sentence split across a chunk boundary doesn't
   lose meaning).
3. **Embed** — each chunk is converted into a list of numbers (a "vector") by an embedding model
   (`all-MiniLM-L6-v2`) that represents its *meaning*. Similar meanings → similar-looking vectors.
4. **Store + retrieve** — all the vectors go into a **FAISS** vector store. When you ask a question,
   your question is *also* turned into a vector, and FAISS finds the `k=4` chunks whose vectors are
   closest to it (i.e. the most relevant text). Those chunks are handed to the LLM as context.

This whole pipeline is exposed to the agent as just another tool: `rag_tool` (in
`src/backend/tools/rag.py`). The LLM calls it exactly like it calls the calculator — it doesn't know
or care that there's a whole embedding pipeline behind it.

### 2.4 What is the checkpointer / persistent memory?
`SqliteSaver` (in `src/backend/memory.py`) is LangGraph's built-in way of saving the *entire state* of
a conversation (every message, every tool call) to a database after every single step, keyed by
`thread_id`. This is why closing and reopening the app doesn't lose your chat history — LangGraph
reloads the saved state for that `thread_id` the next time you use it.

`retrieve_all_threads()` just asks the checkpointer "what `thread_id`s do you know about?" — that's
how the sidebar shows a list of past conversations.

### 2.5 What is streaming?
Instead of waiting for the LLM to finish its whole answer and showing it all at once, `chatbot.stream(
..., stream_mode="messages")` yields pieces of the response **as they're generated**. The UI
(`src/client/app.py`) reads these pieces in a loop and displays each one immediately via
`st.write_stream(...)` — that's the token-by-token typing effect you see.

### 2.6 What is Streamlit `session_state`?
Streamlit re-runs your entire script from top to bottom every time you interact with the page (click
a button, type a message). Normally that would reset all your variables. `st.session_state` is a
dictionary that **survives across reruns** — it's how the app remembers your current `thread_id`,
your chat history so far, and which PDFs you've uploaded, even though the whole script just re-ran.

---

## 3. File-by-file walkthrough

### `src/backend/config.py`
The very first thing that runs. Loads your `.env` file (API keys, tokens) into the environment so
every other file can read them with `os.getenv(...)`.

### `src/backend/llm.py`
Creates two objects every other backend file depends on:
- `llm` — the actual chat model (HuggingFace's `Qwen2.5-7B-Instruct`, wrapped so LangChain can talk
  to it).
- `embeddings` — the model that turns PDF text into vectors for RAG (section 2.3 above).

It imports `config` first so `.env` is guaranteed to be loaded before anything tries to read a key.

### `src/backend/state.py`
Defines `ChatState` — the "shape" of data that flows through the graph. Right now it's just one
field: `messages`, a running list of the conversation. `Annotated[..., add_messages]` tells LangGraph
"when a node returns new messages, *append* them to this list, don't replace it."

### `src/backend/rag/ingest.py`
The RAG pipeline described in section 2.3, plus a small in-memory dictionary
(`_THREAD_RETRIEVERS`) that remembers which retriever belongs to which `thread_id`. This dictionary
is the "PLANNED → Qdrant" item in `implementation_plan.md` — it currently lives in RAM, so it's lost
if the app restarts (unlike the chat history, which is safely in `chatbot.db`).

### `src/backend/tools/` (one file per tool)
- `search.py` — wraps DuckDuckGo search as a tool.
- `calculator.py` — arithmetic (`add`/`sub`/`mul`/`div`).
- `stock.py` — calls the Alpha Vantage API for a stock quote.
- `rag.py` — calls into `rag/ingest.py` to answer questions about the uploaded PDF.
- `__init__.py` — collects all 4 into one list, `tools = [...]`, so `graph.py` only needs one import
  line instead of four.

### `src/backend/memory.py`
Opens the SQLite database (`chatbot.db`) and wraps it in LangGraph's `SqliteSaver` — this *is* the
persistent memory from section 2.4. Also defines `retrieve_all_threads()` for the sidebar.

### `src/backend/graph.py`
The file that **wires everything above together**:
1. Binds the 4 tools to the LLM (`llm.bind_tools(tools)`).
2. Defines `chat_node` — builds a system prompt (telling the LLM about the tools and the current
   `thread_id`), sends the conversation to the LLM, returns its reply.
3. Builds the `StateGraph`: two nodes (`chat_node`, `tools`), wired with the conditional loop from
   section 2.1.
4. Compiles it into `chatbot` — the single object the UI actually imports and calls.

### `src/client/app.py`
The only file that knows about Streamlit. It has **zero AI logic** — it just:
- Manages `session_state` (current thread, chat history, uploaded docs) — section 2.6.
- Renders the sidebar (thread switcher, PDF uploader, "New Chat" button).
- Sends your typed message into `chatbot.stream(...)` and streams the reply back — section 2.5.

---

## 4. "Where do I look if I want to change X?"

| I want to... | Look in |
|---|---|
| Change the LLM model or its settings (temperature, max tokens) | `src/backend/llm.py` |
| Add a new tool | new file in `src/backend/tools/`, then add it to `tools/__init__.py` |
| Change how PDFs are chunked (chunk size, overlap, top-k) | `src/backend/rag/ingest.py` |
| Change the system prompt / agent instructions | `chat_node` in `src/backend/graph.py` |
| Change how/where conversations are saved | `src/backend/memory.py` |
| Change anything about the UI (buttons, layout, sidebar) | `src/client/app.py` |
| Rotate the Alpha Vantage key / read it from `.env` instead of hardcoding | `src/backend/tools/stock.py` (Phase A in `implementation_plan.md`) |

---

## 5. What's still "old code, not yet upgraded" (see `implementation_plan.md`)

- `_THREAD_RETRIEVERS` in `rag/ingest.py` is an in-memory dict — will move to **Qdrant** (Phase A).
- `chatbot.db` is local SQLite — will move to **Neon Postgres** (Phase A), because a serverless
  deploy target (Modal, Phase B) can't rely on a local file surviving between requests.
- The Alpha Vantage key in `tools/stock.py` is still hardcoded — needs rotating + moving to
  `os.getenv(...)` (Phase A).
- There's no tracing/observability yet — **LangSmith** wiring is Phase A.

None of these are bugs in the current code — they're the next planned steps, and this document
exists so you understand *why* each piece is built the way it is before we touch it.
