from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawJob:
    source: str
    external_id: str
    title: str
    location: str
    description_html: str
    description_text: str
    apply_url: str
    posted_at: str | None = None
    workplace: str | None = None
    employment: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    is_remote: bool | None = None
    company_name: str | None = None
