import os
import tempfile
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader

from src.backend.rag.vectorstore import client, vector_store, COLLECTION_NAME, thread_filter


def ingest_pdf(file_bytes: bytes, thread_id: str, filename: Optional[str] = None) -> dict:
    """
    Chunk the uploaded PDF and write it into the shared Qdrant collection,
    tagged with this chat thread's id so it can be retrieved later.

    Returns a summary dict that can be surfaced in the UI.
    """
    if not file_bytes:
        raise ValueError("No bytes received for ingestion.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(file_bytes)
        temp_path = temp_file.name

    try:
        loader = PyPDFLoader(temp_path)
        docs = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
        )
        chunks = splitter.split_documents(docs)

        summary = {
            "filename": filename or os.path.basename(temp_path),
            "documents": len(docs),
            "chunks": len(chunks),
        }

        for chunk in chunks:
            chunk.metadata["thread_id"] = str(thread_id)
            chunk.metadata["filename"] = summary["filename"]
            chunk.metadata["total_pages"] = summary["documents"]
            chunk.metadata["total_chunks"] = summary["chunks"]

        vector_store.add_documents(chunks)

        return summary
    finally:
        # Qdrant keeps its own copy of the text, so the temp file is safe to remove.
        try:
            os.remove(temp_path)
        except OSError:
            pass


def thread_has_document(thread_id: str) -> bool:
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=thread_filter(thread_id),
        limit=1,
    )
    return len(points) > 0


def thread_document_metadata(thread_id: str) -> dict:
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=thread_filter(thread_id),
        limit=1,
    )
    if not points:
        return {}

    payload = points[0].payload.get("metadata", {})
    return {
        "filename": payload.get("filename"),
        "documents": payload.get("total_pages"),
        "chunks": payload.get("total_chunks"),
    }