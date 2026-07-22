"""Module 8 Phase H -- Certificates. Issuance is gated on having no
outstanding fee balance, enforced here rather than left to the UI."""
import uuid

from ems.exceptions import PaymentRequiredError
from ems.repositories.certificate_repository import CertificateRepository
from ems.repositories.payment_repository import PaymentRepository


class CertificateService:
    def __init__(self, payment_repo=None, certificate_repo=None):
        self.payment_repo = payment_repo or PaymentRepository()
        self.certificate_repo = certificate_repo or CertificateRepository()

    def issue(self, student_id: int, cert_type: str) -> dict:
        if self.payment_repo.has_unpaid_invoice(student_id):
            raise PaymentRequiredError(
                f"Student {student_id} has an outstanding fee balance -- "
                "certificate cannot be issued until all semesters are paid"
            )
        code = f"CERT-{uuid.uuid4().hex[:12].upper()}"
        certificate_id = self.certificate_repo.issue(student_id, cert_type, code)
        return {"certificate_id": certificate_id, "verification_code": code}
