# Phase A Step 2 Explanation — FAISS → Qdrant

> Companion to `docs/explanation/structure_explanation.md` (core concepts: agent, tools, RAG,
> checkpointer) and `docs/explanation/phase_a_step1_explanation.md` (cleanup/secrets, the previous
> step). This document covers Phase A Step 2 from `docs/implementation_plan.md`: replacing the
> in-memory FAISS PDF store with a persistent, managed **Qdrant** vector database.

---

## 1. The Big Picture — why swap FAISS for Qdrant

`structure_explanation.md` already described RAG's 4 steps: load → split → embed → store/retrieve.
Step 4 is what's changing here. Previously, "store" meant `FAISS.from_documents(chunks, embeddings)`
— which builds a searchable index **entirely in your Python process's RAM**, held in a dictionary
(`_THREAD_RETRIEVERS`) keyed by `thread_id`.

That's a problem for two connected reasons:

1. **It doesn't survive a restart.** Stop and restart the Streamlit app, and `_THREAD_RETRIEVERS` is
   an empty dict again — every uploaded PDF is gone, even though the chat history (in `chatbot.db`)
   survives fine. RAM-only data structures don't persist; only things written to disk or a database do.
2. **It's fundamentally incompatible with where this project is headed.** Phase B of the plan moves
   the agent onto **Modal**, a serverless platform where each incoming request may run in a **brand
   new, disposable container** with no memory of any previous request. A Python dictionary living in
   one container's RAM is useless if the next question might hit a completely different container.

Qdrant solves both: it's a database that lives **outside** your Python process (on Qdrant's own
servers, in this case their free Cloud tier), specifically built to store and search vector
embeddings. Any process, any container, any restart — as long as it has the URL and API key, it sees
the same data. This is also exactly why the plan pairs this with **Neon Postgres** replacing SQLite in
step 3: same underlying reason, different piece of the puzzle (chat memory instead of PDF vectors).

---

## 2. Core concepts, explained simply

### 2.1 What is a "vector database," and how is it different from a normal database?

A normal database (like SQLite, Postgres) is built to look things up by **exact match** — "find the
row where `id = 42`." A vector database is built to look things up by **similarity** — "find the 4
stored items whose *meaning* is closest to this new item." Under the hood, "meaning" is represented as
a vector (a long list of numbers — 384 of them, in this project, one per dimension the embedding model
outputs). Two chunks of text about similar topics end up with vectors that are numerically close
together; a vector database is optimized specifically to answer "which stored vectors are closest to
this query vector?" fast, even across millions of entries.

### 2.2 What is a "collection"?

Qdrant's equivalent of a SQL "table." One collection holds many "points" (see below), all with vectors
of the same fixed size. This project uses exactly **one** collection, `pdf_chunks`, shared by every
chat thread — not one collection per thread. Section 2.7 explains why.

### 2.3 What is a "payload"? *(the thing you asked about)*

Each entry stored in Qdrant (called a "point") has two parts:
- **The vector itself** — the 384 numbers representing the chunk's meaning. This is what similarity
  search compares.
- **The payload** — a plain JSON-like object of extra data attached to that point, which *isn't* part
  of the similarity math. Think of it as "the label on the box," not the box's contents.

In this project, when a PDF is ingested, each chunk's payload looks like:

```json
{
  "page_content": "the actual chunk of text from the PDF",
  "metadata": {
    "thread_id": "abc-123",
    "filename": "report.pdf",
    "total_pages": 12,
    "total_chunks": 34,
    "page": 3
  }
}
```

(The `page_content` / `metadata` split and the `page` field come from LangChain's `Document` object —
`page` is added automatically by `PyPDFLoader` when it loads the original PDF.)

Payloads exist because raw similarity search alone can't answer "but only search **this thread's**
PDF" — the vector itself has no notion of which thread it belongs to. The payload is where that
bookkeeping information lives, and it's what makes **filtering** (2.5) possible.

### 2.4 What is a "payload index," and why did Qdrant demand one?

This is exactly the error hit while building this step:

```
Bad request: Index required but not found for "metadata.thread_id" of one of the
following types: [keyword, uuid]. Help: Create an index for this key or use a different filter.
```

A normal database index (e.g. on a SQL column) exists so the database *doesn't* have to scan every
single row to answer a query filtered on that column — it keeps a pre-sorted lookup structure instead.
Qdrant has the same concept for payload fields: if you want to **filter** search results by a payload
field (like `metadata.thread_id`), Qdrant needs an index on that field telling it "this field holds
short exact-match strings (`keyword` type), here's how to look them up quickly."

Why does it *require* this rather than just doing a slower unindexed scan automatically? Because
Qdrant Cloud is built for large-scale, low-latency search — an unindexed filter over millions of
points would be a silent performance trap, so instead of doing that quietly, Qdrant refuses and makes
you declare the index explicitly. (Note: a quick sanity-check I ran locally against a temporary
in-memory Qdrant instance did *not* enforce this — it's specifically the real server/cloud engine that
requires it, which is why this didn't show up until testing against the actual Qdrant Cloud cluster.)

**The fix**, in `src/backend/rag/vectorstore.py`:

```python
client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name="metadata.thread_id",
    field_schema=PayloadSchemaType.KEYWORD,
)
```

This declares: "the `metadata.thread_id` field holds keyword-type (short exact-match string) values —
build a lookup index for it." It's safe to call every time the app starts (confirmed by testing it
twice in a row against the real cluster) — Qdrant just keeps the existing index rather than erroring,
so there's no need to track "did I already create this index" separately.

### 2.5 What is "filtering" a vector search?

A **plain** similarity search asks: "give me the closest matches to this vector, out of *everything*
in the collection." A **filtered** similarity search asks: "give me the closest matches, but only
considering points whose payload satisfies this condition." This project filters every PDF search by
`metadata.thread_id == <this chat's thread id>` — combining "semantically similar" (vector search) with
"belongs to this specific conversation" (payload filter) — otherwise one user's uploaded PDF could
leak into another thread's answers, since all threads share the one `pdf_chunks` collection.

### 2.6 Cosine similarity (briefly)

`Distance.COSINE`, set when the collection is created, is the specific math formula Qdrant uses to
decide "how close" two vectors are — it measures the *angle* between them rather than raw distance,
which works well for text embeddings (it cares about *direction of meaning*, not magnitude). You don't
need the formula itself, just that it's the standard, sensible default for this kind of embedding
model, and it's why `all-MiniLM-L6-v2`'s 384-dimensional output was paired with `Distance.COSINE` when
the collection was created.

### 2.7 Why one shared collection instead of one collection per thread?

Creating a brand new Qdrant collection per chat thread was an option, but: collections are a heavier
concept (Qdrant provisions storage/indexes per collection), and the number of chat threads is
unbounded — you'd be creating a new collection every single time someone clicks "New Chat," most of
which might get 0 or 1 PDF uploads. A single shared collection with a `thread_id` payload field is the
standard pattern for this kind of "multi-tenant" data — many logically-separate datasets, all living in
one physical collection, kept apart purely by a filtered field. It's simpler to manage and scales
better than collection-per-thread.

---

## 3. File-by-file: what changed and why

### `src/backend/rag/vectorstore.py` *(new file)*
The shared setup both `ingest.py` (writes) and `rag.py` (reads) depend on:
- Creates one `QdrantClient`, connected via `QDRANT_URL` + `QDRANT_API_KEY` from `.env`.
- Creates the `pdf_chunks` collection if it doesn't already exist, sized for 384-dimension vectors
  (matching `all-MiniLM-L6-v2`, section 2.1) with cosine distance (section 2.6).
- Ensures the `metadata.thread_id` payload index exists (section 2.4) — every startup, safely.
- Wraps it all in a `QdrantVectorStore` (LangChain's adapter object) that both other files use to
  actually add/search documents without touching the raw Qdrant client API directly.
- Exposes `thread_filter(thread_id)` — one shared helper that builds the "only this thread" filter
  (section 2.5), so the filter-building logic exists in exactly one place instead of being duplicated.

### `src/backend/rag/ingest.py`
**Before:** built a fresh `FAISS.from_documents(...)` index per upload, stored the resulting retriever
object in the in-memory `_THREAD_RETRIEVERS` dict, and separately tracked display info
(filename/page-count/chunk-count) in another in-memory dict, `_THREAD_METADATA`.
**After:** both in-memory dicts are gone. Instead:
- Every chunk gets `thread_id`, `filename`, `total_pages`, and `total_chunks` written into its
  `metadata` **before** it's inserted (section 2.3) — this is what lets the same numbers be read back
  later purely from Qdrant, with nothing kept locally.
- `vector_store.add_documents(chunks)` writes them straight into the shared collection.
- `thread_has_document()` and `thread_document_metadata()` (used by the sidebar's "using `file.pdf`
  (N chunks from M pages)" display) now `scroll` (Qdrant's term for "fetch matching points") the
  collection filtered by `thread_id`, instead of doing a dictionary lookup — meaning this info now
  survives a restart too, matching the chat history's persistence.

### `src/backend/tools/rag.py`
**Before:** looked up a stored FAISS retriever object for the thread and called `.invoke(query)` on
it.
**After:** calls `vector_store.similarity_search(query, k=4, filter=thread_filter(thread_id))` directly
against Qdrant — same `k=4` (top 4 chunks) behavior as before, just filtered explicitly instead of
relying on a retriever object that only ever "knew about" one thread's data because of which dict entry
it was stored under.

### `requirements.txt`
- Removed `faiss-cpu` (no longer used anywhere in the codebase).
- Added `qdrant-client==1.18.0` (the low-level Qdrant SDK — used directly for `create_collection`,
  `create_payload_index`, `scroll`) and `langchain-qdrant==1.1.0` (LangChain's `QdrantVectorStore`
  adapter, used for `add_documents`/`similarity_search`).

### `.env` / `.env.example`
Added `QDRANT_URL` and `QDRANT_API_KEY` — the connection details for the Qdrant Cloud cluster.

---

## 4. Issues hit while building this step

### Issue 1: real secrets pasted into `.env.example` instead of `.env` → "target machine actively refused it"

**What happened:** after creating the Qdrant Cloud cluster, the real URL and API key were pasted into
`.env.example` (the *placeholder template*, see step 1's explanation doc, section 2.3) instead of
`.env` (the real config file). Running the app then failed with a low-level connection error:
`ConnectionRefusedError` / "target machine actively refused it."

**Why:** with the values missing from `.env`, `os.getenv("QDRANT_URL")` and
`os.getenv("QDRANT_API_KEY")` both returned `None`. `QdrantClient(url=None, api_key=None)` doesn't
error immediately on that — it just falls back to Qdrant's default local address,
`http://localhost:6333`. Since no Qdrant server was running locally, the operating system refused the
connection outright (nothing was listening on that port at all) — hence "target machine actively
refused it," which is Windows' specific wording for "I tried to connect, and got an explicit rejection,
not a timeout."

**Fix:** moved the real values into `.env`, restored `.env.example` back to placeholders. Confirmed no
actual exposure happened — `.env.example` had only been created locally and was never `git add`ed or
committed, so the real key was never pushed anywhere public.

### Issue 2: `Bad request: Index required but not found for "metadata.thread_id"`

Covered in full in section 2.4 above — Qdrant Cloud requires an explicit payload index before you can
filter search results by a payload field. Fixed by calling `client.create_payload_index(...)` for the
`thread_id` field, every startup (safe/idempotent), in `vectorstore.py`.

### Issue 3: `ModuleNotFoundError: No module named 'torchvision'`, from deep inside `transformers`

**What happened:** a crash originating from
`transformers/models/zoedepth/image_processing_zoedepth.py`, which unconditionally does
`from torchvision.transforms.v2 import functional as tvF` — even though this project never uses
ZoeDepth (an unrelated *image* depth-estimation model) or any vision model at all; this is a pure-text
RAG pipeline.

**Investigation so far:** this could **not** be reproduced by directly testing, one at a time: loading
the embedding model, embedding a query, embedding a batch of chunks, running a full PDF ingestion
through a real Streamlit script-runner thread (including the actual write to Qdrant), or invoking the
chat LLM. All of these worked cleanly in isolation. The error signature matches a known class of
upstream `transformers` bug, where certain versions eagerly attempt to import *all* registered
image-processor backends as a side effect of unrelated auto-class resolution, and the ZoeDepth module
specifically is missing a guard (`is_torchvision_available()`) that other optional-dependency imports
in the library normally have.

**Status: resolved (workaround).** `pip install torchvision` (pinned as `torchvision==0.27.1` in
`requirements.txt`) unblocked it — a full re-test after installing (PDF ingest → Qdrant write →
filtered `rag_tool` query → LLM call, all end-to-end) passed cleanly. The exact internal trigger inside
`transformers` was never pinned down precisely (it didn't reproduce through direct, isolated calls to
the embedding model, ingestion, or the LLM even *before* installing torchvision, which is itself a
little unusual) — but functionally the app now works, and `torchvision` is a legitimate, low-risk
addition (it has no other role in this project; it exists purely to satisfy that one unconditional
import inside `transformers`).

---

## 5. Where things stand after this step

- PDF chunks now live in Qdrant Cloud, not in an in-memory dict — confirmed to survive a page/process
  restart.
- Every read (`rag_tool`) and existence/metadata check (`thread_has_document`,
  `thread_document_metadata`) is scoped correctly to one thread's data via the payload filter.
- `faiss-cpu` fully removed from the project; `torchvision` added to fix the unrelated `transformers`
  import bug.
- Full pipeline verified end-to-end: ingest → Qdrant write → filtered retrieval → LLM call.

Next: Phase A Step 3 — swapping local SQLite (`chatbot.db`) for managed Neon Postgres, for the same
"survive a restart / survive a serverless container" reason described in section 1.
