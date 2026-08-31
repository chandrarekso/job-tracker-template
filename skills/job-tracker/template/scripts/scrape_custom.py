"""
Scrapers for companies with no standard ATS feed, using the real backend
endpoints / server-rendered payloads discovered by inspecting each career site:

  microsoft_pcsx  apply.careers.microsoft.com/api/pcsx/search  -> postedTs (exact)
  apple_ssr       jobs.apple.com search HTML, embedded JSON     -> postDateInGMT (exact)
  paypal_workday  paypal.wd1.myworkdayjobs.com Workday CXS      -> postedOn (relative)
  comeet_html     company careers page HTML w/ Comeet links     -> no date (first_seen)
  google_ssr      google.com/about/careers results HTML         -> no date (first_seen)

Google and Meta publish no posting date anywhere, so recency for those is derived
from first_seen: the first scrape run in which the job ID appeared. That is exact
going forward, but on the very first run every job looks "new" - such rows are
marked date_is_estimated so the dashboard can flag them honestly.
"""
import json
import re
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from common import (BASE, build_job, fetch_json, fetch_text, location_ok,
                    matches_level, matches_role, strip_html, within_7_days,
                    years_experience_ok)


# ---------------------------------------------------------------- Microsoft
MS_LOCATIONS = [config.CRITERIA.get("location", {}).get("query_name", "United States")]
SEARCH_QUERIES = config.CRITERIA.get("search_queries", ["strategy"])


def scrape_microsoft(company):
    out = []
    for query in SEARCH_QUERIES:
      for ms_loc in MS_LOCATIONS:
        data = fetch_json(
            "https://apply.careers.microsoft.com/api/pcsx/search"
            f"?domain=microsoft.com&query={query.replace(' ', '%20')}"
            f"&location={ms_loc.replace(' ', '%20')}&start=0&num=40&sort=recent"
        )
        if not data:
            continue
        for p in (data.get("data") or {}).get("positions", []):
            title = p.get("name", "")
            if not (matches_role(title) and matches_level(title)):
                continue
            locs = ", ".join(p.get("standardizedLocations") or p.get("locations") or [])
            if not location_ok(locs, company.get("priority")):
                continue
            ts = p.get("postedTs")
            dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
            if not within_7_days(dt):
                continue
            desc = strip_html(json.dumps(p.get("descriptionTeaser", "")) + " " +
                              json.dumps(p.get("jobDescription", "")))
            if not years_experience_ok(desc):
                continue
            jid = p.get("id")
            url = f"https://jobs.careers.microsoft.com/global/en/job/{p.get('displayJobId', jid)}/"
            out.append(build_job(company, title, locs, url, desc, dt, jid))
    return dedupe(out)


# -------------------------------------------------------------------- Apple
APPLE_SEARCHES = [
    "https://jobs.apple.com/en-us/search?location=united-states-USA&page=1",
    "https://jobs.apple.com/en-us/search?location=united-states-USA&page=2",
    "https://jobs.apple.com/en-us/search?location=united-states-USA&page=3",
]


def scrape_apple(company):
    out = []
    for url_base in APPLE_SEARCHES:
        html = fetch_text(url_base)
        if not html:
            continue
        # job records are embedded as escaped JSON inside the SSR payload
        for b in re.split(r'\\"positionId\\":', html)[1:]:
            pid = re.match(r'\\"(\d+)\\"', b)
            title = re.search(r'\\"postingTitle\\":\\"(.*?)\\"', b)
            date = re.search(r'\\"postDateInGMT\\":\\"([^"\\]+)\\"', b)
            slug = re.search(r'\\"transformedPostingTitle\\":\\"(.*?)\\"', b)
            if not (pid and title and date):
                continue
            t = title.group(1).replace('\\\\', '')
            if not (matches_role(t) and matches_level(t)):
                continue
            try:
                dt = datetime.fromisoformat(date.group(1).replace("Z", "+00:00"))
            except Exception:
                dt = None
            if not within_7_days(dt):
                continue
            # per-job locations sit in the record's locations[] name fields
            loc = ", ".join(re.findall(r'\\"name\\":\\"([^"\\]{2,40})\\"', b[:4000])[:3])
            if not location_ok(loc):
                continue
            url = (f"https://jobs.apple.com/en-us/details/{pid.group(1)}/"
                   f"{slug.group(1) if slug else ''}")
            out.append(build_job(company, t, loc, url, b[:3000], dt, pid.group(1)))
    return dedupe(out)


# ------------------------------------------------------------------ PayPal
REL_DATE = re.compile(r"posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)", re.I)


def parse_workday_posted(s):
    if not s:
        return None, True
    m = REL_DATE.search(s)
    now = datetime.now(timezone.utc)
    if not m:
        return None, True
    if m.group(1).lower() == "today":
        return now, False
    if m.group(1).lower() == "yesterday":
        return now - timedelta(days=1), False
    if m.group(2):
        return now - timedelta(days=int(m.group(2))), False
    return None, True


def scrape_paypal(company):
    out = []
    for query in ("strategy", "chief of staff", "growth", "transformation"):
        data = fetch_json(
            "https://paypal.wd1.myworkdayjobs.com/wday/cxs/paypal/jobs/jobs",
            data={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": query},
        )
        if not data:
            continue
        for j in data.get("jobPostings", []):
            title = j.get("title", "")
            if not (matches_role(title) and matches_level(title)):
                continue
            loc = j.get("locationsText", "")
            if not location_ok(loc, company.get("priority")):
                continue
            dt, est = parse_workday_posted(j.get("postedOn"))
            if not within_7_days(dt):
                continue
            path = j.get("externalPath", "")
            url = f"https://paypal.wd1.myworkdayjobs.com/en-US/jobs{path}"
            out.append(build_job(company, title, loc, url, title, dt,
                                 j.get("bulletFields", [path])[0], date_is_estimated=est))
    return dedupe(out)


# ------------------------------------------------------------- Comeet (Cyera)
def scrape_comeet(company):
    """Careers page renders each opening as a listitem block carrying title,
    location and the Comeet apply link. No posting date is exposed, so recency
    falls back to first_seen."""
    url = (company.get("source_feed") or {}).get("url")
    html = fetch_text(url) if url else ""
    if not html:
        return []
    out = []
    for block in re.split(r'role="listitem"', html)[1:]:
        title_m = re.search(r'fs-list-field="itemTitle"[^>]*>(.*?)</div>', block, re.S)
        loc_m = re.search(r'fs-list-field="location"[^>]*>(.*?)</div>', block, re.S)
        link_m = re.search(
            r'href="(https://www\.comeet\.com/jobs/[a-z0-9]+/[\d.]+/careers/([A-Z0-9.\-]+))"',
            block, re.I)
        if not (title_m and link_m):
            continue
        title = strip_html(title_m.group(1)).strip()
        loc = strip_html(loc_m.group(1)).strip() if loc_m else ""
        if not (matches_role(title) and matches_level(title)):
            continue
        if not location_ok(loc, company.get("priority")):
            continue
        out.append(build_job(company, title, loc, link_m.group(1), title, None,
                             link_m.group(2), date_is_estimated=True))
    return dedupe(out)


# ------------------------------------------------------------------- Google
GOOGLE_LOCATIONS = [
    ("United%20States", "United States"),
]


def scrape_google(company):
    """Job records live in the AF_initDataCallback('ds:1') JSON embedded in the
    search results page: index 0=id, 1=title, 4=minimum qualifications (years),
    9=locations, 10=salary paragraph, 12=[created_epoch], 13=[updated_epoch].
    The visible page shows no dates, but the payload carries exact timestamps."""
    out = []
    seen_ids = set()
    for q in ("strategy", "chief%20of%20staff", "growth", "transformation"):
        for loc_param, _ in GOOGLE_LOCATIONS:
            page = fetch_text(
                "https://www.google.com/about/careers/applications/jobs/results"
                f"?q={q}&location={loc_param}"
            )
            m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel",
                          page or "", re.S)
            if not m:
                continue
            try:
                records = json.loads(m.group(1))[0]
            except Exception:
                continue
            for j in records:
                try:
                    jid, title = j[0], j[1]
                    if jid in seen_ids:
                        continue
                    quals = strip_html((j[4] or [None, ""])[1])
                    desc = strip_html((j[3] or [None, ""])[1]) + " " + quals
                    locs = ", ".join(loc[0] for loc in (j[9] or []) if loc)
                    sal_html = (j[10] or [None, ""])[1]
                    created = (j[12] or [None])[0]
                except (IndexError, TypeError):
                    continue
                seen_ids.add(jid)
                if not (matches_role(title) and matches_level(title)):
                    continue
                if not location_ok(locs, company.get("priority")):
                    continue
                dt = datetime.fromtimestamp(created, tz=timezone.utc) if created else None
                if not within_7_days(dt):
                    continue
                if not years_experience_ok(quals):
                    continue
                sal_m = re.search(r'\$[\d,]+\s*-\s*\$[\d,]+', sal_html or "")
                url = f"https://www.google.com/about/careers/applications/jobs/results/{jid}"
                out.append(build_job(company, title, locs, url, desc, dt, jid,
                                     salary_hint=sal_m.group(0) if sal_m else None,
                                     date_is_estimated=dt is None))
    return dedupe(out)


# -------------------------------------------------------------------- Plaid
def scrape_plaid(company):
    """plaid.com/careers/openings/ is server-rendered with structured hrefs
    (/careers/openings/<dept>/<office>/<role>/); detail pages carry JSON-LD
    with datePosted. Their old Lever board is empty - do not use it."""
    listing = fetch_text("https://plaid.com/careers/openings/")
    if not listing:
        return []
    hrefs = sorted(set(re.findall(r'href="(/careers/openings/[a-z0-9\-]+/[a-z0-9\-]+/[a-z0-9\-]+/)"', listing)))
    out = []
    for href in hrefs:
        slug_title = href.rstrip("/").split("/")[-1].replace("-", " ")
        office = href.rstrip("/").split("/")[-2].replace("-", " ")
        if not (matches_role(slug_title) and matches_level(slug_title)):
            continue
        page = fetch_text(f"https://plaid.com{href}")
        if not page:
            continue
        m = re.search(r'"datePosted":"(\d{4}-\d{2}-\d{2})', page)
        dt = None
        if m:
            dt = datetime.fromisoformat(m.group(1)).replace(tzinfo=timezone.utc)
        if not within_7_days(dt):
            continue
        tm = re.search(r'"title":"([^"]{5,80})"', page)
        title = tm.group(1) if tm else slug_title.title()
        if not (matches_role(title) and matches_level(title)):
            continue
        loc = office.title().replace("Hq", "HQ")
        if not location_ok(loc):
            continue
        desc = strip_html(page[:40000])
        if not years_experience_ok(desc):
            continue
        out.append(build_job(company, title, loc, f"https://plaid.com{href}",
                             desc, dt, href, date_is_estimated=dt is None))
        time.sleep(0.2)
    return dedupe(out)


# ------------------------------------------------------------------ Netflix
def scrape_netflix(company):
    """Eightfold API behind explore.jobs.netflix.net; t_create is epoch seconds."""
    out = []
    for query in ("strategy", "chief of staff", "growth", "transformation", "consultant"):
        data = fetch_json(
            "https://explore.jobs.netflix.net/api/apply/v2/jobs"
            f"?domain=netflix.com&query={query.replace(' ', '%20')}&num=20&sort_by=timestamp"
        )
        if not data:
            continue
        for p in data.get("positions", []):
            title = p.get("name", "")
            if not (matches_role(title) and matches_level(title)):
                continue
            loc = ", ".join((p.get("locations") or [p.get("location", "")])[:3])
            if not location_ok(loc, company.get("priority")):
                continue
            ts = p.get("t_create")
            dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
            if not within_7_days(dt):
                continue
            desc = strip_html(p.get("job_description", ""))[:20000]
            if not years_experience_ok(desc):
                continue
            url = p.get("canonicalPositionUrl") or \
                f"https://explore.jobs.netflix.net/careers/job/{p.get('id')}"
            out.append(build_job(company, title, loc, url, desc, dt, p.get("id")))
    return dedupe(out)


# ----------------------------------------------------------------- Atlassian
def scrape_atlassian(company):
    """atlassian.com/endpoint/careers/listings returns every posting with an
    iCIMS portal URL; updatedDate is edit-time, so treat it as estimated."""
    data = fetch_json("https://www.atlassian.com/endpoint/careers/listings")
    if not data:
        return []
    out = []
    for j in data:
        title = j.get("title", "") or ""
        if not (matches_role(title) and matches_level(title)):
            continue
        loc = ", ".join(j.get("locations") or []) or (j.get("location") or "")
        if not location_ok(loc, company.get("priority")):
            continue
        upd = (j.get("portalJobPost") or {}).get("updatedDate")
        dt = None
        if upd:
            try:
                dt = datetime.strptime(upd[:16], "%Y-%m-%d %I:%M").replace(tzinfo=timezone.utc)
            except Exception:
                dt = None
        if not within_7_days(dt):
            continue
        url = (j.get("portalJobPost") or {}).get("portalUrl") or j.get("applyUrl", "")
        out.append(build_job(company, title, loc, url,
                             strip_html(j.get("overview", "")), dt, str(j.get("id")),
                             date_is_estimated=True))
    return dedupe(out)


def dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        if j["id"] in seen:
            continue
        seen.add(j["id"])
        out.append(j)
    return out


SCRAPERS = {
    "microsoft_pcsx": scrape_microsoft,
    "apple_ssr": scrape_apple,
    "paypal_workday": scrape_paypal,
    "comeet_html": scrape_comeet,
    "google_ssr": scrape_google,
    "netflix_eightfold": scrape_netflix,
    "atlassian_icims": scrape_atlassian,
    "plaid_html": scrape_plaid,
}


def main():
    with open(f"{BASE}/data/companies.json") as f:
        companies = json.load(f)["companies"]
    results = []
    for c in companies:
        ftype = (c.get("source_feed") or {}).get("type")
        fn = SCRAPERS.get(ftype)
        if not fn:
            continue
        print(f"Scraping {c['name']} via {ftype}...")
        try:
            jobs = fn(c)
        except Exception as e:
            print(f"  ! error: {e}")
            jobs = []
        print(f"  -> {len(jobs)} matching job(s)")
        results.extend(jobs)

    with open(f"{BASE}/data/jobs_custom.json", "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "jobs": results}, f, indent=2)
    print(f"\nWrote {len(results)} jobs to data/jobs_custom.json")


if __name__ == "__main__":
    main()
