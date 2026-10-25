from __future__ import annotations

from urllib.parse import quote

import httpx

from app.sources.base import RawJob
from app.sources.common import check_board, location_name


def fetch(client: httpx.Client, token: str, company_name: str) -> list[RawJob]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{quote(token)}"
    response = client.get(url)
    check_board(response, token)
    payload = response.json()
    jobs: list[RawJob] = []
    for item in payload.get("jobs") or []:
        if item.get("isListed") is False:
            continue
        html_doc = item.get("descriptionHtml") or ""
        text = item.get("descriptionPlain") or ""
        jobs.append(
            RawJob(
                source="ashby",
                external_id=str(item.get("id") or ""),
                title=str(item.get("title") or "").strip(),
                location=location_name(item.get("location")),
                description_html=html_doc,
                description_text=text,
                apply_url=str(item.get("jobUrl") or item.get("applyUrl") or "").strip(),
                posted_at=item.get("publishedAt"),
                workplace=item.get("workplaceType"),
                employment=item.get("employmentType"),
                is_remote=item.get("isRemote") if isinstance(item.get("isRemote"), bool) else None,
                company_name=company_name,
            )
        )
    return [job for job in jobs if job.title and job.external_id]
