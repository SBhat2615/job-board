from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import INDIA_WATCHLIST, SAMPLE_WATCHLIST, database_path
from app.migrate import migrate
from app.parse import normalize, utcnow


class _Row(tuple):
    """A result row that can be read by column name. libsql returns plain tuples."""

    def __new__(cls, columns: list[str], values: tuple):
        row = super().__new__(cls, values)
        row._map = dict(zip(columns, values))  # type: ignore[attr-defined]
        return row

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._map[key]  # type: ignore[attr-defined]
        return tuple.__getitem__(self, key)

    def keys(self) -> list[str]:
        return list(self._map)  # type: ignore[attr-defined]


class _NamedCursor:
    def __init__(self, cursor) -> None:
        self._cursor = cursor
        self.lastrowid = cursor.lastrowid
        self.rowcount = cursor.rowcount
        description = cursor.description or ()
        self._columns = [item[0] for item in description]

    def _row(self, values):
        if values is None:
            return None
        return _Row(self._columns, tuple(values))

    def fetchone(self):
        return self._row(self._cursor.fetchone())

    def fetchall(self):
        return [self._row(values) for values in self._cursor.fetchall()]

    def __iter__(self):
        try:
            rows = iter(self._cursor)
        except TypeError:
            rows = self._cursor.fetchall()
        for values in rows:
            yield self._row(values)


class _NamedConnection:
    def __init__(self, raw) -> None:
        self._raw = raw

    def execute(self, sql: str, parameters: object = ()):
        return _NamedCursor(self._raw.execute(sql, parameters))

    def executescript(self, script: str) -> None:
        self._raw.executescript(script)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


def _turso_settings() -> tuple[str, str] | None:
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if not url and not token:
        return None
    if not url or not token:
        raise RuntimeError("Set both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN, or neither.")
    return url, token


def using_hosted_database() -> bool:
    """True when this process is the hosted board, not a local file."""
    if os.environ.get("JOB_BOARD_DB"):
        return False
    return _turso_settings() is not None


def _open_local() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _open_turso(url: str, token: str) -> _NamedConnection:
    import libsql

    raw = libsql.connect(url, auth_token=token)
    raw.execute("PRAGMA foreign_keys = ON")
    return _NamedConnection(raw)


def _open():
    if os.environ.get("JOB_BOARD_DB"):
        return _open_local()
    remote = _turso_settings()
    if remote is not None:
        return _open_turso(*remote)
    return _open_local()


def load_sample_watchlist(text: str) -> list[dict[str, str]]:
    companies: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line == "[[company]]":
            current = {}
            companies.append(current)
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        current[key.strip()] = value.strip().strip('"').strip("'")
    return [item for item in companies if item.get("name") and item.get("board_type") and item.get("board_token")]


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = _open()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        migrate(conn)
        existing = conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"]
        watchlist = INDIA_WATCHLIST if INDIA_WATCHLIST.exists() else SAMPLE_WATCHLIST
        if existing == 0 and watchlist.exists():
            now = utcnow()
            for item in load_sample_watchlist(watchlist.read_text(encoding="utf-8")):
                conn.execute(
                    """
                    INSERT INTO companies (name, normalized_name, board_type, board_token, is_sample, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (item["name"], normalize(item["name"]), item["board_type"], item["board_token"], now),
                )
        profile = conn.execute("SELECT id FROM profile WHERE id = 1").fetchone()
        if profile is None:
            conn.execute(
                """
                INSERT INTO profile (id, roles_json, locations_json, skills_json)
                VALUES (1, '[]', '[]', '[]')
                """
            )


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(value: str | None, fallback: object) -> object:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback
