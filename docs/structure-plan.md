# Structure Plan — Industry-Standard Project Layout

> Companion to `docs/implementation_plan.md` (the **active** plan — ignore `completion-plan.md`).
> This document does **not** change any logic. It defines the target folder tree and maps every
> piece of **existing** code to its new home, so the project can be rebuilt one file at a time by
> **pasting existing code only**. No new code is added without permission.

## How to use this doc

1. Build the tree **one file at a time**, top of the checklist down.
2. For each file: create it, then paste the **existing** code from the mapped source lines.
3. Anything marked **PLACEHOLDER** is an empty stub for now — its real content comes later, in its
   proper phase from `implementation_plan.md`.
4. Old root files are **kept, not deleted** — the new tree is built alongside them.

---

## Target folder tree

```
ChatBot/
├── src/
│   ├── __init__.py
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── config.py          # env loading (load_dotenv + os.getenv reads)
│   │   ├── llm.py             # HuggingFace LLM + embeddings setup
│   │   ├── state.py           # ChatState TypedDict
│   │   ├── tools/
│   │   │   ├── __init__.py    # gathers the 4 tools into `tools = [...]`
│   │   │   ├── search.py      # DuckDuckGo search_tool
│   │   │   ├── stock.py       # get_stock_price (Alpha Vantage)
│   │   │   ├── calculator.py  # calculator
│   │   │   └── rag.py         # rag_tool (retrieval)
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   └── ingest.py      # ingest_pdf + retriever store + metadata helpers
│   │   ├── memory.py          # checkpointer + retrieve_all_threads
│   │   └── graph.py           # chat_node, ToolNode, StateGraph, compiled `chatbot`
│   ├── client/
│   │   ├── __init__.py
│   │   └── app.py             # Streamlit UI (copied from app_2.py)
│   └── modal_app.py           # PLACEHOLDER — Phase B deploy endpoints
├── eval/                      # PLACEHOLDER — Phase C
│   ├── run_eval.py
│   └── README.md
├── assets/
│   └── sample.pdf             # PLACEHOLDER — demo PDF for eval
├── docs/
│   ├── implementation_plan.md # (existing — the active plan)
│   ├── structure-plan.md      # (this document)
│   ├── completion-plan.md     # (existing — superseded, ignore)
│   └── extract.md             # (existing)
├── requirements.txt           # backend deps (existing, pinned in Phase A)
├── requirements-client.txt    # PLACEHOLDER — Phase B thin-client deps
├── .env                       # (existing — stays git-ignored)
├── .env.example               # PLACEHOLDER — Phase A
├── .gitignore                 # PLACEHOLDER — Phase A
└── README.md                  # PLACEHOLDER — Phase A

# Left untouched at root (originals, not deleted):
#   app_1.py, app_2.py, Langraph_backend.py, Langraph_backend_app.py, chatbot.db, myenv/
```

---

## Why each folder exists (the learning aid)

- **`src/`** — all application source lives here, separated from repo config/docs. Standard convention.
- **`src/backend/`** — the "brain": everything the AI agent needs. No UI code.
- **`src/backend/tools/`** — one file per tool. Easy to read, test, and add new tools later.
- **`src/backend/rag/`** — document ingestion + retrieval storage, isolated from the tools.
- **`src/client/`** — the Streamlit UI only. Talks to the backend; holds no AI logic.
- **`eval/`** — reproducible evaluation harness (Phase C).
- **`assets/`** — static files (sample PDF for the demo/eval).
- **`docs/`** — plans and profile docs.

---

## Existing-code → new-file mapping

Every row moves **existing code only** — no logic changes. Line numbers reference current files.

| New file | Existing source | What moves |
|----------|-----------------|------------|
| `src/backend/config.py` | `Langraph_backend.py:13,26` | `from dotenv import load_dotenv` + `load_dotenv()`. (Env `getenv` reads are Phase A — placeholder comment.) |
| `src/backend/llm.py` | `Langraph_backend.py:14,30-40` | `HuggingFaceEndpoint` + `ChatHuggingFace` `llm`, and `embeddings`. Imports `config`. |
| `src/backend/state.py` | `Langraph_backend.py:173-174` | `ChatState(TypedDict)`. |
| `src/backend/tools/search.py` | `Langraph_backend.py:19,104` | `search_tool = DuckDuckGoSearchRun(...)`. |
| `src/backend/tools/calculator.py` | `Langraph_backend.py:20,106-128` | `calculator` tool. |
| `src/backend/tools/stock.py` | `Langraph_backend.py:17,133-141` | `get_stock_price` tool (key stays hardcoded for now — flagged; rotate in Phase A). |
| `src/backend/tools/rag.py` | `Langraph_backend.py:143-165` | `rag_tool`; imports the store/metadata helpers from `rag/ingest.py`. |
| `src/backend/tools/__init__.py` | `Langraph_backend.py:168` | Re-exports the 4 tools as `tools = [...]`. |
| `src/backend/rag/ingest.py` | `Langraph_backend.py:22-25,42-51,54-98,232-237` | `_THREAD_RETRIEVERS`, `_THREAD_METADATA`, `_get_retriever`, `ingest_pdf`, `thread_has_document`, `thread_document_metadata`, and the splitter/loader/FAISS imports. |
| `src/backend/memory.py` | `Langraph_backend.py:6,11,205-206,225-230` | `sqlite3` conn, `SqliteSaver` checkpointer, `retrieve_all_threads`. |
| `src/backend/graph.py` | `Langraph_backend.py:7,18,169,176-221` | `llm_with_tools` bind, `chat_node`, `ToolNode`, `StateGraph` wiring, compiled `chatbot`. Imports `llm`, `state`, `tools`, `memory`. |
| `src/client/app.py` | `app_2.py` (whole file) | Copied verbatim; only the import line changes to the new package paths. |

**Import rewiring (mechanical):** `app_2.py:2`
`from Langraph_backend import chatbot, retrieve_all_threads, ingest_pdf, thread_document_metadata`
becomes imports from `src.backend.graph`, `src.backend.memory`, and `src.backend.rag.ingest`.

---

## Placeholders vs. real files

- **Real (paste existing code now):** everything under `src/backend/` and `src/client/app.py`.
- **Empty stubs now, filled later:** `src/modal_app.py`, `eval/*`, `assets/sample.pdf`,
  `requirements-client.txt`, `.env.example`, `.gitignore`, `README.md`.

---

## Ordered build checklist (leaf files first, so imports resolve)

1. `src/__init__.py`, `src/backend/__init__.py`, `src/backend/tools/__init__.py`, `src/backend/rag/__init__.py`, `src/client/__init__.py` (empty)
2. `src/backend/config.py`
3. `src/backend/llm.py`
4. `src/backend/state.py`
5. `src/backend/rag/ingest.py`
6. `src/backend/tools/search.py`, `calculator.py`, `stock.py`, `rag.py`
7. `src/backend/tools/__init__.py` (the `tools = [...]` list)
8. `src/backend/memory.py`
9. `src/backend/graph.py`
10. `src/client/app.py` (fix imports only)
11. Verify it runs, then add the PLACEHOLDER files as their phases arrive.

---

## Mapping to `implementation_plan.md` phases

- **Restructure pass (this doc):** pure move/copy of existing code into `src/…`.
- **Phase A** (data layer): `rag/ingest.py` (FAISS→Qdrant), `memory.py` (SQLite→Neon),
  `config.py` (env keys + LangSmith), `tools/rag.py` (thread_id injection), plus new
  `.gitignore` / `.env.example` / `README.md` / pinned `requirements.txt`.
- **Phase B** (deploy): fill `src/modal_app.py`, gut `client/app.py` to HTTP, add `requirements-client.txt`.
- **Phase C** (eval): fill `eval/` + `assets/sample.pdf`.

---

## Bugs carried over untouched (fix in their Phase A step, not during the move)

- Duplicate `st.set_page_config` — `app_2.py:57` and `:97` → collapse to one, first Streamlit command.
- Hardcoded Alpha Vantage key — `Langraph_backend.py:139` → rotate + read from `os.getenv(...)`.

---

## Verification (for this restructure)

1. Every existing function/tool in `Langraph_backend.py` + `app_2.py` appears exactly once in the
   mapping table (nothing dropped, nothing duplicated).
2. No row introduces new logic — each maps to concrete existing line ranges.
3. After building the tree, run the app and confirm it behaves exactly as before (full end-to-end
   check follows `implementation_plan.md`'s own Verification section).
```
