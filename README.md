# Job board

A local board for roles you actually want to read. It collects public Greenhouse, Lever, and Ashby career pages and a few remote listings, then files them under Feed, Outreach, Applied, and Discarded.

It runs on your machine. Nothing here has an account. Jobs, the resume, and drafts stay in `data/`.

## Run

```bash
cd ~/Desktop/PROJECTS/job-board
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

Open http://127.0.0.1:8765

Feature notes are at http://127.0.0.1:8765/docs

## First visit

The first screen asks for a text-based resume PDF. You can replace it later with **Re-upload resume**. The next screen reads the latest role, offers similar roles to check, accepts a typed role, and asks for years of experience.

The feed then shows the roles you checked, within one year below and one year above that range. A posting whose range overlaps stays. A posting with no years stated stays. A posting whose minimum sits above the window is left out. Search looks through every collected job.

## Where the jobs come from

A new database loads the Indian boards in `companies.india.toml`. **Fetch** reads those Greenhouse, Lever, and Ashby pages, then adds listings from [Jobicy](https://jobicy.com/api/v2/remote-jobs), [Remote OK](https://remoteok.com/api), and India or open-remote roles from [Himalayas](https://himalayas.app/jobs/api). Open those listings on the original site.

Naukri, Instahyre, Cutshort, and LinkedIn are not fetched. **Add posting** saves a job you paste, including a LinkedIn one. The save bookmarklet can be blocked on an https page, so paste is the path that works.

Adzuna’s India search is optional. Copy `.env.example` to `.env` and set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. When a target role and a city are saved, that search uses the first of each.

The same role on two boards becomes one card with both apply links. A later fetch updates the text and keeps Applied or Discarded.

## On the board

Filters sit across the top. The market menu starts on **India & remote**. **Newest** is the default sort. **Best match** ranks by preferred phrases and resume overlap. A card does not show a number.

**Discard** stores a reason. “Company is wrong for me” can hide that company. A title phrase is hidden only when one is typed. **Restore** puts the job back and removes that company hide rule.

**Apply External** opens the employer’s posting. The application is filled and submitted on that page. **Description** shows the posting and the company facts you can edit. **Referral** lists people already saved for that job and lets you add another.

**Draft referral** opens in your mail app. Opening mail does not mark it sent. **Mark sent** does, moves the job to Outreach, and schedules a follow-up five days later. **Got referred** files it under Applied, with the referral. **Mark applied** files a job you submitted yourself, without one.

**Draft from checked lines** quotes resume sentences that share a skill with the requirements. Marking a cover note or form answer used does not send it. **Ask about this job** runs when `OPENAI_API_KEY` is set. It can point at a local OpenAI-compatible server through `OPENAI_BASE_URL`.

Company facts come from Wikidata and Wikipedia when the public record matches the name. Optional `TAVILY_API_KEY` adds sourced snippets. There is no ethics score. Prefer and avoid phrases warn or change Best match rank. They do not hide a job.

## Checks

```bash
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/pytest
```

`requirements.lock` is what the GitHub check installs.

## Later

What is already in the repo, and what is still open, is in [ROADMAP.md](ROADMAP.md).
