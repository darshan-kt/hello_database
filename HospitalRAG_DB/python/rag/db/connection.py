import os
from contextlib import contextmanager

from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

_pool: ConnectionPool | None = None


def _conninfo() -> str:
    return (
        f"host={os.getenv('DB_HOST', '127.0.0.1')} "
        f"port={os.getenv('DB_PORT', '5434')} "
        f"dbname={os.getenv('DB_NAME', 'hospital_rag')} "
        f"user={os.getenv('DB_USER', 'rag_app')} "
        f"password={os.getenv('DB_PASSWORD', 'rag_app_pw')}"
    )


def _configure(conn):
    """Runs once per new pooled connection -- registers the pgvector
    type adapter so `vector(384)` columns round-trip as plain Python
    lists/numpy arrays instead of opaque strings."""
    register_vector(conn)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_conninfo(),
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            configure=_configure,
            open=True,
        )
    return _pool


@contextmanager
def get_connection():
    """Yield a pooled connection; commits on success, rolls back on error."""
    with get_pool().connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


@contextmanager
def get_cursor():
    """Yield a (connection, cursor) pair inside a managed transaction."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            yield conn, cur
