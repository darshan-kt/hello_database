#!/usr/bin/env bash
# Narrated end-to-end walkthrough of the mini e-commerce API.
# Invoked by `make demo` -- see docs/04_interactive_learning.md for what
# each step is teaching.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:5000}"
COOKIE_JAR="${COOKIE_JAR:-.cookies.txt}"

if ! command -v jq >/dev/null 2>&1; then
  echo "This script uses 'jq' to pretty-print JSON responses." >&2
  echo "Install it (e.g. 'sudo apt install jq') and re-run 'make demo'." >&2
  exit 1
fi

step() {
  echo
  echo "———— $1 ————"
  echo "$2"
  echo
}

# A fresh email each run so `make demo` is safe to re-run without hitting
# the duplicate-email constraint on users.email.
EMAIL="demo.$(date +%s)@example.com"

echo "############################################################"
echo "# Full lifecycle demo -- fresh account: $EMAIL"
echo "############################################################"

step "STEP 1/8 -- Register" "POST /api/register   ->   INSERT INTO users (name, email, password_hash, ...)"
curl -sS -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE_URL/api/register" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"Demo Learner\",\"email\":\"$EMAIL\",\"password\":\"learn-123\"}" | jq .

step "STEP 2/8 -- Browse categories" "GET /api/categories   ->   SELECT * FROM categories"
curl -sS "$BASE_URL/api/categories" | jq .

step "STEP 3/8 -- Browse Electronics products" \
  "GET /api/products?category_id=1   ->   SELECT * FROM products WHERE category_id = 1 AND is_active = TRUE"
curl -sS "$BASE_URL/api/products?category_id=1" | jq .

step "STEP 4/8 -- Add to cart (2x Wireless Mouse, 1x Bluetooth Headphones)" \
  "POST /api/cart/items   ->   INSERT ... ON DUPLICATE KEY UPDATE quantity = quantity + N"
curl -sS -b "$COOKIE_JAR" -X POST "$BASE_URL/api/cart/items" \
  -H 'Content-Type: application/json' -d '{"product_id":1,"quantity":2}' | jq .
curl -sS -b "$COOKIE_JAR" -X POST "$BASE_URL/api/cart/items" \
  -H 'Content-Type: application/json' -d '{"product_id":3,"quantity":1}' | jq .

step "STEP 5/8 -- View the cart" "GET /api/cart   ->   cart_items JOIN products, summed into a total"
curl -sS -b "$COOKIE_JAR" "$BASE_URL/api/cart" | jq .

step "STEP 6/8 -- Checkout" \
  "POST /api/checkout   ->   SELECT ... FOR UPDATE (locks stock+cart rows), INSERT orders/order_items, all in one transaction"
CHECKOUT=$(curl -sS -b "$COOKIE_JAR" -X POST "$BASE_URL/api/checkout")
echo "$CHECKOUT" | jq .
ORDER_ID=$(echo "$CHECKOUT" | jq -r .order_id)

step "STEP 7/8 -- Pay for order #$ORDER_ID" \
  "POST /api/orders/$ORDER_ID/pay   ->   INSERT/UPDATE payments; success flips orders.status to 'paid'"
curl -sS -b "$COOKIE_JAR" -X POST "$BASE_URL/api/orders/$ORDER_ID/pay" \
  -H 'Content-Type: application/json' -d '{"method":"card"}' | jq .

step "STEP 8/8 -- Order history" "GET /api/orders   ->   orders JOIN order_items JOIN payments, scoped to the logged-in user"
curl -sS -b "$COOKIE_JAR" "$BASE_URL/api/orders" | jq .

echo
echo "Demo complete. Now try the failure paths yourself, one call at a time:"
echo "  make cart-add PRODUCT=4 QTY=9999 && make checkout    # out-of-stock -> the whole checkout rolls back"
echo "  make pay ORDER=<id> SIMULATE_FAILURE=true             # declined payment, order stays 'pending'"
echo "  make register EMAIL=$EMAIL                            # duplicate email -> 409"
