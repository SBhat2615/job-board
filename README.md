# Job board

A local board for roles you actually want to read. It collects public Greenhouse, Lever, and Ashby career pages, remote listings, and CSV or JSON you already saved, then filters, deduplicates, and files them under Feed, Applied, Discarded, and Outreach.

It runs on your machine. Nothing here has an account.

## Run

```bash
cd ~/Desktop/PROJECTS/job-board
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app
```

Open http://127.0.0.1:8765

Feature notes for the whole board are at http://127.0.0.1:8765/docs

The first visit asks you to upload a resume, and you can replace that file later. The next screen reads the latest role, offers similar roles to select, lets you type more, and asks for years of experience. The feed then shows jobs for the roles you selected, within one year below and one year above. A posting with a wider range stays when it overlaps. Search looks through every collected job. Each job shows its expectations and what is missing from the resume. Filters sit across the top.

A new database starts with the Indian company boards in `companies.india.toml`. If you already have companies, use **Add Indian boards** in Settings. Click **Fetch** to pull their open roles. Fetch also adds remote listings from [Jobicy](https://jobicy.com/api/v2/remote-jobs), [Remote OK](https://remoteok.com/api), and India or open-remote roles from [Himalayas](https://himalayas.app/jobs/api). Open those listings on the original site. The market menu starts on **India & remote**. **Best match** sorts by preferred phrases and resume overlap. Newest stays the default.

Naukri, Instahyre, LinkedIn, and Cutshort do not publish a key this app can call. There is no LinkedIn connector in this setup. Use **Add posting** to paste a job you found, including a LinkedIn one, or copy the save bookmarklet and run it on that page. The bookmarklet can be blocked on LinkedIn because that site is https and this board is local http. Pasting is the reliable path. Adzuna’s India search is optional: copy `.env.example` to `.env` and set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. If you saved a target role and a city, that search uses them. **Add remote company boards** pulls a few large remote-friendly career pages (GitLab, Notion, Figma, Supabase, PostHog) when you want them. **Find more boards** samples the public Greenhouse, Lever, and Ashby registry for Indian or remote locations. It does not download every job. Add a board, then fetch.

## Add a company

Settings asks for a platform and a board token. The token is the slug in the public careers URL:

- Greenhouse: `https://boards.greenhouse.io/discord` → `discord`
- Lever: `https://jobs.lever.co/wealthfront` → `wealthfront`
- Ashby: `https://jobs.ashbyhq.com/linear` → `linear`

Fetch again after adding one. The same role posted on two boards becomes one card with both apply links.

## Import

CSV or JSON. Each row needs `title` and `company`. Optional columns: `url`, `location`, `description`, `source`, `posted_at`. An example lives in `examples/jobs.csv`.

## Filters, discard, resume

The sidebar filters the current tab. Profile settings are saved for the role cards, warnings, and drafts. Opening the board does not apply them. The market menu starts on India and remote.

Discard stores a reason. Choosing “Company is wrong for me” also hides that company from later fetches. A title phrase is hidden only when you type one. Restore on the Discarded tab puts the job back and removes that company hide rule. Other phrase rules stay until you delete them in Settings.

Upload a text-based resume PDF. Cards then show skills that appear in the requirements or responsibilities, and skills from that section that the resume does not list. Benefits and equal-opportunity text are left out of that comparison. Until then there is no match marker.

Each card also shows the first requirement lines, and flags when the posting says US-only or similar, open worldwide, relocation required, or a years requirement. If your years of experience are saved, a higher requirement is marked as above them. Preferred phrases raise a job when you choose **Best match**. A poor-fit phrase adds a warning and leaves the job on the board. Discard is still how a company gets hidden.

Salary is compared only inside the currency you pick. Jobs with no parsed salary stay visible unless you hide them. Work-authorization tags appear only when the posting says so.

## Apply

**Prepare application** shows the name, email, phone, links, and note saved under Settings → Application, with a copy button on each line and a link to the portal. Greenhouse, Lever, and Ashby only accept the application on the employer’s own form, so the submit button stays there.

**Copy autofill bookmarklet** copies a bookmark address. On a portal page, that bookmark fills the usual name, email, phone, and link fields from this app. It does not submit. If the portal blocks it, use the copy buttons.

## Referrals

Opening a description lists emails and LinkedIn profiles that were written on the posting, and anyone you add. It does not guess private addresses. **Draft referral** writes a note from your application profile. Edit it, open it in your mail app, then **Mark sent**. That schedules a follow-up five days later. **Write follow-up** drafts the next note. The Outreach tab keeps drafts, sent mail, replies, and what is due.

**Draft from checked lines** quotes resume sentences that share a skill with the requirements. Uncheck a line that does not belong. It saves a cover note and form answers on that job. You edit them before copying anything onto a portal. Marking one used does not send it.

**Ask about this job** appears when `OPENAI_API_KEY` is set. It sends one question, the posting excerpt, and the checked lines for that job. The rest of the feed is not scored. Copy `.env.example` to `.env` to add the key, and set `OPENAI_BASE_URL` if the endpoint is not OpenAI. A local Ollama server can be that endpoint. Restart the board after saving the file. Each job already lists what its requirements are missing from the resume, with or without a key.

## Company facts

The first fetch looks up each company on Wikidata and Wikipedia and stores team size, industry, and a short summary when the public record is clearly that company. Open a description to edit those fields or refresh them. There is no generated ethics score. Public notes keep their source link.

To also append web snippets, copy `.env.example` to `.env` and set `TAVILY_API_KEY`. The board works without it.

## Later

What is already in the repo, and what is still open, is in [ROADMAP.md](ROADMAP.md). Add the next points under TODO there.

Full job text and your resume text are stored. The role cards compare requirement skills in the collected postings with the resume. A future source, such as an Apify connector, can return the same job shape and go through the existing dedupe path. Register it in `app/sources/__init__.py`.
