# Copyright (c) 2026 Zenable, Inc.
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from ledger import db

pytestmark = pytest.mark.unit

PLACEMENTS = "SELECT order_id, placed_at FROM order_placements ORDER BY order_id"
ORDERS_WITH_PLACEMENTS = (
    "SELECT orders.id, orders.customer, order_placements.placed_at, orders.status "
    "FROM orders JOIN order_placements ON order_placements.order_id = orders.id ORDER BY orders.id"
)


@pytest.fixture
def legacy(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A database as it was before migrations: baseline layout, placed_at on orders, version 0."""
    connection = db.connect(tmp_path / "legacy.db")
    connection.executescript(db.SCHEMA_FILE.read_text())
    connection.executescript(
        "INSERT INTO orders (id, customer, placed_at, status) VALUES "
        "(1, 'customer-1', '2026-10-01', 'open'), (2, 'customer-2', '2026-10-02', 'shipped');"
        "INSERT INTO order_items (order_id, sku, quantity) VALUES "
        "(1, 'SKU-00001', 2), (2, 'SKU-00002', 1);"
    )
    yield connection
    connection.close()


def _columns(connection: sqlite3.Connection) -> list[str]:
    return [row["name"] for row in connection.execute("PRAGMA table_info(orders)")]


def test_upgrade_keeps_every_placed_at(legacy: sqlite3.Connection) -> None:
    assert db.migrate(legacy) == 2

    assert db.schema_version(legacy) == 2
    assert "placed_at" not in _columns(legacy)
    rows = legacy.execute(PLACEMENTS).fetchall()
    assert [tuple(row) for row in rows] == [(1, "2026-10-01"), (2, "2026-10-02")]


def test_downgrade_restores_placed_at(legacy: sqlite3.Connection) -> None:
    db.migrate(legacy)

    assert db.migrate(legacy, 1) == 1

    assert db.schema_version(legacy) == 1
    assert _columns(legacy) == ["id", "customer", "placed_at", "status"]
    rows = legacy.execute("SELECT id, customer, placed_at, status FROM orders ORDER BY id")
    assert [tuple(row) for row in rows] == [
        (1, "customer-1", "2026-10-01", "open"),
        (2, "customer-2", "2026-10-02", "shipped"),
    ]
    assert legacy.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 2


def test_round_trip_keeps_orders_and_items(connection: sqlite3.Connection) -> None:
    before = connection.execute(ORDERS_WITH_PLACEMENTS).fetchall()
    items = connection.execute("SELECT * FROM order_items ORDER BY id").fetchall()

    db.migrate(connection, 1)
    db.migrate(connection)

    assert connection.execute(ORDERS_WITH_PLACEMENTS).fetchall() == before
    assert connection.execute("SELECT * FROM order_items ORDER BY id").fetchall() == items
    assert len(before) == 800


def test_downgrade_stops_rather_than_drop_an_order_without_a_placement(
    legacy: sqlite3.Connection,
) -> None:
    db.migrate(legacy)
    legacy.execute("DELETE FROM order_placements WHERE order_id = 1")
    legacy.commit()

    with pytest.raises(sqlite3.IntegrityError):
        db.migrate(legacy, 1)

    assert db.schema_version(legacy) == 2
    assert "placed_at" not in _columns(legacy)
    assert legacy.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 2


def test_migrate_rejects_unknown_versions(legacy: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        db.migrate(legacy, 3)
