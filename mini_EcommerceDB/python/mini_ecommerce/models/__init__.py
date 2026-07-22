from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class User:
    user_id: Optional[int]
    name: str
    email: str
    password_hash: str
    role: str = "customer"
    created_at: Optional[datetime] = None


@dataclass
class Category:
    category_id: Optional[int]
    name: str
    description: Optional[str] = None


@dataclass
class Product:
    product_id: Optional[int]
    category_id: int
    name: str
    price: Decimal
    stock_quantity: int
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class CartItem:
    cart_item_id: Optional[int]
    cart_id: int
    product_id: int
    quantity: int


@dataclass
class Order:
    order_id: Optional[int]
    user_id: int
    status: str
    total_amount: Decimal
    created_at: Optional[datetime] = None


@dataclass
class OrderItem:
    order_item_id: Optional[int]
    order_id: int
    product_id: int
    quantity: int
    unit_price: Decimal


@dataclass
class Payment:
    payment_id: Optional[int]
    order_id: int
    amount: Decimal
    method: str
    status: str = "pending"
    paid_at: Optional[datetime] = None
