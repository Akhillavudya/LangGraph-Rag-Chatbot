# Frontend Restyle Explanation — a modern chatbot look for the Streamlit client

> Companion to `frontend-plan.md` (the plan) and `docs/explanation/structure_explanation.md`. This covers
> the UI-only restyle of `src/client/app.py` plus a new theme file — making the app look and behave like
> a typical modern chatbot (ChatGPT/Claude style) **without changing backend logic**. It also covers two
> follow-up fixes: moving PDF upload into the chat input, and stopping raw tool JSON from leaking when you
> revisit a saved conversation.

---

## 1. The Big Picture — why this step exists

The app worked, but it *looked* like a dev tool: wide edge-to-edge layout, the Streamlit hamburger/footer
chrome, a sidebar full of raw thread UUIDs, and PDF upload bolted onto the sidebar. The restyle turns it
into something that reads like a finished product: a narrow centered conversation column, a dark theme
with a single accent color, avatars on each turn, a slim ChatGPT-style sidebar, and file upload living
inside the chat bar. None of this touches how answers are produced — it's pure presentation, so it will
carry over unchanged into the Phase B Step 3 thin-client rewrite.

---

## 2. Core concepts, explained simply

### 2.1 Streamlit theming is *config*, not code
Streamlit reads `.streamlit/config.toml` at launch and repaints every built-in widget from a handful of
color values. This is the update-safe way to theme — you use Streamlit's own knobs instead of fighting its
internals with CSS. The five that matter: `base` (dark/light starting palette), `primaryColor` (the single
accent used on buttons/focus/the send arrow), `backgroundColor` (main canvas), `secondaryBackgroundColor`
(the sidebar/panels, a slightly different shade so they separate), and `textColor` — plus `font`.

### 2.2 `set_page_config` must be the first Streamlit call
`st.set_page_config(...)` locks page-level settings (title, tab icon, layout) *before* anything renders,
so it has to run before any other `st.` call or Streamlit errors. `layout="centered"` (vs `"wide"`) is
what gives the signature narrow reading column.

### 2.3 Custom CSS in Streamlit — and its trade-off
There's no official API to hide the menu/footer or cap the column width, so we inject a tiny CSS block via
`st.markdown(..., unsafe_allow_html=True)`. The catch: CSS targets Streamlit's internal class/testid names
(e.g. `[data-testid="stChatInput"]`), which **can change between Streamlit versions**. So we keep the CSS
minimal and lean on the theme file for the heavy lifting.

### 2.4 A chat message is a container, its text is the content
`st.chat_message(role, avatar=...)` creates the **row** (icon + bubble). Whatever you call *inside* it
(`st.text(...)`, `st.write_stream(...)`) is the **content**. Two separate layers — the avatar decorates the
row, not the text.

### 2.5 `st.chat_input` can accept files — and its return type changes shape
With the default `accept_file=False`, `st.chat_input` returns a plain **string**. With `accept_file=True,
file_type=["pdf"]` it returns a **`ChatInputValue`** object with two parts: `.text` (what was typed) and
`.files` (the attached `UploadedFile`s — same objects the old sidebar uploader gave us). That's why one
submit can be text-only, file-only, or both, and the handler checks `.files` and `.text` independently.

### 2.6 The checkpointer stores the agent's *full* trail — the UI must filter it
A RAG turn is saved as **four** messages, not two: your question, an empty `AIMessage` (the model deciding
to call a tool), a `ToolMessage` (the retriever's raw JSON), and the final `AIMessage` answer. The live
chat only ever shows the last one; the **revisit** path must filter out `ToolMessage`s and empty turns, or
the raw JSON leaks into the conversation.

### 2.7 Deletion must hit the database, not just the list
The sidebar is only a *view*; the source of truth is the checkpointer in Neon. Removing a thread from the
in-memory Python list alone makes it reappear next launch, because `retrieve_all_threads()` re-reads the
DB. Real deletion calls `checkpointer.delete_thread(...)`; the list/UI update is cosmetic follow-through.

---

## 3. File-by-file

### `.streamlit/config.toml` *(new)*
The theme: `base="dark"`, `primaryColor="#7C5CFC"` (indigo accent), a dark canvas `#0E1117` with a slightly
lighter sidebar `#1A1D29`, light text, sans-serif font. Change `primaryColor` in one line to re-brand.

### `src/client/app.py` *(edited — presentation + two behavior fixes)*
- **Page config:** `layout="wide"` → `"centered"`, added a `page_icon`, and renamed the bot from
  "Multi Utility Chatbot" to **"Sage"** (tab title + on-page title).
- **CSS block:** hides the hamburger menu, footer, and toolbar; caps the column at 760px; rounds the chat
  input.
- **Avatars:** an `AVATARS = {"user": "🧑", "assistant": "🤖"}` map passed as `avatar=` to all three
  `st.chat_message(...)` calls (history, user turn, assistant turn).
- **Slim sidebar:** dropped the app-title line, the thread-ID readout, the sidebar PDF status box, and the
  sidebar file uploader. What's left is ChatGPT-style: a `💬 Chats` header, a pinned `➕ New chat` button,
  a divider, then the conversation list.
- **Conversation titles from the first message:** new `thread_title(thread_id)` helper reads a thread's
  messages via the checkpointer, takes the first `HumanMessage`, collapses whitespace, and truncates to 35
  chars (falls back to "New chat" for empty threads) — replacing the raw UUID labels.
- **Per-chat delete:** each conversation row now has a `🗑` button (laid out with `st.sidebar.columns`).
  It calls `delete_thread(...)`, removes the thread from `chat_threads` and its `ingested_docs` entry,
  starts a fresh chat if you deleted the active one, and reruns.
- **Upload moved into the chat bar:** `st.chat_input(..., accept_file=True, file_type=["pdf"])`. The
  handler now (a) ingests any attached PDF (`if user_input.files:`) and (b) runs the chat turn
  (`if user_input.text:`) using a `prompt_text` variable. A `📎 Using <filename>` caption under the title
  shows the active document.
- **Leak fix on revisit:** the `selected_thread` loader now skips `ToolMessage`s and empty-content
  messages, keeping only real human/assistant text.

### `src/backend/memory.py` *(edited — one new function)*
Added `delete_thread(thread_id)`, a thin wrapper over `checkpointer.delete_thread(str(thread_id))` (the
`str(...)` converts the `uuid.UUID` to the text the DB stores). This is the only backend change; it exists
because deletion must happen where the checkpointer lives.

---

## 4. Issues hit while building

### 4.1 Raw tool JSON leaked into revisited conversations
- **What happened:** after reopening a saved chat, a big blob of JSON (retrieved chunks + metadata)
  appeared as an assistant message, sometimes preceded by a blank 🤖 bubble.
- **Why it happened:** the revisit loader mapped *every* non-human message to "assistant" and printed its
  `.content`. A RAG turn stores four messages — including the empty tool-call `AIMessage` and the raw-JSON
  `ToolMessage` — so those internal messages got rendered. The live chat never showed them because it only
  appends the final answer text.
- **How we solved it:** filter the loader — `if isinstance(msg, ToolMessage) or not str(msg.content).strip(): continue`.
- **Lesson:** the checkpointer is the agent's *complete* memory (reasoning + tool calls), not a clean chat
  transcript. Any UI that reads it back must decide which message *types* to display.

### 4.2 `ImportError: cannot import name 'delete_thread'`
- **What happened:** the app crashed at startup on `from src.backend.memory import ..., delete_thread`.
- **Why it happened:** `app.py` was wired to import `delete_thread` before that function existed in
  `memory.py`. Python resolves imports at load time — it found the module but not the name.
- **How we solved it:** added the `delete_thread` function to `memory.py`.
- **Lesson:** the mirror image of the earlier `No module named 'src'` bug — that was "can't find the
  module," this is "found the module, can't find the name inside it." When importing, confirm the name
  actually exists in the target file.

---

## 5. Where things stand + what's next

The client now looks and behaves like a standard modern chatbot: dark centered theme, avatars, a slim
ChatGPT-style sidebar with first-message titles and per-chat delete, and PDF upload inside the chat bar —
with the tool-JSON leak fixed. All of this is presentation/UX layered on the existing in-process backend,
so it carries over unchanged into **Phase B Step 3**, which swaps only the data plumbing (in-process calls
→ HTTP to the Modal backend). Next up: that thin-client rewrite and deploy.
