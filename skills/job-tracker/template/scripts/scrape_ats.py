"""
Pulls current postings from every company whose source_feed is a standard ATS
(Greenhouse / Lever / Ashby), filters them via the shared rules in common.py,
and writes data/jobs_ats.json for merge_jobs.py to combine.

Greenhouse recency uses first_published (true post date), not updated_at.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (BASE, build_job, fetch_json, is_us_location, location_ok,
                    matches_level, matches_role, strip_html, within_7_days,
                    years_experience_ok)

JOBS_PATH = f"{BASE}/data/jobs_ats.json"


def parse_iso(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None
    except Exception:
        return None


def scrape_greenhouse(slug, company):
    data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
    if not data:
        return []
    out = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not (matches_role(title) and matches_level(title)):
            continue
        loc = (j.get("location") or {}).get("name", "")
        if not location_ok(loc, company.get("priority")):
            continue
        dt = parse_iso(j.get("first_published") or j.get("updated_at"))
        if not within_7_days(dt):
            continue
        desc = strip_html(j.get("content", ""))
        if not years_experience_ok(desc):
            continue
        out.append(build_job(company, title, loc, j.get("absolute_url"),
                             desc, dt, str(j.get("id"))))
    return out


def scrape_lever(slug, company):
    data = fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if not data:
        return []
    out = []
    for j in data:
        title = j.get("text", "")
        if not (matches_role(title) and matches_level(title)):
            continue
        loc = (j.get("categories") or {}).get("location", "") or ""
        if not location_ok(loc, company.get("priority")):
            continue
        created = j.get("createdAt")
        dt = datetime.fromtimestamp(created / 1000, tz=timezone.utc) if created else None
        if not within_7_days(dt):
            continue
        desc = (j.get("descriptionPlain") or "") + " " + " ".join(
            strip_html(str(li)) for li in j.get("lists", []))
        if not years_experience_ok(desc):
            continue
        out.append(build_job(company, title, loc, j.get("hostedUrl"), desc, dt, j.get("id")))
    return out


def scrape_ashby(slug, company):
    data = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if not data:
        return []
    out = []
    for j in data.get("jobs", []):
        title = j.get("title", "")
        if not (matches_role(title) and matches_level(title)):
            continue
        loc = j.get("location", "") or ""
        secondary = [s.get("location", "") for s in j.get("secondaryLocations", []) if s.get("location")]
        all_locs = " ".join([loc] + secondary)
        if not location_ok(all_locs, company.get("priority")):
            continue
        # A role can be posted in several countries with a non-US primary. Show the
        # US option rather than the primary, or the row reads as wrongly included.
        if not is_us_location(loc):
            us_opts = [s for s in secondary if is_us_location(s)]
            if us_opts:
                loc = ", ".join(us_opts[:3]) + f" (+{len(secondary) - len(us_opts)} non-US)"
        dt = parse_iso(j.get("publishedAt"))
        if not within_7_days(dt):
            continue
        desc = strip_html(j.get("descriptionHtml", "") or "")
        if not years_experience_ok(desc):
            continue
        comp = j.get("compensation") or {}
        salary_hint = comp.get("compensationTierSummary") if isinstance(comp, dict) else None
        out.append(build_job(company, title, loc, j.get("jobUrl"), desc, dt,
                             j.get("id"), salary_hint))
    return out


SCRAPERS = {"greenhouse": scrape_greenhouse, "lever": scrape_lever, "ashby": scrape_ashby}


def main():
    with open(f"{BASE}/data/companies.json") as f:
        companies = json.load(f)["companies"]

    all_jobs = []
    for company in companies:
        feed = company.get("source_feed") or {}
        fn = SCRAPERS.get(feed.get("type"))
        if not fn:
            continue
        try:
            jobs = fn(feed["slug"], company)
        except Exception as e:
            print(f"  ! error scraping {company['name']}: {e}")
            jobs = []
        if jobs:
            print(f"{company['name']}: {len(jobs)} matching job(s)")
        all_jobs.extend(jobs)
        time.sleep(0.15)

    with open(JOBS_PATH, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "jobs": all_jobs}, f, indent=2)
    print(f"\nWrote {len(all_jobs)} jobs to data/jobs_ats.json")


if __name__ == "__main__":
    main()
