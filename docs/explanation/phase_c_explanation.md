# Phase C Explanation — The evaluation harness (`eval/`)

> Companion to `docs/explanation/structure_explanation.md` and the Phase A/B explainers. Phase A built a
> managed data layer, Phase B deployed the agent. Phase C answers a different question: **is it any
> good, and how fast is it?** — with numbers you can put on a CV instead of "it works on my machine."

---

## 1. The Big Picture — why this step exists

Up to now we've *built* features and eyeballed them ("I asked a question, it answered"). That's not
evidence. An **evaluation harness** turns "seems fine" into **measured facts**: on a fixed set of
questions with known answers, retrieval finds the right passage X% of the time, and responses take Y
seconds. Two payoffs:

- **It catches regressions.** Change the chunk size, the embedding model, or `k`, re-run the harness,
  and see instantly whether quality went up or down — instead of hoping.
- **It's the DS/AI-engineering story.** "Built a chatbot" is weak; "measured retrieval hit-rate@4 = 92%
  and p95 latency = 3.1s on a 13-question benchmark, traced in LangSmith" is a real engineering claim.

The key idea is a **fixed benchmark**: one known document (`assets/sample.pdf`) and a frozen list of
questions with known answers (`eval/dataset.py`). Because the inputs never change, the output numbers
are comparable across runs.

---

## 2. Core concepts, explained simply

### 2.1 Ground truth
The "correct answer" we compare against. Our sample PDF was written on purpose so every fact appears in
exactly one place (e.g. "founded in **2014**", flagship product "**TideCast**"). Each question stores a
short unique string (`expect`) that a correct chunk must contain. That string *is* the ground truth for
retrieval — no human grading needed.

### 2.2 Retrieval vs. generation
A RAG system has two halves that can fail independently:
- **Retrieval** — did vector search fetch the right chunk from Qdrant?
- **Generation** — did the LLM write a good answer from that chunk?

We evaluate **retrieval** directly because it's cheap, deterministic, and the usual culprit: if the
right chunk never gets retrieved, even a perfect LLM can't answer. (Generation quality usually needs an
LLM-as-judge or human grading — out of scope here.)

### 2.3 Hit-rate@k
"In the top **k** retrieved chunks, did the correct one show up at all?" `hit-rate@4 = 0.92` means for
92% of questions, one of the top 4 chunks contained the answer. We score at **k = 4** because that's
exactly how many chunks `rag_tool` retrieves (`similarity_search(..., k=4)`) — so the metric reflects
what the agent actually sees. `hit-rate@1` is the stricter "was the *very first* chunk right?"

### 2.4 Recall@k (and why it equals hit-rate here)
**Recall** = "of all the relevant chunks, what fraction did we retrieve?" In general a question could
have several relevant chunks. In our benchmark each question has **one** relevant passage, so "did we
get it?" (hit-rate) and "what fraction of the one relevant chunk did we get?" (recall) are the same
number. That's why the plan says "recall@k" and the harness reports hit-rate — for a single-answer
benchmark they coincide.

### 2.5 MRR (Mean Reciprocal Rank)
Hit-rate ignores *where* in the list the answer appeared; MRR rewards it being near the top. For each
question you take `1 / rank` of the first correct chunk (rank 1 → 1.0, rank 2 → 0.5, rank 4 → 0.25,
never found → 0), then average over all questions. MRR close to 1.0 means the right chunk is usually
ranked first — a sign of a well-tuned retriever.

### 2.6 Latency: TTFT and total
- **TTFT (time-to-first-token)** — how long until the *first* word of the answer appears. This is what a
  user actually feels as "responsiveness," and for a streaming UI it matters more than total time.
- **Total** — until the last token. We measure both by timing the same `chatbot.stream(...)` loop the
  app uses, marking the clock when the first non-empty `AIMessage` token arrives and again at the end.

### 2.7 Percentiles (p50 / p95)
Averages hide bad cases. **p50** (the median) = the middle value: half the turns were faster. **p95** =
95% of turns were faster than this — it captures the "slow tail" users complain about. Reporting p95,
not just the average, is standard practice for latency because one occasional 10-second response matters
even if the average looks fine. (A cold-started Modal container is exactly the kind of thing p95
surfaces.)

### 2.8 Offline vs. online evaluation
This is **offline** eval: a fixed dataset, run on demand, before shipping. **Online** eval watches real
production traffic (via LangSmith). We do offline here; because tracing is already on, the latency turns
also appear in LangSmith tagged `metadata.eval = true`, bridging the two.

---

## 3. File-by-file — what was added

### `assets/make_sample_pdf.py` + `assets/sample.pdf`
A script (using `reportlab`) that generates the fixed benchmark document, and the committed PDF itself.
The content is a fictional company handbook where each fact is unique, so a retrieved chunk either
contains the exact answer string or doesn't — no ambiguity. `sample.pdf` is committed so the eval is
reproducible without regenerating it; the script is only for rebuilding it.

### `eval/dataset.py`
The frozen benchmark: `DOC_QA` (13 questions, each with its unique `expect` answer string) and
`LATENCY_PROMPTS` (a short mix of RAG/calculator/general prompts for timing). Keeping the data separate
from the runner means you tune the benchmark without touching the measurement logic.

### `eval/run_eval.py`
The harness. It:
1. Ingests `sample.pdf` into a throwaway `eval-<uuid>` thread (so it never touches real chats).
2. **Retrieval eval** — for each question, runs Qdrant `similarity_search(k=4)` filtered to that thread
   and checks whether the `expect` string is in any top-4 chunk; computes hit-rate@1, hit-rate@4, MRR.
3. **Latency eval** — streams each latency prompt through the real `chatbot` and records TTFT + total;
   computes p50/p95.
4. Writes the results table to `eval/README.md`.
5. **Cleans up** — deletes that thread's chunks from Qdrant and its checkpoints from Neon, so the
   benchmark leaves no trace in the live app.
   Flags: `--no-latency` (retrieval only, no LLM cost), `--no-cleanup` (keep data to inspect).

### `eval/README.md`
The generated report: retrieval + latency tables, per-item detail, and how to reproduce. Committed so
the numbers are visible on GitHub without running anything.

---

## 4. Issues hit while building

_(To fill in as they come up on the first real runs — e.g. an `expect` string that doesn't match the
extracted PDF text, a cold-start inflating p95, or Qdrant cleanup needing `FilterSelector`.)_

- **PDF-text vs. expected-string mismatch (guarded against up front):** a retrieval metric is only valid
  if the `expect` string actually appears in the extracted PDF text. We verified all 13 tokens extract
  from `sample.pdf` with `pypdf` before trusting the scores — otherwise a "miss" could mean a bad
  benchmark, not bad retrieval. **Lesson:** validate your ground truth against the real extracted text,
  or your metric measures the wrong thing.

- **HTTP `402 Payment Required` on the latency turns — the LLM isn't free anymore.**
  - *What happened:* retrieval scored 100% fine, then the latency phase crashed with
    `huggingface_hub.errors.HfHubHTTPError: 402 ... You have depleted your monthly included credits`.
  - *Why:* our LLM call (`Qwen/Qwen2.5-7B-Instruct` via `HuggingFaceEndpoint`) is routed by
    `router.huggingface.co` to a **third-party paid inference provider**. HuggingFace's free-tier
    "included credits" are now effectively ~zero, so the request is refused for billing, not for any code
    reason. Retrieval was unaffected because it uses the **local** embedding model + our own Qdrant — no
    HF billing on that path.
  - *How we diagnosed it:* read the status code literally — `402` = out of credits/quota (vs `401` bad
    key, `429` rate-limited, `403` forbidden). We confirmed the account with
    `HfApi().whoami(token=...)['name']`, then tested a brand-new zero-use account — which **also** 402'd.
    That's the tell: when a fresh account fails identically, the problem is "this product costs money,"
    not "you used up your usage." Spinning up more accounts can't fix a paywall (and violates HF ToS).
  - *How we worked around it:* `python -m eval.run_eval --no-latency` runs retrieval only (no LLM calls),
    so the report still generates with valid hit-rate/MRR numbers. The latency section reads "Skipped."
  - *Lesson:* (1) a `4xx` from a provider is an **account/billing signal, not a code bug** — read the
    code before debugging your logic. (2) The same 402 hits the **live app**, since the deployed Modal
    backend calls the same HF endpoint — so this is a "pick a working LLM provider" decision (a free one
    like Groq, or paid HF credits), parked for a later session. (3) A transient `httpx.ReadTimeout` from
    Qdrant on one run was just network flakiness — a plain re-run succeeded; not every failure is a bug.

---

## 5. Where things stand + what's next

With Phase C, the project has an end-to-end story: an agentic RAG chatbot on managed services (Qdrant +
Neon + LangSmith), split into a serverless Modal backend behind a thin deployed client, **plus a
reproducible benchmark** reporting retrieval quality and latency. To run it: `python -m eval.run_eval`
from the project root (needs the same `.env` keys the app uses), then read `eval/README.md`.

Natural next improvements (optional, beyond the plan): add an LLM-as-judge for answer quality, expand
the benchmark, or wire the harness into CI so every change is scored automatically.
