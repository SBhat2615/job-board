from __future__ import annotations

from urllib.parse import quote

import httpx

from app.htmlutil import html_to_text, prepare_html
from app.sources.base import RawJob
from app.sources.common import check_board, location_name


def fetch(client: httpx.Client, token: str, company_name: str) -> list[RawJob]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{quote(token)}/jobs"
    response = client.get(url, params={"content": "true"})
    check_board(response, token)
    payload = response.json()
    jobs: list[RawJob] = []
    for item in payload.get("jobs") or []:
        content = item.get("content") or ""
        if not content and item.get("id"):
            detail = client.get(f"https://boards-api.greenhouse.io/v1/boards/{quote(token)}/jobs/{item['id']}")
            if detail.status_code == 200:
                content = detail.json().get("content") or ""
        html = prepare_html(content)
        jobs.append(
            RawJob(
                source="greenhouse",
                external_id=str(item.get("id") or ""),
                title=str(item.get("title") or "").strip(),
                location=location_name(item.get("location")),
                description_html=html,
                description_text=html_to_text(html),
                apply_url=str(item.get("absolute_url") or "").strip(),
                posted_at=item.get("first_published") or item.get("updated_at"),
                company_name=company_name,
            )
        )
    return [job for job in jobs if job.title and job.external_id]
