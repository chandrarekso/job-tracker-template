# Learning from dashboard feedback

The user rejects roles in the dashboard with a reason, hits **Copy feedback for
Claude**, and pastes the result. Lines look like:

```
REJECT (Role Mismatch) | Stripe | Sales Strategy Manager, SMB | New York, NY | P2
APPLIED 2026-08-18 | Google | Strategy and Operations Manager, Global Ads
```

This is the loop that makes the tracker better than a job alert. Treat it as the
most valuable input the user gives you.

## What to do with it

**1. Suppress the specific roles.** Write every rejected job into
`data/rejected.json` so it never reappears. That file supports two forms:

```json
{"by_id": {"Stripe::12345": {"reason": "Role Mismatch"}},
 "by_company_title": [{"company": "Stripe", "title": "Sales Strategy Manager, SMB"}]}
```

Use `by_id` when the paste carries an ID. Rows whose job already aged out export
without one — match those on company plus title instead.

**2. Record the applications.** Write `APPLIED` lines into `data/applied.json`
keyed by job ID, with `company`, `title`, and `at`. This seeds the tracker so it
survives a browser with no local state, and stops an already-applied role
reappearing in the open list.

**3. Generalise the reason into a filter change.** This is the part that
matters — suppression alone fixes one row, a filter change fixes the pattern.

| Reason | What it usually means | Where to change it |
|---|---|---|
| Role Mismatch | wrong function | `role.rejected_function_heads` or `role.exclude` |
| Seniority Issue | right function, wrong level | `seniority.*` lists, or the tenure band |
| Link Issue | the posting URL is broken | that company's scraper, not the filters |
| Already Applied | tracked elsewhere | suppress only, change nothing |
| Application Time Limits | closed or expired | suppress only; consider a shorter `recency_days` |

## Generalising well

**Use the function-head test.** The same words appear on both sides of a good
title. `role.rejected_function_heads` is matched against only the part of the
title before the first comma or dash, because that's what names the actual
function. "Finance & BizOps, Strategic Partnerships" has head "finance &
bizops" — a bizops role worth keeping. "Strategic Partner Manager, Creators" has
head "strategic partner manager" — a partnerships role. A whole-title match
cannot separate those two; the head test can.

Only put a phrase in `role.full_title_excludes` if it disqualifies the role
**wherever it appears**. "Strategic finance" qualifies. "Partnerships" does not.

**Anchor prefixes that need anchoring.** `role.rejected_head_prefixes` matches
at the *start* of the head. That's how "Product Manager, Growth" gets dropped
while "Growth Product Manager" survives — if the user actually wants the latter.
Ask if you're unsure which they meant.

**Don't add company-level penalties from role rejections.** A user rejecting six
roles at one company is telling you about those roles, not about the company.
Confirm before touching `scoring.company_points`.

## Always validate before shipping

Every applied role must still pass the filters after your change. Load
`data/applied.json`, run each title through `matches_role` and `matches_level`
with the new config, and confirm zero regressions. If a change would filter out
something they already applied to, it's too aggressive — narrow it.

Some rejections are genuinely indistinguishable by title alone. Don't contort
the filters to catch those; suppress them individually in `rejected.json` and
say so.

## Then

Rebuild the dashboard, republish to the same artifact URL, and tell the user in
plain terms what changed: "Roles like *X* won't show up again, and I've tightened
*Y*." Name the tradeoff if there is one — if a rule might also drop something
they'd want, say which kind of role and offer to reverse it.
