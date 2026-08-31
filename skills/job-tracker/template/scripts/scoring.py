"""
Callback-likelihood scoring.

Four weighted dimensions, weights set in config/criteria.json:

    Role fit          what the job actually is
    Industry          how much the user wants that sector
    Technical fit     overlap with the user's actual stack
    Tenure            how close the demanded seniority is to the user's

Each dimension is scored internally against a fixed REFERENCE_MAX and then
converted to a 0-1 fraction. The final score is

    round(sum(fraction[d] * weight[d]) - penalties)

Keeping an internal reference scale (rather than scoring straight into the
configured weight) matters for two reasons: the tuned thresholds inside each
scorer stay meaningful when a user re-weights, and the dashboard can re-rank
live from the stored fractions without a rescan — including when a weight is
set to zero, which a divide-by-weight approach could not handle.

Tenure also acts as a HARD GATE: roles outside the user's band are dropped
entirely, because those aren't callback candidates at all.

Industry is assigned per COMPANY via the catalog's sector tag rather than
sniffed from the job text - Uber is a marketplace whether or not the JD says
"marketplace".
"""
import json
import re

import config

REFERENCE_MAX = {"role": 35, "industry": 25, "technical": 20, "tenure": 20}

# --------------------------------------------------------------- catalog load
def _sector_by_company():
    """Sector tags come from the user's own company list, which onboarding
    writes. There is no shipped company catalog — a company with no tag scores
    neutral rather than zero (see industry_points)."""
    try:
        with open(config.data_path("companies.json")) as f:
            return {c["name"]: c.get("sector", "other")
                    for c in json.load(f).get("companies", [])}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


SECTOR_BY_COMPANY = _sector_by_company()
SECTOR_POINTS = config.sector_points()
# Optional per-company overrides on the 0-100 desirability scale. Sector points
# are the default; a named company here wins, which is how a hand-tuned setup
# keeps companies that share a sector but not the user's interest in them
# (e.g. two fintechs the user rates very differently).
COMPANY_POINTS = {k: float(v) for k, v in
                  config.CRITERIA.get("scoring", {}).get("company_points", {}).items()}
_TENURE_MIN, _TENURE_MAX, _IDEAL_MIN, _IDEAL_MAX = config.tenure_band()
_IN_STACK, _OUT_OF_STACK = config.technical_stack()
_ROLE = config.role_rules()

# a JD can pull a company up: a mandate matching the user's target sector inside
# an otherwise off-sector company is still relevant work
SECTOR_SIGNALS = config.CRITERIA.get("scoring", {}).get("sector_signals", [])

ROLE_PATTERNS = [(int(p["points"]), p["patterns"])
                 for p in config.CRITERIA.get("scoring", {}).get("role_patterns", [])]
# Anything reaching the scorer already cleared the role filter, so a zero here
# would contradict that gate; this is the floor for "in scope but the title
# doesn't match a named pattern".
ROLE_FLOOR = config.CRITERIA.get("scoring", {}).get("role_floor", 15)
BONUS_SIGNALS = config.CRITERIA.get("scoring", {}).get("role_bonus_signals", [])


# ---------------------------------------------------------------- dimensions
def industry_points(company, text):
    if company in COMPANY_POINTS:
        base = COMPANY_POINTS[company]
    else:
        sector = SECTOR_BY_COMPANY.get(company)
        # unknown company -> neutral-ish rather than zero, so a newly added
        # employer isn't buried before its sector is tagged
        base = float(SECTOR_POINTS.get(sector, 48.0)) if sector else 48.0
    base = base / 100.0 * REFERENCE_MAX["industry"]
    hits = sum(1 for k in SECTOR_SIGNALS if k in text)
    cap = REFERENCE_MAX["industry"]
    if hits >= 4 and base < cap:
        base = min(cap, base + 7)
    elif hits >= 2 and base < cap:
        base = min(cap, base + 4)
    return round(base, 2)


def role_points(title, text):
    t = (title or "").lower()
    best = 0
    for pts, patterns in ROLE_PATTERNS:
        if any(re.search(p, t) for p in patterns):
            best = max(best, pts)
    if best == 0:  # title alone inconclusive - fall back to the description
        for pts, patterns in ROLE_PATTERNS:
            if any(re.search(p, text) for p in patterns):
                best = max(best, min(pts, 25))  # capped: JD match is weaker evidence
    best = max(best, ROLE_FLOOR)
    if sum(1 for k in BONUS_SIGNALS if k in text) >= 2:
        best = min(REFERENCE_MAX["role"], best + 4)
    return best


def technical_points(text):
    ins = sum(1 for k in _IN_STACK if k in text)
    outs = len(re.findall("|".join(re.escape(k) for k in _OUT_OF_STACK), text)) \
        if _OUT_OF_STACK else 0
    if outs >= 3:
        return 3                       # genuinely a different discipline
    if outs >= 1 and ins == 0:
        return 8
    if ins >= 4:
        return 20                      # explicitly the stack the user has
    if ins >= 2:
        return 17
    if ins == 1:
        return 14
    return 12                          # no technical requirement stated


YEARS_RANGE = re.compile(r"(\d{1,2})\s*(?:-|to|–|—)\s*(\d{1,2})\+?\s*years?")
YEARS_PLUS = re.compile(r"(\d{1,2})\s*\+?\s*years?")


def required_years(text):
    """The role's TARGET seniority in years, or None if unstated.

    Job ads escalate: "Minimum qualifications: 2 years ... Preferred: 6 years".
    The minimum is a floor for eligibility, not a description of the level, so
    the HIGHEST stated figure is what actually signals seniority. Taking the
    minimum instead wrongly reads a 6-year role as a 2-year one.
    """
    if not text:
        return None
    yrs = [int(n) for n in YEARS_PLUS.findall(text) if 0 < int(n) <= 25]
    m = YEARS_RANGE.search(text)
    if m:
        yrs += [int(m.group(1)), int(m.group(2))]
    return max(yrs) if yrs else None


def tenure_gate(text):
    """False -> drop the role entirely (outside the user's tenure band)."""
    if not config.gates()["tenure"]:
        return True
    y = required_years(text)
    if y is None:
        return True
    return _TENURE_MIN <= y <= _TENURE_MAX


def tenure_points(text):
    y = required_years(text)
    if y is None:
        return 14          # unstated: neutral, slight benefit of the doubt
    if _IDEAL_MIN <= y <= _IDEAL_MAX:
        return 20
    if _IDEAL_MAX < y <= _TENURE_MAX:
        return 13
    if _TENURE_MIN <= y < _IDEAL_MIN:
        return 10
    return 0               # gate should already have removed these


# ------------------------------------------------- visa sponsorship (gate)
# For a user who needs sponsorship, a posting that rules it out is a closed
# pipeline regardless of fit. Matched against explicitly negative phrasing only -
# "sponsorship available" and similar must NOT trigger this.
NO_SPONSOR = re.compile(
    r"(?:un(?:able|willing)|not able|cannot|can'?t|do(?:es)? not|will not|won'?t|no longer)"
    r"[^.]{0,40}?sponsor"
    r"|not (?:eligible|available) for (?:immigration |visa |employment )?sponsorship"
    r"|no (?:visa |immigration )?sponsorship"
    r"|without (?:the need for )?(?:visa |immigration |employer )?sponsorship"
    r"|sponsorship is not"
    r"|authorized to work in the (?:us|u\.s\.|united states)[^.]{0,60}without sponsorship",
    re.I)


def sponsorship_gate(text):
    """False -> drop the role: the posting explicitly rules out sponsorship.

    Deliberately tests ONLY the negative phrasing. An earlier version also
    matched "offered" phrasing as an override, which backfired: "able to
    sponsor" is a substring of "UNable to sponsor", and "sponsorship is
    available" of "NO visa sponsorship is available", so both refusals read as
    offers. Positive phrasings ("we sponsor", "sponsorship available") simply
    fail to match NO_SPONSOR, so no override is needed.
    """
    if not config.gates()["sponsorship"]:
        return True
    if not text:
        return True
    return not NO_SPONSOR.search(text)


# ------------------------------------------------- work-mode penalty
CITY_HINT = None


def _city_hint():
    global CITY_HINT
    if CITY_HINT is None:
        cities = config.CRITERIA.get("location", {}).get("city_hints", [])
        CITY_HINT = re.compile("|".join(re.escape(c) for c in cities), re.I) \
            if cities else re.compile(r"(?!x)x")
    return CITY_HINT


def remote_penalty(location):
    """A fully-remote listing draws far more applicants than an onsite one, so
    identical fit converts worse. Roles naming a city (even alongside remote)
    are not penalised."""
    pen = config.work_mode_rules()["remote_penalty"]
    if not pen:
        return 0
    loc = (location or "").lower()
    if "remote" in loc and not _city_hint().search(loc):
        return pen
    return 0


# ------------------------------------------------------------------- scoring
def score_job(title, description, company, location=""):
    """Returns (score_0_100, parts). `parts` carries both the reference points
    and the 0-1 fractions the dashboard re-weights from."""
    text = f"{title} {description}".lower()
    raw = {
        "role": role_points(title, text),
        "industry": industry_points(company, text),
        "technical": technical_points(text),
        "tenure": tenure_points(text),
    }
    fractions = {k: round(min(1.0, v / REFERENCE_MAX[k]), 4) for k, v in raw.items()}
    w = config.weights()
    total = sum(fractions[k] * w[k] for k in fractions)

    pen = remote_penalty(location)
    parts = {
        "points": {k: round(v, 1) for k, v in raw.items()},
        "fractions": fractions,
        "weights": {k: round(v, 1) for k, v in w.items()},
    }
    if pen:
        parts["penalties"] = {"remote": pen}
        total -= pen
    return int(round(max(0, min(100, total)))), parts
