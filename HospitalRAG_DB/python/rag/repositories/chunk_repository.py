from typing import Optional

from pgvector import Vector

from rag.db.connection import get_connection


class ChunkRepository:
    def create(
        self,
        document_id: int,
        chunk_index: int,
        content: str,
        content_hash: str,
        token_count: int,
        embedding,
        embedding_model: str,
    ) -> Optional[int]:
        """Returns None (instead of inserting) if this exact chunk
        content was already stored for this document -- the
        UNIQUE(document_id, content_hash) constraint plus ON CONFLICT
        DO NOTHING is the dedup mechanism, not an application-side
        check, so it's race-safe."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO document_chunks
                           (document_id, chunk_index, content, content_hash, token_count,
                            embedding, embedding_model)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (document_id, content_hash) DO NOTHING
                       RETURNING chunk_id""",
                    (document_id, chunk_index, content, content_hash, token_count,
                     Vector(embedding), embedding_model),
                )
                row = cur.fetchone()
                return row["chunk_id"] if row else None

    def get_by_id(self, chunk_id: int) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.*, d.title AS document_title
                       FROM document_chunks c
                       JOIN hospital_documents d ON d.document_id = c.document_id
                       WHERE c.chunk_id = %s""",
                    (chunk_id,),
                )
                return cur.fetchone()

    def list_by_document(self, document_id: int) -> list[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM document_chunks WHERE document_id = %s ORDER BY chunk_index",
                    (document_id,),
                )
                return cur.fetchall()

    def count(self) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM document_chunks")
                return cur.fetchone()["n"]

    # -- retrieval -------------------------------------------------------

    def similarity_search(
        self, query_embedding, top_k: int = 5, department_id: Optional[int] = None
    ) -> list[dict]:
        """Cosine similarity search via pgvector's `<=>` operator
        (cosine *distance*; similarity = 1 - distance). Ordering by the
        raw operator lets the HNSW index on `embedding` do the work --
        computing similarity in a SELECT expression and sorting on that
        would not use the index. See docs/03_optimization.md.

        The query vector is wrapped in `Vector(...)` explicitly: a bare
        Python list adapts to a Postgres `double precision[]` array by
        default, and `vector <=> double precision[]` has no matching
        operator -- INSERT tolerates a plain list (assignment context
        allows an implicit cast to the target column's type), but a
        comparison in WHERE/ORDER BY does not. This was a real bug
        caught by actually running a query, not a hypothetical."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.chunk_id, c.document_id, c.chunk_index, c.content,
                              d.title AS document_title, d.department_id,
                              1 - (c.embedding <=> %(qv)s) AS similarity
                       FROM document_chunks c
                       JOIN hospital_documents d ON d.document_id = c.document_id
                       WHERE %(dept)s::bigint IS NULL OR d.department_id = %(dept)s
                       ORDER BY c.embedding <=> %(qv)s
                       LIMIT %(k)s""",
                    {"qv": Vector(query_embedding), "dept": department_id, "k": top_k},
                )
                return cur.fetchall()

    def lexical_search(self, query_text: str, top_k: int = 5) -> list[dict]:
        """Keyword (full-text) search over the same chunk store, used by
        the evaluation harness to compare semantic vs. lexical recall."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT c.chunk_id, c.document_id, c.chunk_index, c.content,
                              d.title AS document_title,
                              ts_rank(c.search_vector, plainto_tsquery('english', %s)) AS rank
                       FROM document_chunks c
                       JOIN hospital_documents d ON d.document_id = c.document_id
                       WHERE c.search_vector @@ plainto_tsquery('english', %s)
                       ORDER BY rank DESC
                       LIMIT %s""",
                    (query_text, query_text, top_k),
                )
                return cur.fetchall()
