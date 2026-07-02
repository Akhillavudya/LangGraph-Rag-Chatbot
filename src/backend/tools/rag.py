
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from src.backend.rag.vectorstore import vector_store, thread_filter
from src.backend.rag.ingest import thread_document_metadata


@tool
def rag_tool(query: str, config: RunnableConfig) -> dict:
    """Retrieve relevant information from the uploaded PDF for this chat thread.

    Call this for any question about the uploaded document. Pass only the user's
    question as `query`; the thread is resolved automatically.
    """
    # thread_id comes from the graph's run config (set by the UI), never from the LLM — always correct.
    thread_id = config.get("configurable", {}).get("thread_id")

    if not thread_id:
        return {"error": "No thread_id available in config.", "query": query}

    # Semantic search over Qdrant, restricted to just this thread's PDF chunks.
    results = vector_store.similarity_search(query, k=4, filter=thread_filter(thread_id))

    if not results:
        return {
            "error": "No document indexed for this chat. Upload a PDF first.",
            "query": query,
        }

    context = [doc.page_content for doc in results]
    metadata = [doc.metadata for doc in results]

    return {
        "query": query,
        "context": context,
        "metadata": metadata,
        "source_file": thread_document_metadata(thread_id).get("filename"),
    }
