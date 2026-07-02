# Frontend Plan — a basic "modern chatbot" look for the Streamlit app

> Goal: make the Streamlit UI look like a typical modern chatbot (ChatGPT / Claude / Gemini style)
> **without** changing any backend logic. Kept deliberately **basic** — a clean, familiar chat layout,
> not a full custom design system. We do this *before* deploying, and carry the look into the Phase B
> Step 3 thin-client rewrite (styling is independent of where the data comes from).

---

## 1. What "modern chatbot look" means (the target)

The look almost every chatbot shares today boils down to a few things:

1. **A narrow, centered conversation column** — text sits in a readable ~700–760px column in the middle
   of the screen, not stretched edge-to-edge.
2. **Clean message rows with avatars** — each turn shows a small icon (user vs assistant) and the text,
   with comfortable spacing. Assistant answers stream in live.
3. **An input box pinned to the bottom** — rounded, always reachable, with the cursor ready.
4. **Minimal chrome** — the default Streamlit hamburger menu, the "Deploy" button, and the
   "Made with Streamlit" footer are hidden, so it feels like a product, not a dev tool.
5. **A consistent theme** — one background color, one accent color, one font, applied everywhere.
6. **A simple sidebar** — "New chat" button + past conversations list (we already have this).

That's it. No animations, no custom component libraries — just the familiar, tidy chat feel.

---

## 2. Design decisions (basic, opinionated defaults)

| Decision | Choice (basic) | Why |
|---|---|---|
| Theme mode | **Dark** with a soft accent (e.g. indigo/violet) | Most modern chat UIs default dark; easy on the eyes. Easy to switch to light later. |
| Accent color | one primary color (e.g. `#7C5CFC`) | Used for buttons, highlights — a single accent reads as "designed". |
| Font | Streamlit's default sans / or "Inter"-like sans | Clean, neutral, chatbot-standard. |
| Layout | **centered** column, max-width ~760px | The signature chatbot reading column. |
| Avatars | emoji or simple icons (🧑 / 🤖) | Zero dependencies, instantly recognizable. |
| Chrome | hide menu + footer + top toolbar | Makes it feel like a finished app. |

Everything here is a value you can tweak in one place later — the plan is structured so colors/width are
easy to change.

---

## 3. Files we'll touch (and what each is for)

1. **`.streamlit/config.toml`** *(new)* — Streamlit's built-in **theme** file. Sets base mode
   (dark/light), primary/background/text colors, and font. This is the "official," update-safe way to
   theme; it colors all the standard widgets automatically. No Python involved.
2. **`src/client/app.py`** *(edit — small, surgical)* — three UI-only touches:
   - `st.set_page_config(...)`: page title, an emoji icon, `layout="centered"`.
   - A **small CSS block** via `st.markdown(..., unsafe_allow_html=True)` to: hide the menu/footer/toolbar,
     constrain the max content width, and round/space the chat input.
   - Add **avatars** to the existing `st.chat_message("user"/"assistant")` calls.
   > Only presentation lines change. The data flow (`chatbot.stream`, ingest, thread loading) is left
   > exactly as-is now, and will be swapped to HTTP in Step 3 independently.

No backend files (`src/backend/*`, `modal_app.py`) are touched at all.

---

## 4. Step-by-step build order (small steps, check-in between each)

**Step F1 — Theme file.**
Create `.streamlit/config.toml` with the dark theme + accent color + font. Run the app locally and
confirm the whole UI recolors (sidebar, buttons, input) with no code change. *Teaches: Streamlit theming
is config, not code.*

**Step F2 — Page config + centered column.**
Set `st.set_page_config` (title, icon, `layout="centered"`) and confirm the conversation sits in a narrow
centered column. *Teaches: `set_page_config` must be the first Streamlit call.*

**Step F3 — Hide Streamlit chrome + width/input polish.**
Add the small CSS block to hide the menu/footer/toolbar, cap content width, and round the input. Confirm
it now reads like a product. *Teaches: how/where custom CSS is injected in Streamlit, and its trade-offs
(CSS targets Streamlit's classes, which can change between versions — so keep it minimal).*

**Step F4 — Avatars on chat messages.**
Add `avatar=` to the user/assistant `st.chat_message(...)` calls so each turn has an icon. Confirm the
familiar chat-row look. *Teaches: the difference between the message container and its content.*

**(Optional) Step F5 — tiny extras**, only if wanted: a one-line header/subtitle, a "typing…"/spinner
while the first token loads, or an empty-state welcome message. Skip for "just basic."

After F1–F4 the app looks like a standard modern chatbot. Each step is independently visible locally, so
you see progress immediately.

---

## 5. Deliberately out of scope (keeping it basic)

- No custom React/HTML components or third-party Streamlit component packages.
- No heavy CSS overrides that fight Streamlit's internals (brittle across versions).
- No light/dark toggle switch (we just pick dark; changing is a one-line config edit).
- No message-level actions (copy button, regenerate, feedback thumbs) — nice-to-have, later.

---

## 6. How this fits with the rest of the project

- **Done before deploy, on the current app**, because `src/client/app.py` still runs locally against the
  in-process backend — instant visual feedback loop.
- **Carried into Phase B Step 3 unchanged.** Step 3 rewrites only the *data plumbing* (in-process calls →
  HTTP to Modal). The theme file and the CSS/avatar/layout lines from this plan move over as-is, since
  they don't depend on where answers come from.
- Net result: by the time we deploy, the thin client both *looks* like a real chatbot and *is* a clean
  client/server app — a stronger portfolio piece.

---

## 7. Next action

Start at **Step F1** (the theme file). Say "start F1" (or "do F1 for me") and I'll provide the
`.streamlit/config.toml` contents + the one command to see it live.
