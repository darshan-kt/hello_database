from typing import Optional

from psycopg.errors import UniqueViolation

from rag.db.connection import get_connection
from rag.exceptions import DuplicateDocumentError
from rag.models import HospitalDocument


class DocumentRepository:
    def create(
        self,
        title: str,
        source_type: str,
        original_filename: str,
        file_hash: str,
        department_id: Optional[int] = None,
        uploaded_by: Optional[int] = None,
    ) -> int:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO hospital_documents
                               (title, source_type, original_filename, file_hash, department_id, uploaded_by)
                           VALUES (%s, %s, %s, %s, %s, %s) RETURNING document_id""",
                        (title, source_type, original_filename, file_hash, department_id, uploaded_by),
                    )
                    return cur.fetchone()["document_id"]
        except UniqueViolation as exc:
            # The failed INSERT's transaction is already rolled back by
            # get_connection()'s __exit__ at this point (it propagated
            # out of the `with` block above) -- looking up the existing
            # document has to happen in a *new* connection/transaction,
            # not the aborted one. Trying to reuse it raises
            # InFailedSqlTransaction, a real bug caught by actually
            # re-uploading a duplicate file, not a hypothetical.
            existing = self.get_by_file_hash(file_hash)
            raise DuplicateDocumentError(
                f"This exact file was already uploaded as document "
                f"#{existing['document_id']} ({existing['title']!r})"
            ) from exc

    def get_by_file_hash(self, file_hash: str) -> Optional[dict]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT document_id, title FROM hospital_documents WHERE file_hash = %s",
                    (file_hash,),
                )
                return cur.fetchone()

    def get_by_id(self, document_id: int) -> Optional[HospitalDocument]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM hospital_documents WHERE document_id = %s", (document_id,)
                )
                row = cur.fetchone()
                return HospitalDocument(**row) if row else None

    def list_all(self) -> list[HospitalDocument]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM hospital_documents ORDER BY uploaded_at DESC")
                return [HospitalDocument(**row) for row in cur.fetchall()]

    def list_by_department(self, department_id: int) -> list[HospitalDocument]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM hospital_documents WHERE department_id = %s ORDER BY uploaded_at DESC",
                    (department_id,),
                )
                return [HospitalDocument(**row) for row in cur.fetchall()]

    def set_status(
        self, document_id: int, status: str, error_message: Optional[str] = None
    ) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if status == "indexed":
                    cur.execute(
                        """UPDATE hospital_documents
                           SET status = %s, error_message = %s, indexed_at = now()
                           WHERE document_id = %s""",
                        (status, error_message, document_id),
                    )
                else:
                    cur.execute(
                        "UPDATE hospital_documents SET status = %s, error_message = %s WHERE document_id = %s",
                        (status, error_message, document_id),
                    )

    def delete(self, document_id: int) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM hospital_documents WHERE document_id = %s", (document_id,)
                )
