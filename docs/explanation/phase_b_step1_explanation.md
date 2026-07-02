# Phase B Step 1 Explanation — Getting set up on Modal

> Companion to `docs/explanation/structure_explanation.md` and the Phase A step docs. This covers the
> very first step of **Phase B** from `docs/implementation_plan.md`: installing Modal, authenticating,
> and proving remote execution with a throwaway "hello world" — *before* we wrap the real agent. No
> application code changed in this step; it's setup + understanding the tool we're about to build on.

---

## 1. The Big Picture — why this step exists

Phase B's job is to split the app into two programs: a **thin Streamlit client** (UI only) and a
**Modal serverless backend** (the LangGraph agent). Before writing that backend, it's worth spending one
small step just proving Modal works on your machine and understanding *what it even is* — so that when we
later put your whole chatbot behind Modal, only the contents are new, not the mechanics.

This step de-risks everything: if Modal auth or install were broken, we'd want to find out with 6 lines
of code, not while debugging a 100-line backend.

---

## 2. Core concepts, explained simply

### 2.1 What is Modal?
A service that runs your Python functions on **its** computers, on demand. You write normal Python, add a
decorator, and Modal ships the function to the cloud, runs it, and returns the result. You don't rent or
manage a server — you think in *functions*, not machines. This is what **"serverless"** means: there is a
server, you just never touch it, and it only exists for the seconds your function runs.

### 2.2 Container
An isolated, pre-packaged mini-computer environment (its own Python, libraries, filesystem) that Modal
creates fresh to run your function. **Fresh** is the key word — each run can get a brand-new empty
container, so nothing stored in an ordinary Python variable survives between requests. This is exactly
why Phase A moved PDF vectors to Qdrant and chat memory to Neon: nothing important lives inside a
container that could vanish.

### 2.3 The three pieces of a Modal script
- **`modal.App("name")`** — the deployable unit that groups your functions (a project namespace).
- **`@app.function()`** — marks a function to run remotely on Modal instead of locally.
- **`@app.local_entrypoint()`** — the piece that runs on *your* machine and kicks off the remote call.

### 2.4 `.remote()` vs `.local()`
Calling `square.remote(6)` sends the call to Modal's cloud; `square.local(6)` would run it on your
laptop. Same function, two places to run it — you choose per call.

### 2.5 Cost / safety model (a beginner worry worth writing down)
- Modal's **free tier** gives a monthly compute credit (~$30/mo at time of writing) and needs **no credit
  card** to start.
- **No card entered = you cannot be charged.** When free credits run out, the app simply *pauses* until
  next month — it never silently bills you. Worst case is "demo offline," not "surprise bill."
- Every request to an endpoint = a run = a little spend. So an *open* public endpoint means strangers
  spend your credits. Defense (built in Phase B step 2): a **bearer token** on the endpoints (a shared
  password the client has and strangers don't), rejecting unauthorized requests before any work runs.
  Optionally cap `max_containers` so a flood can't scale up.
- Note: a **public GitHub repo** (code is readable) is unrelated to endpoint cost — that's free.

---

## 3. File-by-file: what changed and why

### `scratch_modal_hello.py` (throwaway — deleted at end of step)
A 6-line Modal app with one remote `square` function and a local entrypoint. Running
`modal run scratch_modal_hello.py` printed a message *from inside the cloud container* plus
`the square is 36`, proving the full loop: local code → shipped to Modal → run remotely → result
returned. Deleted afterward because it was only a proof, not part of the product.

### `requirements.txt`
Added `modal==1.5.1` (the exact installed version), matching the project's pin-everything rule. This was
intentionally deferred from Phase A step 6 to here, where Modal is first used.

### `CLAUDE.md`
Adjusted the code-commenting rule to **one comment per function** (was: comment every non-obvious block),
per the human's preference for lighter inline comments.

### Application code
**Unchanged.** No `src/` files were touched — this step is setup only.

---

## 4. Issues hit while building this step

None blocking. Two small things worth noting:

- **Backslashes vanished in the Bash tool.** Running `myenv\Scripts\python.exe ...` through the `!` bash
  prompt collapsed to `myenvScriptspython.exe: command not found`, because Bash treats `\` as an escape
  character. **Lesson:** on Windows, use **forward slashes** (`myenv/Scripts/python.exe`) when a command
  goes through Bash; PowerShell accepts either.
- **`modal setup` is interactive** (opens a browser to log in and writes a token to `~/.modal.toml` on
  your machine, *not* into the repo). That token is your Modal credential — like `.env` secrets, it stays
  local and is never committed.

---

## 5. Where things stand after this step

- Modal is installed (`modal==1.5.1`, pinned), your account is authenticated, and you've personally run
  Python on a Modal cloud container and gotten the result back.
- You understand the mental model — ship function → run remotely → return result — that the real backend
  will use, plus the ephemeral-container reason Phase A's managed data layer was a prerequisite, plus the
  cost/safety model (free tier + no card + bearer token).
- No application code changed yet.

**Next: Phase B Step 2** — write the real `modal_app.py` that wraps the LangGraph agent and exposes it as
web endpoints (`/chat` streaming, `/ingest`, `/threads`, `/history`), with secrets via `modal.Secret` and
a bearer token guarding the endpoints.
