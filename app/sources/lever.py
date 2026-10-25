from __future__ import annotations

import html
from urllib.parse import quote

import httpx

from app.htmlutil import html_to_text
from app.sources.base import RawJob
from app.sources.common import check_board, location_name


def _salary(item: dict) -> tuple[int | None, int | None, str | None, str | None]:
    raw = item.get("salaryRange") or {}
    if not isinstance(raw, dict):
        return None, None, None, None
    low = raw.get("min")
    high = raw.get("max")
    if low is None and high is None:
        return None, None, None, None
    def as_int(value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(round(float(value)))
    return as_int(low), as_int(high), (raw.get("currency") or None), (raw.get("interval") or None)


def fetch(client: httpx.Client, token: str, company_name: str) -> list[RawJob]:
    url = f"https://api.lever.co/v0/postings/{quote(token)}"
    response = client.get(url, params={"mode": "json"})
    check_board(response, token)
    payload = response.json()
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("postings") or []
    else:
        rows = payload
    jobs: list[RawJob] = []
    for item in rows:
        parts_html = [item.get("description") or ""]
        text_parts = [item.get("descriptionPlain") or "", item.get("openingPlain") or ""]
        for block in item.get("lists") or []:
            heading = str(block.get("text") or "").strip()
            body = block.get("content") or ""
            if heading:
                parts_html.append(f"<h3>{html.escape(heading)}</h3>")
                text_parts.append(heading)
            parts_html.append(body)
            text_parts.append(html_to_text(body))
        html_doc = "\n".join(part for part in parts_html if part)
        text = "\n".join(part.strip() for part in text_parts if part and part.strip())
        if not text:
            text = html_to_text(html_doc)
        low, high, currency, interval = _salary(item)
        categories = item.get("categories") or {}
        jobs.append(
            RawJob(
                source="lever",
                external_id=str(item.get("id") or ""),
                title=str(item.get("text") or "").strip(),
                location=location_name(categories.get("location") or item.get("country")),
                description_html=html_doc,
                description_text=text,
                apply_url=str(item.get("hostedUrl") or item.get("applyUrl") or "").strip(),
                posted_at=item.get("createdAt"),
                workplace=item.get("workplaceType"),
                employment=categories.get("commitment"),
                salary_min=low,
                salary_max=high,
                salary_currency=currency,
                salary_interval=interval,
                company_name=company_name,
            )
        )
    return [job for job in jobs if job.title and job.external_id]
