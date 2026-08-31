---
name: job-tracker
description: Personal job-search tracker that scrapes company job boards, scores roles against the user's background, and publishes a dashboard. Use when the user wants to set up a job tracker, run or refresh a job scan, see new roles, give feedback on bad matches, adjust their search criteria or scoring weights, or add/remove/reprioritise target companies. Triggers include "set up my job tracker", "scan", "find me jobs", "any new roles", and pasted dashboard feedback.
---

# Job Tracker

A job-search pipeline the user owns: it scrapes the job boards of companies they
pick, filters by their role and seniority rules, scores each posting for callback
likelihood, and publishes a dashboard they can triage from.

The user is probably **not technical**. Never show them a traceback, a file
path, or a JSON blob unless they ask. Talk about "your criteria", not
"criteria.json". Do the work; report the outcome.

## Routing

| The user says | Go to |
|---|---|
| "set up my job tracker", or `~/job-tracker/config/profile.json` is missing | **Onboarding** below |
| "scan", "refresh", "any new roles", or pastes the scan command | `references/scanning.md` |
| pastes dashboard feedback (`REJECT (...)` / `APPLIED ...` lines) | `references/feedback.md` |
| "change my weights", "score industry higher", pastes weights text | `references/tuning.md` |
| "add/remove company", "make X a P1" | `references/companies.md` |
| "why did this role show up / not show up" | `references/tuning.md` |
| "redo my setup", "change my profile", "I want different roles" | **Onboarding** below — rerun only the steps that changed, keeping the rest |

Everything lives in `~/job-tracker/`. Scans are **on demand only** — never set up
a schedule unless the user explicitly asks for one.

`catalog/feedback.json` is the one file you never edit. It carries the feedback
destination belonging to whoever published this template. If the user would
rather not send feedback, set `feedback_enabled: false` in their profile — that
hides the Send button and leaves Copy working.

---

## Onboarding

Four steps. Run them in order, one message at a time — do not dump all the
questions at once. After each step, show what you captured and let them correct
it before moving on.

### First, read what they already gave you

The README offers a fill-in template, so their opening message may already
answer half of this — and it will have blanks and placeholder examples in it.
Before asking anything:

- **Take what's there.** Treat any filled line as their answer. Never re-ask
  something they've already told you; it reads as not having listened.
- **Ignore the scaffolding.** Lines they left blank, deleted, or left as the
  `e.g.` example text are not answers. A line reading `e.g. Stripe, Ramp, Figma`
  is the template's own example, not their company list.
- **Say what you got before asking for the rest.** One short list of what you
  captured, then only the questions that are genuinely still open.
- **Still confirm the CV-derived parts.** Even a fully-filled template doesn't
  cover what the CV says about their tools and functions, and people
  under-describe themselves. Propose those and let them correct.

If they said "suggest some for me" for companies, that's a real answer — do the
suggesting rather than pushing the question back at them.

Scaffold first. The starting files live in a `template/` directory **next to
this SKILL.md**. Copy it to `~/job-tracker/` if that doesn't exist yet, then
copy `config/profile.example.json` and `config/criteria.example.json` to
`profile.json` and `criteria.json`. Those examples are tuned for strategy /
business-operations roles; treat them as a starting shape to overwrite, not as
defaults to keep.

If `template/` is missing next to this file — some install routes copy only the
skill — fetch it instead, then carry on:

```bash
git clone --depth 1 https://github.com/chandrarekso/job-tracker-template /tmp/jt \
  && cp -R /tmp/jt/skills/job-tracker/template ~/job-tracker && rm -rf /tmp/jt
```

Everything after this point runs from `~/job-tracker/`, never from the skill
directory — the skill is shared across projects, the user's tracker is theirs.

### Step 1 — Background and search parameters

Ask for their CV first: *"Drop your CV in the chat — PDF or Word is fine — and
I'll pull your background out of it. Or just tell me what you do."*

If they share a CV, read it and extract: current title, total years of
experience, functions they've actually performed, tools and software they use,
industries they've worked in, and any seniority signals. Summarise it back in
five or six lines and ask them to correct anything wrong. Never guess at years
of experience — if the CV is ambiguous, ask.

Then **propose, don't interrogate**. Based on the CV, suggest:

- **Roles** — 4-6 target job functions, as titles they'd actually see on a
  posting. Say which ones you're less sure about.
- **Industries** — read `catalog/sectors.json` and rank those sectors from most
  to least relevant to their background. Add a sector if none of them fit.
- **Seniority** — a years band and the titles that are a level too junior or too
  senior for them.

Present each as a short list and say plainly: **"Change anything — add, remove,
or reorder. These are just a starting point."** Their edits win over your
suggestions every time, even when you think they're casting too wide or too
narrow. If you believe a choice will hurt their results, say so in one sentence,
then do what they asked.

### Step 2 — Companies, location, work mode

Ask these together, they're quick:

1. **Target companies.** The template ships with **no company list** — this is
   theirs to build. Ask who they're targeting. If they're not sure, suggest
   15-25 real employers in the sectors they ranked highest, drawn from what you
   know of that market and their location, and say plainly that these are
   suggestions to react to, not a curated list. Then resolve each one — see
   `references/companies.md`. Expect this to take a couple of minutes and tell
   them so; it's the slowest part of setup and it only happens once.
2. **Prioritise them.** *"Split these into three groups: P1 dream companies,
   P2 strong interest, P3 worth knowing about."* P1 gets highlighted in the
   dashboard and is what they check first. If they'd rather not sort all of
   them, ask only for the P1s and put the rest in P3.
3. **Location.** A country-wide search, or specific cities? Do they want remote
   roles included?
4. **Work mode.** Onsite, hybrid, remote — which will they take? Note that
   fully-remote postings draw far more applicants, so the scoring can dock them
   a few points; ask whether they want that.
5. **Visa sponsorship.** *"Do you need an employer to sponsor a work visa?"* If
   yes, postings that explicitly refuse sponsorship get dropped entirely — this
   matters a lot, so ask it directly rather than inferring from the CV.

Now write `config/profile.json` and `config/criteria.json`. Map their answers
onto the shape in the `.example.json` files. Two things to get right:

- `role.include` should be **broader** than their stated titles — it's a
  first-pass net, and the head-test rules below it do the precision work.
- `scoring.sector_points` comes from their industry ranking, on a 0-100 scale.
  Spread the values out; a flat ranking gives the industry dimension nothing to
  say.

### Step 3 — Brief them on the scoring

Before the first scan, explain how roles get scored. Read
`references/scoring-brief.md` and deliver it in your own words — it's a briefing,
not a document to paste.

Cover the four dimensions and what each one measures, the default weights, the
two hard gates (tenure and sponsorship) and that those *drop* roles rather than
scoring them low, and the remote penalty if they enabled it.

Then: *"Want to change the weights now, or try the defaults and adjust once you
see real roles?"* Most people should see roles first — the sliders on the
dashboard's Profile & criteria tab re-rank instantly, so tuning is cheap later.
If they do want changes now, write them to `scoring.weights` in criteria.json.

### Step 4 — First scan and publish

Run the scan (`references/scanning.md`), then publish the dashboard as an
Artifact and give them the link.

Then walk them through it in four bullets — refresh with the Request scan
button, triage with Applied/Reject, teach the filters with Copy feedback, retune
with the weight sliders. The dashboard has a "How to use" panel that says the
same thing, so keep it brief and point them there.

Close by telling them the two things they'll want next: say **"scan"** any time
to refresh, and paste the **Copy feedback** output after rejecting a few roles
so the filters learn. That feedback loop is what makes this better than a job
alert, so make sure they know it exists.

---

## Things that go wrong

**A first scan returning very few roles is normal** — the default window is 7
days and most companies post nothing in a given week. Say so, rather than
letting them think it's broken. If it's genuinely zero across 20+ companies,
check that `role.include` isn't too narrow before touching anything else.

**Never widen a user's criteria to make the numbers look better.** An empty
result they can trust beats a padded one they can't.

**Company identity is not the same as a matching slug.** Always run
`scripts/audit_boards.py` after resolving a new company — see
`references/companies.md` for why this bites.
