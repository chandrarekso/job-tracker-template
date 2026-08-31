# Managing the company list

The template ships with **no companies**. The list in `data/companies.json` is
built entirely from what the user names during onboarding, and grows from there.

## Adding a company

1. **Check `catalog/known_feeds.json` first.** A handful of large employers don't
   publish through any standard ATS and have a purpose-built scraper already in
   `scripts/scrape_custom.py`. If the company is listed there, write its feed
   type straight into `data/companies.json` — running `resolve_sources.py` on it
   would only return `unresolved`.
2. Otherwise run `python3 scripts/resolve_sources.py "Company Name"` — it tries
   slug variants against the Greenhouse, Lever and Ashby public board APIs. With
   no arguments it resolves only companies still marked `unresolved`, so it
   won't clobber feeds that already work.
3. **Run `python3 scripts/audit_boards.py`.** Not optional. See below.
4. Set the company's sector (one of the ids in `catalog/sectors.json`) in
   `data/companies.json`, and its priority in `criteria.json` under
   `company_priorities`.
5. Rescan and republish.

## Bulk-adding during onboarding

Resolving 20 companies means 20 rounds of network lookups. Add them to
`data/companies.json` with `{"type": "unresolved"}` first, then run
`resolve_sources.py` once with no arguments to sweep them all, then
`audit_boards.py` once. Report which ones failed rather than silently dropping
them.

## Why the audit step is not optional

**A slug existing does not mean it belongs to the company you want.** This is
the single most common way the tracker goes quietly wrong: it produces a working
feed full of the wrong company's jobs, and nothing looks broken.

Real cases, all found the hard way:

- `greenhouse/lovable` is an Italian retailer. The real Lovable is
  `ashby/lovable`.
- `greenhouse/linkedin` is an unrelated outfit called "LI Test Company".
- `lever/mistral` and `lever/plaid` are abandoned empty boards. The real Mistral
  is `ashby/mistral.ai`; Plaid publishes on its own site with JSON-LD dates.

`audit_boards.py` fetches each board's own name and compares it to the company
name, printing `VERIFY-FAIL` for mismatches. Run it after every resolve, and
treat a FAIL as "not resolved" rather than "probably fine".

## When nothing resolves

The company doesn't use one of the three standard systems. Options, in order of
preference:

1. **Check for JSON-LD.** Many career sites embed schema.org `JobPosting` data
   with an exact `datePosted`. That's the best outcome — write a small scraper
   modeled on the `plaid_html` one in `scrape_custom.py`.
2. **Find the real backend endpoint.** Career pages are usually a thin client
   over a JSON API. The existing custom scrapers were all built this way, and
   `scrape_custom.py`'s docstring lists which endpoint each one uses.
3. **Fall back to a browser pass** if it's bot-blocked. See `scanning.md`.
4. **Leave it `unresolved`.** The dashboard footer says how many companies are
   unresolved, so the user isn't misled into thinking they're covered. That's a
   legitimate end state — say so rather than faking coverage.

## Changing priorities

Priorities live in `criteria.json` under `company_priorities`, not in the
catalog — the catalog stays preference-free so it can be reused by anyone.
Editing a priority needs only a dashboard rebuild, not a rescan.

## Removing a company

Drop it from `data/companies.json` and from `company_priorities`. Its past jobs
stay in `seen.json`, which is harmless — that file only tracks first-seen dates.
