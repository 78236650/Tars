-- InsightForge demo schema (Apache Doris — MySQL protocol)
-- 在 Doris FE 就绪后由 scripts/seed-doris.sh 执行

CREATE DATABASE IF NOT EXISTS insight_demo;
USE insight_demo;

CREATE TABLE IF NOT EXISTS product_lines (
    code VARCHAR(32),
    name VARCHAR(128),
    region VARCHAR(32)
)
UNIQUE KEY(code)
DISTRIBUTED BY HASH(code) BUCKETS 1
PROPERTIES ('replication_num' = '1');

CREATE TABLE IF NOT EXISTS users (
    id BIGINT,
    name VARCHAR(64),
    city VARCHAR(64),
    created_at DATETIME
)
UNIQUE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 1
PROPERTIES ('replication_num' = '1');

CREATE TABLE IF NOT EXISTS products (
    id BIGINT,
    product_line_code VARCHAR(32),
    name VARCHAR(128),
    price DECIMAL(12, 2)
)
UNIQUE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 1
PROPERTIES ('replication_num' = '1');

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT,
    user_id BIGINT,
    status VARCHAR(16),
    amount DECIMAL(14, 2),
    created_at DATETIME
)
UNIQUE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 1
PROPERTIES ('replication_num' = '1');

CREATE TABLE IF NOT EXISTS order_items (
    id BIGINT,
    order_id BIGINT,
    product_id BIGINT,
    quantity INT,
    line_amount DECIMAL(14, 2)
)
UNIQUE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 1
PROPERTIES ('replication_num' = '1');

INSERT INTO product_lines VALUES
    ('east', '华东产品线', '华东'),
    ('south', '华南产品线', '华南');

INSERT INTO users VALUES
    (1, '张三', '上海', '2026-01-05 10:00:00'),
    (2, '李四', '杭州', '2026-01-08 11:00:00'),
    (3, '王五', '深圳', '2026-01-10 09:30:00');

INSERT INTO products VALUES
    (1, 'east', '华东旗舰款', 1999.00),
    (2, 'east', '华东标准款', 899.00),
    (3, 'south', '华南热销款', 1299.00);

INSERT INTO orders VALUES
    (101, 1, 'paid', 1999.00, '2026-05-01 10:00:00'),
    (102, 1, 'paid', 899.00, '2026-05-02 14:00:00'),
    (103, 2, 'paid', 1299.00, '2026-05-03 09:00:00'),
    (104, 3, 'pending', 1299.00, '2026-05-10 16:00:00'),
    (105, 2, 'refunded', 899.00, '2026-05-11 11:00:00');

INSERT INTO order_items VALUES
    (1, 101, 1, 1, 1999.00),
    (2, 102, 2, 1, 899.00),
    (3, 103, 3, 1, 1299.00),
    (4, 104, 3, 1, 1299.00),
    (5, 105, 2, 1, 899.00);
