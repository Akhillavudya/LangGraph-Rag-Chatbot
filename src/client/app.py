import os
import uuid
import requests
import streamlit as st

st.set_page_config(
    page_title="Sage",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

# UI-only CSS: hide Streamlit chrome, cap the reading width, round the chat input
st.markdown(
    """
    <style>
      /* hide the top-right hamburger menu, the "Deploy" button, and the footer */
      #MainMenu {visibility: hidden;}
      footer {visibility: hidden;}
      [data-testid="stToolbar"] {display: none;}

      /* keep the conversation in a narrow, centered reading column */
      .block-container {max-width: 760px; padding-top: 2.5rem;}

      /* round the chat input box a little */
      [data-testid="stChatInput"] {border-radius: 12px;}

      /* force the sidebar to stay open and visible (override any collapsed state) */
      section[data-testid="stSidebar"] {
        display: flex !important;
        visibility: visible !important;
        transform: none !important;
        margin-left: 0 !important;
        min-width: 260px !important;
        width: 260px !important;
      }
      /* keep the little arrow that reopens the sidebar visible too */
      [data-testid="stSidebarCollapsedControl"],
      [data-testid="collapsedControl"] {
        display: block !important;
        visibility: visible !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

#*******************************backend config *************************

# Read the backend URL + token from st.secrets (local file) or environment (Streamlit Cloud).
API_URL = (st.secrets.get("MODAL_ENDPOINT_URL") or os.getenv("MODAL_ENDPOINT_URL", "")).rstrip("/")
TOKEN = st.secrets.get("CHATBOT_API_TOKEN") or os.getenv("CHATBOT_API_TOKEN", "")
AUTH = {"Authorization": f"Bearer {TOKEN}"}

if not API_URL or not TOKEN:
    st.error("Missing MODAL_ENDPOINT_URL or CHATBOT_API_TOKEN in secrets.")
    st.stop()

#*******************************HTTP helpers (talk to Modal) ***********

# Fetch every past thread_id from the backend for the sidebar list.
def get_threads():
    resp = requests.get(f"{API_URL}/threads", headers=AUTH, timeout=30)
    resp.raise_for_status()
    return resp.json()["threads"]

# Fetch one thread's chat history (already filtered to user/assistant text server-side).
def get_history(thread_id):
    resp = requests.get(f"{API_URL}/history", params={"thread_id": thread_id}, headers=AUTH, timeout=30)
    resp.raise_for_status()
    return resp.json()["messages"]

# Upload a PDF's bytes to the backend, which chunks it into Qdrant for this thread.
def ingest_pdf(file_bytes, filename, thread_id):
    files = {"file": (filename, file_bytes, "application/pdf")}
    resp = requests.post(f"{API_URL}/ingest", files=files, data={"thread_id": thread_id}, headers=AUTH, timeout=300)
    resp.raise_for_status()
    return resp.json()

# Stream the assistant's answer token-by-token from the backend's /chat endpoint.
def stream_chat(message, thread_id):
    with requests.post(
        f"{API_URL}/chat",
        json={"message": message, "thread_id": thread_id},
        headers=AUTH,
        stream=True,
        timeout=300,
    ) as resp:
        resp.raise_for_status()
        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                yield chunk

#*******************************utility functions **********************

# Start a fresh conversation with a new thread_id and an empty history.
def reset_chat():
    st.session_state["thread_id"] = str(uuid.uuid4())
    st.session_state["message_history"] = []

#*************************Session Setup ********************************

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4())

if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "ingested_docs" not in st.session_state:
    st.session_state["ingested_docs"] = {}

thread_key = st.session_state["thread_id"]
thread_docs = st.session_state["ingested_docs"].setdefault(thread_key, {})
selected_thread = None

#******************************Sidebar UI *****************************
st.sidebar.title("💬 Chats")

if st.sidebar.button("➕  New chat", use_container_width=True):
    reset_chat()
    st.rerun()

st.sidebar.divider()

# past conversations from the backend; labelled by a short slice of the thread id
try:
    threads = get_threads()
except Exception:
    st.sidebar.error("Can't reach backend.")
    threads = []

if not threads:
    st.sidebar.caption("No conversations yet.")
else:
    for thread_id in threads:
        if st.sidebar.button(thread_id[:8], key=f"side-thread-{thread_id}", use_container_width=True):
            selected_thread = thread_id

#*********************** Main UI *************************************

st.title("Sage")

# emoji shown next to each turn (user vs assistant)
AVATARS = {"user": "🧑", "assistant": "🤖"}

# show the PDF currently attached to this thread, like a file chip
if thread_docs:
    active_doc = list(thread_docs.values())[-1]
    st.caption(f"📎 Using `{active_doc.get('filename')}`")

# loading the conversation history
for message in st.session_state["message_history"]:
    with st.chat_message(message["role"], avatar=AVATARS.get(message["role"])):
        st.text(message["content"])

user_input = st.chat_input(
    "Ask about your document or attach a PDF",
    accept_file=True,
    file_type=["pdf"],
)

# ingest any PDF attached through the chat input into this thread
if user_input and user_input.files:
    for uploaded_pdf in user_input.files:
        if uploaded_pdf.name in thread_docs:
            st.info(f"`{uploaded_pdf.name}` already processed for this chat.")
        else:
            with st.status("Indexing PDF…", expanded=True) as status_box:
                summary = ingest_pdf(uploaded_pdf.getvalue(), uploaded_pdf.name, thread_key)
                thread_docs[uploaded_pdf.name] = summary
                status_box.update(label="✅ PDF indexed", state="complete", expanded=False)

if user_input and user_input.text:
    prompt_text = user_input.text

    st.session_state["message_history"].append({"role": "user", "content": prompt_text})
    with st.chat_message("user", avatar=AVATARS["user"]):
        st.text(prompt_text)

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):
        ai_message = st.write_stream(stream_chat(prompt_text, thread_key))

    st.session_state["message_history"].append({"role": "assistant", "content": ai_message})

st.divider()

if selected_thread:
    st.session_state["thread_id"] = selected_thread
    st.session_state["message_history"] = get_history(selected_thread)
    st.session_state["ingested_docs"].setdefault(selected_thread, {})
    st.rerun()
