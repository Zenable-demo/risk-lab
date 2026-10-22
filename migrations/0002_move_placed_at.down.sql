-- Put placed_at back on orders, copied from order_placements.
-- The LEFT JOIN keeps every order: an order with no placement makes the
-- NOT NULL check fail, which rolls the whole downgrade back.
CREATE TABLE orders_restored (
    id INTEGER PRIMARY KEY,
    customer TEXT NOT NULL,
    placed_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
);

INSERT INTO orders_restored (id, customer, placed_at, status)
    SELECT orders.id, orders.customer, order_placements.placed_at, orders.status
    FROM orders LEFT JOIN order_placements ON order_placements.order_id = orders.id;

DROP TABLE order_placements;
DROP TABLE orders;
ALTER TABLE orders_restored RENAME TO orders;
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer);
