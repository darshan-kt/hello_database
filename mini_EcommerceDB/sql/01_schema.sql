-- Mini E-Commerce schema
-- Module 2: MySQL Schema Implementation
-- Target: MySQL 8.0+ (InnoDB, utf8mb4)

DROP DATABASE IF EXISTS mini_ecommerce;
CREATE DATABASE mini_ecommerce CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mini_ecommerce;

-- ---------------------------------------------------------------------
-- Users
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(120)      NOT NULL,
    email         VARCHAR(255)      NOT NULL,
    password_hash VARCHAR(255)      NOT NULL,
    role          ENUM('customer', 'admin') NOT NULL DEFAULT 'customer',
    created_at    TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_email UNIQUE (email)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Categories
-- ---------------------------------------------------------------------
CREATE TABLE categories (
    category_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    description VARCHAR(500),
    CONSTRAINT uq_categories_name UNIQUE (name)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Products
-- ---------------------------------------------------------------------
CREATE TABLE products (
    product_id     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_id    BIGINT UNSIGNED NOT NULL,
    name           VARCHAR(200)    NOT NULL,
    description    VARCHAR(1000),
    price          DECIMAL(10, 2)  NOT NULL,
    stock_quantity INT             NOT NULL DEFAULT 0,
    is_active      BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id) REFERENCES categories(category_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_products_price_nonneg CHECK (price >= 0),
    CONSTRAINT chk_products_stock_nonneg CHECK (stock_quantity >= 0)
) ENGINE=InnoDB;

CREATE INDEX idx_products_category ON products(category_id);

-- ---------------------------------------------------------------------
-- Cart  (one active cart per user)
-- ---------------------------------------------------------------------
CREATE TABLE cart (
    cart_id    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id    BIGINT UNSIGNED NOT NULL,
    created_at TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cart_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_cart_user UNIQUE (user_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- CartItems
-- ---------------------------------------------------------------------
CREATE TABLE cart_items (
    cart_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cart_id      BIGINT UNSIGNED NOT NULL,
    product_id   BIGINT UNSIGNED NOT NULL,
    quantity     INT             NOT NULL,
    CONSTRAINT fk_cart_items_cart
        FOREIGN KEY (cart_id) REFERENCES cart(cart_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_cart_items_product
        FOREIGN KEY (product_id) REFERENCES products(product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT uq_cart_items_cart_product UNIQUE (cart_id, product_id),
    CONSTRAINT chk_cart_items_qty_pos CHECK (quantity > 0)
) ENGINE=InnoDB;

CREATE INDEX idx_cart_items_product ON cart_items(product_id);

-- ---------------------------------------------------------------------
-- Orders
-- ---------------------------------------------------------------------
CREATE TABLE orders (
    order_id     BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT UNSIGNED NOT NULL,
    status       ENUM('pending', 'paid', 'shipped', 'delivered', 'cancelled')
                 NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(10, 2)  NOT NULL,
    created_at   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_orders_total_nonneg CHECK (total_amount >= 0)
) ENGINE=InnoDB;

-- Composite, not two separate indexes: order history is always "this
-- user's orders, newest first" -- (user_id, created_at) serves both the
-- WHERE and the ORDER BY in one index, avoiding a filesort. See
-- docs/03_optimization.md for the EXPLAIN evidence.
CREATE INDEX idx_orders_user_created ON orders(user_id, created_at);
CREATE INDEX idx_orders_status ON orders(status);

-- ---------------------------------------------------------------------
-- OrderItems (immutable price/quantity snapshot)
-- ---------------------------------------------------------------------
CREATE TABLE order_items (
    order_item_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id      BIGINT UNSIGNED NOT NULL,
    product_id    BIGINT UNSIGNED NOT NULL,
    quantity      INT             NOT NULL,
    unit_price    DECIMAL(10, 2)  NOT NULL,
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id) REFERENCES products(product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_order_items_qty_pos CHECK (quantity > 0),
    CONSTRAINT chk_order_items_price_nonneg CHECK (unit_price >= 0)
) ENGINE=InnoDB;

CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);

-- ---------------------------------------------------------------------
-- Payments (one per order)
-- ---------------------------------------------------------------------
CREATE TABLE payments (
    payment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id   BIGINT UNSIGNED NOT NULL,
    amount     DECIMAL(10, 2)  NOT NULL,
    method     ENUM('card', 'upi', 'wallet', 'cod') NOT NULL,
    status     ENUM('pending', 'success', 'failed', 'refunded')
               NOT NULL DEFAULT 'pending',
    paid_at    TIMESTAMP NULL,
    CONSTRAINT fk_payments_order
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT uq_payments_order UNIQUE (order_id),
    CONSTRAINT chk_payments_amount_nonneg CHECK (amount >= 0)
) ENGINE=InnoDB;
