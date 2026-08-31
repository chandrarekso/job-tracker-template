# Tuning weights and criteria

## Saving edited weights

The dashboard's sliders change scoring **in the browser only**. When the user
pastes something like:

> Update my job tracker scoring weights to: Role fit 40, Industry 30, Technical
> fit 15, Tenure 15. Save them to config/criteria.json and rebuild the dashboard.

write those numbers into `scoring.weights` in `criteria.json`, rebuild, and
republish to the same artifact URL. Confirm briefly and name what moved — "Role
fit up from 35 to 40, so titles matter more and sector matters less."

Weights are normalised to 100 at scoring time, so they don't need to sum
correctly. A weight of 0 is valid and switches a dimension off.

## Answering "why did this role show up?"

Each score cell carries a per-dimension breakdown in its tooltip. To explain a
specific job, read its `score_parts` in `data/jobs.json`:

- `fractions` — how well it did on each dimension, 0 to 1
- `weights` — what those were multiplied by
- `penalties` — anything subtracted, e.g. the remote penalty

The final score is `sum(fraction × weight) − penalties`. Walk through the two
dimensions that dominated rather than reciting all four.

## Answering "why didn't X show up?"

Work through the pipeline in order and stop at the first thing that excludes it:

1. **Is the company tracked?** Check `data/companies.json`.
2. **Does that company's feed resolve?** An `unresolved` type means it's never
   scraped. A `browser_only` type means it needs a browser pass that may not
   have run.
3. **Recency** — was it posted inside `recency_days`?
4. **Role filter** — run the title through `matches_role`.
5. **Level filter** — run it through `matches_level`.
6. **Location and work mode** — `location_ok` covers both.
7. **Hard gates** — tenure and sponsorship, from the description text.
8. **Suppressed** — is it in `data/rejected.json` from earlier feedback?

Tell them which step dropped it and what would have to change. Don't change
anything without asking — several of these rules exist because the user asked
for them.

## Changing the tenure band

`seniority.tenure_min` / `tenure_max` gate hard; `tenure_ideal_min` /
`tenure_ideal_max` set the scoring sweet spot. Widening the gate is the single
most effective way to increase result volume, and the most likely to fill the
dashboard with roles they won't get. If they ask for more results, propose this
with the tradeoff stated, and let them decide.

## A note on drift

Filters tightened from feedback accumulate. Every few rounds, check whether the
rules still make sense together — especially `too_senior_trailing` and the
head-prefix rules, which are judgement calls that are easy to reverse. Say so if
you think one has outlived its evidence.
