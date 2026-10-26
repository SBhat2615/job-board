from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.ask import ask_job, write_role_comparison
from app.board import (
    Conflict,
    Filters,
    Missing,
    delete_company,
    delete_rule,
    discard_job,
    finish_welcome,
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
from app.collect import fetch_boards, import_posting
from app.config import load_env
from app.contacts import (
    add_contact,
    apply_packet,
    autofill_payload,
    create_application_drafts,
    create_message,
    delete_contact,
    list_outreach,
    update_message,
)
from app.db import connect, init_db
from app.enrich import enrich_company
from app.roles import review
from app.vocab import vocab_payload

STATIC = Path(__file__).resolve().parent / "static"
log = logging.getLogger("jobboard")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_env()
    init_db()
    yield


app = FastAPI(title="Job board", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
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
    full_name: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    notice_period: str = ""
    current_title: str = ""
    cover_note: str = ""
    prefer_text: str = ""
    avoid_text: str = ""
    yoe_min: int | None = None
    yoe_max: int | None = None


class FactsIn(BaseModel):
    team_size: int | None = None
    industry: str = ""
    summary: str = ""


class DiscardIn(BaseModel):
    reason: str
    note: str = ""
    hide_company: bool = False
    hide_phrase: str = ""


class ContactIn(BaseModel):
    name: str = ""
    role: str = ""
    email: str = ""
    link: str = ""


class MessageIn(BaseModel):
    kind: str
    contact_id: int | None = None
    parent_id: int | None = None


class PostingIn(BaseModel):
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str
    source: str = "linkedin"


class DraftIn(BaseModel):
    evidence: list[str] = Field(default_factory=list)


class AskIn(BaseModel):
    question: str
    evidence: list[str] = Field(default_factory=list)


def _cors(response: Response) -> None:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"


class MessageUpdate(BaseModel):
    subject: str
    body: str
    status: str = "draft"
    follow_up_on: str = ""


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Missing as exc:
        raise HTTPException(404, str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, "That record was not found.") from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/docs")
def docs() -> FileResponse:
    return FileResponse(STATIC / "docs.html")


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


@app.get("/api/profile/autofill")
def profile_autofill(response: Response) -> dict:
    response.headers["Access-Control-Allow-Origin"] = "*"
    return _call(autofill_payload)


@app.post("/api/profile/resume")
async def post_resume(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    return _call(save_resume, data, file.filename or "resume.pdf")


@app.get("/api/companies")
def companies() -> list[dict]:
    return _call(list_companies)


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
    market: str = "",
    sort: str = "",
    curated: str = "",
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
        market=market,
        sort=sort,
        curated=curated in {"1", "true", "on"},
    )
    return _call(list_jobs, filters)


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: int) -> dict:
    return _call(get_job, job_id)


@app.get("/api/jobs/{job_id}/packet")
def packet(job_id: int) -> dict:
    return _call(apply_packet, job_id)


@app.post("/api/jobs/{job_id}/contacts")
def post_contact(job_id: int, payload: ContactIn) -> dict:
    return _call(add_contact, job_id, payload.name, payload.role, payload.email, payload.link)


@app.delete("/api/contacts/{contact_id}")
def remove_contact(contact_id: int) -> dict:
    _call(delete_contact, contact_id)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/messages")
def post_message(job_id: int, payload: MessageIn) -> dict:
    return _call(create_message, job_id, payload.kind, payload.contact_id, payload.parent_id)


@app.patch("/api/messages/{message_id}")
def patch_message(message_id: int, payload: MessageUpdate) -> dict:
    return _call(update_message, message_id, payload.subject, payload.body, payload.status, payload.follow_up_on)


@app.get("/api/outreach")
def outreach() -> dict:
    return _call(list_outreach)


@app.post("/api/profile/welcome")
def post_welcome() -> dict:
    return _call(finish_welcome)


@app.get("/api/profile/roles")
def profile_roles() -> dict:
    return _call(review)


@app.post("/api/profile/roles/compare")
def profile_roles_compare() -> dict:
    load_env()
    return _call(write_role_comparison)


@app.post("/api/jobs/{job_id}/drafts")
def post_drafts(job_id: int, payload: DraftIn) -> dict:
    return _call(create_application_drafts, job_id, payload.evidence)


@app.post("/api/jobs/{job_id}/ask")
def post_ask(job_id: int, payload: AskIn) -> dict:
    load_env()
    return _call(ask_job, job_id, payload.question, payload.evidence)


@app.options("/api/import/posting")
def import_posting_options() -> Response:
    response = Response(status_code=204)
    _cors(response)
    return response


@app.post("/api/import/posting")
def post_posting(payload: PostingIn, response: Response) -> dict:
    _cors(response)
    return _call(
        import_posting,
        payload.title,
        payload.company,
        payload.location,
        payload.url,
        payload.description,
        payload.source,
    )


@app.post("/api/jobs/{job_id}/applied")
def applied(job_id: int) -> dict:
    _call(mark_applied, job_id)
    return {"ok": True}


@app.post("/api/jobs/{job_id}/referred")
def referred(job_id: int) -> dict:
    _call(mark_applied, job_id, True)
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
