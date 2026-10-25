from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import DATA_DIR, DB_PATH, INDIA_WATCHLIST, SAMPLE_WATCHLIST
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
    contacts_scanned INTEGER NOT NULL DEFAULT 0,
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
    hide_unknown_salary INTEGER NOT NULL DEFAULT 0,
    full_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    linkedin_url TEXT NOT NULL DEFAULT '',
    github_url TEXT NOT NULL DEFAULT '',
    portfolio_url TEXT NOT NULL DEFAULT '',
    notice_period TEXT NOT NULL DEFAULT '',
    current_title TEXT NOT NULL DEFAULT '',
    cover_note TEXT NOT NULL DEFAULT '',
    prefer_text TEXT NOT NULL DEFAULT '',
    avoid_text TEXT NOT NULL DEFAULT '',
    yoe_min INTEGER,
    yoe_max INTEGER,
    welcome_done INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(kind, normalized_value)
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    link TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    subject TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    follow_up_on TEXT,
    sent_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_answers (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_comparisons (
    cache_key TEXT PRIMARY KEY,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS board_suggestions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    board_type TEXT NOT NULL,
    board_token TEXT NOT NULL,
    sample_location TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL,
    UNIQUE(board_type, board_token)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_jobs_dedupe ON jobs(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_jobs_posted ON jobs(posted_at);
CREATE INDEX IF NOT EXISTS idx_contacts_job ON contacts(job_id);
CREATE INDEX IF NOT EXISTS idx_messages_job ON messages(job_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status, follow_up_on);
CREATE INDEX IF NOT EXISTS idx_job_answers_job ON job_answers(job_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_job_email ON contacts(job_id, email) WHERE email != '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_job_link ON contacts(job_id, link) WHERE link != '';
"""

_PROFILE_COLUMNS = {
    "full_name": "TEXT NOT NULL DEFAULT ''",
    "email": "TEXT NOT NULL DEFAULT ''",
    "phone": "TEXT NOT NULL DEFAULT ''",
    "city": "TEXT NOT NULL DEFAULT ''",
    "linkedin_url": "TEXT NOT NULL DEFAULT ''",
    "github_url": "TEXT NOT NULL DEFAULT ''",
    "portfolio_url": "TEXT NOT NULL DEFAULT ''",
    "notice_period": "TEXT NOT NULL DEFAULT ''",
    "current_title": "TEXT NOT NULL DEFAULT ''",
    "cover_note": "TEXT NOT NULL DEFAULT ''",
    "prefer_text": "TEXT NOT NULL DEFAULT ''",
    "avoid_text": "TEXT NOT NULL DEFAULT ''",
    "yoe_min": "INTEGER",
    "yoe_max": "INTEGER",
    "welcome_done": "INTEGER NOT NULL DEFAULT 0",
}


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


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn: sqlite3.Connection) -> None:
    profile_columns = _column_names(conn, "profile")
    for name, ddl in _PROFILE_COLUMNS.items():
        if name not in profile_columns:
            conn.execute(f"ALTER TABLE profile ADD COLUMN {name} {ddl}")
    if "contacts_scanned" not in _column_names(conn, "jobs"):
        conn.execute("ALTER TABLE jobs ADD COLUMN contacts_scanned INTEGER NOT NULL DEFAULT 0")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
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
