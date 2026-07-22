# ============================================================================
# Mini E-Commerce -- Interactive Learning Makefile
#
# Run `make` or `make help` to see every step. Each target prints the HTTP
# call and the SQL/transaction happening underneath it before running it,
# so you can watch a database concept (constraint, index, transaction,
# lock) trigger in real time instead of just reading about it.
#
# See docs/04_interactive_learning.md for the full guided tour.
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Overridable variables (e.g. `make products CATEGORY=2`) -------------
BASE_URL          ?= http://localhost:5000
COOKIE_JAR        ?= .cookies.txt
NAME              ?= Demo Learner
EMAIL             ?= demo.learner@example.com
PASSWORD          ?= learn-123
CATEGORY          ?=
PRODUCT           ?= 1
QTY               ?= 1
ORDER             ?=
METHOD            ?= card
SIMULATE_FAILURE  ?= false
TABLE             ?= products

PRETTY = jq . 2>/dev/null || cat

.PHONY: help up down reset logs ps status reseed test clean \
        db-shell db-tables db-describe explain \
        register login logout me categories products \
        cart cart-add cart-remove checkout pay orders demo open-ui

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; \
	  printf "\nMini E-Commerce -- Interactive Learning Makefile\n"; \
	  printf "==================================================\n"} \
	  /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo ""
	@echo "Suggested first run:"
	@echo "  make up            # start MySQL + backend"
	@echo "  make demo          # watch the full lifecycle happen, narrated"
	@echo "  make db-shell      # then go look at the rows it created yourself"
	@echo ""
	@echo "Full guided tour: docs/04_interactive_learning.md"
	@echo ""

##@ Infrastructure

up: ## Start MySQL + the backend (builds the image on first run)
	@echo "==> docker compose up -d --build"
	docker compose up -d --build
	@echo "==> Waiting for both containers to report healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' mini_ecommerce_mysql 2>/dev/null)" = "healthy" ] && \
	       [ "$$(docker inspect -f '{{.State.Health.Status}}' mini_ecommerce_backend 2>/dev/null)" = "healthy" ]; do \
	  sleep 2; \
	done
	@echo "==> Ready.  UI: $(BASE_URL)   MySQL: localhost:3307 (user=ecom_app pass=ecom_app_pw)"

down: ## Stop containers (keeps the database volume)
	docker compose down

reset: ## Full reset: wipe the DB volume, rebuild, restart from scratch
	@echo "==> Wiping containers + database volume for a clean slate..."
	docker compose down -v
	$(MAKE) --no-print-directory up
	rm -f $(COOKIE_JAR)

logs: ## Follow the backend's logs
	docker compose logs -f backend

ps: status
status: ## Show container status
	docker compose ps

reseed: ## Reload sql/02_seed.sql (run this after `make test`, which truncates every table)
	@echo "==> Reloading demo seed data into MySQL..."
	docker exec -i mini_ecommerce_mysql mysql -uroot -prootpass mini_ecommerce < sql/02_seed.sql
	@echo "==> Done -- refresh $(BASE_URL)"

test: ## Run the pytest suite inside Docker against the real MySQL (WARNING: truncates all tables)
	@echo "==> Running tests inside the backend container. Note: this truncates every table first."
	docker compose run --rm backend pytest -v

clean: ## Stop containers, delete the DB volume, and forget your local session cookie
	docker compose down -v
	rm -f $(COOKIE_JAR)

open-ui: ## Open the web UI in your default browser
	@command -v xdg-open >/dev/null 2>&1 && xdg-open $(BASE_URL) || \
	 command -v open >/dev/null 2>&1 && open $(BASE_URL) || \
	 echo "Open $(BASE_URL) manually."

##@ Explore the database directly (see what the API is doing underneath)

db-shell: ## Open an interactive MySQL shell inside the container
	@echo "==> Try: SHOW TABLES;  DESCRIBE products;  SELECT * FROM orders;  SELECT * FROM order_items;"
	docker exec -it mini_ecommerce_mysql mysql -uroot -prootpass mini_ecommerce

db-tables: ## List every table in the schema
	docker exec mini_ecommerce_mysql mysql -uroot -prootpass mini_ecommerce -e "SHOW TABLES;"

db-describe: ## Show a table's columns, types, keys. Vars: TABLE (default: products)
	docker exec mini_ecommerce_mysql mysql -uroot -prootpass mini_ecommerce -e "DESCRIBE $(TABLE);"

explain: ## Run EXPLAIN on the 4 key query patterns from docs/03_optimization.md
	@echo "==> EXPLAIN: browse products by category  (idx_products_category, type=ref)"
	@docker exec mini_ecommerce_mysql mysql -uroot -prootpass mini_ecommerce \
	  -e "EXPLAIN SELECT * FROM products WHERE category_id = 1 AND is_active = TRUE;"
	@echo ""
	@echo "==> EXPLAIN: a user's order history, newest first  (idx_orders_user_created, no filesort)"
	@docker exec mini_ecommerce_mysql mysql -uroot -prootpass mini_ecommerce \
	  -e "EXPLAIN SELECT * FROM orders WHERE user_id = 3 ORDER BY created_at DESC;"
	@echo ""
	@echo "==> EXPLAIN: line items for an order  (idx_order_items_order, type=ref)"
	@docker exec mini_ecommerce_mysql mysql -uroot -prootpass mini_ecommerce \
	  -e "EXPLAIN SELECT * FROM order_items WHERE order_id = 1;"
	@echo ""
	@echo "==> EXPLAIN: login lookup by email  (uq_users_email, type=const -- single-row point lookup)"
	@docker exec mini_ecommerce_mysql mysql -uroot -prootpass mini_ecommerce \
	  -e "EXPLAIN SELECT * FROM users WHERE email = 'asha@example.com';"

##@ Step by step through the API (each target = one HTTP call; session persists in $(COOKIE_JAR))

register: ## STEP 1 -- Create an account. Vars: NAME, EMAIL, PASSWORD
	@echo "==> POST /api/register   ->   INSERT INTO users (...)   [DuplicateEmailError -> 409 if email taken]"
	@curl -sS -c $(COOKIE_JAR) -b $(COOKIE_JAR) -X POST $(BASE_URL)/api/register \
	  -H 'Content-Type: application/json' \
	  -d '{"name":"$(NAME)","email":"$(EMAIL)","password":"$(PASSWORD)"}' | $(PRETTY)

login: ## STEP 1b -- Log in instead (demo mode: any email/password works, account auto-created if new). Vars: EMAIL, PASSWORD
	@echo "==> POST /api/login   ->   SELECT * FROM users WHERE email = ...  (auto-creates the account if not found; password isn't checked)"
	@curl -sS -c $(COOKIE_JAR) -b $(COOKIE_JAR) -X POST $(BASE_URL)/api/login \
	  -H 'Content-Type: application/json' \
	  -d '{"email":"$(EMAIL)","password":"$(PASSWORD)"}' | $(PRETTY)

me: ## Show who you're logged in as (reads the session cookie, no DB write)
	@echo "==> GET /api/me"
	@curl -sS -b $(COOKIE_JAR) $(BASE_URL)/api/me | $(PRETTY)

logout: ## Clear your session
	@echo "==> POST /api/logout"
	@curl -sS -c $(COOKIE_JAR) -b $(COOKIE_JAR) -X POST $(BASE_URL)/api/logout | $(PRETTY)

categories: ## STEP 2 -- List product categories
	@echo "==> GET /api/categories   ->   SELECT * FROM categories"
	@curl -sS $(BASE_URL)/api/categories | $(PRETTY)

products: ## STEP 3 -- Browse products, optionally filtered. Vars: CATEGORY (id)
	@echo "==> GET /api/products$(if $(CATEGORY),?category_id=$(CATEGORY),)"
	@echo "    SQL: SELECT * FROM products$(if $(CATEGORY), WHERE category_id = $(CATEGORY) AND is_active = TRUE,)"
	@curl -sS "$(BASE_URL)/api/products$(if $(CATEGORY),?category_id=$(CATEGORY),)" | $(PRETTY)

cart-add: ## STEP 4 -- Add a product to your cart. Vars: PRODUCT (id), QTY
	@echo "==> POST /api/cart/items   ->   INSERT ... ON DUPLICATE KEY UPDATE quantity = quantity + $(QTY)"
	@curl -sS -b $(COOKIE_JAR) -X POST $(BASE_URL)/api/cart/items \
	  -H 'Content-Type: application/json' \
	  -d '{"product_id":$(PRODUCT),"quantity":$(QTY)}' | $(PRETTY)

cart-remove: ## Remove a product line from your cart. Vars: PRODUCT (id)
	@echo "==> DELETE /api/cart/items/$(PRODUCT)   ->   DELETE FROM cart_items WHERE ..."
	@curl -sS -b $(COOKIE_JAR) -X DELETE $(BASE_URL)/api/cart/items/$(PRODUCT) | $(PRETTY)

cart: ## STEP 5 -- View your cart and running total
	@echo "==> GET /api/cart   ->   cart_items JOIN products, summed"
	@curl -sS -b $(COOKIE_JAR) $(BASE_URL)/api/cart | $(PRETTY)

checkout: ## STEP 6 -- Turn your cart into an order (one atomic transaction). Prints the order_id you need next.
	@echo "==> POST /api/checkout   ->   SELECT ... FOR UPDATE (locks stock+cart), INSERT orders/order_items, all-or-nothing"
	@curl -sS -b $(COOKIE_JAR) -X POST $(BASE_URL)/api/checkout | $(PRETTY)
	@echo "    Note the order_id above, then: make pay ORDER=<id>"

pay: ## STEP 7 -- Pay for an order. Vars: ORDER (required), METHOD, SIMULATE_FAILURE (true/false)
	@if [ -z "$(ORDER)" ]; then echo "Usage: make pay ORDER=<order_id> [METHOD=card] [SIMULATE_FAILURE=true]"; exit 1; fi
	@echo "==> POST /api/orders/$(ORDER)/pay   ->   INSERT/UPDATE payments; success flips orders.status to 'paid'"
	@curl -sS -b $(COOKIE_JAR) -X POST $(BASE_URL)/api/orders/$(ORDER)/pay \
	  -H 'Content-Type: application/json' \
	  -d '{"method":"$(METHOD)","simulate_failure":$(SIMULATE_FAILURE)}' | $(PRETTY)

orders: ## STEP 8 -- View your order history with items + payment status
	@echo "==> GET /api/orders   ->   orders JOIN order_items JOIN payments, scoped to you"
	@curl -sS -b $(COOKIE_JAR) $(BASE_URL)/api/orders | $(PRETTY)

##@ All-in-one

demo: ## Run the entire lifecycle above in one narrated command (safe to re-run)
	@BASE_URL=$(BASE_URL) COOKIE_JAR=$(COOKIE_JAR) bash scripts/api_walkthrough.sh
