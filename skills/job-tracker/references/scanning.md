# Running a scan

Scans are on demand. The user triggers one by saying "scan", or by pasting the
command the dashboard's **⟳ Request scan** button copies.

## Order of operations

The browser pass has to happen **before** the pipeline runs, because
`ingest_browser.py` reads the file it writes.

1. **Browser pass** (only if the user tracks a bot-blocked company — see below).
   Refresh `data/browser_harvest.json`.
2. **Pipeline**: `zsh ~/job-tracker/run_scan.sh`, which runs `scrape_ats.py`,
   `scrape_custom.py`, `ingest_browser.py`, `merge_jobs.py`, `build_dashboard.py`
   in that order.
3. **Publish**: republish `dashboard/index.html` as an Artifact. Pass the
   **same file path** every time so it redeploys to the same URL — the user has
   that link saved. If this session didn't publish it, pass the stored artifact
   URL explicitly, or the publish creates a second artifact with a new link.
4. **Report what changed** versus the previous scan, not just the totals.

## What "report what changed" means

Before running, note the job IDs currently in `data/jobs.json`. After, diff them.
Then tell the user:

- how many roles are **new** since the last scan, named with company and title
- how many **aged out** of the recency window
- anything that **broke** — a company whose scraper returned an error, or zero
  when it usually returns something

Do not just say "5 roles found". They saw 5 last time too; what they want to know
is which one is new.

If a scraper errors, say which company and that it's a scraper problem, not a
"no jobs" result. Those are indistinguishable in the numbers, which is exactly
why the distinction matters.

## Browser pass

Some employers block plain-HTTP scraping and can only be harvested from a real
browser session. Whether the user has any depends on their company list; check
`data/companies.json` for `"type": "browser_only"`.

Write results to `data/browser_harvest.json` in this shape:

```json
{"companies": {"CompanyName": [{"id": "...", "title": "...", "location": "...", "full": "..."}]}}
```

`full` should be the job description text if you have it — it feeds the tenure
and sponsorship gates. Without it those gates can't fire, and the role gets
scored on its title alone.

These sources publish no posting date, so recency falls back to `first_seen`:
the first scan in which the ID appeared. On a user's very first scan everything
looks new, so those rows are flagged `date_is_estimated` and the dashboard
labels them honestly rather than claiming they're fresh.

### Sites known to need this

**Meta** — `metacareers.com`, filtered search. Harvest every page via
`a[href*="/profile/job_details/"]`. The next-page control is a DIV mislabeled
`aria-label="Button to select next week"`; that is not a typo in these notes.

**Uber** — listing pages are newest-first at
`jobs.uber.com/en/jobs?page=N&pagesize=10`. A `pagesize` above 10 hangs. The SPA
is flaky — dismiss the cookie modal with "Essential Only" first. For
role-matching titles, open each detail page and read the schema.org JSON-LD
(`datePosted`, `jobLocation`); detail pages *are* date-stamped even though the
listing isn't. Detail pages are Cloudflare-blocked to plain HTTP — browser only.

If the user tracks neither, skip this step entirely and don't mention it.

## After the scan

If the run produced zero new roles, say so plainly and don't republish with
fanfare. A quiet week is a real answer.
