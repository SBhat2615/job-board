# Roadmap

A tracker for applications you have already found. You save a role from the page you are on, then keep the posting, the person you asked, and the next follow-up in one place. LinkedIn, Naukri, Instahyre, and company sites stay where you discover roles. This app does not become another one of those.

A feed of public career pages is a side door. It can put a matching role on the board. It is not the point of the product.

No account yet. Jobs, the resume, and drafts stay in the local database. The **Revamp** below adds accounts and a hosted copy. It does not block the tracker on this machine.

This sheet is the working list. The sections above the Revamp are the current state. The next step is the first open box under **TODO**.

## Already in the repo

### Board

- Local app at `http://127.0.0.1:8765/`. Feature notes live at `/docs`.
- The database is `data/jobs.sqlite`. Schema changes are numbered files in `app/migrations`. `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` open a hosted database instead.
- Tabs: Feed, Outreach, Applied, Discarded. Outreach holds a job after a referral is marked sent. Applied splits into With referral and Without referral.
- Filters across the top: search, one role, market, sort, platform, work mode, seniority, employment, team size, work authorization, location, posted date, salary.
- Market starts on India & remote. Preferred locations are saved and stay unselected until chosen. Bangalore also matches Bengaluru.
- Newest is the default sort. Best match ranks by preferred phrases and resume overlap. There is no numeric score on a card.
- Discard stores a reason. “Company is wrong for me” can hide that company. A title phrase is hidden only when one is typed. Restore puts the job back and removes that company hide rule.
- The same role on two boards becomes one card with both apply links. A later fetch updates the text and keeps Applied or Discarded.

### How the feed is chosen

- First screen is a resume PDF upload. A file already on disk can be read, or replaced. **Re-upload resume** does the same later.
- The next screen reads the latest role, lists similar roles to check, accepts a typed role, and asks for years of experience.
- The feed shows the checked roles only. Search looks through every collected job.
- Years use a window of one year below and one year above. A posting whose range overlaps that window stays. A posting with no years stated stays. A posting whose minimum sits above the window is left out.
- Each card has **Expectations** (the requirements excerpt) and **What's missing** (requirement skills from a fixed catalog that are not on the resume).
- Similar roles are a local map. Machine learning engineer can suggest AI engineer, SDE (AI), Generative AI engineer, LLM engineer, and Applied ML engineer. Data scientist, data engineer, software engineer, backend, and frontend have smaller maps. A suggestion is not included until it is checked. A typed role matches its own words.

### Sources

- Greenhouse, Lever, and Ashby company boards. A new database loads the Indian boards in `companies.india.toml`.
- Fetch also pulls Jobicy, Remote OK, and Himalayas (India or open-remote).
- Optional Adzuna India search when `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are set. It uses the first saved role and the first city.
- **Add posting** saves a job you paste, including a LinkedIn one. A save bookmarklet tries to read the open page and often fails, because that page is https and this board is http. Paste is what works today.

### Apply, mail, and company notes

- Settings → Application holds the name and contact details used in referral drafts. Until a name is saved, a draft says “[your name]”.
- **Apply External** opens the employer’s posting. The application is filled and submitted on that page.
- Contacts come from text on the posting, plus contacts you add.
- **Draft referral** opens in your mail app. Opening mail does not mark it sent. **Mark sent** does, moves the job to Outreach, and schedules a follow-up five days later. **Got referred** moves it to Applied under With referral.
- **Draft from checked lines** quotes resume sentences that share a skill with the requirements. Marking a cover note or form answer used does not send it.
- **Ask about this job** runs when `OPENAI_API_KEY` is set. It can point at a local OpenAI-compatible server through `OPENAI_BASE_URL`. The question is about that one job.
- Company facts come from Wikidata and Wikipedia when the public record matches the name. Optional `TAVILY_API_KEY` adds sourced snippets. There is no ethics score.
- Prefer and avoid phrases warn or change Best match rank. They do not hide a job.

## Left as-is on purpose

- Naukri, Instahyre, Cutshort, and LinkedIn are not crawled as feeds. A job on one of those sites is saved from the page you have open, by the extension in the first TODO, or pasted when that page cannot be read.
- The board does not submit an application or send mail.
- Private emails are not guessed.
- ESCO and Hirebase are not called. Role matching stays on this machine.
- Full job-board CSV dumps are not downloaded.

## Open, not scheduled

These are gaps already visible in the current board. They are not the next slice until they are copied into **TODO**.

- The similar-role map covers a few families. A role outside that map has no suggestions until you type one.
- A resume that lists skills and no job title gets its latest role from those skills.
- The curated list is only as full as the boards already fetched. A role with few public Greenhouse, Lever, or Ashby postings stays a short list until more boards or pasted jobs are added.
- A new source, such as an Apify connector, can be registered in `app/sources/__init__.py` and reuse the existing dedupe path. None is registered.

## Revamp, before the TODO list

The Revamp is accounts and a hosted copy of this tracker, on free plans. Other people can sign up. Each person keeps their own profile, resume, statuses, hide rules, contacts, and drafts. A saved posting stays with the person who saved it. Fetched postings can be shared. The steps stay in this order. They do not block the tracker on this machine.

### How it should look

- A light page with one accent color, one open-licensed sans font served by the app, and a fixed type scale. Colors, spacing, radius, and shadows are named tokens in one place.
- A top bar with the board name, search, **Add posting**, and the account menu.
- Feed, Outreach, Applied, and Discarded as one segmented control with counts.
- A row of quick chips above the list, each with a count: every checked role, India, Remote, and Posted this week.
- A filter rail on the left on a desktop, and a drawer on a phone. It covers role, location, work mode, seniority, source, posted date, and salary. Each option shows how many jobs it keeps. It replaces the thirteen dropdowns across the top.
- A compact job row: a company initial tile, the title, the company and cities, how long ago it was posted, a New badge, one summary line from the posting, and tags for seniority, work mode, and employment. The row opens in place to Description, Company facts, Referral, and What's missing, with **Apply External**, **Discard**, and **Mark applied**.
- A three-step strip on a first visit (pick roles, open a job, ask for a referral) that can be closed.
- Loading, empty, and error states on every list. It works on a phone, by keyboard, and with a screen reader.

The layout borrows the idea of a referral list site. No code, text, or images are copied.

### Steps

- [x] **1. Clean up and lock in what works now.**

  Remove the routes the screen no longer uses: adding a company board, watchlists, file import, and board suggestions. Bring README, `/docs`, and **Already in the repo** in line with the current screen. Add `pytest` tests for the API as it stands: the feed choice by roles and years, the merge of the same role across boards, discard and restore, **Mark sent** to Outreach, **Got referred** to Applied with referral, and **Mark applied** to Applied without referral. Add `ruff` for lint and format, a dependency lock file, and a GitHub Actions check on every push. The rewrite then has a safety net.

- [x] **2. Database layer and migrations.**

  Replace the `ALTER TABLE` checks in `app/db.py` with numbered migration files and a schema version table. One connection module opens the local SQLite file, or a Turso database when its URL and token are set. Turso's `libsql` Python client keeps the `sqlite3` interface, so the SQL stays as written.

- [ ] **3. Accounts, and data that belongs to one person.**

  Sign in with Google, asking for the basic profile and email only. No password is stored. The session is a signed cookie that scripts cannot read, and every write checks the request's origin.

  Shared rows: fetched postings, their apply links, and the public company record. Rows owned by one person: profile, resume text, hide rules, contacts, drafts, form answers, their own notes on a company, and a new per-person job state (status, referred, discard reason, applied date). A pasted posting is visible only to the person who added it. Every query takes the signed-in user, and tests prove one account cannot read or change another's rows.

  A person can download everything they own as JSON, and delete the account with every row it owns. The resume keeps its text only, not the PDF. On `127.0.0.1` the board still runs with one built-in user and no sign-in, and a script copies the current `data/jobs.sqlite` into that user.

  On the hosted copy, **Fetch** is the daily scheduled run, not a button anyone can press. **Ask about this job** stays local only, because it would bill the owner's model key for every user.

- [ ] **4. One API contract for both sides.**

  Every route returns a typed response model. The list route returns one page of jobs (50 at a time, with a cursor for the next page), the count on each tab, and the count on each filter option. The OpenAPI file is served under `/api`, and the frontend's TypeScript types are generated from it. CI fails when the generated types are out of date.

- [ ] **5. The new frontend in `web/`.**

  React with strict TypeScript, Vite, and Tailwind. TanStack Query holds server data. React Router has Feed, Outreach, Applied, Discarded, Settings, and Docs. Filters live in the URL, so the back button and a saved link restore the same view. A small set of shared parts (button, chip, tabs, job row, panel, dialog, field, toast) is built on accessible primitives such as Radix UI. ESLint, Prettier, `tsc`, and Vitest with Testing Library run in CI.

  In development, Vite proxies `/api` to the board on 8765. In production, FastAPI serves the built `web/dist`, so the page and the API share one origin and need no CORS.

  Screens, in order: the list with the filter rail and search; the opened row; Outreach and the two Applied groups; the welcome steps (resume, roles, years); Settings; then **Add posting**, Discard, and the referral draft. The old `app/static` screen stays until each screen matches it, then it is deleted.

- [ ] **6. Checks in a real browser.**

  Playwright runs the main path: sign in (a test-only sign-in), upload a resume, pick roles, discard and restore, **Mark sent** to Outreach, and **Got referred** to Applied. The same run checks accessibility with axe and takes phone-width screenshots.

- [ ] **7. Deploy on free plans.**

  The site and the database are both hosted. The empty copy is live at https://job-board-blue-nine.vercel.app, and opening it asks for the Vercel account. The local jobs and resume are not in that database. Sign-in is worth building because the accounts live in Turso, which stays up when the site is idle. Neither host keeps a database on its own disk: that disk is wiped on restart.

  - The site runs on the [Vercel Hobby](https://vercel.com/docs/plans/hobby) plan, which needs no card. FastAPI and the built pages are one project on one domain, so the sign-in cookie is same-origin. Hobby is for a personal, non-commercial project. Vercel runs Python 3.12 or newer, and `libsql` 0.1.11 has a Linux x86_64 wheel for 3.12. A function may run for 5 minutes, which covers a page and a resume upload. The first request after idle starts the function again. It does not show a one-minute loading page.
  - The data lives on the [Turso](https://turso.tech/pricing) free plan, which needs no card and does not sleep: 5 GB, 500 million rows read, and 10 million rows written a month. Hitting a limit blocks the database until the next month. It does not add a charge. Vercel has no database that can hold this SQLite data. Its disk is temporary, and Blob stores files, not these tables.
  - The PDF copy under `data/` moves into the database before deploy. The extracted resume text is already stored there. A host restart would otherwise delete the file.
  - The daily fetch is a GitHub Actions schedule that writes straight to Turso. The site does not stay awake to make those calls.
  - GitHub Pages (`github.io`) only serves static files, so it cannot run this Python app or keep a resume behind a login. Fly.io has no lasting free allowance. Railway's free credit is about $1 a month after the trial, which will not keep the app running. Cloudflare would mean rewriting the app, and its free database is 500 MB with 100,000 rows written a day. Render's free web service can run the app, but it sleeps after 15 idle minutes and the next visit waits about a minute. Its free Postgres expires 30 days after creation. Render stays the backup if the Vercel deploy cannot install `libsql`.
  - Google client keys, the session key, the Turso token, and the Adzuna keys are host secrets, never in the repo.
  - Sign-in and **Add posting** are rate limited. A resume upload has a size cap. Responses carry security headers.
  - A privacy page says what is stored and how to delete it. India's data protection law applies once other people's details are stored.
  - Confirm these limits on the pricing pages again before the deploy.

## TODO

Tick a box when that item is done. The next step is the first open box. The Revamp has its own order and does not block these.

### Tracker

- [ ] **Save the open job.** Next step.

  A Chrome extension reads the job page you already have open and sends the title, company, location, description, and page URL to this board. You click Save on that tab. It does not walk search results, and it does not log into LinkedIn, Naukri, Instahyre, or any other site.

  It posts to `POST /api/import/posting`. That handler today accepts source `linkedin` or `import`. This build also accepts a Naukri or Instahyre label so the card can name where the job came from. The description still has to be real text, 40 characters or more. If the page cannot be read, the popup shows the fields it got and you fill the gaps. **Add posting** paste stays for that case.

  Until accounts exist, the extension talks only to `http://127.0.0.1:8765`. The hosted site is one shared profile, so it is not the extension target yet. The bookmarklet is not the path. It fails because those pages are https and this board is http.

  A saved job uses the same role match, years window, expectations, and drafts as a fetched job.

- [ ] **A person and a follow-up on that job.**

  On the saved job, add a point of contact or a referral: a name, a title when you have one, and a way to reach them that you type in. An address that was never published stays blank. The board does not guess one.

  **Draft referral** opens your mail app. Opening mail does not mark it sent. **Mark sent** moves the job to Outreach and sets a follow-up five days out. The due follow-up sits on that job. **Got referred** files it under Applied, with the referral. **Mark applied** files one you submitted yourself. The board does not send the message.

- [ ] **Interview, offer, and no reply.**

  On an applied job, mark Interview, Offer, or No reply. Applied keeps its two groups, and these sit inside them. A later fetch updates the posting text and leaves the mark where you set it. No reply is for an application that has been quiet longer than a number of days you choose.

- [ ] **Interview memory on a posting.**

  On a job card, keep your own record of the interview next to the posting. Add links to write-ups you already have for that company or role, and write your own account of how the interview went. A posting can hold several links and one write-up. This stays separate from the posting text, the cover draft, and the referral mail.

- [ ] **A referral offer, saved by hand.**

  When someone posts that they can refer, or that their team is hiring, paste that post the same way as a job. Keep who wrote it, how they asked to be contacted, the role, company, and city, and the link to the original post. If a job for that company is already on the board, attach the offer to it. Outreach and Applied then show whether you already wrote or applied. Nothing is crawled. The original post stays the source of truth.

- [ ] **A Closed tab, and a daily check that applied jobs are still open.**

  Add **Closed** after Discarded. Once a day, look up each applied job on its career page or board API. If that posting is gone, move the job to Closed and keep the application record. A job that was never applied to, and is no longer on the career page, is deleted. A job that is only hidden by the role or years filter stays where it is.

  A board that fails to load is left as it was. One failed fetch must not close every job on that board. A posting that comes back after it was closed is the same job, not a second card.

  Himalayas has a single-job endpoint for this check. Greenhouse, Lever, and Ashby show a closed role by its absence from the next board fetch.

- [ ] **What's missing, past a skill list.**

  **What's missing** on a card currently names requirement skills from a fixed catalog that are not on the resume. For that posting, also say what to build and which skills to develop so the resume is a stronger match for getting selected. Keep it about this one job and the expectations already on the card, not a general course list.

- [ ] **Auto apply on an external site.**

  Add an option on the job, beside **Apply External**, that applies on the employer’s site with the name, contact details, and resume already saved in Settings. It runs only when you choose it for that job. The filled fields are shown first, and nothing is submitted until you confirm that job. Greenhouse, Lever, and Ashby come first, because those are the boards Fetch already reads. Any other career page stays as **Apply External** until it can be filled the same way. The option does not walk the feed and apply on its own.

- [ ] **Whole words, and a check of what each word does.**

  A hide phrase and a role word match a whole word, so a short word cannot hide or pull in a longer one. A check lists each saved word, how many jobs it keeps or drops, and one example, including a word that matches nothing.

- [ ] **Contradictory lines on a card.**

  A posting can say Remote and, later, US only, or match the skills and then describe long-term maintenance of an old system. When both show up, the card says so in words, next to the location and years flags. The job stays until you discard it. From [I got tired of job hunting, so I started building Dorker](https://www.linkedin.com/pulse/i-got-tired-job-hunting-so-started-building-dorker-podolianchuk-olqpf/).

- [ ] **The kind of work, in a sentence.**

  Prefer and avoid phrases stay. Also save one sentence for the work you want and one for the work you do not. A keyword match that conflicts with those sentences gets a warning and stays on the board. There is no score. From [I got tired of job hunting, so I started building Dorker](https://www.linkedin.com/pulse/i-got-tired-job-hunting-so-started-building-dorker-podolianchuk-olqpf/).

- [ ] **A cover draft from notes you wrote.**

  Keep a few notes in your own words. On a job, check the notes that belong, then draft from those checked notes only. You edit the draft. The board does not submit it. This extends **Draft from checked lines**. From [I got tired of job hunting, so I started building Dorker](https://www.linkedin.com/pulse/i-got-tired-job-hunting-so-started-building-dorker-podolianchuk-olqpf/).

- [ ] **Which of your notes an answer used.**

  **Ask about this job** lists the resume lines and notes it relied on. Uncheck one and ask again. From [I got tired of job hunting, so I started building Dorker](https://www.linkedin.com/pulse/i-got-tired-job-hunting-so-started-building-dorker-podolianchuk-olqpf/).

- [ ] **A wrong recommendation.**

  From a card, say this job should not have been shown, and why. You can save that note as an avoid phrase. From [I got tired of job hunting, so I started building Dorker](https://www.linkedin.com/pulse/i-got-tired-job-hunting-so-started-building-dorker-podolianchuk-olqpf/).

### Feed, later

These grow the side door. Naukri, Instahyre, Cutshort, and LinkedIn stay out of Fetch.

- [ ] **A public career link.**

  Paste a public careers-page link. The board reads that page and fills title, company, location, description, and apply link, plus salary, years, and work mode when the page states them. Any field the page does not give can be typed in. If the page cannot be read, the same form stays open. This is for a public Greenhouse, Lever, or Ashby page. It does not see a LinkedIn, Naukri, or Instahyre page that only exists inside a login. The extension is the path for those.

- [ ] **B. A daily fetch of online postings, preferring India.**

  No extra scraper is needed for the boards already on this app. **Fetch** already reads Greenhouse, Lever, and Ashby, plus Jobicy, Remote OK, and Himalayas. Himalayas publishes a free JSON API, refreshes about once a day, and can filter by country. Adzuna’s India search is already wired and runs when `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are set. Naukri, Instahyre, Cutshort, and LinkedIn stay out of this fetch.

  The new piece is a daily run of that existing fetch, limited to the India and remote market and the roles people have selected. On the hosted copy it is the GitHub Actions schedule from Revamp step 7.

- [ ] **A same-day notice for companies you are watching.**

  Keep a short list of companies, separate from the full India fetch. Check only that list more often than the daily run. The first time a company is added, the jobs already on its board stay quiet. After that, a new role that matches the selected roles and years raises a notice on this Mac. Nothing is raised when nothing new opened. The board still does not send mail.

- [ ] **A weekly list of what opened.**

  Once a week, show the roles that appeared since the last summary and still match the selected roles and years. Order them by how much of the resume they already cover. Each line says why it is there, in words: the role, the years, and the location. No number on the card. The list lives on the board.

- [ ] **New since the last fetch.**

  Mark a job New until you open it, based on the first time this board stored it. The posted date stays whatever the career page reported, because that date is often an edit. A daily fetch keeps a job the first time it is seen, even when that posted date is older, so a slow career page is not dropped.

- [ ] **Workday and Oracle career boards.**

  Greenhouse, Lever, and Ashby miss many large employers. Add those two board types the same way an Indian board is added: a company name and its public board address in `companies.india.toml`, then Fetch. A career site that refuses anything but a browser stays out.

- [ ] **Titles above your years stay out of the curated feed.**

  A posting with no years stated currently stays visible, including Staff, Principal, and Director. When the saved window sits below those titles, leave them out of the curated feed. Search can still find them.

- [ ] **Roles, not only the companies already listed.**

  The India list is a ceiling: a company that is not on it never appears. Add a fetch that looks for the selected roles on employer career sites outside that list, still preferring India. It does not download every posting. A word that shows up in most technology postings is not enough, on its own, to pull a job in.

- [ ] **A broader title only when the description is specific.**

  Some matching roles never use the selected title. After the exact role match, keep a wider title only when the description also names the specific work. Similar-role suggestions stay unchecked until you select them.

- [ ] **Current roles from the old sheet.**

  Use this sheet as a list of places to look, not as live jobs: [company sheet](https://docs.google.com/spreadsheets/d/1pZ4OFgx0Lg5rjwgJrrmwks7cmjsKjf8qeVXBPBR_tro/edit?gid=0#gid=0). A row is a hint (a company, and a role or link when the row has one). From those hints, look for openings that match the roles and years already selected. The sheet is not public, so the first step is a copy this machine can read, then a pass over the columns.
