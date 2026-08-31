"""Single source of truth for everything that varies between users.

Every other script imports BASE and CONFIG from here rather than hardcoding a
path or a keyword list. BASE is derived from this file's own location, so a
scaffolded copy works wherever the user put it.

Two files back this:
  config/profile.json   who the user is (experience, skills, locations, CVs)
  config/criteria.json  what to look for and how to score it

Both are written by the onboarding Q&A and are meant to be hand-edited after.
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE, "config")
DATA_DIR = os.path.join(BASE, "data")


def _load(name):
    path = os.path.join(CONFIG_DIR, name)
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(
            f"Missing {path}.\n"
            "Run the onboarding first — in Claude, say: set up my job tracker"
        )
    except json.JSONDecodeError as e:
        raise SystemExit(f"{path} is not valid JSON: {e}")


PROFILE = _load("profile.json")
CRITERIA = _load("criteria.json")


def data_path(*parts):
    return os.path.join(DATA_DIR, *parts)


# ------------------------------------------------------------------ accessors
# Read through helpers rather than indexing the dicts directly, so a config
# written by an older onboarding still runs when new keys are added.

def role_rules():
    r = CRITERIA.get("role", {})
    return {
        "include": [k.lower() for k in r.get("include", [])],
        "exclude": [k.lower() for k in r.get("exclude", [])],
        "rejected_function_heads": [k.lower() for k in r.get("rejected_function_heads", [])],
        "full_title_excludes": [k.lower() for k in r.get("full_title_excludes", [])],
        "rejected_head_prefixes": [k.lower() for k in r.get("rejected_head_prefixes", [])],
    }


def seniority_rules():
    s = CRITERIA.get("seniority", {})
    return {
        "too_senior": [k.lower() for k in s.get("too_senior", [])],
        "too_junior": [k.lower() for k in s.get("too_junior", [])],
        "too_senior_title": [k.lower() for k in s.get("too_senior_title", [])],
        "too_junior_title": [k.lower() for k in s.get("too_junior_title", [])],
        "too_senior_trailing": [k.lower() for k in s.get("too_senior_trailing", [])],
        "allow_bare_associate": s.get("allow_bare_associate", False),
        "always_allow": [k.lower() for k in s.get("always_allow", [])],
    }


def weights():
    """Scoring weights. Normalised to sum to 100 so a user who edits one weight
    without rebalancing the others still gets a 0-100 score."""
    w = dict(CRITERIA.get("scoring", {}).get("weights", {}))
    for k in ("role", "industry", "technical", "tenure"):
        w.setdefault(k, 25)
    total = sum(max(0, v) for v in w.values())
    if total <= 0:
        return {"role": 25, "industry": 25, "technical": 25, "tenure": 25}
    return {k: max(0, v) * 100.0 / total for k, v in w.items()}


def sector_points():
    """{sector: 0-100 desirability}. Onboarding writes this from the user's
    stated industry preferences."""
    return {k: float(v) for k, v in
            CRITERIA.get("scoring", {}).get("sector_points", {}).items()}


def tenure_band():
    t = CRITERIA.get("seniority", {})
    return (t.get("tenure_min", 3), t.get("tenure_max", 8),
            t.get("tenure_ideal_min", 4), t.get("tenure_ideal_max", 6))


def gates():
    g = CRITERIA.get("gates", {})
    return {
        "tenure": g.get("tenure", True),
        # only meaningful when the user needs sponsorship
        "sponsorship": g.get("sponsorship", bool(PROFILE.get("needs_sponsorship"))),
    }


def recency_days():
    return int(CRITERIA.get("recency_days", 7))


def work_mode_rules():
    """Which of onsite/hybrid/remote the user will take, and the score penalty
    applied to fully-remote listings (they draw far more applicants)."""
    wm = CRITERIA.get("work_mode", {})
    return {
        "accept": [m.lower() for m in wm.get("accept", ["onsite", "hybrid", "remote"])],
        "remote_penalty": float(wm.get("remote_penalty", 0)),
    }


def location_rules():
    loc = CRITERIA.get("location", {})
    return {
        "country": loc.get("country", "US"),
        "mode": loc.get("mode", "country_wide"),   # country_wide | cities
        "cities": [c.lower() for c in loc.get("cities", [])],
        "include_remote": loc.get("include_remote", True),
    }


def company_priorities():
    """{company_name: 'P1'|'P2'|'P3'} chosen during onboarding."""
    return CRITERIA.get("company_priorities", {})


def technical_stack():
    p = PROFILE.get("skills", {})
    return ([k.lower() for k in p.get("in_stack", [])],
            [k.lower() for k in p.get("out_of_stack", [])])


def cv_variants():
    return PROFILE.get("cv_variants", [])


def feedback_form_url():
    return (PROFILE.get("feedback_form_url") or "").strip()


def compiled(patterns):
    return [re.compile(p, re.I) for p in patterns]
