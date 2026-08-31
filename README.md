# Job Tracker

A job search that runs itself and tells you which roles are actually worth your
time.

It checks the job boards of companies you pick, throws out everything that isn't
your role or your level, scores what's left on how likely it is to get you a
callback, and puts it on a dashboard you can triage in a couple of minutes.

You talk to it in plain English. There's no code to write and nothing to
configure by hand.

---

## Setup — 4 steps

### 1. Get Claude Code

Download it from **[claude.com/claude-code](https://claude.com/claude-code)**.
The Mac or Windows app is fine; you don't need a terminal.

### 2. Install the tracker

Open Claude Code and paste this as a normal message:

```text
Install the job tracker skill from
https://github.com/chandrarekso/job-tracker-template

Clone it and copy skills/job-tracker, including its template folder,
into ~/.claude/skills/
```

### 3. Restart Claude Code

Quit it and open it again. It only looks for new skills at startup, so it won't
find the tracker until you do this.

### 4. Attach your CV and say:

```text
set up my job tracker
```

Claude reads your CV, suggests the roles, industries and seniority that fit,
and asks you to correct anything it got wrong. About ten minutes of questions,
then it runs the first scan and hands you your dashboard.

---

## Two things worth knowing

**Nothing here is permanent.** Once you're set up you can say things like
`only New York`, `add Figma as a P1`, or `redo my job tracker setup`.

**A thin first scan is normal.** It only looks at the last 7 days, and most
companies post nothing in a given week.

<details>
<summary>Front-load your answers instead (optional)</summary>

If you already know what you want, paste this at step 4 rather than the short
version. **Delete any line you're unsure about** — Claude asks about the gaps
and won't re-ask anything you've answered.

```text
Set up my job tracker. My CV is attached.

WHAT I'M LOOKING FOR
- Job titles:            e.g. Analytics Manager, Business Intelligence Lead
- Industries:            e.g. fintech and health tech; not enterprise software
- Seniority:             e.g. 4-7 years; not director level
- Deal-breakers:         e.g. no pure sales roles, no people-management

WHERE
- Location:              e.g. New York and Boston only  /  anywhere in the US
- Onsite, hybrid, remote: e.g. hybrid or onsite, not fully remote

COMPANIES
- Dream companies (P1):  e.g. Stripe, Ramp, Figma
- Interested (P2):       e.g. Notion, Databricks
- Or: suggest some for me

PRACTICAL
- Visa sponsorship:      e.g. yes, I need it  /  no
- Only show roles posted in the last: 7 days
```

</details>

<details>
<summary>Other ways to install</summary>

**In a terminal running `claude`,** the plugin manager works. Note that
`/plugin` does nothing in the desktop or web app, which is why it isn't the
default:

```bash
/plugin marketplace add chandrarekso/job-tracker-template
```

```bash
/plugin install job-tracker
```

**By hand,** one command:

```bash
git clone --depth 1 https://github.com/chandrarekso/job-tracker-template /tmp/jt && mkdir -p ~/.claude/skills && cp -R /tmp/jt/skills/job-tracker ~/.claude/skills/ && rm -rf /tmp/jt
```

</details>

<details>
<summary>You'll also need Python 3</summary>

Already on every Mac. On Windows, install it from
[python.org](https://python.org) and tick **Add Python to PATH** during setup.

</details>

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
