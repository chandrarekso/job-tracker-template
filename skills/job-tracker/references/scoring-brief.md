# The scoring model — brief for the user

Deliver this in your own words, conversationally. It's a briefing before the
first scan, not a document to paste. Aim for a minute of reading.

## The one-line version

Every posting gets a 0-100 score for **how likely it is to convert into a
callback** — not how good the job is. A dream role that wants twelve years of
experience scores low, and that's correct.

## Four dimensions

| Dimension | Default weight | What it measures |
|---|---|---|
| **Role fit** | 35 | How closely the title and description match the functions they want |
| **Industry** | 25 | How much they want that company's sector |
| **Technical fit** | 20 | Overlap between the tools the role asks for and the ones they use |
| **Tenure** | 20 | How close the demanded years of experience are to theirs |

Weights are normalised to 100, so they can move one without rebalancing the
others.

Two details worth mentioning, because they surprise people:

- **Industry is scored per company, not from the job text.** A marketplace is a
  marketplace whether or not the posting says "marketplace". A strong mandate in
  their target space can still pull an off-sector employer up a few points.
- **Tenure reads the highest number in the posting.** Ads escalate: "minimum 2
  years… preferred 6 years" is a six-year role. Reading the minimum would
  mislabel it as junior.

## Two hard gates

These **drop** roles rather than scoring them low, because they're closed
pipelines regardless of fit:

- **Tenure** — outside their band, the role never appears at all.
- **Sponsorship** — if they need a visa sponsored, postings that explicitly
  refuse it are dropped. Only negative phrasing triggers this; "sponsorship
  available" is safe.

Say this explicitly. A user who doesn't know about the gates will think the
scraper is broken when a role they saw elsewhere doesn't show up.

## The remote penalty

If enabled, fully-remote postings lose a few points — they draw far more
applicants, so identical fit converts worse. Roles naming a city aren't
penalised, even if remote is also an option. It's off unless they asked for it.

## What they should do with this

Nothing yet. The weight sliders on the dashboard's **Profile & criteria** tab
re-rank the table live, so it's much easier to tune once there are real roles on
screen than in the abstract. Offer the change now, but recommend waiting.

When they do move a slider, the change lives in their browser until they hit
**Copy weights for Claude** and paste it — that's what makes it permanent.
