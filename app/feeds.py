"""Remote listings from public feeds. Company boards stay in app.sources."""

from __future__ import annotations

import os

import httpx

from app.config import USER_AGENT
from app.market import is_india, is_open_remote
from app.sources.base import RawJob
from app.sources.common import BoardError

_CAP = 40


def _positive(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return number or None


def _keep_remote_ok(location: str) -> bool:
    text = (location or "").strip()
    if not text:
        return True
    if is_india(text) or is_open_remote(text):
        return True
    blocked = ("united states", "usa", "u.s.", "united kingdom", "europe", "canada", "latam")
    return not any(word in text.casefold() for word in blocked)


def _jobicy(client: httpx.Client, geo: str) -> list[dict]:
    response = client.get(
        "https://jobicy.com/api/v2/remote-jobs",
        params={"count": 50, "geo": geo},
    )
    if response.status_code != 200:
        raise BoardError(f"Jobicy returned HTTP {response.status_code}.")
    payload = response.json()
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(jobs, list):
        raise BoardError("Jobicy did not return a job list.")
    return [item for item in jobs if isinstance(item, dict)]


def _from_jobicy(item: dict) -> RawJob | None:
    title = str(item.get("jobTitle") or "").strip()
    company = str(item.get("companyName") or "").strip()
    external_id = str(item.get("id") or "").strip()
    if not title or not company or not external_id:
        return None
    geo = str(item.get("jobGeo") or "").strip()
    if geo and not (is_india(geo) or is_open_remote(geo)):
        return None
    kinds = item.get("jobType") or []
    employment = ""
    if isinstance(kinds, list) and kinds:
        employment = str(kinds[0])
    elif isinstance(kinds, str):
        employment = kinds
    return RawJob(
        source="jobicy",
        external_id=external_id,
        title=title,
        location=geo or "Remote",
        description_html=str(item.get("jobDescription") or item.get("jobExcerpt") or ""),
        description_text="",
        apply_url=str(item.get("url") or "").strip(),
        posted_at=item.get("pubDate"),
        employment=employment or None,
        is_remote=True,
        company_name=company,
    )


def _from_remote_ok(item: dict) -> RawJob | None:
    if not item.get("position"):
        return None
    title = str(item.get("position") or "").strip()
    company = str(item.get("company") or "").strip()
    external_id = str(item.get("id") or "").strip()
    location = str(item.get("location") or "").strip()
    if not title or not company or not external_id or not _keep_remote_ok(location):
        return None
    low = _positive(item.get("salary_min"))
    high = _positive(item.get("salary_max"))
    return RawJob(
        source="remoteok",
        external_id=external_id,
        title=title,
        location=location or "Remote",
        description_html=str(item.get("description") or ""),
        description_text="",
        apply_url=str(item.get("url") or item.get("apply_url") or "").strip(),
        posted_at=item.get("date") or item.get("epoch"),
        salary_min=low,
        salary_max=high,
        salary_currency="USD" if low or high else None,
        salary_interval="year" if low or high else None,
        is_remote=True,
        company_name=company,
    )


def _from_adzuna(item: dict) -> RawJob | None:
    title = str(item.get("title") or "").strip()
    company = str((item.get("company") or {}).get("display_name") or "").strip()
    external_id = str(item.get("id") or "").strip()
    if not title or not company or not external_id:
        return None
    location = str((item.get("location") or {}).get("display_name") or "India")
    low = _positive(item.get("salary_min"))
    high = _positive(item.get("salary_max"))
    return RawJob(
        source="adzuna",
        external_id=external_id,
        title=title,
        location=location,
        description_html="",
        description_text=str(item.get("description") or ""),
        apply_url=str(item.get("redirect_url") or "").strip(),
        posted_at=item.get("created"),
        salary_min=low,
        salary_max=high,
        salary_currency="INR" if low or high else None,
        salary_interval="year" if low or high else None,
        company_name=company,
    )


def _prefer(jobs: list[RawJob]) -> list[RawJob]:
    india = [job for job in jobs if is_india(job.location, job.description_text)]
    rest = [job for job in jobs if job not in india]
    return (india + rest)[:_CAP]


def _from_himalayas(item: dict) -> RawJob | None:
    title = str(item.get("title") or "").strip()
    company = str(item.get("companyName") or "").strip()
    external_id = str(item.get("guid") or "").strip()
    places = item.get("locationRestrictions") or []
    if isinstance(places, str):
        places = [places]
    location = ", ".join(str(place).strip() for place in places if str(place).strip())
    if not title or not company or not external_id:
        return None
    if not (is_india(location) or is_open_remote(location)):
        return None
    low = _positive(item.get("minSalary"))
    high = _positive(item.get("maxSalary"))
    employment = str(item.get("employmentType") or "")
    return RawJob(
        source="himalayas",
        external_id=external_id,
        title=title,
        location=location or "Remote",
        description_html=str(item.get("description") or item.get("excerpt") or ""),
        description_text="",
        apply_url=str(item.get("applicationLink") or "").strip(),
        posted_at=item.get("pubDate"),
        employment=employment or None,
        salary_min=low,
        salary_max=high,
        salary_currency=(str(item.get("currency") or "").upper() or None) if low or high else None,
        salary_interval="year" if low or high else None,
        is_remote=True if is_open_remote(location) and not is_india(location) else None,
        company_name=company,
    )


def _himalayas(client: httpx.Client) -> list[RawJob]:
    found: list[RawJob] = []
    cursor = None
    for _ in range(6):
        params: dict[str, object] = {"limit": 50}
        if cursor:
            params["cursor"] = cursor
        response = client.get("https://himalayas.app/jobs/api", params=params)
        if response.status_code != 200:
            raise BoardError(f"Himalayas returned HTTP {response.status_code}.")
        payload = response.json()
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            raise BoardError("Himalayas did not return a job list.")
        for item in jobs:
            if isinstance(item, dict) and (job := _from_himalayas(item)):
                found.append(job)
        cursor = payload.get("nextCursor") if isinstance(payload, dict) else None
        if not cursor or len(found) >= _CAP:
            break
    return found


def fetch_remote_feeds(
    client: httpx.Client,
    what: str = "",
    where: str = "",
) -> tuple[list[RawJob], list[dict[str, str]]]:
    """Return listings and non-fatal feed errors. Caps each feed."""
    found: list[RawJob] = []
    errors: list[dict[str, str]] = []
    jobicy: list[RawJob] = []
    for geo in ("anywhere", "apac"):
        try:
            for item in _jobicy(client, geo):
                job = _from_jobicy(item)
                if job:
                    jobicy.append(job)
        except (BoardError, httpx.HTTPError, ValueError) as exc:
            message = str(exc) if isinstance(exc, BoardError) else "Jobicy could not be reached."
            errors.append({"company": "Jobicy", "message": message})
            break
    unique: list[RawJob] = []
    seen: set[str] = set()
    for job in jobicy:
        if job.external_id in seen:
            continue
        seen.add(job.external_id)
        unique.append(job)
    found.extend(_prefer(unique))
    try:
        response = client.get("https://remoteok.com/api", headers={"User-Agent": USER_AGENT})
        if response.status_code != 200:
            raise BoardError(f"Remote OK returned HTTP {response.status_code}.")
        payload = response.json()
        if not isinstance(payload, list):
            raise BoardError("Remote OK did not return a job list.")
        remote = [job for item in payload if isinstance(item, dict) and (job := _from_remote_ok(item))]
        found.extend(_prefer(remote))
    except (BoardError, httpx.HTTPError, ValueError) as exc:
        message = str(exc) if isinstance(exc, BoardError) else "Remote OK could not be reached."
        errors.append({"company": "Remote OK", "message": message})
    try:
        found.extend(_prefer(_himalayas(client)))
    except (BoardError, httpx.HTTPError, ValueError) as exc:
        message = str(exc) if isinstance(exc, BoardError) else "Himalayas could not be reached."
        errors.append({"company": "Himalayas", "message": message})
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()
    if app_id and app_key:
        try:
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": 25,
                "what": (what or "software engineer")[:80],
                "content-type": "application/json",
            }
            if where.strip():
                params["where"] = where.strip()[:80]
            response = client.get("https://api.adzuna.com/v1/api/jobs/in/search/1", params=params)
            if response.status_code != 200:
                raise BoardError(f"Adzuna returned HTTP {response.status_code}.")
            results = response.json().get("results") or []
            found.extend(job for item in results if isinstance(item, dict) and (job := _from_adzuna(item)))
        except (BoardError, httpx.HTTPError, ValueError) as exc:
            message = str(exc) if isinstance(exc, BoardError) else "Adzuna could not be reached."
            errors.append({"company": "Adzuna", "message": message})
    return found, errors
