# Roadmap

Personal job board on this machine. No account. Jobs, the resume, and drafts stay in the local database.

This sheet is the working list. The sections above the TODO are the current state. Add the next high-level points under **TODO**. The next slice starts from those lines.

## Already in the repo

### Board

- Local app at `http://127.0.0.1:8765/`. Feature notes live at `/docs`.
- Tabs: Feed, Applied, Discarded, Outreach.
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

- Greenhouse, Lever, and Ashby company boards. Indian boards ship in `companies.india.toml`.
- Fetch also pulls Jobicy, Remote OK, and Himalayas (India or open-remote).
- **Find more boards** samples a public registry for Indian or remote boards. It does not download every job. A board is added only when you click Add.
- Optional remote company boards (GitLab, Notion, Figma, Supabase, PostHog) are added only from Settings.
- Optional Adzuna India search when `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are set. It uses the first saved role and the first city.
- CSV or JSON import. Example: `examples/jobs.csv`.
- **Add posting** saves a job you paste, including a LinkedIn one. A save bookmarklet posts to this board. On an https page the browser may block it, so paste is the path that works.

### Apply, mail, and company notes

- Settings → Application fills the apply packet and the referral drafts. Until a name is saved, a draft says “[your name]”.
- **Prepare application** copies those fields and links to the employer’s form. The autofill bookmarklet fills common fields and does not submit.
- Contacts come from text on the posting, plus contacts you add.
- **Draft referral** opens in your mail app. Opening mail does not mark it sent. **Mark sent** does, and a referral then schedules a follow-up five days later.
- **Draft from checked lines** quotes resume sentences that share a skill with the requirements. Marking a cover note or form answer used does not send it.
- **Ask about this job** runs when `OPENAI_API_KEY` is set. It can point at a local OpenAI-compatible server through `OPENAI_BASE_URL`. The question is about that one job.
- Company facts come from Wikidata and Wikipedia when the public record matches the name. Optional `TAVILY_API_KEY` adds sourced snippets. There is no ethics score.
- Prefer and avoid phrases warn or change Best match rank. They do not hide a job.

## Left as-is on purpose

- Naukri, Instahyre, Cutshort, and LinkedIn are not crawled as feeds. Saving the LinkedIn job you have open is a future item below. Until that exists, **Add posting** is how a LinkedIn job gets onto the board.
- The board does not submit an application or send mail.
- Private emails are not guessed.
- ESCO and Hirebase are not called. Role matching stays on this machine.
- Full job-board CSV dumps are not downloaded. Company suggestions sample short ranges of the public registry.

## Open, not scheduled

These are gaps already visible in the current board. They are not the next slice until they are copied into **TODO**.

- The similar-role map covers a few families. A role outside that map has no suggestions until you type one.
- **What's missing** only names skills in the fixed catalog. A tool that is not in the catalog never appears.
- A resume that lists skills and no job title gets its latest role from those skills.
- The curated list is only as full as the boards already fetched. A role with few public Greenhouse, Lever, or Ashby postings stays a short list until more boards or pasted jobs are added.
- README and `/docs` still have a few sentences from the older feed: a sidebar, role cards, and “saving a role does not filter the feed.”
- There is no automated test suite.
- A new source, such as an Apify connector, can be registered in `app/sources/__init__.py` and reuse the existing dedupe path. None is registered.

## TODO

Future work. These are requirements, not a build order. The next slice is whichever of these you pick.

### Interview memory on a posting

On a job card, keep your own record of the interview next to the posting.

- Add links to interview write-ups you already have for that company or that role (a doc, a post, a page).
- Write your own account of how the interview went, and edit it later.
- A posting can hold several links and one write-up. Removing a link or clearing the write-up leaves the job itself in place.
- This record stays with that job. It is separate from the posting text, the cover draft, and the referral mail.

### Save a posting from its page

When you have found a job on a careers page or another site, give the board the link. The board reads that page and stores the posting, instead of you pasting the description by hand.

- Store the title, company, location, description, and apply link.
- Store salary, years, and work mode when the page states them.
- The saved job then uses the same role match, years window, expectations, gaps, and drafts as any other job.
- If the page cannot be read, the board says so and leaves **Add posting** as the way to paste it.

On that same save, attach a short list of people you could ask for a referral for that role.

- A person is a name, a title when the page gives one, and a way to reach them that is written on the posting or on a public page that posting points to: an email on the page, or a profile link.
- You can add a person, edit one, or remove one. People already found in the description stay.
- An address that was never published is left blank. The board does not fill one in.

### Save the LinkedIn job you are viewing

From a LinkedIn job that is open, send it to the board and have the posting stored without pasting each field.

- The board stores the same fields as a careers-page save: title, company, location, link, and description, plus salary, years, and work mode when that page states them.
- People shown on that page for a referral are stored the same way as on any other saved posting.
- This is one job you are looking at. It is not a crawl of LinkedIn search or of a person’s connections.
- The current save bookmarklet often fails because LinkedIn is https and this board is http on your machine. This item is the version that actually stores the fields. Pasting remains available when the page cannot be read.

### Current roles from the old sheet

Later, use this sheet as a list of places to look, not as a list of live jobs: [company sheet](https://docs.google.com/spreadsheets/d/1pZ4OFgx0Lg5rjwgJrrmwks7cmjsKjf8qeVXBPBR_tro/edit?gid=0#gid=0).

- The sheet is outdated, so a row is a hint: a company, and a role or a link when the row has one. A row is not imported as an open posting.
- From those hints, look for openings that match the roles and years already selected on the board, and add the ones that are still open through the same save path as any other posting.
- The sheet is not public, so the first step is still open: a copy this machine can read (an export, or access you grant), then a pass over the columns to see which ones name a company, a role, or a link.
