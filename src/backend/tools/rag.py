
from typing import Optional

from langchain_core.tools import tool

from src.backend.rag.vectorstore import vector_store, thread_filter
from src.backend.rag.ingest import thread_document_metadata


@tool
def rag_tool(query: str, thread_id: Optional[str] = None) -> dict:
    """
    Retrieve relevant information from the uploaded PDF for this chat thread.
    Always include the thread_id when calling this tool.
    """
    if not thread_id:
        return {"error": "No thread_id provided.", "query": query}

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