# Copyright (c) 2026 Zenable, Inc.
"""SQLite connection, schema, and migrations."""

import sqlite3
from pathlib import Path

from ledger.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_FILE = PROJECT_ROOT / "schema.sql"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
# schema.sql is the layout every database starts from; migrations move it forward.
BASELINE_VERSION = 1


def connect(path: Path | str) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA journal_mode={settings.journal_mode}")
    return connection


def apply_schema(connection: sqlite3.Connection) -> None:
    """Create the baseline tables, then bring them up to the latest version."""
    connection.executescript(SCHEMA_FILE.read_text())
    migrate(connection)


def reset(connection: sqlite3.Connection) -> None:
    """Drop everything and apply the schema again."""
    connection.executescript(
        "DROP TABLE IF EXISTS order_placements; DROP TABLE IF EXISTS order_items; "
        "DROP TABLE IF EXISTS orders; PRAGMA user_version = 0;"
    )
    apply_schema(connection)


def _migration_files() -> list[tuple[int, Path, Path]]:
    """(version, up script, down script) for every migration, oldest first."""
    steps = []
    for up in sorted(MIGRATIONS_DIR.glob("*.up.sql")):
        version = int(up.name.split("_", 1)[0])
        down = up.with_name(up.name.removesuffix(".up.sql") + ".down.sql")
        steps.append((version, up, down))
    return steps


def schema_version(connection: sqlite3.Connection) -> int:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    # Databases made before migrations existed report 0 but have the baseline layout.
    return version or BASELINE_VERSION


def _run(connection: sqlite3.Connection, script: Path, version: int) -> None:
    """Run one migration and its version change in a single transaction."""
    try:
        connection.executescript(
            f"BEGIN;\n{script.read_text()}\nPRAGMA user_version = {version};\nCOMMIT;"
        )
    except sqlite3.Error:
        connection.rollback()
        raise


def migrate(connection: sqlite3.Connection, target: int | None = None) -> int:
    """Move the schema to `target` (the latest version by default), up or down."""
    steps = _migration_files()
    latest = max((version for version, _, _ in steps), default=BASELINE_VERSION)
    target = latest if target is None else target
    if not BASELINE_VERSION <= target <= latest:
        raise ValueError(f"no schema version {target}; choose {BASELINE_VERSION} to {latest}")
    current = schema_version(connection)
    if target > current:
        for version, up, _ in steps:
            if current < version <= target:
                _run(connection, up, version)
    else:
        for version, _, down in reversed(steps):
            if target < version <= current:
                _run(connection, down, version - 1)
    return target
