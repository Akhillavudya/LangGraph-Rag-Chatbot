import streamlit as st
from src.backend.graph import chatbot
from src.backend.memory import retrieve_all_threads, delete_thread
from src.backend.rag.ingest import ingest_pdf, thread_document_metadata
from langchain_core.messages import HumanMessage,AIMessage,ToolMessage
import uuid
st.set_page_config(page_title="Sage", page_icon="🤖", layout="centered")

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
    </style>
    """,
    unsafe_allow_html=True,
)
#*******************************utility functions ***********************

#generating new thread_id while click of new chat button
def generate_thread_id():
    thread_id = uuid.uuid4()
    return thread_id

#reseting previous chat and generated a new thread_id on click  new chat
def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(st.session_state['thread_id'])
    st.session_state['message_history'] = []  # clearing previous chat

#adding new thread_id in chat_threads if it does not present
def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)

def load_conversation(thread_id):
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    # Check if messages key exists in state values, return empty list if not
    return state.values.get('messages', [])

#build a short sidebar title from a thread's first user message (ChatGPT style)
def thread_title(thread_id):
    for msg in load_conversation(thread_id):
        if isinstance(msg, HumanMessage):
            text = " ".join(msg.content.split())
            return text[:35] + "…" if len(text) > 35 else text
    return "New chat"


#*************************Session Setup ***************

#create a place to store messeages
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

#first thread id generating 
if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()

# createing place store all thread_id's in chat_threads
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = retrieve_all_threads()

if "ingested_docs" not in st.session_state:
    st.session_state["ingested_docs"] = {}

add_thread(st.session_state['thread_id'])

#rag docs threads
thread_key = str(st.session_state["thread_id"])
thread_docs = st.session_state["ingested_docs"].setdefault(thread_key, {})
threads = st.session_state["chat_threads"][::-1]
selected_thread = None

#******************************Sidebar UI *********************
st.sidebar.title("💬 Chats")

# start a fresh conversation (new thread) — pinned at the top like ChatGPT
if st.sidebar.button("➕  New chat", use_container_width=True):
    reset_chat()
    st.rerun()

st.sidebar.divider()

# clean list of past conversations; label is a short slice of the thread id
if not threads:
    st.sidebar.caption("No conversations yet.")
else:
    for thread_id in threads:
        open_col, del_col = st.sidebar.columns([0.82, 0.18])
        if open_col.button(thread_title(thread_id), key=f"side-thread-{thread_id}", use_container_width=True):
            selected_thread = thread_id
        # delete just this conversation from the DB and the UI
        if del_col.button("🗑", key=f"del-thread-{thread_id}", use_container_width=True):
            delete_thread(thread_id)
            st.session_state["chat_threads"].remove(thread_id)
            st.session_state["ingested_docs"].pop(str(thread_id), None)
            if str(thread_id) == thread_key:
                reset_chat()
            st.rerun()
#*********************** Main UI ************************

st.title("Sage")

# emoji shown next to each turn (user vs assistant)
AVATARS = {"user": "🧑", "assistant": "🤖"}

# show the PDF currently attached to this thread, like a file chip
if thread_docs:
    active_doc = list(thread_docs.values())[-1]
    st.caption(f"📎 Using `{active_doc.get('filename')}`")

# loading the conversation history
for message in st.session_state['message_history']:
    with st.chat_message(message['role'], avatar=AVATARS.get(message['role'])): #Create a chat bubble in Streamlit
        st.text(message['content'])  #Displays the message on that chat bubble


user_input = st.chat_input(
    'Ask about your document or attach a PDF',
    accept_file=True,
    file_type=["pdf"],
)  #chat input box with a ChatGPT-style attach button

# ingest any PDF attached through the chat input into this thread
if user_input and user_input.files:
    for uploaded_pdf in user_input.files:
        if uploaded_pdf.name in thread_docs:
            st.info(f"`{uploaded_pdf.name}` already processed for this chat.")
        else:
            with st.status("Indexing PDF…", expanded=True) as status_box:
                summary = ingest_pdf(
                    uploaded_pdf.getvalue(),
                    thread_id=thread_key,
                    filename=uploaded_pdf.name,
                )
                thread_docs[uploaded_pdf.name] = summary
                status_box.update(label="✅ PDF indexed", state="complete", expanded=False)

if user_input and user_input.text:
    prompt_text = user_input.text

    # first add the message to message_history
    st.session_state['message_history'].append({'role': 'user', 'content': prompt_text})  #appending user message in state
    with st.chat_message('user', avatar=AVATARS["user"]):
        st.text(prompt_text)

    #helful at langSmith & calling thread_id
    CONFIG = {
        "configurable": {"thread_id": thread_key},
        "metadata": {"thread_id": thread_key},
        "run_name": "chat_turn",
    }
    
    #Assistant streaming block
    with st.chat_message('assistant', avatar=AVATARS["assistant"]):
         # Use a mutable holder so the generator can set/modify it
         status_holder = {"box": None}

       # this code for streaming using stream and write stream
         def ai_only_stream():
           for message_chunk,metadata in chatbot.stream(
              {'messages':[HumanMessage(content = prompt_text)]},
              config=CONFIG,
              stream_mode='messages'
            ):
                # Lazily create & update the SAME status container when any tool runs
                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "tool")
                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(
                            f"🔧 Using `{tool_name}` …", expanded=True
                        )
                    else:
                        status_holder["box"].update(
                            label=f"🔧 Using `{tool_name}` …",
                            state="running",
                            expanded=True,
                        )
               

               # Stream Only assistant tokens
                if isinstance(message_chunk,AIMessage):
                   yield message_chunk.content

         ai_message = st.write_stream(ai_only_stream())
         
         # Finalize only if a tool was actually used
         if status_holder["box"] is not None:
            status_holder["box"].update(
                label="✅ Tool finished", state="complete", expanded=False
            )

    # first add the message to message_history
    st.session_state['message_history'].append(
        {'role': 'assistant', 'content': ai_message}
        )  #appending ai message in session state
    
    doc_meta = thread_document_metadata(thread_key)
    if doc_meta:
        st.caption(
            f"Document indexed: {doc_meta.get('filename')} "
            f"(chunks: {doc_meta.get('chunks')}, pages: {doc_meta.get('documents')})"
        )


st.divider()

if selected_thread:
    st.session_state["thread_id"] = selected_thread
    messages = load_conversation(selected_thread)

    temp_messages = []
    for msg in messages:
        # keep only human/assistant text; skip tool outputs and empty tool-call turns
        if isinstance(msg, ToolMessage) or not str(msg.content).strip():
            continue
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        temp_messages.append({"role": role, "content": msg.content})
    st.session_state["message_history"] = temp_messages
    st.session_state["ingested_docs"].setdefault(str(selected_thread), {})
    st.rerun() 