# Interactive Learning Guide

This project is set up so you can learn relational-database concepts by
*doing* — one `make` command at a time — instead of only reading SQL. Every
command prints the HTTP call it's making and the SQL/transaction happening
underneath it, and you're encouraged to drop into `make db-shell` between
steps to see the actual rows change.

Requires: `docker`, `make`, `curl`, `jq` (only `jq` isn't preinstalled on
most systems — `sudo apt install jq` / `brew install jq`).

Full command reference: `make help`. This document is the guided tour —
what to run, in what order, and *why*, mapped back to the database concept
each step teaches.

---

## Stage 0 — Start the environment

```bash
make up
```

**What happens:** `docker compose` starts two containers — `mysql` and
`backend` — on a shared Docker network. The `backend` container has
`depends_on: mysql: condition: service_healthy` in `docker-compose.yml`,
so it won't even start until MySQL's healthcheck passes. On MySQL's
*first* boot, it automatically executes every `.sql` file mounted into
`/docker-entrypoint-initdb.d/` — that's `sql/01_schema.sql` then
`sql/02_seed.sql` — which is why the database already has tables and
sample data the moment `make up` finishes.

**Concept:** container startup ordering and dependency health, and how a
database image bootstraps a schema on first run (this only happens once
per volume — that's why `make reset` deletes the volume to start clean).

---

## Stage 1 — Look at the schema before touching the API

```bash
make db-tables
make db-describe TABLE=products
make db-describe TABLE=order_items
make db-shell        # then: SELECT * FROM users; SELECT * FROM products;
```

**What happens:** `db-describe` runs `DESCRIBE <table>`, showing you each
column's type, nullability, and key role (`PRI`, `MUL`, `UNI`) straight
from MySQL's own catalog — not from documentation that can drift out of
date. `db-shell` drops you into a real `mysql` client inside the
container.

**Concept:** this is the schema from `sql/01_schema.sql` made concrete —
primary keys (`PRI`), foreign keys (`MUL` — indexed, "multiple" rows can
share a value), and unique constraints (`UNI`) are things you can *see*,
not just read about. Compare what you see here against the ER diagram in
`docs/02_er_diagram.md`.

**Try it:** run `SELECT * FROM payments;` in `db-shell` right now — it's
empty. Come back and re-run it after Stage 3's checkout+pay steps and
watch a row appear.

---

## Stage 2 — Indexes and `EXPLAIN`

```bash
make explain
```

**What happens:** this runs `EXPLAIN` on the four query patterns the app
actually uses (browse by category, order history, order line items,
login by email) and shows MySQL's query plan for each — which index it
picked, and how many rows it expects to scan.

**Concept:** an index turns "scan every row" (`type: ALL`) into "jump
straight to the matching rows" (`type: ref` or `const`). The order-history
query is the interesting one: it's indexed on `(user_id, created_at)` — a
*composite* index — specifically so `ORDER BY created_at DESC` doesn't
need a separate sort step (`Using filesort`) after the lookup. Full
writeup with before/after evidence: `docs/03_optimization.md`.

---

## Stage 3 — Walk the business flow, one HTTP call at a time

Each of these is one `make` target = one HTTP request = one (or a few)
SQL statements. Your session persists across calls via a cookie file
(`.cookies.txt`) that `make` writes and reads automatically — that's how
`make cart` knows *whose* cart to show without you passing a user id
around.

| # | Command | HTTP call | SQL underneath | Concept |
|---|---------|-----------|-----------------|---------|
| 1 | `make register` | `POST /api/register` | `INSERT INTO users (...)` | Primary key auto-increment; `UNIQUE(email)` constraint |
| 1b | `make login EMAIL=... PASSWORD=...` | `POST /api/login` | `SELECT * FROM users WHERE email = ...`, then `INSERT` if not found | Point lookup on a unique index; demo mode skips the password check and auto-creates unknown emails (see Stage 4's "duplicate email" test, which still applies to `/api/register`) |
| 2 | `make categories` | `GET /api/categories` | `SELECT * FROM categories` | Plain table scan (it's a tiny table — no index needed) |
| 3 | `make products CATEGORY=1` | `GET /api/products?category_id=1` | `SELECT * FROM products WHERE category_id = 1` | Foreign key column doubling as a filter, backed by `idx_products_category` |
| 4 | `make cart-add PRODUCT=1 QTY=2` | `POST /api/cart/items` | `INSERT ... ON DUPLICATE KEY UPDATE quantity = quantity + 2` | Upsert pattern — the `UNIQUE(cart_id, product_id)` constraint is what makes "add the same product twice" *increment* instead of duplicate |
| 5 | `make cart` | `GET /api/cart` | `cart_items JOIN products` | A join, because a cart line only stores `product_id` + `quantity` — the name and price are looked up live |
| 6 | `make checkout` | `POST /api/checkout` | `SELECT ... FOR UPDATE`, then `INSERT` into `orders` + `order_items`, `DELETE FROM cart_items` — **one transaction** | Atomicity + row locking (see Stage 4) |
| 7 | `make pay ORDER=<id>` | `POST /api/orders/<id>/pay` | `INSERT ... ON DUPLICATE KEY UPDATE` into `payments`; on success, `UPDATE orders SET status='paid'` | A second, separate transaction — see why in Stage 4 |
| 8 | `make orders` | `GET /api/orders` | `orders JOIN order_items JOIN payments` | A three-table join, and why `order_items.unit_price` is a stored snapshot rather than a live lookup (`docs/02_er_diagram.md`) |

Run them in order once, then go back to `make db-shell` and
`SELECT * FROM orders; SELECT * FROM order_items; SELECT * FROM payments;`
to see exactly what each step wrote.

---

## Stage 4 — Break it on purpose

The interesting part of a database isn't the happy path — it's what
happens when a constraint is violated or a transaction can't complete.
Each of these is designed to fail, on purpose, so you can watch the
failure mode:

```bash
# Duplicate email -> UNIQUE constraint violation, surfaced as HTTP 409
make register EMAIL=asha@example.com

# Add a product that doesn't exist -> FK constraint violation, HTTP 404
curl -sS -b .cookies.txt -X POST http://localhost:5000/api/cart/items \
  -H 'Content-Type: application/json' -d '{"product_id":99999,"quantity":1}' | jq .

# Out of stock -> checkout raises OutOfStockError, HTTP 409, and the
# ENTIRE transaction rolls back (nothing is partially applied)
make cart-add PRODUCT=4 QTY=9999
make checkout
make db-describe TABLE=products     # stock_quantity for product 4 is unchanged -- proof of rollback

# Declined payment -> order stays 'pending', is retryable
make pay ORDER=<id> SIMULATE_FAILURE=true
make orders                         # status: pending, payment.status: failed
make pay ORDER=<id>                 # retry for real -- same order, same payment row
make orders                         # status: paid
```

**Concept, out-of-stock case:** `checkout_service.checkout()`
(`python/mini_ecommerce/services/checkout_service.py`) opens one
connection, takes `SELECT ... FOR UPDATE` locks on the cart and product
rows, and only commits after *every* line succeeds. If any line is out of
stock, the whole connection is rolled back — including lines that *would*
have succeeded. Run `make cart-add` with two products (one in stock, one
not) and `make checkout`, then check both products' stock in `db-shell` —
neither changed.

**Concept, declined payment:** checkout and payment are deliberately
**two separate transactions** (see the module docstring in
`checkout_service.py`). A payment gateway is a slow external call — you
don't want to hold database locks open while waiting on it. That's why a
decline doesn't undo the order: the order and stock decrement already
committed in Stage 3; only the `payments` row and `orders.status` are
touched by `pay`. This is also why retrying payment for the same order
had to be built as an *upsert* (`INSERT ... ON DUPLICATE KEY UPDATE`) in
`payment_repository.py` — `payments.order_id` is `UNIQUE`, so a naive
second `INSERT` would crash. (This was a real bug caught by clicking
through the UI, not a hypothetical — see the README's "What each failure
test proves" section.)

---

## Stage 5 — See it all happen automatically

```bash
make demo
```

Runs Stages 3 end-to-end against a fresh, randomly-generated account, so
it's safe to re-run as many times as you like. Read `scripts/api_walkthrough.sh`
alongside the output — it's the same eight calls from the table above,
just scripted with narration.

## Stage 6 — Verify your understanding against the test suite

```bash
make test
```

Every failure mode from Stage 4 has a corresponding automated test in
`tests/` (see the mapping table in the README). Reading a test after
you've triggered the same failure by hand is a good way to check your
mental model against the actual assertions — e.g.
`tests/test_checkout.py::test_checkout_with_multiple_products_one_out_of_stock_rolls_back_both`
is exactly the two-product rollback you triggered above, asserted in code.

`make test` truncates every table (that's how the tests stay independent
of each other). Run `make reseed` afterward to get the demo catalog back,
or `make reset` for a full clean slate.

---

## Cheat sheet

```
make up                    start everything
make demo                  watch the full lifecycle, narrated
make db-shell               poke at the raw tables yourself
make explain                see the query plans
make register / login       STEP 1
make categories / products  STEP 2-3  (browse)
make cart-add / cart        STEP 4-5  (build a cart)
make checkout / pay         STEP 6-7  (the transactional core)
make orders                 STEP 8    (see what you bought)
make test                   run the automated tests (truncates tables)
make reseed                  put the demo data back
make reset                   nuke everything and start over
```
