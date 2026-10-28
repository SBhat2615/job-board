<div align="center">

# Job board

A tracker for an application you have already found.

Save the role, the person you asked, and the date you mean to follow up. The posting stays with that record.

[**Open the live app**](https://job-board-blue-nine.vercel.app)

[![Live app](https://img.shields.io/badge/live-job--board-0f766e?style=flat-square)](https://job-board-blue-nine.vercel.app)
[![CI](https://github.com/SBhat2615/job-board/actions/workflows/ci.yml/badge.svg)](https://github.com/SBhat2615/job-board/actions/workflows/ci.yml)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue?style=flat-square)](https://www.python.org/downloads/release/python-3100/)

[Roadmap](ROADMAP.md) · [Feature notes](http://127.0.0.1:8765/docs)

</div>

The live app is the hosted copy. Opening it asks for the Vercel account that owns the project. Your jobs and resume stay on your machine, in `data/jobs.sqlite`, and are not copied there.

---

## The pipeline

```text
Feed  →  Outreach  →  Applied
                ↘
                  Discarded
```

| Stage | What it means |
| --- | --- |
| **Feed** | A role you are still reading. |
| **Outreach** | You marked a referral or follow-up as sent. A follow-up is dated five days later. |
| **Applied** | Split into **with a referral** and **without one**. |
| **Discarded** | A role you set aside, with a reason. Restore puts it back. |

Opening a mail draft does not mark it sent. **Mark sent** does.

## What you can do

- **Add posting** saves a job you paste, including one from LinkedIn. The board does not crawl LinkedIn, Naukri, Instahyre, or Cutshort.
- **Description** shows the posting and the company facts you can edit.
- **Referral** lists people saved on that job and lets you add another. The draft opens in your mail app.
- **Got referred** files the job under Applied, with the referral. **Mark applied** files one you submitted yourself.
- **Apply External** opens the employer’s page. You submit the application there.
- **Fetch** reads public Greenhouse, Lever, and Ashby boards, plus [Jobicy](https://jobicy.com/api/v2/remote-jobs), [Remote OK](https://remoteok.com/api), and India or open-remote roles from [Himalayas](https://himalayas.app/jobs/api). The same role on two boards becomes one card with both apply links.
- A resume PDF on the first visit suggests roles and a years window. The feed keeps roles you checked, one year below and one year above that range. A card does not show a match score.

## Run it locally

Requires Python 3.10.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Notes on each feature are at [/docs](http://127.0.0.1:8765/docs).

A new database loads the Indian boards in `companies.india.toml`. Leave `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` unset so this copy keeps using `data/jobs.sqlite`.

## Configuration

Copy `.env.example` to `.env`. Every key is optional.

| Variable | Used for |
| --- | --- |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | An India search, using the first saved role and city. |
| `TAVILY_API_KEY` | A few sourced snippets on a company. Facts still come from Wikidata and Wikipedia without it. |
| `OPENAI_API_KEY` | **Ask about this job**, and the role comparison. Point `OPENAI_BASE_URL` at a local server if you want one. |
| `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | A hosted database, only when both are set. |
| `JOB_BOARD_DB` | Forces a local SQLite file. The tests set this so they never touch Turso. |

## Stack

FastAPI and Uvicorn serve the API and the pages in `app/static`. SQLite holds the data, with numbered migrations in `app/migrations`. The hosted database is Turso, through `libsql`. GitHub Actions runs Ruff and pytest on every push.

## Checks

```bash
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/pytest
```

CI installs `requirements.lock`.

## Status

The tracker works on this machine. Accounts, a Chrome extension that saves the open job page, and a public sign-in are still ahead. The working list is [ROADMAP.md](ROADMAP.md).
