from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings

from src.backend import config  # noqa: F401  (loads .env before anything below reads it)

# Chat LLM served by Groq's free API — supports tool-calling and streaming, reads GROQ_API_KEY from env.
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.7)

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
