import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool
from dotenv import load_dotenv

load_dotenv()

_pool: MySQLConnectionPool | None = None


def _build_pool() -> MySQLConnectionPool:
    return MySQLConnectionPool(
        pool_name="mini_ecommerce_pool",
        pool_size=5,
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3307")),
        database=os.getenv("DB_NAME", "mini_ecommerce"),
        user=os.getenv("DB_USER", "ecom_app"),
        password=os.getenv("DB_PASSWORD", "ecom_app_pw"),
        autocommit=False,
    )


def get_pool() -> MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = _build_pool()
    return _pool


@contextmanager
def get_connection():
    """Yield a pooled connection; commits on success, rolls back on error."""
    conn = get_pool().get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_cursor(dictionary: bool = True):
    """Yield a (connection, cursor) pair inside a managed transaction."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=dictionary)
        try:
            yield conn, cursor
        finally:
            cursor.close()
