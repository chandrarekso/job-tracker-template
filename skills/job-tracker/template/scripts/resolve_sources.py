"""
Auto-detect which ATS (Greenhouse / Lever / Ashby) each tracked company publishes
jobs through, by trying common slug variants against each platform's public
read-only job board API. Writes results back into data/companies.json as a
"source" field: {"type": "greenhouse|lever|ashby", "slug": "..."} or
{"type": "unresolved"} if nothing matched (these need a manual ATS lookup or
fall back to a best-effort web search at scrape time).
"""
import json
import re
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

DATA_PATH = config.data_path("companies.json")

UA = {"User-Agent": "Mozilla/5.0 (job-tracker-dashboard/1.0)"}


def slug_variants(name):
    base = name.lower()
    base = base.replace("&", "and")
    stripped = re.sub(r"[^a-z0-9\s\-\.]", "", base)
    no_space = re.sub(r"\s+", "", stripped)
    hyphen = re.sub(r"\s+", "-", stripped.strip())
    dot_removed = stripped.replace(".", "")
    variants = {no_space, hyphen, dot_removed.replace(" ", ""), dot_removed.replace(" ", "-")}
    # common suffix-stripped variants (e.g. "Fireworks AI" -> "fireworks")
    for suffix in [" ai", " inc", " io", " health", " power", " computing", " sciences", " technologies"]:
        if base.endswith(suffix):
            trimmed = base[: -len(suffix)].strip()
            trimmed = re.sub(r"[^a-z0-9\s\-]", "", trimmed)
            variants.add(re.sub(r"\s+", "", trimmed))
            variants.add(re.sub(r"\s+", "-", trimmed))
    return [v for v in variants if v]


def try_url(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                body = resp.read()
                return body
    except urllib.error.HTTPError:
        return None
    except Exception:
        return None
    return None


def check_greenhouse(slug):
    body = try_url(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if body:
        try:
            data = json.loads(body)
            if isinstance(data.get("jobs"), list):
                return True
        except Exception:
            pass
    return False


def check_lever(slug):
    body = try_url(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if body:
        try:
            data = json.loads(body)
            if isinstance(data, list):
                return True
        except Exception:
            pass
    return False


def check_ashby(slug):
    body = try_url(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if body:
        try:
            data = json.loads(body)
            if "jobs" in data:
                return True
        except Exception:
            pass
    return False


def resolve(name):
    for slug in slug_variants(name):
        if check_greenhouse(slug):
            return {"type": "greenhouse", "slug": slug}
    for slug in slug_variants(name):
        if check_lever(slug):
            return {"type": "lever", "slug": slug}
    for slug in slug_variants(name):
        if check_ashby(slug):
            return {"type": "ashby", "slug": slug}
    return {"type": "unresolved"}


def main():
    """Resolves only companies that still need it.

    Re-resolving everything would clobber the hand-built custom feeds
    (google_ssr, apple_ssr, browser_only and friends) with an "unresolved",
    since those companies deliberately don't appear on any standard ATS. Pass
    --all to override, and pass names to resolve just those.
    """
    force = "--all" in sys.argv
    only = {a.lower() for a in sys.argv[1:] if not a.startswith("-")}

    with open(DATA_PATH) as f:
        data = json.load(f)

    resolved = skipped = 0
    for company in data["companies"]:
        name = company["name"]
        if only and name.lower() not in only:
            continue
        current = (company.get("source_feed") or {}).get("type", "unresolved")
        if current != "unresolved" and not force and not only:
            skipped += 1
            continue
        result = resolve(name)
        company["source_feed"] = result
        status = result["type"]
        resolved += 1
        print(f"{name:30s} -> {status}" + (f" ({result.get('slug')})" if status != 'unresolved' else ""))
        time.sleep(0.15)  # be polite to shared public APIs

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nResolved {resolved}, left {skipped} existing feed(s) untouched.")
    if resolved:
        print("NOW RUN: python3 scripts/audit_boards.py  "
              "(a matching slug is not proof of a matching company)")


if __name__ == "__main__":
    main()
