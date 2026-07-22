"""
Flask API + static UI host for the mini e-commerce backend.

This is a thin HTTP layer over the repository/service classes built in
Module 3-6 -- it does not contain business logic itself, it translates
HTTP requests into repository/service calls and domain exceptions into
HTTP status codes.
"""
import dataclasses
import hashlib
import os
from datetime import datetime
from decimal import Decimal
from functools import wraps

from flask import Flask, jsonify, request, session
from flask.json.provider import DefaultJSONProvider

from mini_ecommerce.exceptions import (
    DuplicateEmailError,
    EmptyCartError,
    MiniEcommerceError,
    OutOfStockError,
    ProductNotFoundError,
)
from mini_ecommerce.repositories.cart_repository import CartRepository
from mini_ecommerce.repositories.category_repository import CategoryRepository
from mini_ecommerce.repositories.order_repository import OrderRepository
from mini_ecommerce.repositories.payment_repository import PaymentRepository
from mini_ecommerce.repositories.product_repository import ProductRepository
from mini_ecommerce.repositories.user_repository import UserRepository
from mini_ecommerce.services.checkout_service import CheckoutService


class JSONProvider(DefaultJSONProvider):
    """Teach Flask's JSON encoder about Decimal (money) and datetime
    (timestamps) -- both come straight out of MySQL rows via the
    repositories and are not JSON-serializable by default."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


app = Flask(__name__, static_folder="static", static_url_path="")
app.json = JSONProvider(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

users = UserRepository()
categories = CategoryRepository()
products = ProductRepository()
carts = CartRepository()
orders = OrderRepository()
payments = PaymentRepository()
checkout_service = CheckoutService()


def hash_password(raw: str) -> str:
    # SHA-256 for demo simplicity. A real system would use bcrypt/argon2
    # with a per-user salt; called out explicitly so it's not mistaken
    # for a production-ready choice.
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Not logged in"), 401
        return fn(*args, **kwargs)

    return wrapper


@app.errorhandler(MiniEcommerceError)
def handle_domain_error(exc: MiniEcommerceError):
    status = 400
    if isinstance(exc, DuplicateEmailError):
        status = 409
    elif isinstance(exc, ProductNotFoundError):
        status = 404
    elif isinstance(exc, OutOfStockError):
        status = 409
    elif isinstance(exc, EmptyCartError):
        status = 400
    return jsonify(error=str(exc), type=type(exc).__name__), status


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    return jsonify(status="ok")


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------
@app.post("/api/register")
def register():
    data = request.get_json(force=True)
    name, email, password = data.get("name"), data.get("email"), data.get("password")
    if not name or not email or not password:
        return jsonify(error="name, email and password are required"), 400
    user_id = users.create(name, email, hash_password(password))
    session["user_id"] = user_id
    return jsonify(user_id=user_id, name=name, email=email), 201


@app.post("/api/login")
def login():
    """Demo mode: any email/password combination logs you in. If the
    email doesn't belong to an existing account, one is created on the
    spot -- this is a learning sandbox, not a real auth system, so
    there's no password to get wrong."""
    data = request.get_json(force=True)
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    if not email:
        return jsonify(error="email is required"), 400

    user = users.get_by_email(email)
    if user is None:
        display_name = email.split("@")[0].replace(".", " ").replace("_", " ").title() or "Guest"
        try:
            users.create(display_name, email, hash_password(password))
        except DuplicateEmailError:
            pass  # lost a race with another request creating the same email
        user = users.get_by_email(email)

    session["user_id"] = user.user_id
    return jsonify(user_id=user.user_id, name=user.name, email=user.email)


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@require_login
def me():
    user = users.get_by_id(session["user_id"])
    return jsonify(user_id=user.user_id, name=user.name, email=user.email)


# ---------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------
@app.get("/api/categories")
def list_categories():
    return jsonify([dataclasses.asdict(c) for c in categories.list_all()])


@app.get("/api/products")
def list_products():
    category_id = request.args.get("category_id", type=int)
    items = products.list_by_category(category_id) if category_id else products.list_all()
    return jsonify([dataclasses.asdict(p) for p in items])


# ---------------------------------------------------------------------
# Cart
# ---------------------------------------------------------------------
@app.get("/api/cart")
@require_login
def get_cart():
    cart_id = carts.get_or_create_cart(session["user_id"])
    lines = carts.list_items(cart_id)
    payload = [line._asdict() for line in lines]
    total = sum(line.quantity * line.unit_price for line in lines)
    return jsonify(cart_id=cart_id, items=payload, total=total)


@app.post("/api/cart/items")
@require_login
def add_cart_item():
    data = request.get_json(force=True)
    product_id = data.get("product_id")
    quantity = int(data.get("quantity", 1))
    if not product_id or quantity <= 0:
        return jsonify(error="product_id and a positive quantity are required"), 400
    cart_id = carts.get_or_create_cart(session["user_id"])
    carts.add_item(cart_id, product_id, quantity)
    return jsonify(ok=True), 201


@app.delete("/api/cart/items/<int:product_id>")
@require_login
def remove_cart_item(product_id: int):
    cart_id = carts.get_or_create_cart(session["user_id"])
    carts.remove_item(cart_id, product_id)
    return jsonify(ok=True)


# ---------------------------------------------------------------------
# Checkout & payment
# ---------------------------------------------------------------------
@app.post("/api/checkout")
@require_login
def do_checkout():
    user_id = session["user_id"]
    cart_id = carts.get_or_create_cart(user_id)
    result = checkout_service.checkout(user_id, cart_id)
    return jsonify(order_id=result.order_id, total_amount=result.total_amount), 201


@app.post("/api/orders/<int:order_id>/pay")
@require_login
def pay_order(order_id: int):
    order = orders.get_by_id(order_id)
    if order is None or order.user_id != session["user_id"]:
        return jsonify(error="Order not found"), 404

    data = request.get_json(silent=True) or {}
    method = data.get("method", "card")
    simulate_failure = bool(data.get("simulate_failure", False))

    processor = (lambda amount, m: False) if simulate_failure else None
    kwargs = {"processor": processor} if processor else {}
    success = checkout_service.pay(order_id, order.total_amount, method, **kwargs)
    return jsonify(success=success, order_id=order_id)


# ---------------------------------------------------------------------
# Order history
# ---------------------------------------------------------------------
@app.get("/api/orders")
@require_login
def order_history():
    user_orders = orders.list_by_user(session["user_id"])
    result = []
    for order in user_orders:
        items = orders.list_items(order.order_id)
        payment = payments.get_by_order_id(order.order_id)
        result.append(
            {
                **dataclasses.asdict(order),
                "items": items,
                "payment": dataclasses.asdict(payment) if payment else None,
            }
        )
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
