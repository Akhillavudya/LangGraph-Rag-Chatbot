import modal

# The Modal app: the namespace all our backend functions/endpoints live under.
app = modal.App("chatbot-backend")

# The cloud container's environment: our pinned deps + the src/ package copied in.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("src")
)

# Pulls our keys (Neon, Qdrant, HF, LangSmith, bearer token) into the container as env vars.
secrets = [modal.Secret.from_name("chatbot-secrets")]


# Builds and returns the FastAPI web app; runs once per container.
@app.function(image=image, secrets=secrets)
@modal.asgi_app()
def fastapi_app():
    import os
    from fastapi import FastAPI, Header, HTTPException, Depends, UploadFile, File, Form
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
    from langchain_core.messages import HumanMessage, AIMessage

    # Import the agent once per container (this connects to Neon/Qdrant and loads the embedder).
    from src.backend.graph import chatbot
    from src.backend.memory import retrieve_all_threads
    from src.backend.rag.ingest import ingest_pdf

    web = FastAPI()

    # Rejects any request whose Authorization header isn't our shared bearer token.
    def require_token(authorization: str = Header(None)):
        expected = os.environ["CHATBOT_API_TOKEN"]
        if authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    # Open liveness check — confirms the endpoint is reachable, no token needed.
    @web.get("/health")
    def health():
        return {"status": "ok"}

    # Returns every past thread_id so the client can build its sidebar list.
    @web.get("/threads", dependencies=[Depends(require_token)])
    def threads():
        return {"threads": retrieve_all_threads()}

    # Returns one thread's chat history (user + assistant turns) read from Neon.
    @web.get("/history", dependencies=[Depends(require_token)])
    def history(thread_id: str):
        state = chatbot.get_state(config={"configurable": {"thread_id": thread_id}})
        messages = state.values.get("messages", [])
        result = []
        for message in messages:
            if isinstance(message, HumanMessage):
                result.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage) and message.content:
                result.append({"role": "assistant", "content": message.content})
        return {"messages": result}

    # Accepts an uploaded PDF + thread_id, chunks it into Qdrant, returns an index summary.
    @web.post("/ingest", dependencies=[Depends(require_token)])
    async def ingest(thread_id: str = Form(...), file: UploadFile = File(...)):
        file_bytes = await file.read()
        return ingest_pdf(file_bytes, thread_id=thread_id, filename=file.filename)

    # Describes the JSON body the client must POST: a message and which thread it belongs to.
    class ChatRequest(BaseModel):
        message: str
        thread_id: str

    # Runs the agent and streams only the assistant's tokens back as they're generated.
    @web.post("/chat", dependencies=[Depends(require_token)])
    def chat(req: ChatRequest):
        config = {
            "configurable": {"thread_id": req.thread_id},
            "metadata": {"thread_id": req.thread_id},
            "run_name": "chat_turn",
        }

        # Generator: yield each assistant token chunk as the graph produces it.
        def token_stream():
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=req.message)]},
                config=config,
                stream_mode="messages",
            ):
                if isinstance(message_chunk, AIMessage) and message_chunk.content:
                    yield message_chunk.content

        return StreamingResponse(token_stream(), media_type="text/plain")

    return web