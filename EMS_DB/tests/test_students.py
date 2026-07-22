import pytest

from ems.exceptions import DuplicateEmailError


def test_create_student(student_repo, sample_department_id):
    student_id = student_repo.create(sample_department_id, "Asha Rao", "asha@example.com", "hash")
    student = student_repo.get_by_id(student_id)
    assert student.name == "Asha Rao"
    assert student.email == "asha@example.com"


def test_duplicate_email_rejected(student_repo, sample_department_id):
    student_repo.create(sample_department_id, "Asha Rao", "asha@example.com", "hash")
    with pytest.raises(DuplicateEmailError):
        student_repo.create(sample_department_id, "Impersonator", "asha@example.com", "otherhash")


def test_get_by_email_missing_returns_none(student_repo):
    assert student_repo.get_by_email("nobody@example.com") is None


def test_search_by_name(student_repo, sample_department_id):
    student_repo.create(sample_department_id, "Zendaya Coleman", "zendaya@example.com", "hash")
    results = student_repo.search("Zendaya")
    assert len(results) == 1
    assert results[0].name == "Zendaya Coleman"
