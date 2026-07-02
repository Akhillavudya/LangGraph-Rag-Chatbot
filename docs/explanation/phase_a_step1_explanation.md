# Phase A Step 1 Explanation — Cleanup & Secrets

> Companion to `docs/explanation/structure_explanation.md` (read that one first if you haven't — it
> explains how the whole app works). This document covers just the first step of Phase A from
> `docs/implementation_plan.md`: **cleanup and secrets**, before any new tech (Qdrant, Neon,
> LangSmith) gets added.

---

## 1. The Big Picture — why this step exists

Before adding any new moving parts (a vector database, a managed Postgres, tracing), the plan
deliberately starts with **hygiene**: fixing things that are wrong *right now* in the working app,
independent of any upgrade. Two of these were actual security problems, not just style issues:

- A real API key was hardcoded in source code that's already pushed to a **public** GitHub repo.
- `.env` (which holds live secrets) existed but nothing showed newcomers what keys they'd need.

The other two were correctness bugs that happened to survive the file restructure:
- Streamlit was being told to configure the page **twice**, which is invalid.
- `requirements.txt` had no version numbers, so `pip install` could silently pull different package
  versions than the ones this project was actually built and tested against.

None of this is "new functionality" — it's making the existing app **safe to make public and safe to
rebuild from scratch**, which has to happen before layering Qdrant/Neon/Modal on top.

---

## 2. Core concepts, explained simply

### 2.1 Why never hardcode a secret (API key, password, token) in source code

Source code is meant to be **shared** — with teammates, on GitHub, in your CV portfolio. A secret is
meant to be known by **only you** (and the service you're calling). The moment a secret is typed
directly into a `.py` file, those two goals collide: anyone who can read the code can read the secret.

The fix is always the same pattern: the code reads the secret from the **environment** at runtime
(`os.getenv("SOME_KEY")`) instead of containing it. The actual value lives only in a local `.env`
file, which is never committed to git (see `.gitignore`). This way the *code* is safe to publish, and
the *secret* stays only on your machine (or later, in Modal/Streamlit's secret managers).

### 2.2 Why a leaked key is still leaked even after you "fix" the code

This one surprises most beginners: git doesn't just track the *current* state of your files — it
keeps **every past version**, forever, in the repo's history. So even after editing
`src/backend/tools/stock.py` to remove the hardcoded Alpha Vantage key, the *old* version of that file
— with the key still in it — is permanently visible via `git log` / `git show` on any commit before the
fix. Since this repo is public on GitHub, that old key is public too, permanently, regardless of what
the file looks like today.

The only real fix for an already-leaked key is to **rotate it** — go to the provider (Alpha Vantage),
generate a brand new key, and treat the old one as burned. Editing the code stops the leak from
happening *again*, but rotation is what neutralizes the *existing* leak.

### 2.3 `.env` vs `.env.example` — what's the difference

- **`.env`** — the real file, with your actual live keys. Listed in `.gitignore`, so git ignores it
  completely — it's never committed, never pushed, stays only on your machine.
- **`.env.example`** — a template with the same variable *names* but fake placeholder values (like
  `your_api_key_here`). This one **is** committed to git, on purpose — it's how anyone cloning the
  repo (including a recruiter checking out your project) knows *which* environment variables they need
  to set, without you ever exposing what your real values are.

Both files exist side-by-side for exactly this reason: one is the real config (private), the other is
documentation of *what config is needed* (public).

### 2.4 Why `st.set_page_config()` can only be called once

Streamlit runs your script **top to bottom, every single time** something happens on the page (a
click, typing in a box). `set_page_config()` sets global page options (browser tab title, layout) and
Streamlit's rule is: it must be the **very first** Streamlit command that runs, and it can only run
**once** per script execution. Calling it a second time later in the same script is a contradiction —
which config wins? — so Streamlit either errors or silently ignores the second call, depending on
version. The fix is simply: one call, at the top, before anything else.

### 2.5 Why pin dependency versions in `requirements.txt`

`pip install langchain` with no version number always grabs whatever the **latest** release is *at
the moment you run the command* — which could be a different version tomorrow than it was today.
That's a problem for reproducibility: the exact versions you built and tested against
(`langgraph==1.1.6`, `streamlit==1.56.0`, etc.) are the only combination you *know* works together.
Pinning (`package==exact.version.number`) means anyone else (or future-you, on a new machine) installs
that exact combination, not whatever happens to be newest.

---

## 3. File-by-file: what changed and why

### `src/backend/tools/stock.py`
**Before:** `apikey=C9PE94QUEW9VWGFM` hardcoded directly in the request URL.
**After:** `api_key = os.getenv("ALPHAVANTAGE_API_KEY")`, read at call time.
Also added `from src.backend import config  # noqa: F401` — this import's only job is to trigger
`config.py`'s `load_dotenv()` (see 2.1), guaranteeing `.env` is loaded into the environment *before*
`os.getenv(...)` tries to read from it. Without that import, if `stock.py` were ever imported before
anything else that loads `config`, `os.getenv("ALPHAVANTAGE_API_KEY")` could return `None`.

### `src/client/app.py`
**Before:** `st.set_page_config(...)` appeared twice — once near the top (before the sidebar), once
again right before `st.title(...)`.
**After:** kept as a single call, as the very first Streamlit command in the file (see 2.4).

### `.env.example` *(new file)*
Lists every environment variable the app needs (`HUGGINGFACEHUB_API_TOKEN`,
`ALPHAVANTAGE_API_KEY`, `LANGCHAIN_*`), with placeholder values instead of real ones (see 2.3).

### `requirements.txt`
Every dependency pinned to the exact version installed in this project's `myenv` virtual environment
(see 2.5), by running `pip freeze` inside that venv and matching version numbers to what's actually
verified working.

---

## 4. Issues hit while building this step

### Issue: `ModuleNotFoundError: No module named 'src'`

**What happened:** after pasting the fixes above and running `streamlit run src/client/app.py`, the
app crashed immediately on its very first import line (`from src.backend.graph import chatbot`) with
`ModuleNotFoundError: No module named 'src'` — even though the `src` folder and its `__init__.py`
files were all present and correct.

**Why:** this project's code is organized as a Python **package** — `src/backend/...`,
`src/client/...` — and importing `from src.backend...` only works if the **project root folder**
(the `ChatBot/` folder that contains `src/`) is on Python's *import search path*
(`sys.path`). How that search path gets built depends on *how* you launch the command:

- `streamlit run src/client/app.py` (calling the `streamlit` command directly) — Streamlit only adds
  the script's **own folder** (`src/client/`) to the search path. The project root is never added, so
  `src` (as a package name) isn't findable.
- `python -m streamlit run src/client/app.py` (running Streamlit *as a Python module*, via `-m`) —
  Python's `-m` flag has a documented side effect: it adds the **current working directory** to the
  search path first. Since you run this command from the project root, that root is now searchable,
  and `import src.backend...` resolves correctly.

**Fix:** always launch with `python -m streamlit run src/client/app.py`, from the project root. The
README was updated to document this explicitly so it's not a recurring trap.

---

## 5. Where things stand after this step

- No secrets in source code anymore; the leaked Alpha Vantage key has been rotated.
- `.env.example` exists so the repo is self-documenting for anyone (including future-you) setting it
  up fresh.
- The Streamlit page-config bug is fixed.
- `requirements.txt` is fully pinned.
- The app is confirmed to launch cleanly via `python -m streamlit run src/client/app.py`.

Next: Phase A Step 2 — swapping the in-memory FAISS retriever for a persistent Qdrant vector store
(see `docs/explanation/phase_a_step2_explanation.md`).
