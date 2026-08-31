# Job Tracker

A job search that runs itself and tells you which roles are actually worth your
time.

It checks the job boards of companies you pick, throws out everything that isn't
your role or your level, scores what's left on how likely it is to get you a
callback, and puts it on a dashboard you can triage in a couple of minutes.

You talk to it in plain English. There's no code to write and nothing to
configure by hand.

---

## What you need

- **[Claude Code](https://claude.com/claude-code)** — the desktop app for Mac or
  Windows is the easiest way in. You won't need a terminal.
- **Python 3** — already installed on macOS. On Windows, get it from
  [python.org](https://python.org) and tick "Add Python to PATH" during setup.

## Install

In Claude Code, run:

```bash
/plugin marketplace add chandrarekso/job-tracker-template
```

Then:

```bash
/plugin install job-tracker
```

## Start

Say this in the chat:

> set up my job tracker

It'll ask for your CV, read it, and suggest the roles, industries and seniority
that fit your background. Change anything you disagree with — the suggestions
are a starting point, not a verdict. Then it asks which companies you're
targeting, where you want to work, and whether you need visa sponsorship.

When that's done it explains how the scoring works, runs the first scan, and
gives you a link to your dashboard.

The whole thing takes about ten minutes.

---

## Using it

**Get fresh roles.** Say `scan`. It re-checks every company and updates your
dashboard at the same link.

**Triage.** Each role has ✓ Applied and ✗ Reject. Rejecting asks why.

**Teach it.** After rejecting a few roles, hit **Copy feedback for Claude** and
paste it into the chat. It tightens your criteria so those roles stop showing
up. This is the part that makes it better than a job alert — a tracker you've
corrected twice is dramatically more useful than one you haven't.

**Re-tune the scoring.** The **Profile & criteria** tab has sliders for the four
scoring dimensions. Drag one and the table re-ranks instantly. To keep the
change, hit **Copy weights for Claude** and paste it.

**Change your company list.** Just say so — "add Notion", "make Stripe a P1",
"drop the infra companies".

---

## How the scoring works

Each role gets 0-100 for **how likely it is to convert into a callback** — not
how good the job is. A dream role wanting twelve years of experience scores low,
and that's the point.

| Dimension | Default | What it measures |
|---|---|---|
| Role fit | 35 | How closely the title matches the functions you want |
| Industry | 25 | How much you want that company's sector |
| Technical fit | 20 | Overlap between the role's tools and yours |
| Tenure | 20 | How close its experience ask is to yours |

Two filters **drop** roles rather than scoring them low, because they're closed
doors regardless of fit: roles outside your years band, and — if you need visa
sponsorship — postings that explicitly refuse it.

---

## What's in the box

**No company list.** You build yours during setup — name whoever you're
targeting and Claude works out how to read their job board, verifying it belongs
to the right company before trusting it. If you're not sure who to target, it'll
suggest employers in the sectors you picked.

What ships is the machinery for reading boards. Most companies publish through
one of three standard systems, handled generically. Some large employers don't —
Google, Meta, Apple, Netflix, Microsoft, PayPal, Plaid, Uber and Atlassian each
need their own approach, and purpose-built scrapers for those are included and
working. Name any of them and it just wires up.

---

## Where your data lives

Everything stays on your machine, in `~/job-tracker/`. Your CV is read during
setup and never stored. The dashboard is published as a private page that only
you can see unless you choose to share it.

The **Feedback** tab sends a message to whoever shared this template with you. It
carries nothing but what you type — no name, no email, no job data — and it's
optional.

---

## If something looks wrong

**Very few roles on the first scan** is normal. The default window is the last 7
days, and most companies post nothing in a given week.

**A role you saw elsewhere didn't show up.** Ask: "why didn't the X role at Y
show up?" It'll walk back through the filters and tell you exactly which one
dropped it.

**Nothing at all, across every company.** Your role keywords are probably too
narrow. Say "my criteria are too tight" and it'll widen them with you.

---

## Making it your own

`config/profile.json` is you; `config/criteria.json` is what you're looking for
and how it's scored. Both are plain text with comments, and both are safe to
edit by hand if you want to — but you never have to. Asking in the chat does the
same thing.

---

## License

MIT. Fork it, change it, share it.
