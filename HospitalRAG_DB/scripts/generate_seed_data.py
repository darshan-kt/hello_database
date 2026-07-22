"""
Module 6 seed data equivalent for this project: a small set of real
(hand-written but genuinely informative) hospital documents, ingested
through the actual IngestionService -- so seeding exercises extraction,
chunking, embedding, and pgvector storage exactly the way an admin
uploading a document through the UI would.

Usage:
    python scripts/generate_seed_data.py           # skips if already seeded
    python scripts/generate_seed_data.py --force    # wipes and reseeds
"""
import argparse
import hashlib
from pathlib import Path

from rag.db.connection import get_pool
from rag.repositories.department_repository import DepartmentRepository
from rag.repositories.document_repository import DocumentRepository
from rag.repositories.user_repository import UserRepository
from rag.security import hash_password
from rag.services.ingestion_service import IngestionService

SAMPLE_DIR = Path(__file__).parent / "sample_documents"

DEPARTMENTS = [
    ("General Medicine", "GENMED"),
    ("Cardiology", "CARDIO"),
    ("Pharmacy", "PHARM"),
    ("Infection Control", "INFCTRL"),
    ("Billing & Insurance", "BILLING"),
    ("Administration", "ADMIN"),
]

# (filename, friendly title, department code)
DOCUMENTS = [
    ("dengue_treatment_protocol.md", "Dengue Fever Treatment Protocol", "GENMED"),
    ("hypertension_management_guideline.md", "Hypertension Management Guideline", "CARDIO"),
    ("paracetamol_dosage_information.txt", "Paracetamol Dosage Information", "PHARM"),
    ("hand_hygiene_sop.md", "Hand Hygiene SOP", "INFCTRL"),
    ("insurance_preauthorization_policy.txt", "Insurance Pre-Authorization Policy", "BILLING"),
    ("discharge_summary_guidelines.md", "Discharge Summary Documentation Guidelines", "ADMIN"),
]

EXTENSION_TO_SOURCE_TYPE = {".md": "markdown", ".txt": "txt", ".pdf": "pdf"}

TABLES_IN_FK_ORDER = [
    "message_citations", "messages", "conversations", "audit_logs",
    "document_chunks", "hospital_documents", "users", "departments",
]


def already_seeded(cur) -> bool:
    cur.execute("SELECT COUNT(*) AS n FROM hospital_documents")
    return cur.fetchone()["n"] > 0


def wipe(cur):
    cur.execute(f"TRUNCATE TABLE {', '.join(TABLES_IN_FK_ORDER)} RESTART IDENTITY CASCADE")


def main(force: bool):
    pool = get_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            if already_seeded(cur) and not force:
                print("Database already has documents -- skipping. Pass --force to wipe and reseed.")
                return
            if force:
                print("==> --force: wiping existing data...")
                wipe(cur)
        conn.commit()

    department_repo = DepartmentRepository()
    user_repo = UserRepository()
    document_repo = DocumentRepository()
    ingestion_service = IngestionService()

    print("==> Departments...")
    dept_ids = {}
    for name, code in DEPARTMENTS:
        dept_ids[code] = department_repo.create(name, code)

    print("==> Admin account (admin@hospital.test / admin-123)...")
    admin_id = user_repo.create(
        "Chief Medical Informatics Officer",
        "admin@hospital.test",
        hash_password("admin-123"),
        department_id=dept_ids["ADMIN"],
        role="admin",
    )

    print("==> Demo staff account (demo.staff@hospital.test / learn-123)...")
    user_repo.create(
        "Demo Staff Nurse",
        "demo.staff@hospital.test",
        hash_password("learn-123"),
        department_id=dept_ids["GENMED"],
        role="staff",
    )

    print(f"==> Ingesting {len(DOCUMENTS)} sample documents (extract -> chunk -> embed -> store)...")
    for filename, title, dept_code in DOCUMENTS:
        path = SAMPLE_DIR / filename
        file_bytes = path.read_bytes()
        source_type = EXTENSION_TO_SOURCE_TYPE[path.suffix.lower()]

        document_id = document_repo.create(
            title=title,
            source_type=source_type,
            original_filename=filename,
            file_hash=hashlib.sha256(file_bytes).hexdigest(),
            department_id=dept_ids[dept_code],
            uploaded_by=admin_id,
        )
        result = ingestion_service.ingest(document_id, file_bytes, source_type)
        print(f"    {title}: {result['chunks_stored']} chunks stored")

    print("\nSeed complete.")
    print("  Admin login:  admin@hospital.test / admin-123")
    print("  Staff login:  demo.staff@hospital.test / learn-123")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="wipe existing data and reseed")
    args = parser.parse_args()
    main(force=args.force)
