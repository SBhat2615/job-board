from __future__ import annotations

import csv
import hashlib
import io
import json

from app.sources.base import RawJob
from app.vocab import SOURCES


def _external_id(company: str, title: str, url: str, given: str) -> str:
    if given.strip():
        return given.strip()[:120]
    digest = hashlib.sha1(f"{company}|{title}|{url}".encode()).hexdigest()
    return digest[:16]


def _rows_from_csv(data: bytes) -> list[dict]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("The CSV needs a header row with title and company.")
    rows = []
    for raw in reader:
        rows.append({(key or "").strip().lower(): (value or "").strip() for key, value in raw.items()})
    return rows


def _rows_from_json(data: bytes) -> list[dict]:
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError("That JSON file could not be read.") from exc
    if isinstance(payload, dict):
        payload = payload.get("jobs", [])
    if not isinstance(payload, list):
        raise ValueError("JSON imports should be a list of jobs, or an object with a jobs list.")
    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rows.append({str(key).strip().lower(): "" if value is None else str(value).strip() for key, value in item.items()})
    return rows


def parse_upload(filename: str, data: bytes) -> list[RawJob]:
    if len(data) > 5_000_000:
        raise ValueError("File is larger than 5 MB.")
    name = (filename or "").lower()
    if name.endswith(".json") or data.lstrip()[:1] in {b"{", b"["}:
        rows = _rows_from_json(data)
    else:
        rows = _rows_from_csv(data)
    jobs: list[RawJob] = []
    for row in rows:
        title = row.get("title") or row.get("text") or ""
        company = row.get("company") or row.get("company_name") or ""
        if not title or not company:
            continue
        url = row.get("url") or row.get("apply_url") or ""
        html = row.get("description_html") or ""
        text = row.get("description") or row.get("description_text") or ""
        if not html and "<" in text and ">" in text:
            html = text
        source = (row.get("source") or "import").lower()
        if source not in SOURCES:
            source = "import"
        jobs.append(
            RawJob(
                source=source,
                external_id=_external_id(company, title, url, row.get("external_id") or row.get("id") or ""),
                title=title,
                location=row.get("location") or "",
                description_html=html,
                description_text="" if html else text,
                apply_url=url,
                posted_at=row.get("posted_at") or row.get("posted") or None,
                company_name=company,
            )
        )
        if len(jobs) >= 2000:
            break
    if not jobs:
        raise ValueError("No jobs found. Each row needs a title and a company.")
    return jobs
