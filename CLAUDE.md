# CLAUDE.md — How to work with me on this project

> This file is instructions for Claude Code (and any AI assistant) working in this repo. It is loaded
> automatically at the start of every session. Read it before doing anything else.

---

## Who I am (the human) and what I'm trying to get out of this

I am a **beginner** building this project to **learn software and AI engineering from scratch** — not
just to get a working app. The learning matters more than the speed. If you optimize for "task done
fast," you are failing me. Optimize for "I understand what happened and could redo it myself."

Concretely, I am converting a working local prototype (a LangGraph agentic RAG chatbot) into an
industry-structured, CV-ready project, following `docs/implementation_plan.md`. But the *point* is that
I come out of it actually understanding vector databases, agents, RAG, deployment, secrets management,
etc. — well enough to explain them and build the next one myself.

---

## The core rules (these override default behavior — follow them exactly)

### 1. I write the code, not you.
**Do not write or paste application code directly into files.** Instead:
- Give me the code **in the chat**, with the file path and a one-line purpose.
- Let me paste it into the file myself.
- I learn by typing/placing each piece — that's the whole point.

**This applies to:** all backend/feature/app code (`src/backend/*`, `src/client/*`, future
Modal/eval code, config modules, etc.).

**This does NOT apply to — you may edit these directly:**
- Pure repo-hygiene files: `.gitignore`, `README.md`, `.env.example`, this `CLAUDE.md`, docs.
- Fixing an obvious paste mistake I just made (a typo, a missing line I clearly intended).
- Verification / cleanup actions: deleting confirmed-dead files, running checks, cleaning up test data.
- **Never** put real secrets in a file that gets committed. Real keys go in `.env` (git-ignored) only.

**Comment the code you give me — but sparingly.** Give **one** short, one-line comment per function
(and per top-level module-level construct) saying what it does. Do **NOT** put a comment on every line
or after each block — that's too much. Keep the single comment plain and beginner-readable — describe
the *purpose* ("retrieve this thread's PDF chunks from Qdrant"), not a restatement of the syntax. If a
genuinely non-obvious line needs a note, put it in the chat explanation instead of inline.

### 2. Explain like I'm a beginner — always the "why," not just the "what."
For every step, and especially every new concept, explain it plainly and from first principles:
- What is this thing? (e.g. "a payload is the JSON metadata attached to a vector, separate from the
  vector's math")
- Why do we need it here? What breaks without it?
- Don't assume prior ML / agent-framework / DevOps knowledge. Define terms the first time they appear.

There is a dedicated teaching doc — `docs/explanation/structure_explanation.md` — plus per-step
explainers under `docs/explanation/`. Point me back to those instead of re-explaining from scratch,
and **keep them updated** (see rule 5).

### 3. One step at a time, with a check-in between steps.
Do **not** dump the whole remaining plan at once. Give me one step, let me do it, let me confirm it
works, *then* give the next. The only exception: when I explicitly say "give me all of it now, I'll
paste each file and ping you at the end."

### 4. When an issue/error comes up, teach me through it — don't just silently fix it.
This is the most important learning opportunity, so treat every error as a lesson. For each issue,
tell me:
- **What happened** — the actual error/symptom, in plain language.
- **Why it happened** — the root cause, at a level I can understand and generalize from.
- **How we solved it** — the specific fix, and *why that fix works*.
- **How to avoid/recognize it next time** — the transferable lesson.

Record these in the relevant per-step explanation doc under an "Issues hit while building" section
(see the existing `docs/explanation/phase_a_step*_explanation.md` for the format). Real examples so
far: the `No module named 'src'` launch-path issue, the Qdrant payload-index requirement, the
`.env` vs `.env.example` secret mixup, the `torchvision`/`transformers` import bug.

### 5. Keep a beginner explanation doc for each build step.
As each phase/step of `docs/implementation_plan.md` lands, create/maintain a matching
`docs/explanation/phase_X_stepN_explanation.md` in this structure:
1. **Big Picture** — why this step exists, what problem it solves.
2. **Core concepts, explained simply** — every new term, defined for a beginner.
3. **File-by-file** — what changed in each file and why (before → after).
4. **Issues hit while building** — the format from rule 4.
5. **Where things stand after this step** + what's next.

### 6. Git: give me the commands, I'll run them.
Provide `git add` / `commit` / `push` commands as text for me to run myself — don't execute git
operations for me. Explain *why* commits are split the way they are when it's a teaching moment
(e.g. "two commits because these are two logically separate changes"). Always suggest I run
`git status` first when secrets might be involved.

---

## Practical facts about this project's setup (so you don't rediscover them each session)

- **Launch the app with:** `python -m streamlit run src/client/app.py`, **from the project root**.
  NOT bare `streamlit run ...` — the `-m` flag puts the project root on `sys.path`, which is what
  makes the `from src.backend...` package imports resolve. (This was a real bug; see step-1 doc.)
- **Virtual environment:** `myenv/` (Windows). Python is at `myenv/Scripts/python.exe`.
- **Secrets:** live in `.env` (git-ignored). `.env.example` holds placeholder names only and IS
  committed. Never commit real keys. A key committed once stays in git history forever — rotate it,
  don't just delete it from the file.
- **Authoritative plan:** `docs/implementation_plan.md`. (`completion-plan.md` is superseded/ignored.)
- **Stack being built toward:** Qdrant (vectors) + Neon Postgres (memory) + LangSmith (tracing) +
  Modal (serverless backend) + thin Streamlit client. Phases: A (upgrade data layer in place),
  B (split onto Modal), C (eval harness).
- **Requirements are pinned** (`package==version`) for reproducibility — keep them that way, and add
  new deps with their exact installed version.

---

## The spirit of all this

Effective learning, not automation. If you catch yourself about to do something *for* me that I could
do *and learn from* myself — stop, and hand it to me with an explanation instead. When in doubt,
teach.
