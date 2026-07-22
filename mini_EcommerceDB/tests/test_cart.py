def test_add_item_creates_line(cart_repo, sample_user_id, sample_product_id):
    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    cart_repo.add_item(cart_id, sample_product_id, 2)

    lines = cart_repo.list_items(cart_id)
    assert len(lines) == 1
    assert lines[0].quantity == 2


def test_adding_same_product_twice_increments_quantity(cart_repo, sample_user_id, sample_product_id):
    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    cart_repo.add_item(cart_id, sample_product_id, 2)
    cart_repo.add_item(cart_id, sample_product_id, 3)

    lines = cart_repo.list_items(cart_id)
    assert len(lines) == 1
    assert lines[0].quantity == 5


def test_get_or_create_cart_is_idempotent(cart_repo, sample_user_id):
    cart_id_1 = cart_repo.get_or_create_cart(sample_user_id)
    cart_id_2 = cart_repo.get_or_create_cart(sample_user_id)
    assert cart_id_1 == cart_id_2


def test_remove_item(cart_repo, sample_user_id, sample_product_id):
    cart_id = cart_repo.get_or_create_cart(sample_user_id)
    cart_repo.add_item(cart_id, sample_product_id, 1)
    cart_repo.remove_item(cart_id, sample_product_id)
    assert cart_repo.list_items(cart_id) == []
