import pytest

from mini_ecommerce.exceptions import DuplicateEmailError


def test_create_user(user_repo):
    user_id = user_repo.create("Asha Rao", "asha@example.com", "hashed-pw")
    user = user_repo.get_by_id(user_id)
    assert user.name == "Asha Rao"
    assert user.email == "asha@example.com"
    assert user.role == "customer"


def test_duplicate_email_rejected(user_repo):
    user_repo.create("Asha Rao", "asha@example.com", "hashed-pw")
    with pytest.raises(DuplicateEmailError):
        user_repo.create("Asha Impersonator", "asha@example.com", "other-hash")


def test_get_by_email_missing_returns_none(user_repo):
    assert user_repo.get_by_email("nobody@example.com") is None
