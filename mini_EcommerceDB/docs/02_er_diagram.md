# Module 1 — Database Design (ERD, Normalization, Constraints)

## Entity-Relationship Diagram

```text
Users (1) ────< Cart (1)              Categories (1) ────< Products
  │                │                                            │
  │                └──< CartItems >───────────────────────────┘
  │
  └──< Orders (1) ────< OrderItems >───────────────────────────┘
                │
                └──(1:1)── Payments
```

Cardinalities:

- `Users 1 --- 1 Cart` (one active cart per user)
- `Cart 1 --- * CartItems`, `CartItems * --- 1 Products`
- `Users 1 --- * Orders`
- `Orders 1 --- * OrderItems`, `OrderItems * --- 1 Products`
- `Orders 1 --- 1 Payments`
- `Categories 1 --- * Products`

## Normalization

Target: **3NF**.

- **1NF**: every column atomic (no comma-separated product lists, etc.).
- **2NF**: every non-key column depends on the *whole* primary key. All
  tables here use a single-column surrogate key (`*_id`), so partial
  dependency cannot occur.
- **3NF**: no transitive dependencies. E.g. `OrderItems.unit_price` looks
  like it duplicates `Products.price`, but it is *not* a normalization
  violation — it is an intentional snapshot (see below), not a derivable
  copy that should be looked up live.

### Deliberate denormalization

- `OrderItems.unit_price` and `Orders.total_amount` are stored, not
  computed on read. Historical orders must reflect the price paid at
  purchase time, which is independent of `Products.price` after the
  fact. `total_amount` is a cached aggregate to avoid summing
  `OrderItems` on every order-history read; it is written once at
  checkout inside the same transaction, so it can never drift.

## Constraints Summary

| Table       | Key Constraints                                                        |
|-------------|--------------------------------------------------------------------------|
| Users       | PK `user_id`; UNIQUE `email`                                            |
| Categories  | PK `category_id`; UNIQUE `name`                                         |
| Products    | PK `product_id`; FK `category_id`→Categories; CHECK `price >= 0`, `stock_quantity >= 0` |
| Cart        | PK `cart_id`; FK `user_id`→Users; UNIQUE `user_id`                      |
| CartItems   | PK `cart_item_id`; FK `cart_id`→Cart, `product_id`→Products; UNIQUE `(cart_id, product_id)`; CHECK `quantity > 0` |
| Orders      | PK `order_id`; FK `user_id`→Users; CHECK `total_amount >= 0`            |
| OrderItems  | PK `order_item_id`; FK `order_id`→Orders, `product_id`→Products; CHECK `quantity > 0`, `unit_price >= 0` |
| Payments    | PK `payment_id`; FK `order_id`→Orders; UNIQUE `order_id`                |
