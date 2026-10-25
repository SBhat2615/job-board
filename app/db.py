from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import DATA_DIR, DB_PATH, SAMPLE_WATCHLIST
from app.parse import normalize, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    board_type TEXT,
    board_token TEXT,
    team_size INTEGER,
    industry TEXT,
    summary TEXT,
    signals_json TEXT NOT NULL DEFAULT '[]',
    source_url TEXT,
    enriched_at TEXT,
    user_edited INTEGER NOT NULL DEFAULT 0,
    is_sample INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    title_folded TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    location TEXT,
    normalized_location TEXT NOT NULL DEFAULT '',
    description_html TEXT NOT NULL DEFAULT '',
    description_text TEXT NOT NULL DEFAULT '',
    apply_url TEXT,
    url_key TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    posted_at TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT,
    salary_interval TEXT,
    work_mode TEXT NOT NULL DEFAULT 'unknown',
    seniority TEXT NOT NULL DEFAULT 'unknown',
    employment TEXT NOT NULL DEFAULT 'unknown',
    work_auth TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'feed',
    discard_reason TEXT,
    discard_note TEXT,
    applied_at TEXT,
    discarded_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, source, external_id)
);

CREATE TABLE IF NOT EXISTS job_links (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_id TEXT,
    apply_url TEXT,
    url_key TEXT NOT NULL DEFAULT '',
    UNIQUE(job_id, source, url_key)
);

CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    roles_json TEXT NOT NULL DEFAULT '[]',
    locations_json TEXT NOT NULL DEFAULT '[]',
    work_mode TEXT NOT NULL DEFAULT 'any',
    seniority TEXT NOT NULL DEFAULT 'any',
    salary_min INTEGER,
    salary_currency TEXT NOT NULL DEFAULT 'USD',
    skills_json TEXT NOT NULL DEFAULT '[]',
    resume_text TEXT,
    resume_filename TEXT,
    hide_unknown_salary INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(kind, normalized_value)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_dedupe ON jobs(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_at);
"""


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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
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
        conn.executescript(SCHEMA)
        existing = conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"]
        if existing == 0 and SAMPLE_WATCHLIST.exists():
            now = utcnow()
            for item in load_sample_watchlist(SAMPLE_WATCHLIST.read_text(encoding="utf-8")):
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
