"""
database/db.py — SQLite connection, initialization, and parameterized helpers.
"""
import sqlite3
import pathlib
import threading

_DB_PATH = pathlib.Path(__file__).parent.parent / "eduhope.db"
_SCHEMA_PATH = pathlib.Path(__file__).parent / "schema.sql"
_local = threading.local()


def get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection with WAL mode and row_factory."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    """Create tables if they do not exist. Safe to run multiple times."""
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_conn()
    conn.executescript(schema)
    # Migrate databases created before display_name was added.
    student_columns = {row[1] for row in conn.execute("PRAGMA table_info(students)")}
    if "display_name" not in student_columns:
        conn.execute("ALTER TABLE students ADD COLUMN display_name TEXT")
    conn.execute("UPDATE students SET display_name=reference WHERE display_name IS NULL OR display_name=''")
    conn.commit()


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur


def fetchall(sql: str, params: tuple = ()) -> list:
    conn = get_conn()
    cur = conn.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def fetchone(sql: str, params: tuple = ()) -> dict | None:
    conn = get_conn()
    cur = conn.execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else None
