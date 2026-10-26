from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.collect import company_for_name, upsert_job
from app.db import connect
from app.sources.base import RawJob


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JOB_BOARD_DB", str(tmp_path / "jobs.sqlite"))
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def insert_job(client):
    def _insert(
        *,
        title: str,
        company: str,
        location: str,
        description: str,
        source: str = "greenhouse",
        external_id: str | None = None,
        apply_url: str = "https://example.com/jobs/1",
    ) -> tuple[int, str]:
        raw = RawJob(
            source=source,
            external_id=external_id or f"{source}:{company}:{title}:{location}",
            title=title,
            location=location,
            description_html="",
            description_text=description,
            apply_url=apply_url,
            company_name=company,
        )
        with connect() as conn:
            row = company_for_name(conn, company)
            kind = upsert_job(conn, row["id"], row["name"], raw)
            job_id = conn.execute(
                "SELECT id FROM jobs WHERE company_id = ? ORDER BY id DESC LIMIT 1",
                (row["id"],),
            ).fetchone()["id"]
        return int(job_id), kind

    return _insert
