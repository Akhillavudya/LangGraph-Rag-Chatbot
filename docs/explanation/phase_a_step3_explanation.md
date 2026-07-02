# Phase A Step 3 Explanation — SQLite → Neon Postgres

> Companion to `docs/explanation/structure_explanation.md` (core concepts: agent, tools, RAG,
> checkpointer) and `docs/explanation/phase_a_step2_explanation.md` (FAISS → Qdrant, the previous
> step). This document covers Phase A Step 3 from `docs/implementation_plan.md`: replacing the local
> SQLite file (`chatbot.db`) that stored chat memory with a managed **Neon Postgres** database.

---

## 1. The Big Picture — why swap SQLite for Neon

Step 2 moved the **PDF vectors** out of RAM into Qdrant. This step does the exact same thing for the
other half of the app's persisted state: the **chat memory** — the running record of every message in
every thread. Today that lives in `chatbot.db`, a SQLite file sitting on your local disk.

That's fine while the app is one process on your laptop, but it fails for the same two reasons Step 2's
FAISS dict did:

1. **A local file doesn't travel.** It's tied to this one machine's disk.
2. **It's incompatible with where the project is going.** In Phase B the agent runs on **Modal**, where
   each request may execute in a **fresh, disposable container** with its own empty filesystem. A
   `chatbot.db` written by one container is invisible to the next. Chat history would silently reset
   between requests.

**Neon** is managed Postgres — a real database living on Neon's servers, reachable over the network
from any process, container, or restart that has the connection URL. After this step, both halves of
the app's memory (PDF vectors *and* chat history) are external managed services. Nothing important
lives in local RAM or local files anymore — which is the precondition for going serverless.

---

## 2. Core concepts, explained simply

### 2.1 What is the "checkpointer" (recap, because it's the star of this step)

You never wrote chat-history-saving code by hand. LangGraph does it for you through an object called
the **checkpointer**. After each step of the agent graph runs, LangGraph takes a snapshot of the
conversation state — called a **checkpoint** — and saves it, tagged with the conversation's
`thread_id`. Re-opening a thread means the checkpointer replays that thread's saved checkpoints; the
sidebar's thread list (`retrieve_all_threads()`) is just "list every distinct `thread_id` the
checkpointer has ever saved."

The checkpointer is an **interface** with interchangeable back-ends:
- `SqliteSaver` writes checkpoints into a SQLite file.
- `PostgresSaver` writes the identical checkpoints into Postgres.

Because the rest of the app (`graph.py`, `app.py`) only ever calls the *interface* — `.list(...)`, and
`graph.compile(checkpointer=...)` — swapping the back-end touches **only `memory.py`**. That's why this
was a small change, not a rewrite.

### 2.2 What is Postgres, and what is Neon?

**Postgres** (PostgreSQL) is a full-featured, industry-standard relational database — the same family
as SQLite, but built to run as a **server** that many clients connect to over the network, rather than
as a single local file. **Neon** is a company that hosts Postgres for you (a "managed" / "serverless"
Postgres cloud), with a free tier. You don't install or run Postgres yourself; Neon gives you a
connection string and you talk to their server. Same relationship Qdrant Cloud has to Qdrant.

### 2.3 What is a "connection string"?

A single URL that packs everything needed to reach the database:
`postgresql://user:password@host/dbname?sslmode=require`
— the protocol, your username and password, the server's address, which database, and connection
options. `sslmode=require` forces the connection to be **encrypted** (SSL/TLS) — non-negotiable when
your database is out on the public internet, because the password and all data travel over it. Neon
issues this string for you; it goes in `.env` as `NEON_URL` (a real secret — never in `.env.example`).

### 2.4 What is `psycopg`? (the driver)

Python can't speak Postgres's network protocol on its own. `psycopg` is the **driver** — the library
that translates Python calls into the bytes Postgres understands and back. `langgraph-checkpoint-postgres`
(which gives us `PostgresSaver`) uses `psycopg` under the hood. The `[binary]` in `psycopg[binary]`
means "install a precompiled build," so you don't need a C compiler on Windows to install it.

### 2.5 The three connection flags — what they do and why

We open the connection with `Connection.connect(NEON_URL, autocommit=True, prepare_threshold=0,
row_factory=dict_row)`. These are not decoration; each one prevents a real failure mode:

- **`autocommit=True`** — By default a database connection wraps work in a *transaction* that isn't
  saved until you explicitly `commit`. LangGraph manages its own save boundaries and expects each
  checkpoint write to land immediately, so we let the connection auto-commit every statement. Without
  this, writes can sit uncommitted and the checkpointer misbehaves.
- **`prepare_threshold=0`** — psycopg likes to optimise repeated queries by turning them into
  "prepared statements" cached on the server. Neon's connection **pooler** (pgbouncer) doesn't
  guarantee you get the same server-side session each time, so those cached statements can go missing
  and error. Setting the threshold to 0 disables the feature — safe, tiny cost, avoids a class of bug.
- **`row_factory=dict_row`** — tells psycopg to hand back query results as **dicts keyed by column
  name** instead of plain tuples. `PostgresSaver` reads columns by name, so it needs dict rows. (We
  confirmed this by reading the installed library: its own `from_conn_string` opens the connection with
  exactly these same three flags — we're reproducing what the library does for itself.)

### 2.6 Why we did NOT use `PostgresSaver.from_conn_string()` (as the plan literally said)

The implementation plan sketches `PostgresSaver.from_conn_string(NEON_URL)`. But that method is a
**context manager** — it's designed for `with ... as checkpointer:` and it **closes the database
connection when the `with` block ends**. Our app needs a connection that stays open for the app's
entire life (the graph is compiled once at import and used for every message afterward). If we used
`from_conn_string`, the connection would close the moment setup finished and every later query would
fail on a dead connection.

So instead we open a long-lived `Connection` ourselves and pass it to `PostgresSaver(conn)` — mirroring
exactly how the old code passed a long-lived `sqlite3` connection to `SqliteSaver(conn=...)`. **Lesson:
the plan is a sketch of intent, not gospel API.** When a suggested call's *lifecycle* doesn't match how
your app lives (one-shot vs. long-running), adapt it and note why.

### 2.7 What `checkpointer.setup()` does, and why SQLite didn't need it

`setup()` creates the tables Postgres needs to store checkpoints (and runs any schema migrations for
the checkpointer's own version). `SqliteSaver` created its tables lazily on first use, so you never saw
this step; `PostgresSaver` makes it explicit. We call it on **every** startup — it's idempotent (it
checks what already exists and only creates what's missing), so there's no need to track "have I run
setup before?" separately. Same idempotent-on-startup pattern as the Qdrant payload index in Step 2.

---

## 3. File-by-file: what changed and why

### `src/backend/memory.py`
The only real code change of the step. Before → after:
- **Before:** `conn = sqlite3.connect('chatbot.db', check_same_thread=False)` then
  `checkpointer = SqliteSaver(conn=conn)`.
- **After:** read `NEON_URL` from the environment, open a long-lived psycopg `Connection` with the
  three flags from 2.5, wrap it in `PostgresSaver(conn)`, and call `checkpointer.setup()` once at
  startup to create the tables in Neon.
- **`retrieve_all_threads()` is unchanged.** It only uses `checkpointer.list(None)`, which is identical
  across both savers — proof the swap is fully contained in this file.

### `requirements.txt`
- Added `psycopg[binary]==3.3.4` (the Postgres driver) and `langgraph-checkpoint-postgres==3.1.0`
  (provides `PostgresSaver`). Pinned to the exact installed versions, per the repo's
  reproducibility rule.
- `langgraph-checkpoint-sqlite==3.0.3` is **kept for now**, to be removed as a separate cleanup commit
  once Postgres persistence is fully confirmed (prove the new path works before deleting the old one).

### `.env` / `.env.example`
- `.env` gains the real `NEON_URL` connection string (secret — git-ignored).
- `.env.example` gains a `NEON_URL=postgresql://...` **placeholder** so anyone cloning the repo knows
  the variable exists and what shape it has, without seeing a real credential.

### `chatbot.db` (local file)
Now orphaned — nothing reads or writes it anymore. It's already git-ignored. Safe to delete as
cleanup; left in place for now so nothing is destroyed before persistence is verified.

---

## 4. Issues hit while building this step

No runtime errors surfaced — the app started and worked on the first launch after the swap. That was
largely because three predictable pitfalls were designed around up front. Recording them here anyway,
because *avoiding* an error and *understanding why it would have happened* is the transferable lesson:

- **The context-manager trap (would-be dead connection).** Following the plan's literal
  `from_conn_string(...)` would have closed the connection right after setup, and the first chat message
  would have failed on a closed connection. Avoided by opening a long-lived `Connection` instead — see
  2.6.
- **Missing `setup()` (would-be "relation does not exist").** Unlike SQLite, `PostgresSaver` doesn't
  create its tables lazily. Skipping `setup()` would have thrown a Postgres "table/relation does not
  exist" error on the first checkpoint write. Avoided by calling it at startup — see 2.7.
- **Wrong connection flags (would-be pooler / commit bugs).** Omitting `autocommit`, `prepare_threshold=0`,
  or `row_factory=dict_row` invites uncommitted-write, prepared-statement-through-the-pooler, and
  read-by-column-name failures respectively. Avoided by matching the flags the library uses internally
  — see 2.5.

If you *do* later hit a Postgres error (e.g. after switching to Neon's pooled connection string, or on
a fresh clone), the most likely culprits are: `NEON_URL` missing/typo'd in `.env` (SSL or auth error),
or a prepared-statement error through the pooler (confirm `prepare_threshold=0` is set). Record the
specifics here in the rule-4 format if it happens.

---

## 5. Where things stand after this step

- Chat memory now lives in **Neon Postgres**, not a local `chatbot.db` — reachable from any process or
  container with `NEON_URL`.
- Both halves of the app's persisted state are now managed external services: **Qdrant** (PDF vectors,
  Step 2) + **Neon** (chat memory, this step). Nothing important remains in local RAM or local files —
  the app is now structurally ready for the serverless (Modal) split in Phase B.
- The swap was contained entirely in `memory.py`; `graph.py` and `app.py` were untouched, thanks to the
  shared checkpointer interface.

**True end-to-end proof (worth doing if not already):** send a message in a thread, fully stop the
Streamlit app, restart it, reopen the thread — the history should still be there. That specifically
proves the memory survived process death, i.e. that it's really in Neon and not in local RAM.

Next: Phase A Step 4 — **hardening `thread_id` injection**. Right now the agent is *told* (via the
system prompt) to pass the `thread_id` into `rag_tool`, trusting the 7B LLM to copy it correctly. We'll
stop trusting the model and inject the `thread_id` from the graph's config directly, so PDF retrieval
targets the right thread reliably — now critical, because Qdrant filters on exactly that value.
