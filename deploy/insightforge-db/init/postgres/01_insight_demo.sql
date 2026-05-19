-- InsightForge demo schema (PostgreSQL 16)

CREATE TABLE product_lines (
    code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    region VARCHAR(32) NOT NULL
);
COMMENT ON TABLE product_lines IS '产品线维度';

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    city VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE users IS '用户维度';
COMMENT ON COLUMN users.city IS '用户城市';

CREATE TABLE products (
    id BIGSERIAL PRIMARY KEY,
    product_line_code VARCHAR(32) NOT NULL REFERENCES product_lines(code),
    name VARCHAR(128) NOT NULL,
    price NUMERIC(12, 2) NOT NULL
);
COMMENT ON TABLE products IS '商品维度';
COMMENT ON COLUMN products.price IS '标价';

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    status VARCHAR(16) NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL
);
COMMENT ON TABLE orders IS '订单事实表';
COMMENT ON COLUMN orders.status IS 'pending/paid/refunded';
COMMENT ON COLUMN orders.amount IS '订单成交金额 GMV';

CREATE TABLE order_items (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    product_id BIGINT NOT NULL REFERENCES products(id),
    quantity INT NOT NULL,
    line_amount NUMERIC(14, 2) NOT NULL
);
COMMENT ON TABLE order_items IS '订单明细';

INSERT INTO product_lines (code, name, region) VALUES
    ('east', '华东产品线', '华东'),
    ('south', '华南产品线', '华南');

INSERT INTO users (id, name, city, created_at) VALUES
    (1, '张三', '上海', '2026-01-05 10:00:00'),
    (2, '李四', '杭州', '2026-01-08 11:00:00'),
    (3, '王五', '深圳', '2026-01-10 09:30:00');

SELECT setval(pg_get_serial_sequence('users', 'id'), 3);

INSERT INTO products (id, product_line_code, name, price) VALUES
    (1, 'east', '华东旗舰款', 1999.00),
    (2, 'east', '华东标准款', 899.00),
    (3, 'south', '华南热销款', 1299.00);

SELECT setval(pg_get_serial_sequence('products', 'id'), 3);

INSERT INTO orders (id, user_id, status, amount, created_at) VALUES
    (101, 1, 'paid', 1999.00, '2026-05-01 10:00:00'),
    (102, 1, 'paid', 899.00, '2026-05-02 14:00:00'),
    (103, 2, 'paid', 1299.00, '2026-05-03 09:00:00'),
    (104, 3, 'pending', 1299.00, '2026-05-10 16:00:00'),
    (105, 2, 'refunded', 899.00, '2026-05-11 11:00:00');

SELECT setval(pg_get_serial_sequence('orders', 'id'), 105);

INSERT INTO order_items (id, order_id, product_id, quantity, line_amount) VALUES
    (1, 101, 1, 1, 1999.00),
    (2, 102, 2, 1, 899.00),
    (3, 103, 3, 1, 1299.00),
    (4, 104, 3, 1, 1299.00),
    (5, 105, 2, 1, 899.00);

SELECT setval(pg_get_serial_sequence('order_items', 'id'), 5);
