
import os

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    VectorParams,
)
from langchain_qdrant import QdrantVectorStore

from src.backend.llm import embeddings
from src.backend import config  # noqa: F401  (loads .env before anything below reads it)

COLLECTION_NAME = "pdf_chunks"
EMBEDDING_DIM = 384  # output size of sentence-transformers/all-MiniLM-L6-v2
THREAD_ID_FIELD = "metadata.thread_id"

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

if not client.collection_exists(COLLECTION_NAME):
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )

# Idempotent: safe to call every startup, whether the collection is brand new
# or already existed. Qdrant needs this index to filter by thread_id at all.
client.create_payload_index(
    collection_name=COLLECTION_NAME,
    field_name=THREAD_ID_FIELD,
    field_schema=PayloadSchemaType.KEYWORD,
)

vector_store = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings,
)


def thread_filter(thread_id: str) -> Filter:
    """Qdrant filter restricting a search/scroll to one chat thread's chunks."""
    return Filter(
        must=[FieldCondition(key=THREAD_ID_FIELD, match=MatchValue(value=str(thread_id)))]
    )