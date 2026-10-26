"""One question about one open job. Other jobs are never sent to a model."""

from __future__ import annotations

import os

import httpx

from app.config import USER_AGENT
from app.db import connect, dumps
from app.match import annotate, excerpt, split_sections
from app.parse import utcnow


def ask_enabled() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def list_answers(job_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, question, answer, created_at
            FROM job_answers
            WHERE job_id = ?
            ORDER BY id DESC
            LIMIT 8
            """,
            (job_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "question": row["question"],
            "answer": row["answer"],
            "created_at": (row["created_at"] or "")[:16].replace("T", " "),
        }
        for row in rows
    ]


def _confirmed(resume: str, evidence: list[str]) -> list[str]:
    flat = " ".join((resume or "").split()).casefold()
    kept: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        sentence = " ".join(str(item).split())
        key = sentence.casefold()
        if len(sentence) < 12 or len(sentence) > 400 or key in seen:
            continue
        if key not in flat:
            continue
        seen.add(key)
        kept.append(sentence)
        if len(kept) >= 8:
            break
    return kept


def ask_job(job_id: int, question: str, evidence: list[str]) -> dict:
    if not ask_enabled():
        raise ValueError("Add OPENAI_API_KEY to .env to ask about one job, then restart the board.")
    cleaned = " ".join((question or "").split())
    if len(cleaned) < 8:
        raise ValueError("Ask a full question.")
    cleaned = cleaned[:500]
    with connect() as conn:
        row = conn.execute(
            """
            SELECT j.title, j.location, j.description_text, c.name AS company,
                   p.resume_text, p.yoe_min, p.yoe_max
            FROM jobs j
            JOIN companies c ON c.id = j.company_id
            JOIN profile p ON p.id = 1
            WHERE j.id = ?
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(job_id)
        lines = _confirmed(row["resume_text"] or "", evidence)
        evidence_json = dumps(lines)
        cached = conn.execute(
            """
            SELECT id, question, answer, created_at
            FROM job_answers
            WHERE job_id = ? AND question = ? AND evidence_json = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (job_id, cleaned, evidence_json),
        ).fetchone()
        if cached:
            return {
                "id": cached["id"],
                "question": cached["question"],
                "answer": cached["answer"],
                "created_at": (cached["created_at"] or "")[:16].replace("T", " "),
                "cached": True,
            }
        reading = annotate(
            row["description_text"] or "",
            row["location"] or "",
            [],
            False,
            [],
            [],
            row["yoe_min"],
            row["yoe_max"],
        )
        summary = reading["excerpt"] or excerpt(split_sections(row["description_text"] or ""))
        flag_text = ", ".join(flag["label"] for flag in reading["flags"]) or "none"
        yoe = "not listed"
        if row["yoe_min"] is not None or row["yoe_max"] is not None:
            low = row["yoe_min"] if row["yoe_min"] is not None else "?"
            high = row["yoe_max"] if row["yoe_max"] is not None else "?"
            yoe = f"{low}–{high}"
        quoted = "\n".join(f"- {line}" for line in lines) or "(no resume lines checked)"
        prompt = (
            "Answer one question about this job. Use only the posting excerpt, the flags, "
            "and the checked resume lines. If those do not say, say that the posting does not say. "
            "Do not tell the person to apply. Do not invent experience.\n\n"
            f"Role: {row['title']} at {row['company']}\n"
            f"Location: {row['location'] or 'not listed'}\n"
            f"Excerpt: {summary or 'not listed'}\n"
            f"Flags: {flag_text}\n"
            f"Years they listed: {yoe}\n"
            f"Checked resume lines:\n{quoted}\n\n"
            f"Question: {cleaned}"
        )
        answer = _complete(prompt)
        now = utcnow()
        cur = conn.execute(
            """
            INSERT INTO job_answers (job_id, question, evidence_json, answer, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, cleaned, evidence_json, answer[:4000], now),
        )
        saved_id = int(cur.lastrowid)
    return {
        "id": saved_id,
        "question": cleaned,
        "answer": answer[:4000],
        "created_at": now[:16].replace("T", " "),
        "cached": False,
    }


def write_role_comparison() -> dict:
    raise ValueError("Each job lists its expectations and what is missing from your resume.")


def _complete(prompt: str) -> str:
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    key = os.environ["OPENAI_API_KEY"].strip()
    try:
        response = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT},
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=40,
        )
    except httpx.HTTPError as exc:
        raise ValueError("The model could not be reached.") from exc
    if response.status_code != 200:
        raise ValueError("The model did not answer.")
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("The model did not answer.") from exc
    text = " ".join(str(content or "").split())
    if not text:
        raise ValueError("The model returned an empty answer.")
    return text
