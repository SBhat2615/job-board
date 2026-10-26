"""Contacts published on a job post, plus messages the user writes from them."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta

from app.db import loads
from app.parse import utcnow

_EMAIL = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_LINKEDIN = re.compile(r"https?://(?:[\w.]+\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?", re.IGNORECASE)
_SKIP_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "email.com",
    "domain.com",
    "company.com",
    "sentry.io",
    "wixpress.com",
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "linkedin.com",
    "schema.org",
    "w3.org",
}
_SKIP_LOCAL = {
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "notifications",
    "mailer-daemon",
    "nobody",
}
_STATUSES = {"draft", "sent", "replied", "closed"}
_KINDS = {"referral", "follow_up"}


def extract_contacts(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in _EMAIL.finditer(text or ""):
        email = match.group(0).strip().strip(".")
        local, _, domain = email.casefold().partition("@")
        if not domain or domain in _SKIP_DOMAINS or local in _SKIP_LOCAL:
            continue
        if any(local.startswith(prefix) for prefix in ("noreply", "no-reply", "donotreply")):
            continue
        key = f"email:{email.casefold()}"
        if key in seen:
            continue
        seen.add(key)
        found.append({"name": "", "role": "Email on the posting", "email": email, "link": ""})
        if len(found) >= 8:
            return found
    for match in _LINKEDIN.finditer(text or ""):
        link = match.group(0).split("?")[0]
        if not link.endswith("/"):
            link = f"{link}/"
        key = f"link:{link.casefold()}"
        if key in seen:
            continue
        seen.add(key)
        found.append({"name": "", "role": "LinkedIn profile on the posting", "email": "", "link": link})
        if len(found) >= 8:
            break
    return found


def ensure_job_contacts(conn: sqlite3.Connection, job: dict) -> None:
    if job.get("contacts_scanned"):
        return
    _store_extracted(conn, int(job["id"]), int(job["company_id"]), job.get("description_text") or "")
    conn.execute("UPDATE jobs SET contacts_scanned = 1 WHERE id = ?", (job["id"],))
    job["contacts_scanned"] = 1


def scan_unscanned(conn: sqlite3.Connection, limit: int = 300) -> int:
    rows = conn.execute(
        """
        SELECT id, company_id, description_text
        FROM jobs
        WHERE contacts_scanned = 0
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for row in rows:
        ensure_job_contacts(conn, dict(row))
    return len(rows)


def _store_extracted(conn: sqlite3.Connection, job_id: int, company_id: int, text: str) -> None:
    now = utcnow()
    for contact in extract_contacts(text):
        conn.execute(
            """
            INSERT OR IGNORE INTO contacts (company_id, job_id, name, role, email, link, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'posting', ?)
            """,
            (company_id, job_id, contact["name"], contact["role"], contact["email"], contact["link"], now),
        )


def _contact_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "company_id": row["company_id"],
        "name": row["name"],
        "role": row["role"],
        "email": row["email"],
        "link": row["link"],
        "source": row["source"],
    }


def contacts_for_job(conn: sqlite3.Connection, job_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT * FROM contacts
        WHERE job_id = ?
        ORDER BY source = 'user', id
        """,
        (job_id,),
    ).fetchall()
    return [_contact_payload(row) for row in rows]


def add_contact(job_id: int, name: str, role: str, email: str, link: str) -> dict:
    from app.db import connect

    cleaned_name = " ".join(name.split())[:120]
    cleaned_role = " ".join(role.split())[:120]
    cleaned_email = email.strip()[:200]
    cleaned_link = link.strip()[:300]
    if cleaned_email and ("@" not in cleaned_email or " " in cleaned_email):
        raise ValueError("Enter an email address, or leave it blank.")
    if cleaned_link and not cleaned_link.startswith(("http://", "https://")):
        raise ValueError("A profile link should start with https://.")
    if not cleaned_name and not cleaned_email and not cleaned_link:
        raise ValueError("Add a name, an email, or a link.")
    with connect() as conn:
        job = conn.execute("SELECT id, company_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            raise KeyError(job_id)
        now = utcnow()
        try:
            cur = conn.execute(
                """
                INSERT INTO contacts (company_id, job_id, name, role, email, link, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'user', ?)
                """,
                (job["company_id"], job_id, cleaned_name, cleaned_role, cleaned_email, cleaned_link, now),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("That contact is already on this job.") from exc
        row = conn.execute("SELECT * FROM contacts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _contact_payload(row)


def delete_contact(contact_id: int) -> None:
    from app.db import connect

    with connect() as conn:
        cur = conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        if cur.rowcount == 0:
            raise KeyError(contact_id)


def _profile(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if row is None:
        return {}
    return {
        "full_name": row["full_name"] or "",
        "email": row["email"] or "",
        "phone": row["phone"] or "",
        "city": row["city"] or "",
        "linkedin_url": row["linkedin_url"] or "",
        "github_url": row["github_url"] or "",
        "portfolio_url": row["portfolio_url"] or "",
        "notice_period": row["notice_period"] or "",
        "current_title": row["current_title"] or "",
        "cover_note": row["cover_note"] or "",
        "roles": loads(row["roles_json"], []),
        "skills": loads(row["skills_json"], []),
        "resume_text": row["resume_text"] or "",
        "yoe_min": row["yoe_min"],
        "yoe_max": row["yoe_max"],
    }


def _job_brief(conn: sqlite3.Connection, job_id: int) -> sqlite3.Row:
    row = conn.execute(
        """
        SELECT j.id, j.title, j.location, j.apply_url, j.company_id, c.name AS company
        FROM jobs j JOIN companies c ON c.id = j.company_id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()
    if row is None:
        raise KeyError(job_id)
    return row


def split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in (full_name or "").split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _who(profile: dict) -> str:
    return profile.get("full_name") or "[your name]"


def _greeting(contact: dict | None) -> str:
    name = ((contact or {}).get("name") or "").strip()
    return name.split()[0] if name else "there"


def compose_referral(profile: dict, job: sqlite3.Row, contact: dict | None) -> tuple[str, str]:
    who = _who(profile)
    title = job["title"]
    company = job["company"]
    role = (profile.get("current_title") or "").strip()
    if not role and profile.get("roles"):
        role = str(profile["roles"][0])
    intro = f"I'm {who}"
    if role:
        intro += f", a {role}"
    intro += (
        f". I saw the {title} opening at {company} and wanted to ask whether you'd be open "
        "to referring me before I apply on the portal."
    )
    note = (profile.get("cover_note") or "").strip()
    skills = [str(skill) for skill in (profile.get("skills") or [])][:4]
    if not note and skills:
        note = "The posting overlaps with " + ", ".join(skills) + "."
    lines = [f"Hi {_greeting(contact)},", "", intro]
    if note:
        lines.extend(["", note])
    if profile.get("notice_period"):
        lines.extend(["", f"Notice period: {profile['notice_period']}."])
    if job["apply_url"]:
        lines.extend(["", f"Role: {job['apply_url']}"])
    if profile.get("linkedin_url"):
        lines.append(profile["linkedin_url"])
    if profile.get("phone"):
        lines.append(profile["phone"])
    lines.extend(["", "Thank you,", who])
    return f"Referral for {title} at {company}", "\n".join(lines)


def compose_follow_up(profile: dict, job: sqlite3.Row, contact: dict | None) -> tuple[str, str]:
    who = _who(profile)
    title = job["title"]
    company = job["company"]
    body = "\n".join(
        [
            f"Hi {_greeting(contact)},",
            "",
            f"I wrote earlier about the {title} role at {company}. "
            "I know inboxes get buried, so this is only a short follow-up. "
            "If a referral isn't a fit, no problem — I'll apply through the posting.",
            "",
            "Thank you,",
            who,
        ]
    )
    return f"Following up: {title} at {company}", body


def _confirmed_lines(resume: str, evidence: list[str]) -> list[str]:
    flat = " ".join((resume or "").split()).casefold()
    kept: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        sentence = " ".join(str(item).split())
        key = sentence.casefold()
        if len(sentence) < 12 or len(sentence) > 400 or key in seen or key not in flat:
            continue
        seen.add(key)
        kept.append(sentence)
        if len(kept) >= 8:
            break
    if not kept:
        raise ValueError("Check a line from your resume. The draft only quotes lines that are actually in it.")
    return kept


def compose_cover(profile: dict, job: sqlite3.Row, evidence: list[str]) -> tuple[str, str]:
    who = _who(profile)
    title = job["title"]
    company = job["company"]
    role = (profile.get("current_title") or "").strip()
    if not role and profile.get("roles"):
        role = str(profile["roles"][0])
    intro = f"I'm {who}"
    if role:
        intro += f", a {role}"
    intro += f". I'm writing about the {title} role at {company}."
    lines = ["Hello,", "", intro]
    note = (profile.get("cover_note") or "").strip()
    if note:
        lines.extend(["", note])
    lines.extend(["", "From my experience:"])
    lines.extend(f"- {sentence}" for sentence in evidence)
    if profile.get("notice_period"):
        lines.extend(["", f"Notice period: {profile['notice_period']}."])
    if job["apply_url"]:
        lines.extend(["", job["apply_url"]])
    lines.extend(["", "Thank you,", who])
    return f"{title} at {company}", "\n".join(lines)


def compose_answers(profile: dict, job: sqlite3.Row, evidence: list[str]) -> tuple[str, str]:
    who = _who(profile)
    title = job["title"]
    company = job["company"]
    role = (profile.get("current_title") or "").strip()
    why = f"I'm {who}"
    if role:
        why += f", a {role}"
    why += f". I'm interested in the {title} role at {company}."
    note = (profile.get("cover_note") or "").strip()
    notice = (profile.get("notice_period") or "").strip() or "Not listed on your profile."
    yoe = ""
    if profile.get("yoe_min") is not None or profile.get("yoe_max") is not None:
        low = profile.get("yoe_min")
        high = profile.get("yoe_max")
        if low is not None and high is not None and low != high:
            yoe = f"{low}–{high} years"
        else:
            yoe = f"{low if low is not None else high} years"
    parts = ["Why this role", why]
    if note:
        parts.extend(["", note])
    if yoe:
        parts.extend(["", "Experience", yoe])
    parts.extend(["", "Notice period", notice, "", "Points from my resume"])
    parts.extend(f"- {sentence}" for sentence in evidence)
    return f"Form answers: {title} at {company}", "\n".join(parts)


def create_application_drafts(job_id: int, evidence: list[str]) -> dict:
    from app.db import connect

    with connect() as conn:
        job = _job_brief(conn, job_id)
        profile = _profile(conn)
        lines = _confirmed_lines(profile.get("resume_text") or "", evidence)
        now = utcnow()
        saved = {}
        for kind, composer in (("cover", compose_cover), ("answers", compose_answers)):
            subject, body = composer(profile, job, lines)
            cur = conn.execute(
                """
                INSERT INTO messages (
                    job_id, contact_id, parent_id, kind, status, subject, body, created_at, updated_at
                ) VALUES (?, NULL, NULL, ?, 'draft', ?, ?, ?, ?)
                """,
                (job_id, kind, subject, body, now, now),
            )
            row = conn.execute(_MESSAGE_SQL + " WHERE m.id = ?", (cur.lastrowid,)).fetchone()
            saved[kind] = _message_payload(row)
        return saved


def _message_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "job_title": row["job_title"] if "job_title" in row.keys() else "",
        "company": row["company"] if "company" in row.keys() else "",
        "contact_id": row["contact_id"],
        "contact_name": row["contact_name"] if "contact_name" in row.keys() else "",
        "contact_email": row["contact_email"] if "contact_email" in row.keys() else "",
        "contact_link": row["contact_link"] if "contact_link" in row.keys() else "",
        "parent_id": row["parent_id"],
        "kind": row["kind"],
        "status": row["status"],
        "subject": row["subject"],
        "body": row["body"],
        "follow_up_on": row["follow_up_on"],
        "sent_at": (row["sent_at"] or "")[:10] or None,
    }


_MESSAGE_SQL = """
SELECT m.*, j.title AS job_title, c.name AS company,
       ct.name AS contact_name, ct.email AS contact_email, ct.link AS contact_link
FROM messages m
JOIN jobs j ON j.id = m.job_id
JOIN companies c ON c.id = j.company_id
LEFT JOIN contacts ct ON ct.id = m.contact_id
"""


def messages_for_job(conn: sqlite3.Connection, job_id: int) -> list[dict]:
    rows = conn.execute(
        _MESSAGE_SQL + " WHERE m.job_id = ? ORDER BY m.created_at, m.id",
        (job_id,),
    ).fetchall()
    return [_message_payload(row) for row in rows]


def create_message(job_id: int, kind: str, contact_id: int | None, parent_id: int | None) -> dict:
    from app.db import connect

    if kind not in _KINDS:
        raise ValueError("Choose a referral or a follow-up.")
    with connect() as conn:
        job = _job_brief(conn, job_id)
        contact = None
        if contact_id:
            row = conn.execute("SELECT * FROM contacts WHERE id = ? AND job_id = ?", (contact_id, job_id)).fetchone()
            if row is None:
                raise ValueError("That contact is not on this job.")
            contact = _contact_payload(row)
        parent = None
        if kind == "follow_up":
            if not parent_id:
                raise ValueError("A follow-up needs the message it continues.")
            parent = conn.execute(
                "SELECT * FROM messages WHERE id = ? AND job_id = ?",
                (parent_id, job_id),
            ).fetchone()
            if parent is None:
                raise ValueError("The original message is not on this job.")
            if contact is None and parent["contact_id"]:
                contact_id = parent["contact_id"]
                row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
                contact = _contact_payload(row) if row else None
        profile = _profile(conn)
        if kind == "follow_up":
            subject, body = compose_follow_up(profile, job, contact)
        else:
            subject, body = compose_referral(profile, job, contact)
        now = utcnow()
        cur = conn.execute(
            """
            INSERT INTO messages (
                job_id, contact_id, parent_id, kind, status, subject, body, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            (job_id, contact_id, parent_id if kind == "follow_up" else None, kind, subject, body, now, now),
        )
        saved = conn.execute(_MESSAGE_SQL + " WHERE m.id = ?", (cur.lastrowid,)).fetchone()
        return _message_payload(saved)


def _clean_day(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text[:10]
    date.fromisoformat(text)
    return text


def update_message(message_id: int, subject: str, body: str, status: str, follow_up_on: object) -> dict:
    from app.db import connect

    if status not in _STATUSES:
        raise ValueError("Choose draft, sent, replied, or closed.")
    cleaned_subject = " ".join(subject.split())[:180]
    cleaned_body = body.strip()[:8000]
    if not cleaned_subject or not cleaned_body:
        raise ValueError("A message needs a subject and a body.")
    day = _clean_day(follow_up_on)
    with connect() as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            raise KeyError(message_id)
        sent_at = row["sent_at"]
        if status == "sent":
            if not sent_at:
                sent_at = utcnow()
                if day is None and row["kind"] == "referral":
                    day = (date.today() + timedelta(days=5)).isoformat()
        else:
            day = None
        now = utcnow()
        conn.execute(
            """
            UPDATE messages
            SET subject = ?, body = ?, status = ?, follow_up_on = ?, sent_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (cleaned_subject, cleaned_body, status, day, sent_at, now, message_id),
        )
        if status == "sent" and row["kind"] == "follow_up" and row["parent_id"]:
            conn.execute(
                "UPDATE messages SET follow_up_on = NULL, updated_at = ? WHERE id = ?",
                (now, row["parent_id"]),
            )
        if status in {"replied", "closed"} and row["parent_id"]:
            conn.execute(
                "UPDATE messages SET follow_up_on = NULL, updated_at = ? WHERE id = ?",
                (now, row["parent_id"]),
            )
        if status == "sent" and row["kind"] in {"referral", "follow_up"}:
            conn.execute(
                """
                UPDATE jobs SET status = 'outreach', updated_at = ?
                WHERE id = ? AND status = 'feed'
                """,
                (now, row["job_id"]),
            )
        saved = conn.execute(_MESSAGE_SQL + " WHERE m.id = ?", (message_id,)).fetchone()
        return _message_payload(saved)


def list_outreach() -> dict:
    from app.db import connect

    today = date.today().isoformat()
    with connect() as conn:
        rows = [
            _message_payload(row)
            for row in conn.execute(
                _MESSAGE_SQL + " ORDER BY m.follow_up_on IS NULL, m.follow_up_on, m.updated_at DESC"
            ).fetchall()
        ]
    due = [item for item in rows if item["status"] == "sent" and item["follow_up_on"] and item["follow_up_on"] <= today]
    drafts = [item for item in rows if item["status"] == "draft"]
    sent = [item for item in rows if item["status"] == "sent" and item not in due]
    closed = [item for item in rows if item["status"] in {"replied", "closed"}]
    return {
        "today": today,
        "due": due,
        "drafts": drafts,
        "sent": sent,
        "closed": closed[:30],
        "counts": {"due": len(due), "drafts": len(drafts), "sent": len(sent)},
    }


def apply_packet(job_id: int) -> dict:
    from app.db import connect

    with connect() as conn:
        job = _job_brief(conn, job_id)
        profile = _profile(conn)
        links = conn.execute(
            "SELECT source, apply_url FROM job_links WHERE job_id = ? AND apply_url != '' ORDER BY id",
            (job_id,),
        ).fetchall()
    first, last = split_name(profile.get("full_name") or "")
    fields = [
        ("First name", first),
        ("Last name", last),
        ("Email", profile.get("email") or ""),
        ("Phone", profile.get("phone") or ""),
        ("City", profile.get("city") or ""),
        ("LinkedIn", profile.get("linkedin_url") or ""),
        ("GitHub", profile.get("github_url") or ""),
        ("Portfolio", profile.get("portfolio_url") or ""),
        ("Current title", profile.get("current_title") or ""),
        ("Notice period", profile.get("notice_period") or ""),
        ("Note you can paste", profile.get("cover_note") or ""),
    ]
    return {
        "job_id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "apply_url": job["apply_url"] or "",
        "links": [{"source": row["source"], "apply_url": row["apply_url"]} for row in links],
        "fields": [{"label": label, "value": value} for label, value in fields],
        "ready": bool(first and profile.get("email")),
    }


def autofill_payload() -> dict:
    from app.db import connect

    with connect() as conn:
        profile = _profile(conn)
    first, last = split_name(profile.get("full_name") or "")
    return {
        "full_name": profile.get("full_name") or "",
        "first_name": first,
        "last_name": last,
        "email": profile.get("email") or "",
        "phone": profile.get("phone") or "",
        "city": profile.get("city") or "",
        "linkedin_url": profile.get("linkedin_url") or "",
        "github_url": profile.get("github_url") or "",
        "portfolio_url": profile.get("portfolio_url") or "",
        "cover_note": profile.get("cover_note") or "",
    }
