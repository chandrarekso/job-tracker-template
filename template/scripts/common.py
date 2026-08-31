"""Shared filtering + scoring logic used by every scraper backend.

Nothing user-specific lives here any more — the keyword lists, location rules
and tenure band all come from config/criteria.json via config.py, so this file
is identical across every scaffolded copy.
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

import config

BASE = config.BASE
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

_ROLE = config.role_rules()
_SEN = config.seniority_rules()
_LOC = config.location_rules()
_WORK = config.work_mode_rules()

# ---------------------------------------------------------------- location
with open(os.path.join(BASE, "catalog", "location_reference.json")) as _f:
    _LOCREF = json.load(_f)
_COUNTRY = _LOCREF.get(_LOC["country"], _LOCREF["US"])
_MARKERS = [m.lower() for m in _COUNTRY["markers"]]
_FOREIGN = [m.lower() for m in _COUNTRY["foreign_markers"]]
_STATE_CODES = re.compile(_COUNTRY["state_code_regex"], re.I)


def in_country(loc):
    """True if a location string names somewhere in the configured country."""
    l = (loc or "").lower()
    if not l.strip():
        return False
    if any(k in l for k in _MARKERS):
        return True
    # foreign marker beats a bare state-code match ("Berlin, DE" != Delaware)
    if any(k in l for k in _FOREIGN):
        return False
    if _STATE_CODES.search(l):
        return True
    return "remote" in l  # bare "Remote" from a country-focused board


# kept under the old name so third-party scrapers written against it still work
is_us_location = in_country


def location_ok(location_text, priority=None):
    """Country-wide (or the user's chosen cities), and an accepted work mode.

    Work mode is folded in here rather than checked separately because every
    scraper backend already calls this at the right point, and onsite/hybrid/
    remote is nearly always stated in the location string itself.

    `priority` is accepted and ignored — callers in the scraper backends pass it
    and older configs varied the rule by tier.
    """
    l = (location_text or "").lower()
    if not in_country(l):
        return False
    if not work_mode_ok(l):
        return False
    if _LOC["mode"] != "cities":
        return True
    if any(c in l for c in _LOC["cities"]):
        return True
    # a city-restricted search still wants country-wide remote roles, if allowed
    return _LOC["include_remote"] and "remote" in l


def work_mode_of(location_text, description=""):
    """onsite | hybrid | remote | unknown, read from the posting."""
    l = f"{location_text or ''} {description or ''}".lower()
    if "hybrid" in l:
        return "hybrid"
    if re.search(r"\bon-?site\b|\bin-?office\b", l):
        return "onsite"
    if "remote" in l:
        return "remote"
    return "unknown"


def work_mode_ok(location_text, description=""):
    mode = work_mode_of(location_text, description)
    return mode == "unknown" or mode in _WORK["accept"]


# -------------------------------------------------------------------- fetch
def fetch(url, data=None, headers=None, timeout=25):
    h = dict(UA)
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data is not None else None
    if body:
        h.setdefault("Content-Type", "application/json")
        h.setdefault("Accept", "application/json")
    req = urllib.request.Request(url, data=body, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_json(url, data=None, headers=None, retries=3):
    """Retries on 429/5xx with backoff. Without this a rate-limited company
    silently reports zero matches, which is indistinguishable from 'no jobs'."""
    import time as _time
    import urllib.error as _err
    for attempt in range(retries):
        try:
            return json.loads(fetch(url, data, headers))
        except _err.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = 3 * (attempt + 1)
                print(f"  . {e.code} from {url[:52]} - retrying in {wait}s")
                _time.sleep(wait)
                continue
            print(f"  ! {url[:70]}: {e}")
            return None
        except Exception as e:
            print(f"  ! {url[:70]}: {e}")
            return None
    return None


def fetch_text(url):
    try:
        return fetch(url).decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ! {url[:70]}: {e}")
        return ""


# ------------------------------------------------------------------ filters
def matches_role(title):
    t = (title or "").lower()
    if _ROLE["include"] and not any(k in t for k in _ROLE["include"]):
        return False
    if any(k in t for k in _ROLE["exclude"]):
        return False
    # Function-head test: only the part of the title before the first comma or
    # dash names the actual function; what follows is scope. "Finance & BizOps,
    # Strategic Partnerships" has head "finance & bizops" (a bizops role), while
    # "Strategic Partner Manager, Creators" has head "strategic partner manager"
    # (a partnerships role). The same words appear on both sides, so testing the
    # whole title cannot separate them.
    if any(k in t for k in _ROLE["full_title_excludes"]):
        return False
    head = re.split(r"[,\-–—(]", t)[0].strip()
    if any(head.startswith(k) for k in _ROLE["rejected_head_prefixes"]):
        return False
    if any(k in head for k in _ROLE["rejected_function_heads"]):
        return False
    return True


def matches_level(title):
    t = (title or "").lower()
    if any(k in t for k in _SEN["always_allow"]):
        return True
    if any(k in t for k in _SEN["too_senior"]) or any(k in t for k in _SEN["too_senior_title"]):
        return False
    head = re.split(r"[,\-–—(]", t)[0].strip()
    if any(head.endswith(" " + k) for k in _SEN["too_senior_trailing"]):
        return False
    if any(k in t for k in _SEN["too_junior"]) or any(k in t for k in _SEN["too_junior_title"]):
        return False
    if not _SEN["allow_bare_associate"]:
        if re.search(r"\bassociate\b", t) and "senior associate" not in t:
            return False
    return True


def years_experience_ok(text):
    """Hard gates applied to the job description:
      - tenure: drop roles outside the user's band
      - sponsorship: drop roles that explicitly refuse it (if the user needs it)
    Both are dead ends regardless of fit, so they are filtered, not scored.
    Kept under this name because every scraper already calls it at the right
    point in the pipeline."""
    from scoring import sponsorship_gate, tenure_gate
    t = (text or "").lower()
    return tenure_gate(t) and sponsorship_gate(t)


def within_recency(dt):
    if dt is None:
        return True
    return dt >= datetime.now(timezone.utc) - timedelta(days=config.recency_days())


within_7_days = within_recency   # legacy name used by the scraper backends


# ------------------------------------------------------------------- extract
def extract_salary(text):
    if not text:
        return None
    m = re.search(r"\$\s?([\d,]{2,9})(?:\.\d+)?\s*(?:-|to|–|—)\s*\$?\s?([\d,]{2,9})", text)
    if not m:
        return None
    lo = int(m.group(1).replace(",", ""))
    hi = int(m.group(2).replace(",", ""))
    s = re.sub(r"\s+", " ", m.group(0)).strip()
    if hi < 1000:
        return f"{s}/hr"  # hourly rate, label it so it isn't read as an annual range
    if lo < 1000:
        return None  # mixed magnitudes -> not a real salary range
    return s


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub("<[^<]+?>", " ", s or ""))


# ------------------------------------------------------------- recommendation
_CV_VARIANTS = config.cv_variants()
_CUSTOM_BELOW = config.PROFILE.get("custom_cv_below_score", 55)
_HIGH_EFFORT_SIGNALS = config.CRITERIA.get("high_effort_signals", [])


def recommend_cv(title, description, score):
    """Picks the best-matching CV variant, or "Custom" when the fit is weak
    enough that a tailored CV is worth the time."""
    if not _CV_VARIANTS:
        return "Default"
    text = f"{title} {description}".lower()
    for v in _CV_VARIANTS:
        kws = [k.lower() for k in v.get("match_keywords", [])]
        if kws and sum(1 for k in kws if k in text) >= v.get("min_hits", 2):
            return v["id"]
    if score < _CUSTOM_BELOW:
        return "Custom"
    default = next((v for v in _CV_VARIANTS if v.get("default")), _CV_VARIANTS[0])
    return default["id"]


def estimate_effort(description, recommended_cv):
    """High if a custom CV is needed and/or the application has an essay or
    written component; Low if it's just a CV upload plus admin fields."""
    if recommended_cv == "Custom":
        return "High"
    text = (description or "").lower()
    return "High" if any(s.lower() in text for s in _HIGH_EFFORT_SIGNALS) else "Low"


def score_job(title, description, company_name):
    """Score only; callers wanting the per-dimension breakdown use
    scoring.score_job directly."""
    from scoring import score_job as _score
    total, _parts = _score(title, description, company_name)
    return total


# ---------------------------------------------------------------- job record
_PRIORITIES = config.company_priorities()


def build_job(company, title, loc, url, desc, dt, source_id,
              salary_hint=None, date_is_estimated=False):
    from scoring import score_job as _score
    salary = salary_hint or extract_salary(desc)
    score, parts = _score(title, desc, company["name"], loc)
    cv = recommend_cv(title, desc, score)
    priority = company.get("priority") or _PRIORITIES.get(company["name"], "P3")
    return {
        "id": f"{company['name']}::{source_id}",
        "company": company["name"],
        "sector": company.get("sector", "other"),
        "industry": company.get("sector", "other"),   # legacy key for the UI
        "priority": priority,
        "title": (title or "").strip(),
        "location": (loc or "").strip(),
        "work_mode": work_mode_of(loc, desc),
        "salary_range": salary,
        "score": score,
        "score_parts": parts,
        "recommended_cv": cv,
        "effort": estimate_effort(desc, cv),
        "posted_at": dt.isoformat() if dt else None,
        "date_is_estimated": date_is_estimated,
        "application_link": url,
        "applied": False,
        "last_seen": datetime.now(timezone.utc).isoformat(),
    }
