from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.board import (
    Conflict,
    Filters,
    Missing,
    add_company,
    delete_company,
    delete_rule,
    discard_job,
    get_job,
    get_profile,
    list_companies,
    list_jobs,
    list_rules,
    mark_applied,
    restore_job,
    save_resume,
    update_company_facts,
    update_profile,
)
from app.collect import fetch_boards, import_raw_jobs
from app.config import load_env
from app.db import connect, init_db
from app.enrich import enrich_company
from app.importer import parse_upload
from app.vocab import vocab_payload

STATIC = Path(__file__).resolve().parent / "static"
log = logging.getLogger("jobboard")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_env()
    init_db()
    yield


app = FastAPI(title="Job board", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class ProfileIn(BaseModel):
    roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    work_mode: str = "any"
    seniority: str = "any"
    salary_min: int | None = None
    salary_currency: str = "USD"
    skills: list[str] = Field(default_factory=list)
    hide_unknown_salary: bool = False


class CompanyIn(BaseModel):
    name: str
    board_type: str
    board_token: str


class FactsIn(BaseModel):
    team_size: int | None = None
    industry: str = ""
    summary: str = ""


class DiscardIn(BaseModel):
    reason: str
    note: str = ""
    hide_company: bool = False
    hide_phrase: str = ""


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Missing as exc:
        raise HTTPException(404, str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/vocab")
def vocab() -> dict:
    return vocab_payload()


@app.get("/api/profile")
def profile() -> dict:
    return _call(get_profile)


@app.put("/api/profile")
def put_profile(payload: ProfileIn) -> dict:
    return _call(update_profile, payload.model_dump())


@app.post("/api/profile/resume")
async def post_resume(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    return _call(save_resume, data, file.filename or "resume.pdf")


@app.get("/api/companies")
def companies() -> list[dict]:
    return _call(list_companies)


@app.post("/api/companies")
def post_company(payload: CompanyIn) -> dict:
    return _call(add_company, payload.name, payload.board_type, payload.board_token)


@app.patch("/api/companies/{company_id}")
def patch_company(company_id: int, payload: FactsIn) -> dict:
    return _call(update_company_facts, company_id, payload.team_size, payload.industry, payload.summary)


@app.delete("/api/companies/{company_id}")
def remove_company(company_id: int) -> dict:
    _call(delete_company, company_id)
    return {"ok": True}


@app.post("/api/companies/{company_id}/enrich")
def post_enrich(company_id: int, replace: bool = False) -> dict:
    load_env()
    try:
        with connect() as conn:
            return enrich_company(conn, company_id, replace=replace)
    except KeyError as exc:
        raise HTTPException(404, "Company not found.") from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get("/api/rules")
def rules() -> list[dict]:
    return _call(list_rules)


@app.delete("/api/rules/{rule_id}")
def remove_rule(rule_id: int) -> dict:
    _call(delete_rule, rule_id)
    return {"ok": True}


@app.get("/api/jobs")
def jobs(
    status: str = "feed",
    q: str = "",
    role: str = "",
    source: str = "",
    work_mode: str = "",
    seniority: str = "",
    employment: str = "",
    team_size: str = "",
    work_auth: str = "",
    posted_within: str = "",
    salary_min: str = "",
    salary_currency: str = "USD",
    hide_unknown_salary: str = "",
    location: str = "",
) -> dict:
    minimum = None
    if salary_min.strip():
        try:
            minimum = int(salary_min)
        except ValueError as exc:
            raise HTTPException(400, "Minimum salary should be a whole number.") from exc
        if minimum < 0:
            raise HTTPException(400, "Minimum salary cannot be negative.")
    filters = Filters(
        status=status,
        q=q,
        role=role,
        source=source,
        work_mode=work_mode,
        seniority=seniority,
        employment=employment,
        team_size=team_size,
        work_auth=work_auth,
        posted_within=posted_within,
        salary_min=minimum,
        salary_currency=salary_currency or "USD",
        hide_unknown_salary=hide_unknown_salary in {"1", "true", "on"},
        location=location,
    )
    return _call(list_jobs, filters)


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: int) -> dict:
    return _call(get_job, job_id)


@app.post("/api/jobs/{job_id}/applied")
def applied(job_id: int) -> dict:
    _call(mark_applied, job_id)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/discard")
def discard(job_id: int, payload: DiscardIn) -> dict:
    _call(discard_job, job_id, payload.reason, payload.note, payload.hide_company, payload.hide_phrase)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/restore")
def restore(job_id: int) -> dict:
    _call(restore_job, job_id)
    return {"ok": True}


@app.post("/api/fetch")
def fetch() -> dict:
    load_env()
    result = fetch_boards()
    log.info("fetch %s", {key: result[key] for key in ("added", "updated", "merged", "skipped")})
    return result


@app.post("/api/import")
async def import_file(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        raw_jobs = parse_upload(file.filename or "jobs.csv", data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    load_env()
    return import_raw_jobs(raw_jobs)
