-- Realistic seed data for manual exploration and testing.
USE mini_ecommerce;

INSERT INTO users (name, email, password_hash, role) VALUES
('Admin User',   'admin@shop.test',   '$2b$12$placeholderhashadmin000000000000000000000000000', 'admin'),
('Asha Rao',     'asha@example.com',  '$2b$12$placeholderhashasha0000000000000000000000000000', 'customer'),
('Vikram Shah',  'vikram@example.com','$2b$12$placeholderhashvikram000000000000000000000000000', 'customer'),
('Priya Nair',   'priya@example.com', '$2b$12$placeholderhashpriya0000000000000000000000000000', 'customer');

INSERT INTO categories (name, description) VALUES
('Electronics', 'Phones, laptops, and accessories'),
('Books',       'Fiction and non-fiction books'),
('Home',        'Kitchen and home essentials');

INSERT INTO products (category_id, name, description, price, stock_quantity) VALUES
(1, 'Wireless Mouse',        'Ergonomic 2.4GHz wireless mouse',     799.00,  50),
(1, 'USB-C Charger 65W',     'Fast charger with USB-C PD',         1499.00,  30),
(1, 'Bluetooth Headphones',  'Over-ear, 30h battery life',         2999.00,  20),
(2, 'Clean Code',            'A handbook of agile software craft', 899.00,   15),
(2, 'Atomic Habits',         'An easy way to build good habits',   499.00,   40),
(3, 'Stainless Steel Bottle','1L insulated water bottle',           599.00,  60);

-- Asha's cart: 2x Wireless Mouse, 1x Atomic Habits
INSERT INTO cart (user_id) VALUES (2);
INSERT INTO cart_items (cart_id, product_id, quantity) VALUES
(1, 1, 2),
(1, 5, 1);

-- Vikram already has a completed order (paid) to seed order-history queries.
INSERT INTO cart (user_id) VALUES (3);

INSERT INTO orders (user_id, status, total_amount) VALUES
(3, 'paid', 3798.00);

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 3, 1, 2999.00),
(1, 4, 1, 899.00);

-- Reflect the stock decrement that checkout would have applied.
UPDATE products SET stock_quantity = stock_quantity - 1 WHERE product_id = 3;
UPDATE products SET stock_quantity = stock_quantity - 1 WHERE product_id = 4;

INSERT INTO payments (order_id, amount, method, status, paid_at) VALUES
(1, 3798.00, 'card', 'success', NOW());
