"""Columns added after the first database file. A new file already has them."""

from __future__ import annotations

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


def _columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def up(conn) -> None:
    profile_columns = _columns(conn, "profile")
    for name, ddl in _PROFILE_COLUMNS.items():
        if name not in profile_columns:
            conn.execute(f"ALTER TABLE profile ADD COLUMN {name} {ddl}")
    job_columns = _columns(conn, "jobs")
    if "contacts_scanned" not in job_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN contacts_scanned INTEGER NOT NULL DEFAULT 0")
    if "referred" not in job_columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN referred INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            """
            UPDATE jobs SET status = 'outreach'
            WHERE status = 'feed' AND id IN (
                SELECT job_id FROM messages
                WHERE kind IN ('referral', 'follow_up') AND status = 'sent'
            )
            """
        )
