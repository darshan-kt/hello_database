from decimal import Decimal

import pytest

from mini_ecommerce.exceptions import EmptyCartError, OutOfStockError, ProductNotFoundError
from mini_ecommerce.services.checkout_service import CheckoutService


@pytest.fixture
def checkout_service():
    return CheckoutService()


def test_checkout_happy_path(
    cart_repo, product_repo, sample_user_id, sample_product_id, checkout_service
):
    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    cart_repo.add_item(cart_id, sample_product_id, 3)

    result = checkout_service.checkout(sample_user_id, cart_id)

    assert result.total_amount == Decimal("300.00")
    assert cart_repo.list_items(cart_id) == []
    product = product_repo.get_by_id(sample_product_id)
    assert product.stock_quantity == 7  # 10 - 3


def test_checkout_empty_cart_raises(sample_user_id, cart_repo, checkout_service):
    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    with pytest.raises(EmptyCartError):
        checkout_service.checkout(sample_user_id, cart_id)


def test_checkout_out_of_stock_raises_and_rolls_back(
    cart_repo, product_repo, sample_user_id, sample_product_id, checkout_service
):
    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    cart_repo.add_item(cart_id, sample_product_id, 999)  # more than the 10 in stock

    with pytest.raises(OutOfStockError):
        checkout_service.checkout(sample_user_id, cart_id)

    # Rollback verification: stock untouched, cart line untouched, no order created.
    product = product_repo.get_by_id(sample_product_id)
    assert product.stock_quantity == 10
    assert len(cart_repo.list_items(cart_id)) == 1


def test_checkout_with_multiple_products_one_out_of_stock_rolls_back_both(
    cart_repo, product_repo, category_repo, sample_user_id, sample_product_id, checkout_service
):
    """A multi-line checkout must be all-or-nothing: if line 2 fails,
    line 1's stock decrement must also be undone."""
    category_id = category_repo.create("Other", "")
    scarce_product_id = product_repo.create(category_id, "Scarce Item", price=50, stock_quantity=1)

    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    cart_repo.add_item(cart_id, sample_product_id, 2)  # fine, 10 in stock
    cart_repo.add_item(cart_id, scarce_product_id, 5)  # only 1 in stock -> fails

    with pytest.raises(OutOfStockError):
        checkout_service.checkout(sample_user_id, cart_id)

    assert product_repo.get_by_id(sample_product_id).stock_quantity == 10
    assert product_repo.get_by_id(scarce_product_id).stock_quantity == 1
