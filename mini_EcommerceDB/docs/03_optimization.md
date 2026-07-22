# Module 7 — Indexing & Query Optimization

Every query below was run with `EXPLAIN` against the seeded database
(`docker compose up`, `sql/01_schema.sql` + `sql/02_seed.sql`).

## 1. Browse products by category

```sql
EXPLAIN SELECT * FROM products WHERE category_id = 1 AND is_active = TRUE;
```

| type | key                    | rows | Extra       |
|------|------------------------|------|-------------|
| ref  | idx_products_category  | 3    | Using where |

`type = ref` on `idx_products_category` — MySQL jumps straight to the
matching rows instead of scanning the table (`type = ALL`).

## 2. Order history for a user, newest first

The naive index is a single-column `idx_orders_user`:

```sql
EXPLAIN SELECT * FROM orders WHERE user_id = 3 ORDER BY created_at DESC;
```

| type | key             | Extra           |
|------|-----------------|-----------------|
| ref  | idx_orders_user | Using filesort  |

The `WHERE` is indexed, but `ORDER BY created_at` still has to sort the
matching rows separately (`Using filesort`). Since order history is
*always* "this user, newest first," a **composite index**
`(user_id, created_at)` lets the index itself hand back rows in the
right order:

```sql
CREATE INDEX idx_orders_user_created ON orders(user_id, created_at);
EXPLAIN SELECT * FROM orders WHERE user_id = 3 ORDER BY created_at DESC;
```

| type | key                      | Extra                 |
|------|--------------------------|------------------------|
| ref  | idx_orders_user_created  | Backward index scan   |

`Using filesort` is gone — MySQL walks the index backward instead of
sorting. This is the index shipped in `sql/01_schema.sql`; the
single-column version was dropped since the composite index already
serves any query that filters on `user_id` alone (leftmost-prefix rule).

## 3. Order items for an order (checkout / order detail view)

```sql
EXPLAIN SELECT * FROM order_items WHERE order_id = 1;
```

| type | key                    | rows |
|------|------------------------|------|
| ref  | idx_order_items_order  | 2    |

## 4. Login lookup by email

```sql
EXPLAIN SELECT * FROM users WHERE email = 'asha@example.com';
```

| type  | key            | rows |
|-------|----------------|------|
| const | uq_users_email | 1    |

`type = const` — the `UNIQUE` constraint on `email` doubles as the
lookup index, so login is a single-row point lookup, not a scan.

## Why row locking matters more than indexing for checkout

`ProductRepository.lock_for_update` and `CartRepository.list_items_locked`
use `SELECT ... FOR UPDATE`. Without it, two concurrent checkouts reading
the same product's `stock_quantity` could both see "5 in stock," both
decide there's enough, and both commit — overselling. `FOR UPDATE` takes
an exclusive row lock at read time so the second transaction blocks until
the first commits or rolls back, then re-reads the now-current value. This
is a correctness requirement, not a performance one — it's what makes the
checkout transaction serializable with respect to stock.

## General index rules applied in this schema

- Every foreign key has a supporting index (MySQL does not add one
  automatically for the referencing side beyond what's needed for the FK
  itself; explicit indexes here also cover queries that filter on the FK
  column alone, e.g. `idx_products_category`).
- Composite indexes are ordered by (equality column, sort/range column),
  matching the leftmost-prefix rule.
- No index was added speculatively — each one maps to a query pattern
  listed in `docs/01_requirements.md`.
