"""
Merges ATS-feed jobs and custom-scraper jobs into data/jobs.json.

Maintains data/seen.json: {job_id: first_seen_iso}. For companies that publish no
posting date (Google, Meta, Cyera), first_seen is the recency signal - a job is
"new" if this run is the first time its ID has ever been observed. On the very
first run everything is unseen, so those rows stay flagged date_is_estimated and
the dashboard labels them rather than pretending they're 7-day-fresh.

Preserves the "applied" flag and any accept/reject feedback across runs.
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta, timezone

import config
BASE = config.BASE
JOBS = f"{BASE}/data/jobs.json"
CUSTOM = f"{BASE}/data/jobs_custom.json"
ATS = f"{BASE}/data/jobs_ats.json"
BROWSER = f"{BASE}/data/jobs_browser.json"
SEEN = f"{BASE}/data/seen.json"
FEEDBACK = f"{BASE}/data/feedback.json"


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main():
    now = datetime.now(timezone.utc)
    seen = load(SEEN, {})
    feedback = load(FEEDBACK, {})
    # rejected.json is maintained by Claude from the user's pasted dashboard
    # feedback: {job_id: {"reason": ...}}. Role Mismatch / Seniority Issue /
    # Already Applied rejections are suppressed from every future scan.
    # (Link Issue / Application Time Limits are per-posting problems - the job
    # stays suppressed too, but the reason is kept for scraper diagnostics.)
    _rej = load(f"{BASE}/data/rejected.json", {})
    rejected = _rej.get("by_id", {})
    # Rows whose job had already aged out exported without an id, so they are
    # matched on company + normalised title instead.
    def norm(s):
        return " ".join((s or "").lower().replace("&", "and").split())
    rejected_titles = {(r["company"], norm(r["title"])) for r in _rej.get("by_company_title", [])}
    prev = {j["id"]: j for j in load(JOBS, {}).get("jobs", [])}

    incoming = []
    for path in (ATS, CUSTOM, BROWSER):
        incoming.extend(load(path, {}).get("jobs", []))

    first_run = len(seen) == 0
    merged = []
    n_suppressed = 0
    for j in incoming:
        jid = j["id"]
        if jid in rejected or (j["company"], norm(j["title"])) in rejected_titles:
            n_suppressed += 1
            continue
        if jid not in seen:
            seen[jid] = now.isoformat()
        j["first_seen"] = seen[jid]

        # For dateless sources, derive posted_at from first_seen
        if not j.get("posted_at"):
            j["posted_at"] = seen[jid]
            j["date_is_estimated"] = True
            if first_run:
                j["date_note"] = "first scrape - true post date unknown"
            else:
                fs = datetime.fromisoformat(seen[jid])
                j["date_note"] = "newly appeared" if (now - fs) < timedelta(days=1) \
                    else f"first seen {fs.date().isoformat()}"

        # carry over user state
        if jid in prev:
            j["applied"] = prev[jid].get("applied", False)
        if jid in feedback:
            j["feedback"] = feedback[jid]
        merged.append(j)

    # drop anything now older than 7 days by its (possibly estimated) date
    cutoff = now - timedelta(days=config.recency_days())
    kept = []
    for j in merged:
        try:
            dt = datetime.fromisoformat(j["posted_at"])
        except Exception:
            dt = now
        if dt >= cutoff:
            kept.append(j)

    kept.sort(key=lambda j: (-j["score"], j["company"]))

    with open(JOBS, "w") as f:
        json.dump({"generated_at": now.isoformat(), "jobs": kept}, f, indent=2)
    with open(SEEN, "w") as f:
        json.dump(seen, f, indent=2)

    est = sum(1 for j in kept if j.get("date_is_estimated"))
    print(f"Merged {len(kept)} jobs ({est} with estimated dates) -> data/jobs.json")
    if n_suppressed:
        print(f"Suppressed {n_suppressed} previously rejected job(s)")
    print(f"Tracking {len(seen)} job IDs in seen.json")


if __name__ == "__main__":
    main()
