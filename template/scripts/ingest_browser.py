"""
Takes raw job cards harvested from a live browser session (Meta, Uber - sites
that block plain-HTTP scraping) from data/browser_harvest.json, runs them
through the same shared filters as every other source, and writes
data/jobs_browser.json for merge_jobs.py.

These sources publish no posting date, so recency is first_seen-based.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BASE, build_job, location_ok, matches_level, matches_role

URL_TEMPLATES = {
    "Meta": "https://www.metacareers.com/profile/job_details/{id}",
    "Uber": "https://jobs.uber.com/en/jobs/{id}/",
}


def main():
    try:
        with open(f"{BASE}/data/browser_harvest.json") as f:
            harvest = json.load(f)
    except FileNotFoundError:
        print("no browser_harvest.json; writing empty jobs_browser.json")
        harvest = {"companies": {}}

    with open(f"{BASE}/data/companies.json") as f:
        companies = {c["name"]: c for c in json.load(f)["companies"]}

    out = []
    for cname, cards in harvest.get("companies", {}).items():
        company = companies.get(cname)
        if not company:
            continue
        for card in cards:
            title = card.get("title", "")
            if not (matches_role(title) and matches_level(title)):
                continue
            # harvests are US-wide now, so the US location rule applies here too
            loc = card.get("location", "")
            if not location_ok(loc):
                continue
            url = URL_TEMPLATES.get(cname, "{id}").format(id=card["id"])
            out.append(build_job(company, title, loc, url,
                                 card.get("full", title), None, card["id"],
                                 date_is_estimated=True))

    with open(f"{BASE}/data/jobs_browser.json", "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "jobs": out}, f, indent=2)
    print(f"Wrote {len(out)} browser-sourced jobs")


if __name__ == "__main__":
    main()
