# Job board

A local board for roles you actually want to read. It collects public Greenhouse, Lever, and Ashby career pages, plus CSV or JSON you already saved, then filters, deduplicates, and files them under Feed, Applied, and Discarded.

It runs on your machine. Nothing here has an account.

## Run

```bash
cd ~/Desktop/PROJECTS/job-board
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

Open http://127.0.0.1:8765

The first database starts with three sample companies: Discord, Wealthfront, and Linear. Click **Fetch** to pull their open roles. Delete any of them in Settings.

## Add a company

Settings asks for a platform and a board token. The token is the slug in the public careers URL:

- Greenhouse: `https://boards.greenhouse.io/discord` → `discord`
- Lever: `https://jobs.lever.co/wealthfront` → `wealthfront`
- Ashby: `https://jobs.ashbyhq.com/linear` → `linear`

Fetch again after adding one. The same role posted on two boards becomes one card with both apply links.

## Import

CSV or JSON. Each row needs `title` and `company`. Optional columns: `url`, `location`, `description`, `source`, `posted_at`. An example lives in `examples/jobs.csv`.

## Filters, discard, resume

The sidebar filters the current tab. Profile settings are the defaults for the next time you open the board. They start empty, so the first feed is everything you have collected.

Discard stores a reason. Choosing “Company is wrong for me” also hides that company from later fetches. A title phrase is hidden only when you type one. Restore on the Discarded tab puts the job back and removes that company hide rule. Other phrase rules stay until you delete them in Settings.

Upload a text-based resume PDF and cards highlight skills that also appear in the job. Until then there is no match marker.

Salary is compared only inside the currency you pick. Jobs with no parsed salary stay visible unless you hide them. Work-authorization tags appear only when the posting says so.

## Company facts

The first fetch looks up each company on Wikidata and Wikipedia and stores team size, industry, and a short summary when the public record is clearly that company. Open a description to edit those fields or refresh them. There is no generated ethics score. Public notes keep their source link.

To also append web snippets, copy `.env.example` to `.env` and set `TAVILY_API_KEY`. The board works without it.

## Later

Full job text and your resume text are stored, which is enough for a later pass that compares a posting with your background and suggests what to build. That screen is not in this version. A future source, such as an Apify connector, can return the same job shape and go through the existing dedupe path. Register it in `app/sources/__init__.py`.
