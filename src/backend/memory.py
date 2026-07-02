import os

from psycopg import Connection
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver

# Neon connection string, read from .env (managed Postgres, replaces the local chatbot.db file).
NEON_URL = os.getenv("NEON_URL")

# One long-lived connection to Neon, open for the app's whole life (like the old sqlite3 conn).
# - autocommit=True: LangGraph manages its own transactions, so each write must commit on its own.
# - prepare_threshold=0: turn off psycopg's auto prepared-statements, which break through Neon's pooler.
# - row_factory=dict_row: PostgresSaver reads result columns by name, so rows must come back as dicts.
conn = Connection.connect(
    NEON_URL,
    autocommit=True,
    prepare_threshold=0,
    row_factory=dict_row,
)

# The Postgres twin of SqliteSaver: identical interface, stores checkpoints in Neon instead of a file.
checkpointer = PostgresSaver(conn)

# Create the checkpoint tables in Neon on first run; safe/idempotent to call every startup.
checkpointer.setup()


def retrieve_all_threads():
    """Return every distinct thread_id stored in the checkpointer (feeds the sidebar's thread list)."""
    all_threads = set()
    for checkpoint in checkpointer.list(None):
        all_threads.add(checkpoint.config['configurable']['thread_id'])

    return list(all_threads)


def delete_thread(thread_id):
    """Remove all checkpoints for a single thread_id from the checkpointer."""
    checkpointer.delete_thread(str(thread_id))