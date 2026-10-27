from __future__ import annotations

import sqlite3
import sys
import types

import pytest

from app.db import connect, init_db, using_hosted_database


def _use_file(monkeypatch, path) -> None:
    monkeypatch.setenv("JOB_BOARD_DB", str(path))
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)


def _versions(conn) -> list[int]:
    return [int(row["version"]) for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]


def test_new_database_records_every_migration(tmp_path, monkeypatch):
    _use_file(monkeypatch, tmp_path / "jobs.sqlite")
    init_db()
    init_db()
    with connect() as conn:
        assert _versions(conn) == [1, 2]
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    assert "referred" in columns
    assert "contacts_scanned" in columns


def test_old_database_gains_columns_and_moves_a_sent_referral(tmp_path, monkeypatch):
    path = tmp_path / "jobs.sqlite"
    _use_file(monkeypatch, path)
    raw = sqlite3.connect(path)
    raw.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            board_type TEXT,
            board_token TEXT,
            is_sample INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY,
            company_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT NOT NULL,
            title_folded TEXT NOT NULL,
            normalized_title TEXT NOT NULL,
            normalized_location TEXT NOT NULL DEFAULT '',
            description_text TEXT NOT NULL DEFAULT '',
            dedupe_key TEXT NOT NULL,
            posted_at TEXT,
            status TEXT NOT NULL DEFAULT 'feed',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            follow_up_on TEXT
        );
        CREATE TABLE profile (
            id INTEGER PRIMARY KEY,
            roles_json TEXT NOT NULL DEFAULT '[]',
            locations_json TEXT NOT NULL DEFAULT '[]',
            skills_json TEXT NOT NULL DEFAULT '[]'
        );
        INSERT INTO companies (id, name, normalized_name, created_at) VALUES (1, 'Old Co', 'old co', '2020-01-01');
        INSERT INTO jobs (
            id, company_id, source, external_id, title, title_folded, normalized_title, dedupe_key,
            status, created_at, updated_at
        ) VALUES (
            7, 1, 'greenhouse', 'ext', 'Role', 'role', 'role', 'old co|role|', 'feed', '2020-01-01', '2020-01-01'
        );
        INSERT INTO messages (job_id, kind, status) VALUES (7, 'referral', 'sent');
        INSERT INTO profile (id) VALUES (1);
        """
    )
    raw.commit()
    raw.close()

    init_db()
    with connect() as conn:
        job = conn.execute("SELECT status, referred FROM jobs WHERE id = 7").fetchone()
        profile_columns = {row["name"] for row in conn.execute("PRAGMA table_info(profile)")}
        assert _versions(conn) == [1, 2]
    assert job["status"] == "outreach"
    assert job["referred"] == 0
    assert "yoe_min" in profile_columns
    assert "full_name" in profile_columns


def test_existing_referred_column_is_not_backfilled_again(tmp_path, monkeypatch):
    path = tmp_path / "jobs.sqlite"
    _use_file(monkeypatch, path)
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO companies (name, normalized_name, created_at)
            VALUES ('Kept Co', 'kept co', '2020-01-01')
            """
        )
        company_id = conn.execute("SELECT id FROM companies WHERE normalized_name = 'kept co'").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO jobs (
                company_id, source, external_id, title, title_folded, normalized_title, dedupe_key,
                status, referred, created_at, updated_at
            ) VALUES (
                ?, 'greenhouse', 'ext', 'Role', 'role', 'role', 'kept co|role|', 'feed', 0, '2020-01-01', '2020-01-01'
            )
            """,
            (company_id,),
        )
        job_id = conn.execute("SELECT id FROM jobs WHERE external_id = 'ext'").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO messages (job_id, kind, status, subject, body, created_at, updated_at)
            VALUES (?, 'referral', 'sent', 'Hello', 'Please refer me.', '2020-01-01', '2020-01-01')
            """,
            (job_id,),
        )
    init_db()
    with connect() as conn:
        status = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()["status"]
    assert status == "feed"


def test_local_file_wins_over_turso_settings(tmp_path, monkeypatch):
    path = tmp_path / "jobs.sqlite"
    monkeypatch.setenv("JOB_BOARD_DB", str(path))
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret")

    def refuse(*_args, **_kwargs):
        raise AssertionError("Turso was opened even though JOB_BOARD_DB is set.")

    module = types.ModuleType("libsql")
    module.connect = refuse
    monkeypatch.setitem(sys.modules, "libsql", module)
    init_db()
    assert path.exists()


def test_turso_settings_must_come_as_a_pair(monkeypatch):
    monkeypatch.delenv("JOB_BOARD_DB", raising=False)
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="both"):
        with connect():
            pass


def test_turso_rows_can_be_read_by_column_name(monkeypatch):
    monkeypatch.delenv("JOB_BOARD_DB", raising=False)
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret")
    seen: dict[str, object] = {}

    class FakeCursor:
        description = (("ok", None, None, None, None, None, None),)
        lastrowid = 4
        rowcount = 1

        def fetchone(self):
            return (4,)

        def fetchall(self):
            return [(4,)]

        def __iter__(self):
            return iter([(4,)])

    class FakeConnection:
        def execute(self, sql, parameters=()):
            seen["sql"] = sql
            return FakeCursor()

        def executescript(self, script):
            seen["script"] = script

        def commit(self):
            seen["committed"] = True

        def rollback(self):
            seen["rolled"] = True

        def close(self):
            seen["closed"] = True

    def connect_remote(database, auth_token=""):
        seen["database"] = database
        seen["auth_token"] = auth_token
        return FakeConnection()

    module = types.ModuleType("libsql")
    module.connect = connect_remote
    monkeypatch.setitem(sys.modules, "libsql", module)

    with connect() as conn:
        row = conn.execute("SELECT 4 AS ok").fetchone()
    assert seen["database"] == "libsql://example.turso.io"
    assert seen["auth_token"] == "secret"
    assert row["ok"] == 4
    assert row.keys() == ["ok"]
    assert seen["committed"] is True
    assert seen["closed"] is True


def test_turso_query_results_can_be_iterated(monkeypatch):
    monkeypatch.delenv("JOB_BOARD_DB", raising=False)
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret")

    class BareCursor:
        description = (("version", None, None, None, None, None, None),)
        lastrowid = 1
        rowcount = 1

        def fetchone(self):
            return (1,)

        def fetchall(self):
            return [(1,)]

    class BareConnection:
        def execute(self, sql, parameters=()):
            return BareCursor()

        def executescript(self, script):
            return None

        def commit(self):
            return None

        def rollback(self):
            return None

        def close(self):
            return None

    module = types.ModuleType("libsql")
    module.connect = lambda database, auth_token="": BareConnection()
    monkeypatch.setitem(sys.modules, "libsql", module)

    with connect() as conn:
        versions = [row["version"] for row in conn.execute("SELECT version FROM schema_migrations")]
    assert versions == [1]


def test_a_local_file_is_not_the_hosted_board(monkeypatch):
    monkeypatch.setenv("JOB_BOARD_DB", "jobs.sqlite")
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret")
    assert using_hosted_database() is False


def test_both_turso_settings_mark_the_hosted_board(monkeypatch):
    monkeypatch.delenv("JOB_BOARD_DB", raising=False)
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.turso.io")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "secret")
    assert using_hosted_database() is True
