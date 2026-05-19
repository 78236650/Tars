-- InsightForge demo schema (MySQL 8 / Doris MySQL protocol)
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS product_lines (
    code VARCHAR(32) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    region VARCHAR(32) NOT NULL COMMENT '业务区域'
) COMMENT='产品线维度';

CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(64) NOT NULL,
    city VARCHAR(64) COMMENT '用户城市',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) COMMENT='用户维度';

CREATE TABLE IF NOT EXISTS products (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_line_code VARCHAR(32) NOT NULL,
    name VARCHAR(128) NOT NULL,
    price DECIMAL(12, 2) NOT NULL COMMENT '标价',
    FOREIGN KEY (product_line_code) REFERENCES product_lines(code)
) COMMENT='商品维度';

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    status VARCHAR(16) NOT NULL COMMENT 'pending/paid/refunded',
    amount DECIMAL(14, 2) NOT NULL COMMENT '订单成交金额 GMV',
    created_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
) COMMENT='订单事实表';

CREATE TABLE IF NOT EXISTS order_items (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    line_amount DECIMAL(14, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
) COMMENT='订单明细';

INSERT INTO product_lines (code, name, region) VALUES
    ('east', '华东产品线', '华东'),
    ('south', '华南产品线', '华南');

INSERT INTO users (id, name, city, created_at) VALUES
    (1, '张三', '上海', '2026-01-05 10:00:00'),
    (2, '李四', '杭州', '2026-01-08 11:00:00'),
    (3, '王五', '深圳', '2026-01-10 09:30:00');

INSERT INTO products (id, product_line_code, name, price) VALUES
    (1, 'east', '华东旗舰款', 1999.00),
    (2, 'east', '华东标准款', 899.00),
    (3, 'south', '华南热销款', 1299.00);

INSERT INTO orders (id, user_id, status, amount, created_at) VALUES
    (101, 1, 'paid', 1999.00, '2026-05-01 10:00:00'),
    (102, 1, 'paid', 899.00, '2026-05-02 14:00:00'),
    (103, 2, 'paid', 1299.00, '2026-05-03 09:00:00'),
    (104, 3, 'pending', 1299.00, '2026-05-10 16:00:00'),
    (105, 2, 'refunded', 899.00, '2026-05-11 11:00:00');

INSERT INTO order_items (id, order_id, product_id, quantity, line_amount) VALUES
    (1, 101, 1, 1, 1999.00),
    (2, 102, 2, 1, 899.00),
    (3, 103, 3, 1, 1299.00),
    (4, 104, 3, 1, 1299.00),
    (5, 105, 2, 1, 899.00);
