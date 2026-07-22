import pytest

from mini_ecommerce.db.connection import get_pool
from mini_ecommerce.repositories.cart_repository import CartRepository
from mini_ecommerce.repositories.category_repository import CategoryRepository
from mini_ecommerce.repositories.product_repository import ProductRepository
from mini_ecommerce.repositories.user_repository import UserRepository

TABLES_IN_FK_ORDER = [
    "payments",
    "order_items",
    "orders",
    "cart_items",
    "cart",
    "products",
    "categories",
    "users",
]


@pytest.fixture(autouse=True)
def clean_db():
    """Truncate every table before each test so tests are independent of
    seed data and of each other."""
    conn = get_pool().get_connection()
    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in TABLES_IN_FK_ORDER:
        cursor.execute(f"TRUNCATE TABLE {table}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    conn.close()
    yield


@pytest.fixture
def user_repo():
    return UserRepository()


@pytest.fixture
def category_repo():
    return CategoryRepository()


@pytest.fixture
def product_repo():
    return ProductRepository()


@pytest.fixture
def cart_repo():
    return CartRepository()


@pytest.fixture
def sample_user_id(user_repo):
    return user_repo.create("Test User", "test.user@example.com", "hash", "customer")


@pytest.fixture
def sample_category_id(category_repo):
    return category_repo.create("Test Category", "For tests")


@pytest.fixture
def sample_product_id(product_repo, sample_category_id):
    return product_repo.create(
        sample_category_id, "Test Product", price=100, stock_quantity=10
    )
