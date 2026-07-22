from decimal import Decimal

import pytest

from mini_ecommerce.repositories.order_repository import OrderRepository
from mini_ecommerce.repositories.payment_repository import PaymentRepository
from mini_ecommerce.services.checkout_service import CheckoutService


@pytest.fixture
def checkout_service():
    return CheckoutService()


@pytest.fixture
def pending_order(cart_repo, sample_user_id, sample_product_id, checkout_service):
    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    cart_repo.add_item(cart_id, sample_product_id, 2)
    return checkout_service.checkout(sample_user_id, cart_id)


def always_fails(amount: Decimal, method: str) -> bool:
    return False


def test_successful_payment_marks_order_paid(pending_order, checkout_service):
    order_repo = OrderRepository()
    success = checkout_service.pay(
        pending_order.order_id, pending_order.total_amount, "card"
    )
    assert success is True
    assert order_repo.get_by_id(pending_order.order_id).status == "paid"


def test_failed_payment_leaves_order_pending(pending_order, checkout_service):
    order_repo = OrderRepository()
    payment_repo = PaymentRepository()

    success = checkout_service.pay(
        pending_order.order_id, pending_order.total_amount, "card", processor=always_fails
    )

    assert success is False
    assert order_repo.get_by_id(pending_order.order_id).status == "pending"
    payment = payment_repo.get_by_order_id(pending_order.order_id)
    assert payment.status == "failed"


def test_retrying_payment_after_decline_succeeds(pending_order, checkout_service):
    """A declined payment must be retryable: the UNIQUE constraint on
    payments.order_id means a naive second INSERT would raise
    IntegrityError instead of recording the retry."""
    order_repo = OrderRepository()
    payment_repo = PaymentRepository()

    first = checkout_service.pay(
        pending_order.order_id, pending_order.total_amount, "card", processor=always_fails
    )
    assert first is False

    second = checkout_service.pay(pending_order.order_id, pending_order.total_amount, "card")
    assert second is True
    assert order_repo.get_by_id(pending_order.order_id).status == "paid"
    payment = payment_repo.get_by_order_id(pending_order.order_id)
    assert payment.status == "success"
