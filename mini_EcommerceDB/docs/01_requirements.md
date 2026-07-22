# Module 0 — Requirement Analysis & Domain Modeling

## Business Problem

Build the backend database for a small e-commerce platform. Customers
register, browse products by category, add products to a cart, check out,
pay, and view their order history. Admins manage products, inventory, and
order fulfillment.

## Actors

- **Customer** — registers, browses, carts, checks out, views own orders.
- **Admin** — manages categories, products, stock, and views/updates orders.

## Functional Requirements

1. A user can register with a unique email and log in.
2. A user can browse products, filtered by category.
3. A user has exactly one active cart; a cart holds many product lines.
4. Adding the same product twice to a cart increases its quantity, it does
   not create a duplicate line.
5. Checkout converts the cart into an order:
   - Stock is validated and decremented per line.
   - Order total is computed from a *snapshot* of unit price at purchase
     time (price changes later must not alter historical orders).
   - The cart is emptied.
   - All of this happens atomically — if any line fails (e.g. out of
     stock), nothing is committed.
6. A payment is attempted against the order. Failed payment leaves the
   order in a `pending` state and does not ship it; a successful payment
   moves the order to `paid`.
7. A user can list their past orders with line items and payment status.
8. An admin can create/update products and adjust stock; deleting a
   product that has order history is blocked (soft-disable instead).

## Non-Functional Requirements

- Referential integrity enforced at the database level (foreign keys),
  not just in application code.
- Money stored as `DECIMAL`, never `FLOAT`.
- Checkout must be transactional (ACID) with row-level locking to avoid
  overselling stock under concurrent checkouts.
- Query patterns that will be indexed: lookup product by category, lookup
  orders by user, lookup order items by order.

## Entities

| Entity      | Description                                   |
|-------------|------------------------------------------------|
| Users       | Registered customers/admins                    |
| Categories  | Product groupings                               |
| Products    | Sellable items, belong to one category          |
| Cart        | One active cart per user                        |
| CartItems   | Product lines inside a cart                      |
| Orders      | A checked-out cart, owned by a user              |
| OrderItems  | Immutable product/price snapshot lines of an order |
| Payments    | One payment record per order                     |

## Out of Scope (for this mini project)

- Multi-currency, tax/shipping calculation, coupons, refund workflows,
  multi-warehouse inventory. These are natural follow-ups once the core
  flow is solid.
