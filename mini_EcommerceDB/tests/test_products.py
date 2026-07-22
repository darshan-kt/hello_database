import pytest

from mini_ecommerce.exceptions import ProductNotFoundError


def test_invalid_product_cannot_be_added_to_cart(cart_repo, sample_user_id):
    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    with pytest.raises(ProductNotFoundError):
        cart_repo.add_item(cart_id, product_id=999999, quantity=1)


def test_list_by_category_excludes_deactivated_products(product_repo, sample_category_id):
    product_id = product_repo.create(sample_category_id, "Old Product", price=10, stock_quantity=5)
    product_repo.deactivate(product_id)
    assert product_repo.list_by_category(sample_category_id) == []
