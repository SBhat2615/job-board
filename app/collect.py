from __future__ import annotations

import hashlib
import sqlite3

import httpx

from app.config import USER_AGENT
from app.contacts import scan_unscanned
from app.db import connect
from app.enrich import enrich_company
from app.feeds import fetch_remote_feeds
from app.htmlutil import html_to_text, sanitize_html
from app.parse import (
    coerce_datetime,
    detect_employment,
    detect_seniority,
    detect_work_auth,
    detect_work_mode,
    normalize,
    normalize_interval,
    parse_salary,
    url_key,
    utcnow,
)
from app.sources import FETCHERS
from app.sources.base import RawJob
from app.sources.common import BoardError


def _short_error(exc: Exception) -> str:
    if isinstance(exc, BoardError):
        return str(exc)
    if isinstance(exc, httpx.TimeoutException):
        return "The board took too long to respond."
    if isinstance(exc, httpx.HTTPError):
        return "The board could not be reached."
    return "The board could not be read."


def _salary_fields(raw: RawJob, title: str, text: str) -> tuple[int | None, int | None, str | None, str | None]:
    if raw.salary_min or raw.salary_max:
        low = raw.salary_min or raw.salary_max
        high = raw.salary_max or raw.salary_min
        if low is None or high is None:
            return None, None, None, None
        if high < low:
            low, high = high, low
        currency = (raw.salary_currency or "USD").upper()
        return low, high, currency, normalize_interval(raw.salary_interval)
    parsed = parse_salary(f"{title}\n{text}")
    if parsed is None:
        return None, None, None, None
    return parsed.low, parsed.high, parsed.currency, parsed.interval


def _find_existing(
    conn: sqlite3.Connection, company_id: int, raw: RawJob, ukey: str, dedupe: str
) -> tuple[sqlite3.Row | None, str | None]:
    row = conn.execute(
        "SELECT * FROM jobs WHERE company_id = ? AND source = ? AND external_id = ?",
        (company_id, raw.source, raw.external_id),
    ).fetchone()
    if row:
        return row, "same"
    row = conn.execute(
        """
        SELECT j.* FROM job_links l
        JOIN jobs j ON j.id = l.job_id
        WHERE j.company_id = ? AND l.source = ? AND l.external_id = ?
        """,
        (company_id, raw.source, raw.external_id),
    ).fetchone()
    if row:
        return row, "link"
    if ukey and not ukey.startswith("ext:"):
        row = conn.execute(
            "SELECT * FROM jobs WHERE company_id = ? AND url_key = ?",
            (company_id, ukey),
        ).fetchone()
        if row is None:
            row = conn.execute(
                """
                SELECT j.* FROM job_links l
                JOIN jobs j ON j.id = l.job_id
                WHERE j.company_id = ? AND l.url_key = ?
                """,
                (company_id, ukey),
            ).fetchone()
        if row:
            return row, "url"
    row = conn.execute(
        "SELECT * FROM jobs WHERE company_id = ? AND dedupe_key = ?",
        (company_id, dedupe),
    ).fetchone()
    if row:
        return row, "dedupe"
    return None, None


def _ensure_link(conn: sqlite3.Connection, job_id: int, raw: RawJob, ukey: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO job_links (job_id, source, external_id, apply_url, url_key)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job_id, raw.source, raw.external_id, raw.apply_url, ukey),
    )


def upsert_job(conn: sqlite3.Connection, company_id: int, company_name: str, raw: RawJob) -> str:
    title = " ".join((raw.title or "").split())
    if not title or not raw.external_id:
        return "skipped"
    location = " ".join((raw.location or "").split())
    html = sanitize_html(raw.description_html or raw.description_text or "")
    text = (raw.description_text or "").strip() or html_to_text(html)
    posted = coerce_datetime(raw.posted_at)
    ukey = url_key(raw.apply_url) or f"ext:{raw.source}:{raw.external_id}"
    dedupe = f"{normalize(company_name)}|{normalize(title)}|{normalize(location)}"
    title_folded = " ".join(title.casefold().split())
    now = utcnow()
    existing, kind = _find_existing(conn, company_id, raw, ukey, dedupe)

    if existing is None:
        low, high, currency, interval = _salary_fields(raw, title, text)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                company_id, source, external_id, title, title_folded, normalized_title,
                location, normalized_location, description_html, description_text,
                apply_url, url_key, dedupe_key, posted_at,
                salary_min, salary_max, salary_currency, salary_interval,
                work_mode, seniority, employment, work_auth,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                raw.source,
                raw.external_id,
                title,
                title_folded,
                normalize(title),
                location,
                normalize(location),
                html,
                text,
                raw.apply_url,
                ukey,
                dedupe,
                posted,
                low,
                high,
                currency,
                interval,
                detect_work_mode(location, text, raw.workplace, raw.is_remote),
                detect_seniority(title),
                detect_employment(raw.employment, title, text),
                detect_work_auth(text),
                now,
                now,
            ),
        )
        _ensure_link(conn, int(cur.lastrowid), raw, ukey)
        return "added"

    use_text = text if text else existing["description_text"]
    use_html = html if text else existing["description_html"]
    if kind == "same":
        low, high, currency, interval = _salary_fields(raw, title, use_text)
        if low is None:
            low = existing["salary_min"]
            high = existing["salary_max"]
            currency = existing["salary_currency"]
            interval = existing["salary_interval"]
        work_mode = (
            detect_work_mode(location, use_text, raw.workplace, raw.is_remote) if text else existing["work_mode"]
        )
        seniority = detect_seniority(title)
        employment = (
            detect_employment(raw.employment, title, use_text) if (raw.employment or text) else existing["employment"]
        )
        if employment == "unknown" and existing["employment"] != "unknown" and not raw.employment:
            employment = existing["employment"]
        work_auth = detect_work_auth(use_text) if text else existing["work_auth"]
        if work_auth == "unknown" and existing["work_auth"] != "unknown":
            work_auth = existing["work_auth"]
        conn.execute(
            """
            UPDATE jobs SET
                title = ?, title_folded = ?, normalized_title = ?,
                location = ?, normalized_location = ?,
                description_html = ?, description_text = ?,
                apply_url = ?, url_key = ?, dedupe_key = ?,
                posted_at = COALESCE(?, posted_at),
                salary_min = ?, salary_max = ?, salary_currency = ?, salary_interval = ?,
                work_mode = ?, seniority = ?, employment = ?, work_auth = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                title,
                title_folded,
                normalize(title),
                location,
                normalize(location),
                use_html,
                use_text,
                raw.apply_url or existing["apply_url"],
                ukey,
                dedupe,
                posted,
                low,
                high,
                currency,
                interval,
                work_mode,
                seniority,
                employment,
                work_auth,
                now,
                existing["id"],
            ),
        )
        _ensure_link(conn, existing["id"], raw, ukey)
        return "updated"

    longer = len(text) > len(existing["description_text"] or "")
    if longer:
        low, high, currency, interval = _salary_fields(raw, title, text)
        work_mode = detect_work_mode(location, text, raw.workplace, raw.is_remote)
        work_auth = detect_work_auth(text)
        employment = detect_employment(raw.employment, title, text)
        conn.execute(
            """
            UPDATE jobs SET
                description_html = ?, description_text = ?,
                salary_min = COALESCE(?, salary_min),
                salary_max = COALESCE(?, salary_max),
                salary_currency = COALESCE(?, salary_currency),
                salary_interval = COALESCE(?, salary_interval),
                work_mode = ?, work_auth = ?, employment = ?,
                posted_at = COALESCE(posted_at, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (
                html,
                text,
                low,
                high,
                currency,
                interval,
                work_mode,
                work_auth,
                employment if employment != "unknown" else existing["employment"],
                posted,
                now,
                existing["id"],
            ),
        )
    elif (existing["salary_min"] is None) and (raw.salary_min or raw.salary_max):
        low, high, currency, interval = _salary_fields(raw, title, text or existing["description_text"])
        conn.execute(
            """
            UPDATE jobs SET salary_min = ?, salary_max = ?, salary_currency = ?, salary_interval = ?, updated_at = ?
            WHERE id = ?
            """,
            (low, high, currency, interval, now, existing["id"]),
        )
    _ensure_link(conn, existing["id"], raw, ukey)
    return "merged"


def company_for_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row:
    cleaned = " ".join(name.split())
    norm = normalize(cleaned)
    row = conn.execute("SELECT * FROM companies WHERE normalized_name = ?", (norm,)).fetchone()
    if row:
        return row
    now = utcnow()
    cur = conn.execute(
        """
        INSERT INTO companies (name, normalized_name, board_type, board_token, is_sample, created_at)
        VALUES (?, ?, 'import', NULL, 0, ?)
        """,
        (cleaned, norm, now),
    )
    created = conn.execute("SELECT * FROM companies WHERE id = ?", (cur.lastrowid,)).fetchone()
    if created is None:
        raise RuntimeError("Could not save the company.")
    return created


def _enrich_missing(companies: list[sqlite3.Row]) -> list[dict[str, str]]:
    errors = []
    for company in companies:
        if company["enriched_at"]:
            continue
        try:
            with connect() as conn:
                enrich_company(conn, company["id"])
        except (RuntimeError, httpx.HTTPError) as exc:
            errors.append(
                {
                    "company": company["name"],
                    "message": _short_error(exc) if not isinstance(exc, RuntimeError) else str(exc),
                }
            )
    return errors


def fetch_boards() -> dict:
    with connect() as conn:
        companies = [
            dict(row)
            for row in conn.execute(
                """
                SELECT * FROM companies
                WHERE board_token IS NOT NULL AND board_token != ''
                  AND board_type IN ('greenhouse', 'lever', 'ashby')
                ORDER BY name
                """
            )
        ]
    added = updated = merged = skipped = 0
    errors: list[dict[str, str]] = []
    timeout = httpx.Timeout(60.0, connect=10.0)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=True) as client:
        for company in companies:
            fetcher = FETCHERS.get(company["board_type"])
            if fetcher is None:
                errors.append({"company": company["name"], "message": "Unknown board type."})
                continue
            try:
                raw_jobs = fetcher(client, company["board_token"], company["name"])
            except Exception as exc:
                errors.append({"company": company["name"], "message": _short_error(exc)})
                continue
            with connect() as conn:
                for raw in raw_jobs:
                    kind = upsert_job(conn, company["id"], company["name"], raw)
                    if kind == "added":
                        added += 1
                    elif kind == "updated":
                        updated += 1
                    elif kind == "merged":
                        merged += 1
                    else:
                        skipped += 1
        feed_jobs, feed_errors = fetch_remote_feeds(client, *_feed_query())
    errors.extend(feed_errors)
    with connect() as conn:
        for raw in feed_jobs:
            if not raw.company_name:
                skipped += 1
                continue
            company = company_for_name(conn, raw.company_name)
            kind = upsert_job(conn, company["id"], company["name"], raw)
            if kind == "added":
                added += 1
            elif kind == "updated":
                updated += 1
            elif kind == "merged":
                merged += 1
            else:
                skipped += 1
        scan_unscanned(conn)
    enrichment_errors = _enrich_missing(companies)
    return {
        "added": added,
        "updated": updated,
        "merged": merged,
        "skipped": skipped,
        "errors": errors,
        "enrichment_errors": enrichment_errors,
    }


def _feed_query() -> tuple[str, str]:
    with connect() as conn:
        row = conn.execute("SELECT roles_json, locations_json FROM profile WHERE id = 1").fetchone()
    if row is None:
        return "", ""
    from app.db import loads

    roles = [str(item).strip() for item in loads(row["roles_json"], []) if str(item).strip()]
    places = [str(item).strip() for item in loads(row["locations_json"], []) if str(item).strip()]
    where = ""
    for place in places:
        if place.casefold() not in {"remote", "hybrid", "onsite"}:
            where = place
            break
    return (roles[0] if roles else ""), where


def import_posting(title: str, company: str, location: str, url: str, description: str, source: str) -> dict:
    cleaned_title = " ".join((title or "").split())
    cleaned_company = " ".join((company or "").split())
    cleaned_location = " ".join((location or "").split())[:120]
    cleaned_url = (url or "").strip()
    text = (description or "").strip()
    if source not in {"linkedin", "import"}:
        raise ValueError("Choose LinkedIn or another page.")
    if not cleaned_title or len(cleaned_title) > 180:
        raise ValueError("Enter the job title.")
    if not cleaned_company or len(cleaned_company) > 120:
        raise ValueError("Enter the company name.")
    if len(text) < 40:
        raise ValueError("Paste the description. A title alone cannot be matched.")
    if cleaned_url and not cleaned_url.startswith(("http://", "https://")):
        raise ValueError("The posting link should start with https://.")
    external = hashlib.sha1(
        (cleaned_url or f"{cleaned_company}|{cleaned_title}|{cleaned_location}").encode()
    ).hexdigest()[:16]
    raw = RawJob(
        source=source,
        external_id=external,
        title=cleaned_title,
        location=cleaned_location,
        description_html="",
        description_text=text[:50_000],
        apply_url=cleaned_url[:500],
        company_name=cleaned_company,
    )
    return import_raw_jobs([raw])


def import_raw_jobs(raw_jobs: list[RawJob]) -> dict:
    added = updated = merged = skipped = 0
    touched: list[sqlite3.Row] = []
    seen: set[int] = set()
    with connect() as conn:
        for raw in raw_jobs:
            if not raw.company_name:
                skipped += 1
                continue
            company = company_for_name(conn, raw.company_name)
            kind = upsert_job(conn, company["id"], company["name"], raw)
            if kind == "added":
                added += 1
            elif kind == "updated":
                updated += 1
            elif kind == "merged":
                merged += 1
            else:
                skipped += 1
            if company["id"] not in seen:
                seen.add(company["id"])
                touched.append(dict(company))
    enrichment_errors = _enrich_missing(touched[:10])
    return {
        "added": added,
        "updated": updated,
        "merged": merged,
        "skipped": skipped,
        "imported": len(raw_jobs),
        "enrichment_errors": enrichment_errors,
    }
