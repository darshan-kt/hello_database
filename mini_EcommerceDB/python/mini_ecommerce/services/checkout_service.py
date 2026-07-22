"""
Module 6: Checkout (the transactional heart of the project).

Design note: stock reservation + order creation is one ACID transaction.
Payment is deliberately a *separate* step performed after that transaction
commits. Real payment gateways are slow, external HTTP calls -- holding a
database transaction (and its row locks) open while waiting on a gateway
would block every other checkout touching the same products. So:

  1. checkout()  -> atomic: lock cart + stock, create order+order_items,
                    decrement stock, clear cart. Rolls back entirely on
                    any failure (out of stock, empty cart, missing product).
  2. pay()       -> attempts payment against an already-created order.
                    Failure leaves the order in 'pending' (retryable);
                    success moves it to 'paid'. This step does not touch
                    stock, so it never needs to roll back the checkout.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Optional

from mini_ecommerce.db.connection import get_pool
from mini_ecommerce.exceptions import EmptyCartError
from mini_ecommerce.repositories.cart_repository import CartRepository
from mini_ecommerce.repositories.order_repository import OrderRepository
from mini_ecommerce.repositories.payment_repository import PaymentRepository
from mini_ecommerce.repositories.product_repository import ProductRepository

# A payment processor takes (amount, method) and returns True on success.
# Swap this for a real gateway client in production; tests inject a fake
# that returns False to exercise the "failed payment" path.
PaymentProcessor = Callable[[Decimal, str], bool]


def always_succeeds(amount: Decimal, method: str) -> bool:
    return True


@dataclass
class CheckoutResult:
    order_id: int
    total_amount: Decimal


class CheckoutService:
    def __init__(
        self,
        cart_repo: Optional[CartRepository] = None,
        product_repo: Optional[ProductRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        payment_repo: Optional[PaymentRepository] = None,
    ):
        self.cart_repo = cart_repo or CartRepository()
        self.product_repo = product_repo or ProductRepository()
        self.order_repo = order_repo or OrderRepository()
        self.payment_repo = payment_repo or PaymentRepository()

    def checkout(self, user_id: int, cart_id: int) -> CheckoutResult:
        """Atomically turn a cart into a pending order.

        Raises EmptyCartError, OutOfStockError, or ProductNotFoundError and
        leaves the database untouched (full rollback) if anything fails.
        """
        conn = get_pool().get_connection()
        try:
            items = self.cart_repo.list_items_locked(conn, cart_id)
            if not items:
                raise EmptyCartError(f"Cart {cart_id} has no items to check out")

            total = Decimal("0")
            priced_lines = []
            for item in items:
                product = self.product_repo.lock_for_update(conn, item.product_id)
                self.product_repo.decrement_stock(conn, item.product_id, item.quantity)
                line_total = product.price * item.quantity
                total += line_total
                priced_lines.append((item.product_id, item.quantity, product.price))

            order_id = self.order_repo.create(conn, user_id, total)
            for product_id, quantity, unit_price in priced_lines:
                self.order_repo.add_item(conn, order_id, product_id, quantity, unit_price)

            self.cart_repo.clear(conn, cart_id)

            conn.commit()
            return CheckoutResult(order_id=order_id, total_amount=total)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def pay(
        self,
        order_id: int,
        amount: Decimal,
        method: str,
        processor: PaymentProcessor = always_succeeds,
    ) -> bool:
        """Attempt payment for an already-created order.

        Returns True/False for success; always leaves the order and
        payment rows in a consistent state (no exception on decline --
        a declined card is an expected outcome, not a system error).
        """
        conn = get_pool().get_connection()
        try:
            success = processor(amount, method)
            status = "success" if success else "failed"
            self.payment_repo.create(conn, order_id, amount, method, status)
            if success:
                self.order_repo.set_status(conn, order_id, "paid")
            conn.commit()
            return success
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
