# Phase A Step 5 Explanation — LangSmith tracing

> Companion to `docs/explanation/structure_explanation.md` and the earlier Phase A step docs. This
> covers Phase A Step 5 from `docs/implementation_plan.md`: turning on **LangSmith tracing** so every
> agent run is recorded and inspectable. Unlike Steps 2–4, this step changed **no application code** —
> it's pure configuration — which is itself the lesson.

---

## 1. The Big Picture — why tracing exists

Up to now, when the agent answered, you saw only the final text in the Streamlit window. Everything the
agent did to get there was invisible: whether it called `rag_tool` or answered from memory, which four
chunks Qdrant returned, how long the LLM took, what the exact prompt was. When an answer is wrong or
slow, that invisibility means debugging blind.

**Tracing** fixes that: the app automatically sends a structured record of each run — every internal
step, with its inputs, outputs, and timing — to **LangSmith**, a dashboard built by the LangChain team.
You get an inspectable tree of exactly what happened on every turn.

This matters for this project beyond convenience, for two forward-looking reasons:

1. **Phase B (Modal) removes your terminal.** Once the agent runs serverless in the cloud, there's no
   console to watch and no local logs. LangSmith becomes the *only* window into the deployed agent.
2. **Phase C (eval) reads from these traces.** The eval harness pulls latency (and can pull
   retrieval details) straight out of LangSmith. No tracing now → no numbers later.

So tracing is a dependency of two later phases, not a nice-to-have. Turning it on early also means every
run you do from here on is already being recorded.

---

## 2. Core concepts, explained simply

### 2.1 What is LangSmith?

A hosted dashboard (with a free tier) for observing LLM/agent apps. Your app sends it data over HTTPS;
you log in at `smith.langchain.com` to view it. It's the "observability" layer for a LangChain/LangGraph
app — think of it as the equivalent of application logs + a profiler, but purpose-built for agents.

### 2.2 Trace, run, span — the vocabulary

- **Run / Trace** — one top-level execution of your app. Here, **one chat turn = one trace**, named
  `chat_turn` (that name comes from `run_name` in the UI's `CONFIG`).
- **Span** — a nested step *inside* a trace. One `chat_turn` trace contains spans for the `chat_node`
  LLM call, and (if a document question) the `rag_tool` call with its Qdrant search inside it. LangSmith
  shows these as a tree, each with its own timing and its exact inputs/outputs. Clicking into a trace and
  reading the spans is how you see what the agent *actually did*, step by step.
- **Project** — a named bucket that groups traces. Ours is `Chatbot Project`, set by
  `LANGCHAIN_PROJECT`. Every trace this app produces is filed there.

### 2.3 The four environment variables

Tracing is controlled entirely by environment variables — no code:

```
LANGCHAIN_TRACING_V2=true                             # the on/off switch: "true" enables tracing
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com    # where traces are sent (LangSmith's API URL)
LANGCHAIN_API_KEY=lsv2_pt_...                          # authenticates you (the only real secret here)
LANGCHAIN_PROJECT=Chatbot Project                     # which project bucket to file traces under
```

Only `LANGCHAIN_API_KEY` is a secret — it lives in `.env` (git-ignored). The other three are
non-sensitive settings and their placeholder values in `.env.example` are the real values.

> Naming note: newer LangSmith docs use `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`.
> The older `LANGCHAIN_*` names this project uses are still fully supported (they're the backward-compat
> aliases). Either set works; don't mix half-and-half.

### 2.4 Why no code was needed (the "auto-instrumentation" idea)

The tracing hooks are already *built into* LangChain/LangGraph. When you call `chatbot.stream(...)`,
LangChain sets up a "callback manager" for the run, and at that moment it checks: is
`LANGCHAIN_TRACING_V2` true and is there an API key? If yes, it attaches a tracer that ships each step to
LangSmith; if no, it does nothing. So flipping the env var is the entire on-switch — no
`langsmith.init()`, no decorators, no imports to add. This is called **auto-instrumentation**: the
library instruments itself, you just configure it.

### 2.5 Why load order mattered (and why it was already correct)

For that env-var check to see `true`, the variables must be in the process **before** the first run. In
this project, `src/backend/config.py` calls `load_dotenv()` (which reads `.env` into the environment),
and it's imported early via the chain `app.py → graph → llm → config`, all at import time — long before
Streamlit renders or any chat turn fires. So the keys are present in time, and no reordering was needed.
(If `load_dotenv()` had instead run *after* the graph was first used, tracing would silently stay off —
a good general reminder that env-driven features depend on *when* the env is loaded.)

---

## 3. File-by-file: what changed and why

### `.env` (real, git-ignored)
Added the real `LANGCHAIN_API_KEY` (a `lsv2_pt_...` token from the LangSmith dashboard) and confirmed
the other three `LANGCHAIN_*` vars are present. This is the only substantive change of the step.

### `requirements.txt`
Pinned `langsmith==0.7.32` — the client library that actually ships traces to LangSmith. It was already
installed (it comes in as a LangChain dependency); pinning it makes the tracing capability explicit and
reproducible rather than incidental.

### Application code
**Unchanged.** `app.py`'s `CONFIG` already set `run_name: "chat_turn"` and `metadata: {thread_id}` from
earlier work, so traces are named and tagged correctly with no edit. That prior groundwork is why this
step was config-only.

---

## 4. Issues hit while building this step

Traces appeared on the first run after adding the key, so no error was hit. Worth recording the *shape*
of the most common failure anyway, since it's the thing to check first if traces ever stop showing:

- **Symptom:** app works normally but nothing appears in the LangSmith project.
- **Usual causes:** `LANGCHAIN_TRACING_V2` not exactly `true` (a typo, or set to `True`/`1` in a spot
  that expects the string `true`); a wrong/expired `LANGCHAIN_API_KEY`; `.env` not actually loaded
  before the run; or looking at the wrong **project** in the dashboard (traces filed under a different
  `LANGCHAIN_PROJECT` name than the one you're viewing).
- **How to recognise it:** tracing fails *silently* — it never crashes the app, because tracing is
  designed to be non-blocking (a broken tracer must not take down the actual product). So "no trace" is
  a config problem to hunt down, never an app bug. That silent-by-design behaviour is the transferable
  lesson: observability that can't break your app also can't loudly tell you it's misconfigured — you
  verify it by *checking the dashboard*, not by watching for an error.

---

## 5. Where things stand after this step

- Every chat turn is now recorded to LangSmith as a `chat_turn` trace in the `Chatbot Project` project,
  with nested spans for the LLM call and any tool/Qdrant activity — full visibility into each run.
- This was achieved with **zero application-code changes**: four env vars plus a pinned dependency. A
  concrete example of "configuration, not code" — and of how earlier groundwork (`run_name`/`metadata`
  already in `CONFIG`) pays off later.
- The observability foundation that Phase B (deployed agent) and Phase C (eval) both depend on is now in
  place.

**Phase A is essentially complete** (Steps 1–5 done: cleanup/secrets, Qdrant, Neon, thread_id injection,
tracing). Remaining Phase A housekeeping (Step 6): make sure `requirements.txt` is fully pinned and
carries all the new deps — largely done incrementally across the previous steps; `modal` is intentionally
deferred to Phase B, where it's first used. The last small leftovers (the duplicate
`st.set_page_config` in `src/client/app.py`, and the orphaned `chatbot.db`) were cleaned up as a
follow-up right after this step.

Next milestone: **Phase B — split the agent onto Modal + a thin Streamlit client.**
