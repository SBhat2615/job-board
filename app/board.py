from __future__ import annotations

import io
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import RESUME_PATH
from app.db import connect, dumps, loads
from app.parse import annual_ceiling, format_salary, normalize, phrase_key, utcnow
from app.resume import dedupe_skills, detect_skills, overlapping_skills
from app.vocab import (
    CURRENCIES,
    DISCARD_REASONS,
    EMPLOYMENT,
    SENIORITY,
    SOURCES,
    TEAM_SIZES,
    WORK_AUTH,
    WORK_MODES,
)

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_BUCKETS = {
    "1-10": (1, 10),
    "11-50": (11, 50),
    "51-200": (51, 200),
    "201-1000": (201, 1000),
    "1000+": (1000, None),
}


class Conflict(Exception):
    pass


class Missing(Exception):
    pass


@dataclass
class Filters:
    status: str = "feed"
    q: str = ""
    role: str = ""
    source: str = ""
    work_mode: str = ""
    seniority: str = ""
    employment: str = ""
    team_size: str = ""
    work_auth: str = ""
    posted_within: str = ""
    salary_min: int | None = None
    salary_currency: str = "USD"
    hide_unknown_salary: bool = False
    location: str = ""


def _profile_row(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if row is None:
        raise Missing("Profile is missing.")
    return row


def profile_payload(row: sqlite3.Row) -> dict:
    return {
        "roles": loads(row["roles_json"], []),
        "locations": loads(row["locations_json"], []),
        "work_mode": row["work_mode"],
        "seniority": row["seniority"],
        "salary_min": row["salary_min"],
        "salary_currency": row["salary_currency"],
        "skills": loads(row["skills_json"], []),
        "hide_unknown_salary": bool(row["hide_unknown_salary"]),
        "has_resume": bool(row["resume_text"]),
        "resume_filename": row["resume_filename"],
    }


def get_profile() -> dict:
    with connect() as conn:
        return profile_payload(_profile_row(conn))


def _clean_terms(values: list[str], limit: int) -> list[str]:
    cleaned = []
    seen = set()
    for value in values:
        text = " ".join(str(value).split())
        if not text or len(text) > 80:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def update_profile(payload: dict) -> dict:
    work_mode = payload.get("work_mode") or "any"
    seniority = payload.get("seniority") or "any"
    if work_mode != "any" and work_mode not in WORK_MODES:
        raise ValueError("Choose a work mode from the list.")
    if seniority != "any" and seniority not in SENIORITY:
        raise ValueError("Choose a seniority from the list.")
    currency = str(payload.get("salary_currency") or "USD").upper()
    if currency not in CURRENCIES:
        raise ValueError("Choose USD, INR, EUR, or GBP.")
    salary = payload.get("salary_min")
    if salary is not None and salary != "":
        try:
            salary = int(salary)
        except (TypeError, ValueError) as exc:
            raise ValueError("Minimum salary should be a whole number.") from exc
        if salary < 0:
            raise ValueError("Minimum salary cannot be negative.")
    else:
        salary = None
    roles = _clean_terms(list(payload.get("roles") or []), 20)
    locations = _clean_terms(list(payload.get("locations") or []), 20)
    skills = dedupe_skills([str(item) for item in (payload.get("skills") or [])])
    hide = 1 if payload.get("hide_unknown_salary") else 0
    with connect() as conn:
        conn.execute(
            """
            UPDATE profile SET
                roles_json = ?, locations_json = ?, work_mode = ?, seniority = ?,
                salary_min = ?, salary_currency = ?, skills_json = ?, hide_unknown_salary = ?
            WHERE id = 1
            """,
            (dumps(roles), dumps(locations), work_mode, seniority, salary, currency, dumps(skills), hide),
        )
        return profile_payload(_profile_row(conn))


def save_resume(data: bytes, filename: str) -> dict:
    if len(data) > 5_000_000:
        raise ValueError("PDF is larger than 5 MB.")
    if not data.startswith(b"%PDF"):
        raise ValueError("Upload a PDF.")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("This PDF is encrypted.")
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except ValueError:
        raise
    except (PdfReadError, Exception) as exc:
        raise ValueError("This PDF could not be read.") from exc
    if not text:
        raise ValueError("This PDF has no extractable text. Export a text-based PDF and try again.")
    text = text[:200_000]
    skills = detect_skills(text)
    RESUME_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESUME_PATH.write_bytes(data)
    stored_name = " ".join((filename or "resume.pdf").split())[-120:] or "resume.pdf"
    with connect() as conn:
        conn.execute(
            """
            UPDATE profile SET resume_text = ?, resume_filename = ?, skills_json = ?
            WHERE id = 1
            """,
            (text, stored_name, dumps(skills)),
        )
        return profile_payload(_profile_row(conn))


def list_companies() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.id) AS job_count
            FROM companies c
            ORDER BY c.name
            """
        ).fetchall()
    return [_company_payload(row) for row in rows]


def _company_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "board_type": row["board_type"],
        "board_token": row["board_token"],
        "team_size": row["team_size"],
        "industry": row["industry"],
        "summary": row["summary"],
        "signals": loads(row["signals_json"], []),
        "source_url": row["source_url"],
        "enriched_at": row["enriched_at"],
        "user_edited": bool(row["user_edited"]),
        "is_sample": bool(row["is_sample"]),
        "job_count": row["job_count"] if "job_count" in row.keys() else None,
    }


def add_company(name: str, board_type: str, board_token: str) -> dict:
    cleaned = " ".join(name.split())
    if not cleaned or len(cleaned) > 120:
        raise ValueError("Enter a company name.")
    if board_type not in {"greenhouse", "lever", "ashby"}:
        raise ValueError("Board type should be Greenhouse, Lever, or Ashby.")
    token = board_token.strip()
    if not _TOKEN.match(token):
        raise ValueError("The board token should be the slug from the careers URL.")
    norm = normalize(cleaned)
    with connect() as conn:
        existing = conn.execute("SELECT * FROM companies WHERE normalized_name = ?", (norm,)).fetchone()
        if existing and existing["board_token"]:
            raise Conflict(f"{existing['name']} is already on the watchlist.")
        now = utcnow()
        if existing:
            conn.execute(
                """
                UPDATE companies SET name = ?, board_type = ?, board_token = ? WHERE id = ?
                """,
                (cleaned, board_type, token, existing["id"]),
            )
            company_id = existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO companies (name, normalized_name, board_type, board_token, is_sample, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (cleaned, norm, board_type, token, now),
            )
            company_id = int(cur.lastrowid)
        row = conn.execute(
            """
            SELECT c.*, (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.id) AS job_count
            FROM companies c WHERE c.id = ?
            """,
            (company_id,),
        ).fetchone()
        if row is None:
            raise Missing("Company was not saved.")
        return _company_payload(row)


def delete_company(company_id: int) -> None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
        if row is None:
            raise Missing("Company not found.")
        conn.execute(
            "DELETE FROM rules WHERE kind = 'company' AND normalized_value = ?",
            (row["normalized_name"],),
        )
        conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))


def update_company_facts(company_id: int, team_size: int | None, industry: str, summary: str) -> dict:
    if team_size is not None and team_size < 0:
        raise ValueError("Team size cannot be negative.")
    industry = " ".join(industry.split())[:120]
    summary = summary.strip()[:2000]
    with connect() as conn:
        row = conn.execute("SELECT id FROM companies WHERE id = ?", (company_id,)).fetchone()
        if row is None:
            raise Missing("Company not found.")
        conn.execute(
            """
            UPDATE companies
            SET team_size = ?, industry = ?, summary = ?, user_edited = 1
            WHERE id = ?
            """,
            (team_size, industry or None, summary or None, company_id),
        )
        saved = conn.execute(
            """
            SELECT c.*, (SELECT COUNT(*) FROM jobs j WHERE j.company_id = c.id) AS job_count
            FROM companies c WHERE c.id = ?
            """,
            (company_id,),
        ).fetchone()
        if saved is None:
            raise Missing("Company not found.")
        return _company_payload(saved)


def list_rules() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM rules ORDER BY kind, value").fetchall()
    return [
        {"id": row["id"], "kind": row["kind"], "value": row["value"], "created_at": row["created_at"]}
        for row in rows
    ]


def delete_rule(rule_id: int) -> None:
    with connect() as conn:
        cur = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        if cur.rowcount == 0:
            raise Missing("Rule not found.")


def _add_rule(conn: sqlite3.Connection, kind: str, value: str, normalized_value: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO rules (kind, value, normalized_value, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (kind, value, normalized_value, utcnow()),
    )


def discard_job(job_id: int, reason: str, note: str, hide_company: bool, hide_phrase: str) -> None:
    if reason not in DISCARD_REASONS:
        raise ValueError("Choose a discard reason.")
    note = note.strip()[:500]
    phrase = phrase_key(hide_phrase)
    if phrase and len(phrase) < 2:
        phrase = ""
    if len(phrase) > 80:
        raise ValueError("Hide phrases should be 80 characters or fewer.")
    with connect() as conn:
        job = conn.execute(
            """
            SELECT j.id, j.status, c.name, c.normalized_name
            FROM jobs j JOIN companies c ON c.id = j.company_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()
        if job is None:
            raise Missing("Job not found.")
        now = utcnow()
        conn.execute(
            """
            UPDATE jobs
            SET status = 'discarded', discard_reason = ?, discard_note = ?, discarded_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (reason, note or None, now, now, job_id),
        )
        if hide_company:
            _add_rule(conn, "company", job["name"], job["normalized_name"])
        if phrase:
            _add_rule(conn, "phrase", " ".join(hide_phrase.split())[:80], phrase)


def mark_applied(job_id: int) -> None:
    with connect() as conn:
        job = conn.execute("SELECT id, status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            raise Missing("Job not found.")
        if job["status"] == "discarded":
            raise Conflict("Restore this job before marking it applied.")
        now = utcnow()
        conn.execute(
            """
            UPDATE jobs
            SET status = 'applied', applied_at = ?, discard_reason = NULL, discard_note = NULL,
                discarded_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now, now, job_id),
        )


def restore_job(job_id: int) -> None:
    with connect() as conn:
        job = conn.execute(
            """
            SELECT j.id, j.status, c.normalized_name
            FROM jobs j JOIN companies c ON c.id = j.company_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()
        if job is None:
            raise Missing("Job not found.")
        if job["status"] == "discarded":
            conn.execute(
                "DELETE FROM rules WHERE kind = 'company' AND normalized_value = ?",
                (job["normalized_name"],),
            )
        now = utcnow()
        conn.execute(
            """
            UPDATE jobs
            SET status = 'feed', discard_reason = NULL, discard_note = NULL,
                discarded_at = NULL, applied_at = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now, job_id),
        )


def _counts(conn: sqlite3.Connection) -> dict:
    def count(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    feed_all = count("SELECT COUNT(*) FROM jobs WHERE status = 'feed'")
    feed_visible = count(
        """
        SELECT COUNT(*) FROM jobs j
        JOIN companies c ON c.id = j.company_id
        WHERE j.status = 'feed'
        """
        + _rule_sql()
    )
    return {
        "feed": feed_visible,
        "applied": count("SELECT COUNT(*) FROM jobs WHERE status = 'applied'"),
        "discarded": count("SELECT COUNT(*) FROM jobs WHERE status = 'discarded'"),
        "hidden": feed_all - feed_visible,
    }


def _rule_sql() -> str:
    return """
        AND NOT EXISTS (
            SELECT 1 FROM rules r
            WHERE r.kind = 'company' AND r.normalized_value = c.normalized_name
        )
        AND NOT EXISTS (
            SELECT 1 FROM rules r
            WHERE r.kind = 'phrase' AND instr(j.title_folded, r.normalized_value) > 0
        )
    """


def _attach_links(conn: sqlite3.Connection, jobs: list[dict]) -> None:
    ids = [job["id"] for job in jobs]
    grouped: dict[int, list[dict]] = {}
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        marks = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT job_id, source, apply_url FROM job_links WHERE job_id IN ({marks}) ORDER BY id",
            chunk,
        ).fetchall()
        for row in rows:
            grouped.setdefault(row["job_id"], []).append(
                {"source": row["source"], "apply_url": row["apply_url"]}
            )
    for job in jobs:
        links = [link for link in grouped.get(job["id"], []) if link.get("apply_url")]
        if not links and job.get("apply_url"):
            links = [{"source": job["source"], "apply_url": job["apply_url"]}]
        job["links"] = links
        job["sources"] = list(dict.fromkeys([job["source"], *[link["source"] for link in links]]))


def _posted_ok(posted_at: str | None, days: int) -> bool:
    if not posted_at:
        return False
    text = posted_at if len(posted_at) > 10 else posted_at + "T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed >= datetime.now(timezone.utc) - timedelta(days=days)


def _location_ok(job: dict, location: str, preferred: list[str]) -> bool:
    if not location or location == "any":
        return True
    wanted = preferred if location == "__preferred__" else [location]
    wanted = [item.strip() for item in wanted if item and item.strip()]
    if not wanted:
        return True
    loc = (job.get("location") or "").casefold()
    mode = job.get("work_mode")
    aliases = {"on-site": "onsite", "on site": "onsite"}
    for item in wanted:
        word = item.casefold()
        if word in loc:
            return True
        alias = aliases.get(word, word)
        if alias in {"remote", "hybrid", "onsite"} and mode == alias:
            return True
    return False


def _salary_ok(job: dict, filters: Filters) -> bool:
    has_salary = job["salary_min"] is not None or job["salary_max"] is not None
    if filters.hide_unknown_salary and not has_salary:
        return False
    if filters.salary_min is None:
        return True
    same = (job.get("salary_currency") or "").upper() == filters.salary_currency.upper()
    if not has_salary or not same:
        return True
    ceiling = annual_ceiling(job["salary_min"], job["salary_max"], job["salary_interval"])
    if ceiling is None:
        return not filters.hide_unknown_salary
    return ceiling >= filters.salary_min


def _team_ok(team_size: int | None, bucket: str) -> bool:
    if not bucket or bucket == "any":
        return True
    if team_size is None or bucket not in _BUCKETS:
        return False
    low, high = _BUCKETS[bucket]
    if team_size < low:
        return False
    if high is None:
        return True
    return team_size <= high


def _matches(job: dict, filters: Filters, preferred_locations: list[str]) -> bool:
    if filters.q:
        blob = " ".join(
            [
                job.get("title") or "",
                job.get("company") or "",
                job.get("location") or "",
                job.get("description_text") or "",
            ]
        ).casefold()
        if filters.q.casefold() not in blob:
            return False
    if filters.role:
        blob = f"{job.get('title') or ''}\n{job.get('description_text') or ''}".casefold()
        if filters.role.casefold() not in blob:
            return False
    if filters.source and filters.source not in (job.get("sources") or []):
        return False
    for field, column in (
        ("work_mode", "work_mode"),
        ("seniority", "seniority"),
        ("employment", "employment"),
        ("work_auth", "work_auth"),
    ):
        wanted = getattr(filters, field)
        if wanted and wanted != "any" and job.get(column) != wanted:
            return False
    if not _team_ok(job.get("team_size"), filters.team_size):
        return False
    if filters.posted_within:
        if not _posted_ok(job.get("posted_at"), int(filters.posted_within)):
            return False
    if not _location_ok(job, filters.location, preferred_locations):
        return False
    if not _salary_ok(job, filters):
        return False
    return True


def _public_job(job: dict, skills: list[str], has_resume: bool) -> dict:
    text = f"{job.get('title') or ''}\n{job.get('description_text') or ''}"
    return {
        "id": job["id"],
        "company_id": job["company_id"],
        "company": job["company"],
        "title": job["title"],
        "location": job.get("location") or "",
        "source": job["source"],
        "sources": job.get("sources") or [job["source"]],
        "apply_url": job.get("apply_url") or "",
        "links": job.get("links") or [],
        "posted_at": (job.get("posted_at") or "")[:10] or None,
        "salary_label": format_salary(job.get("salary_min"), job.get("salary_max"), job.get("salary_currency"), job.get("salary_interval")),
        "work_mode": job["work_mode"],
        "seniority": job["seniority"],
        "employment": job["employment"],
        "work_auth": job["work_auth"],
        "team_size": job.get("team_size"),
        "industry": job.get("industry") or "",
        "status": job["status"],
        "discard_reason": job.get("discard_reason"),
        "discard_note": job.get("discard_note"),
        "applied_at": (job.get("applied_at") or "")[:10] or None,
        "overlapping_skills": overlapping_skills(skills, text) if has_resume else [],
    }


def _blank_any(value: str) -> str:
    return "" if value in {"", "any"} else value


def list_jobs(filters: Filters) -> dict:
    filters.q = filters.q.strip()[:200]
    filters.role = filters.role.strip()[:80]
    filters.source = _blank_any(filters.source)
    filters.work_mode = _blank_any(filters.work_mode)
    filters.seniority = _blank_any(filters.seniority)
    filters.employment = _blank_any(filters.employment)
    filters.team_size = _blank_any(filters.team_size)
    filters.work_auth = _blank_any(filters.work_auth)
    filters.posted_within = _blank_any(filters.posted_within)
    filters.location = "" if filters.location in {"", "any"} else filters.location.strip()[:80]
    if filters.status not in {"feed", "applied", "discarded"}:
        raise ValueError("Unknown tab.")
    if filters.source and filters.source not in SOURCES:
        raise ValueError("Unknown platform.")
    if filters.work_mode and filters.work_mode not in WORK_MODES:
        raise ValueError("Unknown work mode.")
    if filters.seniority and filters.seniority not in SENIORITY:
        raise ValueError("Unknown seniority.")
    if filters.employment and filters.employment not in EMPLOYMENT:
        raise ValueError("Unknown employment type.")
    if filters.work_auth and filters.work_auth not in WORK_AUTH:
        raise ValueError("Unknown work authorization.")
    if filters.team_size and filters.team_size not in TEAM_SIZES:
        raise ValueError("Unknown team size.")
    if filters.posted_within and filters.posted_within not in {"1", "3", "7", "30"}:
        raise ValueError("Unknown posted-within window.")
    if filters.salary_currency not in CURRENCIES:
        raise ValueError("Unknown currency.")
    rule_sql = _rule_sql() if filters.status == "feed" else ""
    with connect() as conn:
        profile = _profile_row(conn)
        counts = _counts(conn)
        rows = conn.execute(
            f"""
            SELECT j.id, j.company_id, j.source, j.title, j.location, j.apply_url, j.posted_at,
                   j.salary_min, j.salary_max, j.salary_currency, j.salary_interval,
                   j.work_mode, j.seniority, j.employment, j.work_auth, j.status,
                   j.discard_reason, j.discard_note, j.applied_at, j.description_text,
                   c.name AS company, c.team_size, c.industry
            FROM jobs j
            JOIN companies c ON c.id = j.company_id
            WHERE j.status = ?
            {rule_sql}
            ORDER BY j.posted_at IS NULL, j.posted_at DESC, j.id DESC
            """,
            (filters.status,),
        ).fetchall()
        jobs = [dict(row) for row in rows]
        _attach_links(conn, jobs)
    preferred = list(loads(profile["locations_json"], []))
    skills = list(loads(profile["skills_json"], []))
    has_resume = bool(profile["resume_text"])
    matched = [job for job in jobs if _matches(job, filters, preferred)]
    sliced = matched[:500]
    return {
        "total": len(jobs),
        "matched": len(matched),
        "truncated": len(matched) > 500,
        "counts": {key: counts[key] for key in ("feed", "applied", "discarded")},
        "hidden": counts["hidden"],
        "jobs": [_public_job(job, skills, has_resume) for job in sliced],
    }


def get_job(job_id: int) -> dict:
    from app.htmlutil import sanitize_html

    with connect() as conn:
        row = conn.execute(
            """
            SELECT j.*, c.name AS company, c.team_size, c.industry, c.summary,
                   c.signals_json, c.source_url, c.enriched_at, c.user_edited
            FROM jobs j
            JOIN companies c ON c.id = j.company_id
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            raise Missing("Job not found.")
        job = dict(row)
        _attach_links(conn, [job])
        profile = _profile_row(conn)
    skills = list(loads(profile["skills_json"], []))
    payload = _public_job(job, skills, bool(profile["resume_text"]))
    payload.update(
        {
            "description_html": sanitize_html(job.get("description_html") or job.get("description_text") or ""),
            "summary": job.get("summary") or "",
            "signals": loads(job.get("signals_json"), []),
            "source_url": job.get("source_url") or "",
            "enriched_at": job.get("enriched_at"),
            "user_edited": bool(job.get("user_edited")),
        }
    )
    return payload
