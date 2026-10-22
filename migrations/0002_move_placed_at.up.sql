-- Move placed_at out of orders so it can be stored and changed on its own.
-- Every existing placed_at value is copied first, so nothing is lost.
CREATE TABLE order_placements (
    order_id INTEGER PRIMARY KEY REFERENCES orders(id),
    placed_at TEXT NOT NULL
);

INSERT INTO order_placements (order_id, placed_at)
    SELECT id, placed_at FROM orders;

-- SQLite 3.26 has no ALTER TABLE ... DROP COLUMN, so orders is rebuilt without placed_at.
CREATE TABLE orders_slim (
    id INTEGER PRIMARY KEY,
    customer TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open'
);

INSERT INTO orders_slim (id, customer, status)
    SELECT id, customer, status FROM orders;

DROP TABLE orders;
ALTER TABLE orders_slim RENAME TO orders;
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer);
