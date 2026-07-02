# Phase A Step 4 Explanation — Hardening `thread_id` injection

> Companion to `docs/explanation/structure_explanation.md` (core concepts: agent, tools, RAG,
> checkpointer) and the earlier Phase A step docs. This covers Phase A Step 4 from
> `docs/implementation_plan.md`: stop trusting the LLM to pass `thread_id` into `rag_tool`, and inject
> it from the graph's run config instead. Directly builds on Step 2 (Qdrant), which made a correct
> `thread_id` load-bearing.

---

## 1. The Big Picture — why this step exists

After Step 2, PDF retrieval works like this: `rag_tool` does a similarity search in Qdrant **filtered by
`thread_id`**, so a thread only ever sees its own uploaded document. That filter is only as reliable as
the `thread_id` it's handed.

Before this step, that `thread_id` reached the tool by a fragile route: the system prompt *told the LLM*
"call `rag_tool` and include the thread_id `abc-123-...`," and we trusted the 7-billion-parameter model
to copy that UUID **character-for-character** into its tool call. Two things make that a bad bet:

1. **LLMs are not reliable string-copiers.** A small model can drop a character, truncate, or
   hallucinate a plausible-looking UUID — especially in longer conversations.
2. **After Step 2, a wrong `thread_id` fails *silently*.** The Qdrant filter simply matches zero
   chunks, so `rag_tool` returns "no document found" even though the PDF is sitting right there. No
   crash, no error — just a wrong, empty answer. Silent wrong answers are the worst kind of bug.

The fix: the `thread_id` is not a *decision* for the model to make — the **system already knows it** (the
UI sets it in the run config). So we take it out of the model's hands entirely and inject it from that
config. The model can no longer get it wrong because it never touches it.

---

## 2. Core concepts, explained simply

### 2.1 What is a tool's "argument schema," and what does the model actually see?

When you decorate a function with `@tool`, LangChain inspects its parameters and builds a JSON schema
describing them — that schema is what gets sent to the LLM so it knows how to call the tool. Before this
step, `rag_tool(query, thread_id=None)` exposed **two** arguments to the model, so the model was
responsible for filling in both. The whole idea of this step is to shrink what the model sees down to
just `query`, and supply `thread_id` from outside the model.

### 2.2 What is `RunnableConfig`?

Every time the graph runs, it carries a **config** object — a dict that travels alongside the data
through every node. Your UI creates it in `app.py` as
`CONFIG = {"configurable": {"thread_id": thread_key}, "metadata": {...}}` and passes it to
`chatbot.stream(config=CONFIG)`. `configurable` is the sub-dict meant for *your* runtime values (like
`thread_id`); `metadata` is extra tagging (used for LangSmith). `RunnableConfig` is just the type name
for this object in LangChain/LangGraph.

### 2.3 The trick: a `RunnableConfig`-typed parameter is auto-injected and hidden from the model

This is the key mechanism. If a tool function declares a parameter annotated as `RunnableConfig`:

```python
def rag_tool(query: str, config: RunnableConfig) -> dict:
```

LangChain treats `config` as **special**, not as a normal argument:
- It is **excluded from the argument schema** shown to the LLM — the model never knows `config` exists
  and is never asked to fill it. From the model's side, the tool takes only `query`.
- It is **auto-filled at call time** with the current run's config. When `ToolNode` invokes the tool
  during graph execution, LangGraph hands it the same config the graph is running under — the one that
  contains `configurable.thread_id`.

So inside the tool we just read `config["configurable"]["thread_id"]` (via `.get(...)` for safety) and
we have a `thread_id` that came straight from the UI, untouched by the LLM.

### 2.4 `RunnableConfig` vs `InjectedToolArg` — why we chose the former

The plan named both options. `InjectedToolArg` is a marker that says "the model shouldn't fill this
argument; my own code will inject it before calling the tool" — which means *you* have to wire up the
injection somewhere. `RunnableConfig` is simpler here because the injection is **automatic** and works
out-of-the-box with the prebuilt `ToolNode` we already use: no extra wiring, and the value we need
(`thread_id`) is already sitting in the config. Fewer moving parts, same guarantee. `InjectedToolArg`
is the better tool when the value you want to inject *isn't* already in the config (e.g. a per-call
object you construct yourself).

---

## 3. File-by-file: what changed and why

### `src/backend/tools/rag.py`
- **Signature:** `rag_tool(query, thread_id=None)` → `rag_tool(query, config: RunnableConfig)`. The
  model now only supplies `query`; `thread_id` is read from `config` inside the function.
- Added `from langchain_core.runnables import RunnableConfig`; removed the now-unused
  `from typing import Optional`.
- The `if not thread_id: return {"error": ...}` guard is **kept** as a safety net for the unlikely case
  the tool is invoked without a config (e.g. a direct unit-test call).
- Everything after the `thread_id` lookup — the Qdrant `similarity_search` with `thread_filter`, the
  empty-results handling, the returned `context`/`metadata`/`source_file` — is unchanged.

### `src/backend/graph.py` (`chat_node`)
- Deleted the block that pulled `thread_id` out of `config` and string-formatted it into the system
  prompt, plus the `` `{thread_id}` `` instruction. The model no longer needs to know the thread id, so
  the prompt no longer mentions it — it just says "call `rag_tool` with the user's question."
- The node still passes `config=config` to `llm_with_tools.invoke(...)` (that's for tracing/propagation);
  the actual `thread_id` injection into the tool happens inside `ToolNode` at tool-call time, not here.

### `src/client/app.py` (cleanup — done as a follow-up after Step 5)
- Removed the **duplicate** `st.set_page_config(...)` call. The file had one at line 7 *and* a leftover
  second copy at line 59 (carried over from before the Step 1 restructure). Streamlit requires
  `set_page_config` to be called exactly once, as the very first Streamlit command, so the second copy
  was a latent crash. Deleted the line-59 copy, kept the one at line 7. (This was flagged as pending in
  this doc's first version; it was completed together with deleting the orphaned `chatbot.db`.)

---

## 4. Issues hit while building this step

No new runtime errors — the app kept working after the swap, which is itself the point: retrieval
behaved the same in the normal case, but is now immune to the LLM mis-copying the `thread_id`.

The one thing worth flagging as a lesson: this bug class is **invisible in a quick test**. The old
prompt-passing approach worked *most* of the time, so "I tested it and it retrieved fine" did not prove
it was safe — the failure was intermittent and silent (empty results, no error). The transferable
lesson: when a value must be exactly right for a downstream filter/lookup, don't route it through a
component that's only *probably* accurate (an LLM). Move it to a path that's *deterministically* correct
(config injection). Reliability problems that only show up sometimes are worth fixing structurally, not
by hoping the model behaves.

---

## 5. Where things stand after this step

- `rag_tool` gets its `thread_id` from the run config, deterministically — PDF retrieval is now
  correctly scoped to the right thread on **every** call, not just when the LLM copies the UUID right.
- The LLM's tool-calling surface is smaller and simpler (`query` only), which also makes it a bit less
  likely to fumble the call at all.
- The duplicate `set_page_config` in `src/client/app.py` was removed as a follow-up cleanup (see the
  file-by-file note above), closing out the last leftover from the Step 1 restructure.

Next: Phase A Step 5 — **LangSmith tracing**. The `.env` keys are already scaffolded
(`LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` in `.env.example`) and the UI's
`CONFIG` already sets `run_name`/`metadata`; the step is mostly wiring real keys and confirming traces
appear in the LangSmith dashboard — giving visibility into every agent run, which becomes essential once
the agent is deployed on Modal (Phase B) and the eval harness (Phase C) reads from it.
