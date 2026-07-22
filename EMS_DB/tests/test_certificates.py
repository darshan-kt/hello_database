from decimal import Decimal

import pytest

from ems.exceptions import PaymentRequiredError
from ems.repositories.payment_repository import PaymentRepository
from ems.services.certificate_service import CertificateService


def test_certificate_blocked_by_unpaid_invoice(sample_student_id, active_semester_id):
    PaymentRepository().create_invoice(sample_student_id, active_semester_id, Decimal("45000"))

    with pytest.raises(PaymentRequiredError):
        CertificateService().issue(sample_student_id, "transcript")


def test_certificate_issued_once_paid(sample_student_id, active_semester_id):
    payment_repo = PaymentRepository()
    payment_id = payment_repo.create_invoice(sample_student_id, active_semester_id, Decimal("45000"))
    payment_repo.mark_paid(payment_id, "card")

    result = CertificateService().issue(sample_student_id, "transcript")

    assert result["verification_code"].startswith("CERT-")


def test_certificate_issued_with_no_invoices_at_all(sample_student_id):
    """A student with zero payment history (no invoices raised yet) has
    no *unpaid* invoice either -- eligibility is "nothing outstanding,"
    not "has a receipt.\""""
    result = CertificateService().issue(sample_student_id, "completion")
    assert result["certificate_id"] is not None
