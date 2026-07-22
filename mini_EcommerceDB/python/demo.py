"""
End-to-end walkthrough of the mini e-commerce backend against the seeded
database: register a user, browse products, add to cart, check out, pay,
and view order history.

Run: python python/demo.py   (after `docker compose up -d` and seeding)
"""
from mini_ecommerce.exceptions import DuplicateEmailError, OutOfStockError
from mini_ecommerce.repositories.cart_repository import CartRepository
from mini_ecommerce.repositories.category_repository import CategoryRepository
from mini_ecommerce.repositories.order_repository import OrderRepository
from mini_ecommerce.repositories.product_repository import ProductRepository
from mini_ecommerce.repositories.user_repository import UserRepository
from mini_ecommerce.services.checkout_service import CheckoutService


def main():
    users = UserRepository()
    categories = CategoryRepository()
    products = ProductRepository()
    carts = CartRepository()
    orders = OrderRepository()
    checkout = CheckoutService()

    # 1. Register (or reuse) a customer.
    try:
        user_id = users.create("Demo Shopper", "demo.shopper@example.com", "hash")
        print(f"Registered new user #{user_id}")
    except DuplicateEmailError:
        user_id = users.get_by_email("demo.shopper@example.com").user_id
        print(f"Reusing existing user #{user_id}")

    # 2. Browse a category.
    electronics = next(c for c in categories.list_all() if c.name == "Electronics")
    catalog = products.list_by_category(electronics.category_id)
    print(f"\n{electronics.name} catalog:")
    for p in catalog:
        print(f"  #{p.product_id} {p.name:<25} ₹{p.price:>8}  stock={p.stock_quantity}")

    # 3. Add to cart.
    cart_id = carts.get_or_create_cart(user_id)
    first_product = catalog[0]
    carts.add_item(cart_id, first_product.product_id, 2)
    print(f"\nAdded 2x {first_product.name} to cart #{cart_id}")

    # 4. Checkout.
    try:
        result = checkout.checkout(user_id, cart_id)
        print(f"Checked out -> order #{result.order_id}, total ₹{result.total_amount}")
    except OutOfStockError as exc:
        print(f"Checkout failed: {exc}")
        return

    # 5. Pay.
    success = checkout.pay(result.order_id, result.total_amount, method="card")
    print(f"Payment {'succeeded' if success else 'failed'}")

    # 6. Order history.
    print(f"\nOrder history for user #{user_id}:")
    for order in orders.list_by_user(user_id):
        print(f"  #{order.order_id}  status={order.status}  total=₹{order.total_amount}")


if __name__ == "__main__":
    main()
