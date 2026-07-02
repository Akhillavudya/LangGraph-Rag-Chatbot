# The Biggest Issues Faced While Building This App

> A project-wide "hardest problems and what they taught me" summary. Each per-step explainer
> (`phase_a_step*`, `phase_b_step*`, `phase_c`, `frontend_restyle`) has its own full "Issues hit while
> building" section — this file pulls the **biggest, most transferable** ones into one place, in the
> order they were hit, in plain language: *what happened → why → how it was fixed → the lasting lesson.*

---

## 1. `ModuleNotFoundError: No module named 'src'`
*(Phase A, Step 1 — see `phase_a_step1_explanation.md`)*

- **What happened:** the app crashed on startup with `No module named 'src'`, even though the `src/`
  folder and its `__init__.py` clearly existed.
- **Why:** running `streamlit run src/client/app.py` put the *script's* folder on Python's import path,
  not the **project root** — so `from src.backend...` couldn't be resolved.
- **Fix:** launch with `python -m streamlit run src/client/app.py` from the project root. The `-m` flag
  puts the current directory (the project root) on `sys.path`, so the `src` package is importable.
- **Lesson:** "module not found" is usually about **where Python is looking**, not a missing file. How
  you *launch* a program decides what it can import.

## 2. Qdrant refused to filter until I created a "payload index"
*(Phase A, Step 2 — see `phase_a_step2_explanation.md` §2.4)*

- **What happened:** filtering PDF chunks by `thread_id` failed until an explicit index was created.
- **Why:** Qdrant will happily *store* metadata (the "payload"), but it won't let you **filter** on a
  field until you've told it to index that field — otherwise filtered search would be slow/undefined.
- **Fix:** create a payload index on `metadata.thread_id` at startup, idempotently (safe to run every
  boot).
- **Lesson:** a vector DB separates the **vector** (the math) from the **payload** (the JSON metadata),
  and filtering on metadata is a feature you must explicitly enable.

## 3. `No module named 'torchvision'` — from code I never wrote
*(Phase A, Step 2 — see `phase_a_step2_explanation.md`, Issue 3)*

- **What happened:** importing the embedding model blew up deep inside `transformers`, demanding
  `torchvision` — a library this project doesn't use.
- **Why:** a `transformers` code path imported `torchvision` without the usual "is it available?" guard,
  so a missing *optional* dependency became a hard crash.
- **Fix:** install the missing package (`torchvision==0.27.1`, pinned).
- **Lesson:** a traceback pointing deep into a third-party library is often about **its** optional
  dependencies, not your code. Read *where* the import fails before assuming you broke something.

## 4. Secrets: `.env` vs `.env.example`
*(Phase A, Step 1 — a recurring rule throughout)*

- **What happened:** early confusion over which file holds real keys and what gets committed.
- **Why:** two files look alike but do opposite jobs: `.env` holds **real secrets** and is git-ignored;
  `.env.example` holds **placeholder names only** and *is* committed so others know what to fill in.
- **Fix:** real keys live only in `.env`; commit only `.env.example`. Pin the habit of running
  `git status` before committing when secrets are in play.
- **Lesson:** a key committed even once lives in git history forever — you must **rotate** it, not just
  delete the line. Prevention (git-ignore + example file) beats cleanup.

## 5. Pinning dependencies (`package==version`)
*(Phase A, Step 1 — see `phase_a_step1_explanation.md` §2.5)*

- **What happened:** `requirements.txt` had no version numbers, so installs could silently pull different
  package versions on different machines/days.
- **Why:** unpinned deps mean "latest at install time" — a recipe for "works on my machine" breakage.
- **Fix:** pin every dependency to its exact installed version.
- **Lesson:** reproducibility comes from pinning. (This bit again later — see #9.)

## 6. Raw tool JSON leaking into the chat on reload
*(Frontend restyle — see `frontend_restyle_explanation.md`)*

- **What happened:** revisiting a saved conversation showed ugly raw retriever JSON in the chat.
- **Why:** one RAG turn stores **four** messages (the question, an empty tool-call `AIMessage`, the
  `ToolMessage` with raw JSON, and the final answer). The *live* view only renders the last one, but the
  *reload* path replayed **all** of them.
- **Fix:** in the history loader, skip `ToolMessage`s and empty-content messages.
- **Lesson:** what an agent *stores* is not what a user should *see*. The live path and the reload path
  must apply the **same** display filtering.

## 7. Modal on Windows: no live-reload + a `charmap` crash
*(Phase B — see `phase_b_step1/2_explanation.md`)*

- **What happened:** (a) editing `modal_app.py` didn't take effect during `modal serve`; (b) `modal
  deploy` crashed with `'charmap' codec can't encode characters`.
- **Why:** (a) Modal's live-reload isn't supported on Windows; (b) Modal prints Unicode progress
  characters the default Windows console encoding (`cp1252`/charmap) can't render.
- **Fix:** (a) `Ctrl+C` and restart `serve` after each edit; (b) run with `PYTHONIOENCODING=utf-8`.
- **Lesson:** dev-tool behavior is **OS-specific**. When output-printing itself crashes, suspect the
  terminal's text encoding, not your program's logic.

## 8. Streamlit Cloud ignored my dependencies
*(Phase B, Step 3 — see `phase_b_step3_explanation.md`)*

- **What happened:** the deployed client installed the wrong (heavy) dependencies.
- **Why:** Streamlit Community Cloud looks for a file named **exactly** `requirements.txt`, searching the
  **entrypoint's directory** first. A root `requirements-client.txt` was ignored, so it fell back to the
  heavy backend requirements.
- **Fix:** put a thin `requirements.txt` (just `streamlit` + `requests`) next to the entrypoint at
  `src/client/requirements.txt`.
- **Lesson:** deploy platforms have **strict, undocumented-feeling conventions** for file names and
  locations. When a deploy behaves oddly, check *which* config file it actually picked up.

## 9. Cold starts (Modal scales to zero)
*(Phase B, Step 3 — see `phase_b_step3_explanation.md`)*

- **What happened:** the first request after idle could hang and time out.
- **Why:** Modal scales the backend to **zero** when idle to save cost; the next call must cold-start a
  container (spin up, load the embedder, connect to Neon/Qdrant) — which can exceed a short HTTP timeout.
- **Fix:** raise the client's timeouts and soften the UI to a friendly "⏳ Waking up… refresh" message.
- **Lesson:** serverless trades idle cost for **first-call latency**. Design the client to *expect* and
  gracefully absorb cold starts.

## 10. The LLM provider wall: HTTP `402 Payment Required`
*(Phase C — see `phase_c_explanation.md`)*

- **What happened:** the eval (and the live app's generation) began failing with `402 ... You have
  depleted your monthly included credits`.
- **Why:** the LLM ran through HuggingFace's router, which forwards to a **paid third-party inference
  provider**. HF's free-tier credits are now effectively zero. Retrieval kept working because embeddings
  run **locally** — no billing on that path.
- **How I diagnosed it:** read the status code literally (`402` = out of credits, not a code bug),
  confirmed the account with `whoami`, then tested a **brand-new** account — which *also* 402'd. When a
  fresh account fails identically, the problem is "this product costs money," not "you used up usage."
- **Fix:** switch providers entirely — see #11.
- **Lesson:** a `4xx` from a provider is an **account/billing signal**, not a bug in your code. And you
  can't dodge a paywall by making new accounts.

## 11. Switching to Groq — and the `tool_use_failed` bug
*(Phase C — see `phase_c_explanation.md`)*

- **What happened:** after moving to Groq's free API, one turn crashed with `400 tool_use_failed ...
  Failed to call a function`.
- **Why:** `llama-3.3-70b-versatile` **intermittently** emitted a tool call as literal text
  (`<function=name {json}</function>`) instead of a structured `tool_calls` object, so Groq's parser
  rejected it.
- **How I diagnosed it:** the error body's `failed_generation` field showed the exact malformed output.
  Then I ran a small **bake-off** — bound the real tools to five candidate models and invoked the
  breaking prompt several times each. `llama-3.3-70b` failed ~25% of the time; `llama-3.1-8b-instant`,
  `openai/gpt-oss-20b`, and `qwen/qwen3-32b` were all reliable.
- **Fix:** switch to `llama-3.1-8b-instant` (0 failures, plain instruct model, closest to the original
  7B, best latency).
- **Lesson:** function-calling reliability is **model-specific**, not just provider-specific — a bigger
  model isn't automatically better at emitting valid tool JSON. Read the error body, then **measure**
  candidates instead of guessing.

## 12. Installing one package moved a pinned version
*(Phase C — see `phase_c_explanation.md`)*

- **What happened:** `pip install langchain-groq` silently upgraded a pinned dep, `langchain-core`
  (`1.2.30 → 1.4.8`).
- **Why:** the new package required a newer core, and pip resolved it by upgrading — quietly.
- **Fix:** run `pip check` (no conflicts) and the eval (still passes), then re-pin `langchain-core` to
  the version actually installed.
- **Lesson:** adding one dependency can shift others. After any install, **re-check and re-pin** what's
  actually there — don't trust the old lockfile blindly (callback to #5).

## 13. Groq free-tier rate limit (tokens-per-minute)
*(Phase C — see `phase_c_explanation.md`)*

- **What happened:** the full latency eval hit `413 ... tokens per minute (TPM): Limit 6000, Requested
  6918`.
- **Why:** the latency loop ran all six prompts in **one shared thread**, so history accumulated and a
  later RAG turn (four PDF chunks stacked across turns) pushed a single request past the free 6,000
  tokens/minute cap.
- **Why it doesn't hurt the app:** a real user sends one message at a time and never bursts six turns in
  seconds — this is purely a **benchmark** artifact.
- **Fix / decision:** ship with retrieval metrics (the substantive result) and mark latency "Skipped",
  rather than over-engineer rate-limit plumbing for a nice-to-have stat. (The clean fix, if wanted: a
  fresh thread per prompt + retry-on-`429/413` with backoff so the run self-paces.)
- **Lesson:** distinguish a limit that hurts **users** from one that only hurts a **stress test** — and
  don't over-engineer the second. Free tiers cap *rate* (TPM/RPM), not just total usage.

## 14. Transient network flakes to managed services
*(Phase C — see `phase_c_explanation.md`)*

- **What happened:** across eval runs, single calls occasionally failed — Qdrant `ReadTimeout` / SSL
  handshake timeout, and a Neon "server closed the connection unexpectedly."
- **Why:** ordinary network/managed-service flakiness (Neon's free tier also auto-suspends and can drop
  idle connections), amplified by the many back-to-back calls a 6-turn benchmark makes.
- **Fix:** a plain re-run succeeded every time.
- **Lesson:** **not every failure is a bug.** Over a network, transient timeouts happen; a retry is the
  correct first response before you go debugging your own code.

---

## The meta-lessons

Reading back over these, a few themes repeat — and they're the real takeaways:

1. **Read the error literally, and read *where* it comes from.** Half of these (`No module named 'src'`,
   `torchvision`, `402`, `tool_use_failed`) were solved by reading the status code / traceback location
   carefully instead of assuming the bug was in my logic.
2. **"Works on my machine" is a dependency and environment problem.** Pinning, launch paths, OS-specific
   tool behavior, and deploy-platform conventions caused as many issues as the AI code did.
3. **Managed services and free tiers have rules** — payload indexes, rate limits, cold starts, auto-
   suspend, credit walls. Building on them means designing *around* those rules, not fighting them.
4. **Know what's worth fixing.** The latency rate limit was real, but chasing it wasn't worth it for a
   portfolio project — recognizing that is its own engineering skill.
