"""
Identity audit: verify each auto-resolved ATS board actually belongs to the
tracked company (the Lovable bug: greenhouse/'lovable' is an Italian retailer,
the real Lovable is ashby/'lovable').

Greenhouse: GET /v1/boards/{slug} -> {"name": ...}
Ashby:      job-board response has no org name; fall back to the jobs.ashbyhq.com
            page <title>.
Lever:      jobs.lever.co/{slug} page <title> carries the company name.

Prints VERIFY-FAIL lines for any board whose name doesn't loosely match.
"""
import json
import re
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BASE, fetch_json, fetch_text


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def loose_match(expected, found):
    e, f = norm(expected), norm(found)
    if not f:
        return None  # couldn't determine
    return e in f or f in e or e[:6] == f[:6]


def board_name(feed):
    t, slug = feed.get("type"), feed.get("slug")
    if t == "greenhouse":
        d = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}")
        return (d or {}).get("name")
    if t == "ashby":
        html = fetch_text(f"https://jobs.ashbyhq.com/{slug}")
        m = re.search(r"<title>([^<]+)</title>", html or "")
        return m.group(1).replace("Jobs", "").replace("Careers", "").strip() if m else None
    if t == "lever":
        html = fetch_text(f"https://jobs.lever.co/{slug}")
        m = re.search(r"<title>([^<]+)</title>", html or "")
        return m.group(1).split("-")[0].strip() if m else None
    return "SKIP"


def main():
    with open(f"{BASE}/data/companies.json") as f:
        companies = json.load(f)["companies"]
    fails, unknowns = [], []
    for c in companies:
        feed = c.get("source_feed") or {}
        if feed.get("type") not in ("greenhouse", "ashby", "lever"):
            continue
        name = board_name(feed)
        ok = loose_match(c["name"], name) if name != "SKIP" else True
        tag = "OK  " if ok else ("????" if ok is None else "FAIL")
        if ok is False:
            fails.append((c["name"], feed, name))
        if ok is None:
            unknowns.append((c["name"], feed))
        print(f"{tag} {c['name']:22s} {feed.get('type'):10s} {feed.get('slug', ''):22s} -> {name}")
        time.sleep(0.1)
    print(f"\n{len(fails)} VERIFY-FAIL, {len(unknowns)} undetermined")


if __name__ == "__main__":
    main()
