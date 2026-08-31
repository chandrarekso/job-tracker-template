"""Renders data/jobs.json + config/*.json into dashboard/index.html.

Four tabs: Open roles, Application tracker, Profile & criteria, Feedback.

Scores are recomputed in the browser from each job's stored per-dimension
fractions, so moving a weight slider re-ranks the table instantly with no
rescan. All viewer state (applied / rejected / edited weights) lives in
localStorage; the "Copy feedback" export is how it reaches Claude.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

BASE = config.BASE

with open(config.data_path("jobs.json")) as f:
    jobs_data = json.load(f)
try:
    with open(config.data_path("companies.json")) as f:
        companies = json.load(f)["companies"]
except (FileNotFoundError, json.JSONDecodeError):
    companies = []

jobs = jobs_data.get("jobs", [])
generated_at = jobs_data.get("generated_at", "")

# Applications recorded from pasted dashboard feedback. Seeded into the page so
# the tracker is populated even in a browser with no local state, and so an
# already-applied role never reappears in the open list.
try:
    with open(config.data_path("applied.json")) as f:
        applied_seed = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    applied_seed = {}


def _norm(s):
    return " ".join((s or "").lower().replace("&", "and").split())


seed_titles = {(v.get("company"), _norm(v.get("title"))): v.get("at")
               for v in applied_seed.values() if v.get("title")}
for j in jobs:
    at = seed_titles.get((j["company"], _norm(j["title"])))
    if at:
        applied_seed.setdefault(j["id"], {"at": at, "company": j["company"],
                                          "title": j["title"]})

priorities = config.company_priorities()
by_type = {}
for c in companies:
    by_type.setdefault((c.get("source_feed") or {}).get("type", "unknown"), []).append(c["name"])
static_page = sorted(by_type.get("static_page", []))
unresolved = sorted(by_type.get("unresolved", []))
auto_count = len(companies) - len(static_page) - len(unresolved)

# company table rows for the Profile tab
company_rows = sorted(
    ({"name": c["name"],
      "sector": c.get("sector", "other"),
      "priority": priorities.get(c["name"], "P3"),
      "feed": (c.get("source_feed") or {}).get("type", "unresolved")}
     for c in companies),
    key=lambda c: (c["priority"], c["name"]))

try:
    gen_display = datetime.fromisoformat(generated_at).strftime("%b %-d, %Y at %-I:%M %p UTC")
except Exception:
    gen_display = generated_at or "never"

profile = config.PROFILE
criteria = config.CRITERIA
feedback_url = config.feedback_form_url()

TEMPLATE = r"""<title>Job Tracker</title>
<style>
:root {
  --bg: #f6f4ef; --surface: #ffffff; --ink: #1c1b18; --muted: #6f6a5f; --line: #e4e0d6;
  --accent: #b5793a; --accent-ink: #ffffff;
  --p1: #b5793a; --p1-bg: #fbeee0; --p2: #4f5d75; --p2-bg: #e8ecf1; --p3: #8a8578; --p3-bg: #eeece5;
  --good: #3f7d4f; --good-bg: #e4f1e6; --mid: #a3771f; --mid-bg: #f6ecd8;
  --low: #8a8578; --low-bg: #eeece5; --danger: #a1483f; --danger-bg: #f7e6e3;
  --font-display: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #15140f; --surface: #1e1c17; --ink: #ece7db; --muted: #9c9583; --line: #332f27;
    --accent: #d99b52; --accent-ink: #1c1b18;
    --p1: #d99b52; --p1-bg: #3a2c18; --p2: #93a7c9; --p2-bg: #232a38; --p3: #a19b8b; --p3-bg: #2a2822;
    --good: #7fc492; --good-bg: #1e2f22; --mid: #d9b56b; --mid-bg: #34290f;
    --low: #a19b8b; --low-bg: #2a2822; --danger: #d98d82; --danger-bg: #3a221f;
  }
}
:root[data-theme="dark"] {
  --bg: #15140f; --surface: #1e1c17; --ink: #ece7db; --muted: #9c9583; --line: #332f27;
  --accent: #d99b52; --accent-ink: #1c1b18;
  --p1: #d99b52; --p1-bg: #3a2c18; --p2: #93a7c9; --p2-bg: #232a38; --p3: #a19b8b; --p3-bg: #2a2822;
  --good: #7fc492; --good-bg: #1e2f22; --mid: #d9b56b; --mid-bg: #34290f;
  --low: #a19b8b; --low-bg: #2a2822; --danger: #d98d82; --danger-bg: #3a221f;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: 14px; line-height: 1.5; }
.wrap { max-width: 1400px; margin: 0 auto; padding: 32px 24px 64px; }
h1 { font-family: var(--font-display); font-weight: 400; font-size: 32px; margin: 0 0 4px; text-wrap: balance; }
.subtitle { color: var(--muted); font-size: 13.5px; }
.headrow { display: flex; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.headrow .grow { flex: 1; min-width: 260px; }
.scanbtn { background: var(--accent); color: var(--accent-ink); border: none; border-radius: 8px;
  padding: 10px 18px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: var(--font-body); }
.scanbtn:hover { opacity: 0.9; }
.scanhint { font-size: 11.5px; color: var(--muted); max-width: 200px; margin-top: 6px; }
.howto { background: var(--surface); border: 1px solid var(--line); border-left: 3px solid var(--accent);
  border-radius: 10px; padding: 14px 18px; margin: 20px 0 4px; font-size: 13px; }
.howto summary { cursor: pointer; font-weight: 600; font-size: 13.5px; }
.howto ul { margin: 10px 0 0; padding-left: 20px; }
.howto li { margin: 5px 0; color: var(--muted); }
.howto b { color: var(--ink); }
.howto code { font-family: var(--font-mono); font-size: 12px; background: var(--low-bg);
  padding: 1px 5px; border-radius: 4px; color: var(--ink); }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 24px 0; }
.stat { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
.stat .n { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 24px; font-weight: 600; }
.stat .l { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; margin-top: 2px; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); margin-bottom: 18px; flex-wrap: wrap; }
.tab { background: none; border: none; border-bottom: 2px solid transparent; color: var(--muted);
  padding: 10px 18px; font-size: 14.5px; cursor: pointer; font-family: var(--font-body); }
.tab[aria-selected="true"] { color: var(--ink); border-bottom-color: var(--accent); font-weight: 600; }
.controls { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
.chip { border: 1px solid var(--line); background: var(--surface); color: var(--muted); border-radius: 999px;
  padding: 6px 14px; font-size: 12.5px; cursor: pointer; font-family: var(--font-body); }
.chip[aria-pressed="true"] { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); font-weight: 600; }
.chip:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
select.sortsel { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; color: var(--ink);
  padding: 6px 10px; font-size: 12.5px; font-family: var(--font-body); }
.search { margin-left: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
  padding: 6px 12px; font-size: 13px; color: var(--ink); min-width: 200px; font-family: var(--font-body); }
.table-scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); }
table { border-collapse: collapse; width: 100%; }
#pane-open table, #pane-tracker table { min-width: 1300px; }
thead th { position: sticky; top: 0; background: var(--surface); text-align: left; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); padding: 12px 14px;
  border-bottom: 1px solid var(--line); white-space: nowrap; }
thead th[data-sort] { cursor: pointer; }
thead th.sorted { color: var(--ink); }
tbody td { padding: 11px 14px; border-bottom: 1px solid var(--line); vertical-align: middle; }
tbody tr:last-child td { border-bottom: none; }
tbody tr { border-left: 3px solid transparent; }
tbody tr.p1 { border-left-color: var(--p1); }
tbody tr.p2 { border-left-color: var(--p2); }
tbody tr.p3 { border-left-color: var(--p3); }
.company { font-weight: 600; }
.title-cell { max-width: 300px; }
.loc { color: var(--muted); font-size: 11.5px; margin-top: 2px; }
.pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600; white-space: nowrap; }
.pill.p1 { background: var(--p1-bg); color: var(--p1); }
.pill.p2 { background: var(--p2-bg); color: var(--p2); }
.pill.p3 { background: var(--p3-bg); color: var(--p3); }
.pill.industry { background: var(--low-bg); color: var(--muted); font-weight: 500; }
.pill.reason { background: var(--danger-bg); color: var(--danger); font-weight: 500; }
.pill.appliedtag { background: var(--good-bg); color: var(--good); }
.score { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
.score.good { background: var(--good-bg); color: var(--good); }
.score.mid { background: var(--mid-bg); color: var(--mid); }
.score.low { background: var(--low-bg); color: var(--low); }
.effort.High { color: var(--danger); font-size: 12.5px; }
.effort.Low { color: var(--good); font-size: 12.5px; }
.salary { font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-size: 12.5px; color: var(--muted); white-space: nowrap; }
.posted { font-size: 12.5px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.posted .est { color: var(--mid); font-size: 11px; display: block; }
a.apply { color: var(--accent); text-decoration: none; font-weight: 600; font-size: 12.5px; white-space: nowrap; }
a.apply:hover { text-decoration: underline; }
.actions { display: flex; gap: 6px; white-space: nowrap; }
.act { border: 1px solid var(--line); background: var(--surface); border-radius: 6px; cursor: pointer;
  font-size: 12px; padding: 5px 10px; color: var(--muted); font-family: var(--font-body); }
.act.applied { background: var(--good-bg); color: var(--good); border-color: var(--good); font-weight: 600; }
.act.reject:hover { background: var(--danger-bg); color: var(--danger); border-color: var(--danger); }
.reasonbox { position: relative; display: inline-block; }
.reasonmenu { position: absolute; left: 0; top: calc(100% + 4px); z-index: 30; background: var(--surface);
  border: 1px solid var(--line); border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,0.18);
  min-width: 210px; padding: 6px; }
.reasonmenu button { display: block; width: 100%; text-align: left; background: none; border: none;
  padding: 8px 10px; font-size: 13px; color: var(--ink); cursor: pointer; border-radius: 6px; font-family: var(--font-body); }
.reasonmenu button:hover { background: var(--danger-bg); color: var(--danger); }
.reasonmenu .cancel { color: var(--muted); border-top: 1px solid var(--line); border-radius: 0; margin-top: 4px; }
.selbar { position: sticky; bottom: 12px; z-index: 40; margin-top: 14px; display: none;
  align-items: center; gap: 12px; flex-wrap: wrap; background: var(--surface);
  border: 1px solid var(--accent); border-radius: 12px; padding: 12px 16px;
  box-shadow: 0 6px 24px rgba(0,0,0,0.18); }
.selbar.show { display: flex; }
.selbar .count { font-weight: 600; }
.selbar .spacer { flex: 1; }
.openbtn { background: var(--accent); color: var(--accent-ink); border: none; border-radius: 8px;
  padding: 9px 16px; font-size: 13.5px; font-weight: 600; cursor: pointer; font-family: var(--font-body); }
.openbtn:hover { opacity: 0.9; }
.blockpanel { border: 1px solid var(--mid); background: var(--mid-bg); border-radius: 10px;
  padding: 12px 16px; margin-top: 12px; font-size: 13px; display: none; }
.blockpanel.show { display: block; }
.blockpanel ol { margin: 8px 0 0; padding-left: 20px; }
.blockpanel li { margin: 4px 0; }
.blockpanel a { color: var(--accent); font-weight: 600; }
.empty { padding: 40px; text-align: center; color: var(--muted); }
footer { margin-top: 20px; color: var(--muted); font-size: 12px; }
.exportrow { margin-top: 14px; }
#exportbox { width: 100%; min-height: 90px; font-family: var(--font-mono); font-size: 11.5px; margin-top: 8px;
  background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; padding: 10px; display: none; }
.section-h { font-family: var(--font-display); font-size: 20px; font-weight: 400; margin: 26px 0 10px; }
.section-h:first-child { margin-top: 0; }
.toast { position: sticky; bottom: 16px; margin: 12px auto 0; width: fit-content; max-width: 90%;
  background: var(--ink); color: var(--bg); border-radius: 999px; padding: 10px 20px; font-size: 13px;
  opacity: 0; transition: opacity 0.25s; pointer-events: none; }
.toast.show { opacity: 1; }

/* profile + criteria */
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; }
.card h3 { margin: 0 0 10px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-weight: 600; }
.kv { display: flex; gap: 10px; padding: 5px 0; border-bottom: 1px dashed var(--line); font-size: 13px; }
.kv:last-child { border-bottom: none; }
.kv .k { color: var(--muted); min-width: 116px; flex-shrink: 0; }
.kv .v { flex: 1; }
.taglist { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.tag { background: var(--low-bg); color: var(--muted); border-radius: 6px; padding: 2px 8px; font-size: 11.5px; }
.tag.no { background: var(--danger-bg); color: var(--danger); }
.tag.yes { background: var(--good-bg); color: var(--good); }
.weights { max-width: 640px; }
.wrow { display: grid; grid-template-columns: 116px 1fr 52px; gap: 12px; align-items: center; margin: 12px 0; }
.wrow label { font-size: 13.5px; }
.wrow .num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; text-align: right; font-size: 13px; }
input[type=range] { width: 100%; accent-color: var(--accent); }
.wtotal { font-size: 12.5px; color: var(--muted); margin-top: 10px; }
.wtotal.dirty { color: var(--mid); font-weight: 600; }
.wactions { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
.gate { font-size: 13px; padding: 6px 0; border-bottom: 1px dashed var(--line); }
.gate:last-child { border-bottom: none; }

/* feedback */
.fb { max-width: 640px; }
.fb textarea { width: 100%; min-height: 190px; background: var(--surface); color: var(--ink);
  border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; font-size: 14px;
  font-family: var(--font-body); line-height: 1.55; resize: vertical; }
.fb .row { display: flex; gap: 10px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
.fb .note { font-size: 12.5px; color: var(--muted); margin-top: 10px; }
.fb .count { font-size: 12px; color: var(--muted); margin-left: auto; font-variant-numeric: tabular-nums; }
</style>

<div class="wrap">
  <header class="headrow">
    <div class="grow">
      <h1>__DASH_TITLE__</h1>
      <div class="subtitle">__DASH_SUBTITLE__ &middot; refreshed __GEN_DISPLAY__</div>
    </div>
    <div>
      <button class="scanbtn" id="scanbtn">&#10227; Request scan</button>
      <div class="scanhint">Copies the scan command &mdash; paste it into the Claude chat to run.</div>
    </div>
  </header>

  <details class="howto" id="howto">
    <summary>How to use this dashboard</summary>
    <ul>
      <li><b>Refresh the listings.</b> Click <b>&#10227; Request scan</b> above, then paste into your Claude chat &mdash; or just type <code>scan</code>. Claude re-scrapes every company and republishes this page at the same link.</li>
      <li><b>Triage a role.</b> <b>&#10003; Applied</b> moves it to the Application tracker. <b>&#10007; Reject</b> asks why &mdash; that reason is what teaches the filters.</li>
      <li><b>Teach the filters.</b> After rejecting a few roles, hit <b>Copy feedback for Claude</b> at the bottom of Open roles and paste it into the chat. Claude tightens your criteria so those roles stop appearing.</li>
      <li><b>Re-tune your scoring.</b> Open <b>Profile &amp; criteria</b> and drag the weight sliders &mdash; the table re-ranks live. To keep the change, use <b>Copy weights for Claude</b>.</li>
      <li><b>Apply in bulk.</b> Tick several rows and use <b>Open application links</b> to launch them all at once.</li>
    </ul>
  </details>

  <div class="summary" id="summary"></div>

  <div class="tabs" role="tablist">
    <button class="tab" role="tab" aria-selected="true" data-tab="open">Open roles</button>
    <button class="tab" role="tab" aria-selected="false" data-tab="tracker">Application tracker</button>
    <button class="tab" role="tab" aria-selected="false" data-tab="profile">Profile &amp; criteria</button>
    <button class="tab" role="tab" aria-selected="false" data-tab="feedback">Feedback</button>
  </div>

  <div id="pane-open">
    <div class="controls">
      <label style="font-size:12.5px;color:var(--muted);">Sort</label>
      <select class="sortsel" id="sortsel">
        <option value="score">Match score</option>
        <option value="posted_at">Date posted (newest)</option>
        <option value="priority">Priority level</option>
        <option value="company">Company A&ndash;Z</option>
      </select>
      <label style="font-size:12.5px;color:var(--muted);">Location</label>
      <select class="sortsel" id="locsel"><option value="all">All locations</option></select>
      <button class="chip" data-filter="all" aria-pressed="true">All</button>
      <button class="chip" data-filter="P1" aria-pressed="false">P1</button>
      <button class="chip" data-filter="P2" aria-pressed="false">P2</button>
      <button class="chip" data-filter="P3" aria-pressed="false">P3</button>
      <input class="search" id="search" type="text" placeholder="Search company or title&hellip;" />
    </div>

    <div class="table-scroll">
      <table>
        <thead>
          <tr>
            <th><input type="checkbox" id="selall" aria-label="Select all shown" /></th>
            <th>Action</th>
            <th data-sort="company">Company</th>
            <th data-sort="industry">Sector</th>
            <th data-sort="title">Job Title</th>
            <th data-sort="priority">P</th>
            <th data-sort="posted_at">Posted</th>
            <th data-sort="salary_range">Salary</th>
            <th data-sort="score" class="sorted">Score</th>
            <th data-sort="recommended_cv">CV</th>
            <th data-sort="effort">Effort</th>
            <th>Link</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
      <div class="empty" id="empty" style="display:none;">No open roles match the current filters.</div>
    </div>

    <div class="selbar" id="selbar">
      <span class="count" id="selcount">0 selected</span>
      <button class="openbtn" id="openall">Open application links</button>
      <button class="chip" id="marksel">Mark as applied</button>
      <button class="chip" id="clearsel">Clear</button>
      <span class="spacer"></span>
    </div>
    <div class="blockpanel" id="blockpanel"></div>

    <div class="exportrow">
      <button class="chip" id="copybtn">Copy feedback for Claude</button>
      <textarea id="exportbox" readonly></textarea>
    </div>
  </div>

  <div id="pane-tracker" style="display:none;">
    <div class="section-h">Applied</div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Company</th><th>Job Title</th><th>P</th><th>Applied on</th><th>Link</th><th></th></tr></thead>
        <tbody id="applied-rows"></tbody>
      </table>
      <div class="empty" id="applied-empty">Nothing applied yet &mdash; hit &#10003; Applied on a role in the Open roles tab.</div>
    </div>

    <div class="section-h">Rejected</div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Company</th><th>Job Title</th><th>Reason</th><th>Rejected on</th><th></th></tr></thead>
        <tbody id="rejected-rows"></tbody>
      </table>
      <div class="empty" id="rejected-empty">No rejections logged.</div>
    </div>
  </div>

  <div id="pane-profile" style="display:none;">
    <details class="howto" style="margin-top:0;">
      <summary>Where these answers came from &mdash; and how to change them</summary>
      <ul>
        <li>Everything on this page was set during your <b>setup conversation</b>, when Claude read your CV and asked what you were looking for. Nothing here is fixed.</li>
        <li><b>To change any of it</b>, say so in the Claude chat in plain English &mdash; <code>I want to include product roles too</code>, <code>drop the sponsorship filter</code>, <code>only New York</code>, <code>add Figma as a P1</code>.</li>
        <li><b>To redo the whole thing</b>, say <code>redo my job tracker setup</code> and it walks the questions again from scratch.</li>
        <li>The headline at the top of this dashboard is built from these answers, so it changes when they do.</li>
      </ul>
    </details>

    <div class="section-h">Your profile</div>
    <div class="cards" id="profile-cards"></div>

    <div class="section-h">Search criteria</div>
    <div class="cards" id="criteria-cards"></div>

    <div class="section-h">Scoring weights</div>
    <div class="card weights">
      <h3>Drag to re-rank &mdash; the table updates live</h3>
      <div id="wrows"></div>
      <div class="wtotal" id="wtotal"></div>
      <div class="wactions">
        <button class="chip" id="wreset">Reset to saved</button>
        <button class="chip" id="wcopy">Copy weights for Claude</button>
      </div>
      <div class="wtotal" style="margin-top:12px;">
        Weights are normalised to 100, so you can move one without rebalancing the rest.
        Changes stay in this browser until Claude saves them to your config.
      </div>
    </div>

    <div class="section-h">Hard filters</div>
    <div class="card">
      <h3>Roles failing these are dropped, not just scored low</h3>
      <div id="gates"></div>
    </div>

    <div class="section-h">Priority companies <span style="font-size:13px;color:var(--muted);font-family:var(--font-body);">&mdash; __COMPANY_COUNT__ tracked</span></div>
    <div class="controls">
      <button class="chip" data-cfilter="all" aria-pressed="true">All</button>
      <button class="chip" data-cfilter="P1" aria-pressed="false">P1</button>
      <button class="chip" data-cfilter="P2" aria-pressed="false">P2</button>
      <button class="chip" data-cfilter="P3" aria-pressed="false">P3</button>
      <input class="search" id="csearch" type="text" placeholder="Search companies&hellip;" />
    </div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Priority</th><th>Company</th><th>Sector</th><th>Open now</th><th>Job board</th></tr></thead>
        <tbody id="company-rows"></tbody>
      </table>
      <div class="empty" id="company-empty" style="display:none;">No companies match.</div>
    </div>
    <footer>To add, drop or re-prioritise a company, say so in the Claude chat &mdash; it resolves the job board and re-runs the scan.</footer>
  </div>

  <div id="pane-feedback" style="display:none;">
    <div class="section-h">Send feedback</div>
    <div class="fb">
      <p style="color:var(--muted);font-size:13.5px;margin-top:0;">
        Tell the maker what's working, what's missing, or what broke. Goes straight to them &mdash; your message is sent anonymously and isn't linked to you.
      </p>
      <textarea id="fbtext" placeholder="What would make this more useful?"></textarea>
      <div class="row">
        <button class="openbtn" id="fbsend">Send feedback</button>
        <button class="chip" id="fbcopy">Copy instead</button>
        <span class="count" id="fbcount">0 characters</span>
      </div>
      <div class="note" id="fbnote"></div>
    </div>
  </div>

  <footer>__MANUAL_NOTE__ Applied/rejected state is saved in this browser. Use &ldquo;Copy feedback for Claude&rdquo; after rejecting roles &mdash; pasting it in chat is how the filters learn.</footer>
  <div class="toast" id="toast"></div>
</div>

<script>
const JOBS = __JOBS_JSON__;
const APPLIED_SEED = __APPLIED_SEED__;
const PROFILE = __PROFILE_JSON__;
const CRITERIA = __CRITERIA_JSON__;
const COMPANIES = __COMPANIES_JSON__;
const FEEDBACK_URL = __FEEDBACK_URL__;
const METRO_BUCKETS = __METRO_BUCKETS__;
const REASONS = ["Role Mismatch", "Seniority Issue", "Link Issue", "Already Applied", "Application Time Limits"];
const DIMS = ["role", "industry", "technical", "tenure"];
const DIM_LABEL = { role: "Role fit", industry: "Industry", technical: "Technical fit", tenure: "Tenure" };
const DIM_HELP = {
  role: "How closely the job title and description match the functions you want",
  industry: "How much you want that company's sector",
  technical: "Overlap between the tools the role asks for and the ones you use",
  tenure: "How close the demanded years of experience are to yours",
};
const K_APPLIED = "job-tracker-applied-v2";
const K_REJECTED = "job-tracker-rejected-v1";
const K_WEIGHTS = "job-tracker-weights-v1";
const K_OLD_APPLIED = "job-tracker-applied-v1";

const load = k => { try { return JSON.parse(localStorage.getItem(k) || "{}"); } catch (e) { return {}; } };
let applied = load(K_APPLIED);
let rejected = load(K_REJECTED);
const oldApplied = load(K_OLD_APPLIED);
for (const [id, v] of Object.entries(oldApplied)) {
  if (v && !applied[id]) applied[id] = { at: new Date().toISOString().slice(0, 10) };
}
// server-recorded applications win on first load; local edits still override later
for (const [id, v] of Object.entries(APPLIED_SEED)) {
  if (!applied[id]) applied[id] = v;
}

// Saved weights come from the config the last scan used; a local edit overrides
// them until Claude writes it back.
const SAVED_WEIGHTS = (() => {
  const w = (CRITERIA.scoring && CRITERIA.scoring.weights) || {};
  const out = {};
  DIMS.forEach(d => out[d] = Number(w[d] != null ? w[d] : 25));
  return out;
})();
let weights = (() => {
  const stored = load(K_WEIGHTS);
  const out = {};
  DIMS.forEach(d => out[d] = Number(stored[d] != null ? stored[d] : SAVED_WEIGHTS[d]));
  return out;
})();

const save = () => {
  // storage is unavailable in some embedding contexts; never let that break the UI
  try {
    localStorage.setItem(K_APPLIED, JSON.stringify(applied));
    localStorage.setItem(K_REJECTED, JSON.stringify(rejected));
    localStorage.setItem(K_WEIGHTS, JSON.stringify(weights));
  } catch (e) {
    console.warn("state not persisted:", e.message);
  }
};

const jobsById = {};
JOBS.forEach(j => jobsById[j.id] = j);

let state = { filter: "all", loc: "all", search: "", sortKey: "score", sortDir: "desc",
              openReason: null, cfilter: "all", csearch: "" };
const selected = new Set();
let visibleIds = [];

// ------------------------------------------------------------------ scoring
// Recomputed in the browser from each job's stored per-dimension fractions, so
// moving a slider re-ranks instantly. Mirrors scoring.score_job exactly:
//   round(sum(fraction[d] * normalisedWeight[d]) - penalties)
function normWeights(w) {
  const total = DIMS.reduce((s, d) => s + Math.max(0, w[d] || 0), 0);
  const out = {};
  if (total <= 0) { DIMS.forEach(d => out[d] = 25); return out; }
  DIMS.forEach(d => out[d] = Math.max(0, w[d] || 0) * 100 / total);
  return out;
}
function scoreOf(j) {
  const p = j.score_parts;
  if (!p || !p.fractions) return j.score || 0;   // pre-weighting scan data
  const w = normWeights(weights);
  let total = DIMS.reduce((s, d) => s + (p.fractions[d] || 0) * w[d], 0);
  const pen = p.penalties || {};
  for (const k in pen) total -= pen[k];
  return Math.round(Math.max(0, Math.min(100, total)));
}
function scoreTitle(j) {
  const p = j.score_parts;
  if (!p || !p.fractions) return "";
  const w = normWeights(weights);
  const bits = DIMS.map(d =>
    `${DIM_LABEL[d]} ${Math.round((p.fractions[d] || 0) * w[d])}/${Math.round(w[d])}`);
  const pen = p.penalties || {};
  for (const k in pen) bits.push(`${k} \u2212${pen[k]}`);
  return bits.join(" \u00b7 ");
}

const LOC_BUCKETS = METRO_BUCKETS.map(([name, re]) => [name, new RegExp(re, "i")]);
function jobBuckets(j) {
  const l = (j.location || "").toLowerCase();
  const hits = LOC_BUCKETS.filter(([, re]) => re.test(l)).map(([name]) => name);
  return hits.length ? hits : ["Other"];
}
(function initLocSel() {
  const present = new Set();
  JOBS.forEach(j => jobBuckets(j).forEach(b => present.add(b)));
  const sel = document.getElementById("locsel");
  [...LOC_BUCKETS.map(([n]) => n), "Other"].filter(n => present.has(n)).forEach(n => {
    const o = document.createElement("option");
    o.value = n; o.textContent = n;
    sel.appendChild(o);
  });
  sel.addEventListener("change", e => { state.loc = e.target.value; render(); });
})();

const scoreClass = s => s >= 78 ? "good" : s >= 62 ? "mid" : "low";
const esc = s => (s == null ? "" : String(s)).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const toast = msg => {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2600);
};

function fmtPosted(j) {
  if (!j.posted_at) return "\u2014";
  const days = Math.floor((Date.now() - new Date(j.posted_at).getTime()) / 86400000);
  const rel = days <= 0 ? "today" : days === 1 ? "1 day ago" : days + " days ago";
  return j.date_is_estimated ? rel + '<span class="est">' + esc(j.date_note || "estimated") + '</span>' : rel;
}

function sortRows(rows) {
  const key = state.sortKey;
  const flip = state.sortDir === "asc" ? -1 : 1;
  // "desc" means the natural reading order per key:
  // score high\u2192low, posted newest\u2192oldest, priority P1\u2192P3, company A\u2192Z
  const cmp = {
    score: (a, b) => scoreOf(b) - scoreOf(a),
    posted_at: (a, b) => (b.posted_at || "").localeCompare(a.posted_at || ""),
    priority: (a, b) => (a.priority || "").localeCompare(b.priority || ""),
    company: (a, b) => (a.company || "").localeCompare(b.company || ""),
  }[key] || ((a, b) =>
    (a[key] || "").toString().toLowerCase().localeCompare((b[key] || "").toString().toLowerCase()));
  return rows.sort((a, b) => cmp(a, b) * flip);
}

function render() {
  const tbody = document.getElementById("rows");
  const empty = document.getElementById("empty");
  let rows = JOBS.filter(j => {
    if (rejected[j.id] || applied[j.id]) return false;
    if (state.filter !== "all" && j.priority !== state.filter) return false;
    if (state.loc !== "all" && !jobBuckets(j).includes(state.loc)) return false;
    if (state.search) {
      const s = state.search.toLowerCase();
      if (!j.company.toLowerCase().includes(s) && !j.title.toLowerCase().includes(s)) return false;
    }
    return true;
  });
  rows = sortRows(rows);

  document.getElementById("summary").innerHTML = `
    <div class="stat"><div class="n">${rows.length}</div><div class="l">Open roles</div></div>
    <div class="stat"><div class="n">${JOBS.filter(j => j.priority === "P1" && !applied[j.id] && !rejected[j.id]).length}</div><div class="l">P1 open</div></div>
    <div class="stat"><div class="n">${Object.keys(applied).length}</div><div class="l">Applied</div></div>
    <div class="stat"><div class="n">${Object.keys(rejected).length}</div><div class="l">Rejected</div></div>
  `;

  if (!rows.length) { tbody.innerHTML = ""; empty.style.display = "block"; }
  else {
    empty.style.display = "none";
    tbody.innerHTML = rows.map(j => {
      const showMenu = state.openReason === j.id;
      const sc = scoreOf(j);
      return `<tr class="${j.priority.toLowerCase()}">
        <td><input type="checkbox" class="rowsel" data-sel="${esc(j.id)}" ${selected.has(j.id) ? "checked" : ""} aria-label="Select ${esc(j.title)}" /></td>
        <td><div class="actions">
          <button class="act" data-apply="${esc(j.id)}">\u2713 Applied</button>
          <span class="reasonbox">
            <button class="act reject" data-reject="${esc(j.id)}">\u2717 Reject</button>
            ${showMenu ? `<span class="reasonmenu">` + REASONS.map(r =>
              `<button data-reason="${esc(r)}" data-rid="${esc(j.id)}">${esc(r)}</button>`).join("") +
              `<button class="cancel" data-cancelreason="1">Cancel</button></span>` : ""}
          </span>
        </div></td>
        <td class="company">${esc(j.company)}</td>
        <td><span class="pill industry">${esc(j.sector || j.industry)}</span></td>
        <td class="title-cell">${esc(j.title)}<div class="loc">${esc(j.location || "")}</div></td>
        <td><span class="pill ${j.priority.toLowerCase()}">${j.priority}</span></td>
        <td class="posted">${fmtPosted(j)}</td>
        <td class="salary">${j.salary_range ? esc(j.salary_range) : "\u2014"}</td>
        <td><span class="score ${scoreClass(sc)}" title="${esc(scoreTitle(j))}">${sc}</span></td>
        <td>${esc(j.recommended_cv)}</td>
        <td class="effort ${j.effort}">${j.effort}</td>
        <td><a class="apply" href="${esc(j.application_link)}" target="_blank" rel="noopener">Open \u2192</a></td>
      </tr>`;
    }).join("");
  }

  tbody.querySelectorAll("[data-apply]").forEach(b => b.addEventListener("click", () => {
    applied[b.dataset.apply] = { at: new Date().toISOString().slice(0, 10) };
    delete rejected[b.dataset.apply];
    save(); state.openReason = null; render(); renderTracker(); renderCompanies();
    toast("Moved to Application tracker");
  }));
  tbody.querySelectorAll("[data-reject]").forEach(b => b.addEventListener("click", () => {
    state.openReason = state.openReason === b.dataset.reject ? null : b.dataset.reject;
    render();
  }));
  tbody.querySelectorAll("[data-reason]").forEach(b => b.addEventListener("click", () => {
    const id = b.dataset.rid, reason = b.dataset.reason;
    rejected[id] = { reason, at: new Date().toISOString().slice(0, 10) };
    if (reason === "Already Applied") applied[id] = applied[id] || { at: "earlier" };
    save(); state.openReason = null; render(); renderTracker(); renderCompanies();
    toast("Rejected: " + reason + " \u2014 use Copy feedback to teach Claude");
  }));
  tbody.querySelectorAll("[data-cancelreason]").forEach(b => b.addEventListener("click", () => {
    state.openReason = null; render();
  }));
  tbody.querySelectorAll(".rowsel").forEach(cb => cb.addEventListener("change", e => {
    const id = e.target.dataset.sel;
    e.target.checked ? selected.add(id) : selected.delete(id);
    renderSelBar();
  }));

  visibleIds = rows.map(j => j.id);
  const all = document.getElementById("selall");
  all.checked = visibleIds.length > 0 && visibleIds.every(id => selected.has(id));
  all.indeterminate = !all.checked && visibleIds.some(id => selected.has(id));
  renderSelBar();
}

function renderSelBar() {
  const bar = document.getElementById("selbar");
  const n = selected.size;
  bar.classList.toggle("show", n > 0);
  document.getElementById("selcount").textContent = n + " selected";
  document.getElementById("openall").textContent =
    n === 1 ? "Open 1 application link" : `Open ${n} application links`;
}

function renderTracker() {
  const aBody = document.getElementById("applied-rows");
  const rBody = document.getElementById("rejected-rows");
  const aList = Object.entries(applied).map(([id, v]) => ({ id, at: v.at, job: jobsById[id] }));
  const rList = Object.entries(rejected).map(([id, v]) => ({ id, ...v, job: jobsById[id] }));

  aBody.innerHTML = aList.map(({ id, at, job }) => {
    const title = job ? job.title : id.split("::")[1] || id;
    const company = job ? job.company : id.split("::")[0];
    return `<tr>
      <td class="company">${esc(company)}</td>
      <td>${esc(title)}${job ? `<div class="loc">${esc(job.location || "")}</div>` : ""}</td>
      <td>${job ? `<span class="pill ${job.priority.toLowerCase()}">${job.priority}</span>` : "\u2014"}</td>
      <td><span class="pill appliedtag">${esc(at)}</span></td>
      <td>${job ? `<a class="apply" href="${esc(job.application_link)}" target="_blank" rel="noopener">Open \u2192</a>` : "\u2014"}</td>
      <td><button class="act" data-unapply="${esc(id)}">Undo</button></td>
    </tr>`;
  }).join("");
  document.getElementById("applied-empty").style.display = aList.length ? "none" : "block";

  rBody.innerHTML = rList.map(({ id, reason, at, job }) => {
    const title = job ? job.title : id.split("::")[1] || id;
    const company = job ? job.company : id.split("::")[0];
    return `<tr>
      <td class="company">${esc(company)}</td>
      <td>${esc(title)}</td>
      <td><span class="pill reason">${esc(reason)}</span></td>
      <td style="font-size:12.5px;">${esc(at)}</td>
      <td><button class="act" data-unreject="${esc(id)}">Undo</button></td>
    </tr>`;
  }).join("");
  document.getElementById("rejected-empty").style.display = rList.length ? "none" : "block";

  rBody.querySelectorAll("[data-unreject]").forEach(b => b.addEventListener("click", () => {
    delete rejected[b.dataset.unreject]; save(); render(); renderTracker(); renderCompanies();
  }));
  aBody.querySelectorAll("[data-unapply]").forEach(b => b.addEventListener("click", () => {
    delete applied[b.dataset.unapply]; save(); render(); renderTracker(); renderCompanies();
  }));
}

// -------------------------------------------------------- profile & criteria
function kv(k, v) {
  return `<div class="kv"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`;
}
function tags(list, cls) {
  if (!list || !list.length) return '<span style="color:var(--muted);">\u2014</span>';
  return `<div class="taglist">` +
    list.map(t => `<span class="tag ${cls || ""}">${esc(t)}</span>`).join("") + `</div>`;
}

function renderProfile() {
  const p = PROFILE, c = CRITERIA;
  const loc = c.location || {}, wm = c.work_mode || {}, sen = c.seniority || {};

  document.getElementById("profile-cards").innerHTML = `
    <div class="card">
      <h3>Background</h3>
      ${kv("Name", esc(p.name || "\u2014"))}
      ${kv("Current title", esc(p.current_title || "\u2014"))}
      ${kv("Experience", p.years_experience != null ? esc(p.years_experience) + " years" : "\u2014")}
      ${kv("Headline", esc(p.headline || "\u2014"))}
    </div>
    <div class="card">
      <h3>Tools you work with</h3>
      ${tags((p.skills || {}).in_stack, "yes")}
      <h3 style="margin-top:14px;">Treated as a different discipline</h3>
      ${tags((p.skills || {}).out_of_stack, "no")}
    </div>
    <div class="card">
      <h3>CV variants</h3>
      ${(p.cv_variants || []).length
        ? (p.cv_variants || []).map(v =>
            kv(v.id, esc(v.label || "") + (v.default ? ' <span class="tag">default</span>' : ""))).join("")
        : '<span style="color:var(--muted);">None configured</span>'}
      ${kv("Custom CV below", esc(p.custom_cv_below_score != null ? p.custom_cv_below_score : 55))}
    </div>
    <div class="card">
      <h3>Work authorisation</h3>
      ${kv("Needs sponsorship", p.needs_sponsorship
          ? '<span class="tag no">Yes \u2014 postings that refuse it are dropped</span>'
          : '<span class="tag yes">No</span>')}
    </div>`;

  const role = c.role || {};
  document.getElementById("criteria-cards").innerHTML = `
    <div class="card">
      <h3>Target roles \u2014 title must contain</h3>
      ${tags(role.include, "yes")}
    </div>
    <div class="card">
      <h3>Ruled out</h3>
      ${tags((role.rejected_function_heads || []).concat(role.rejected_head_prefixes || []), "no")}
    </div>
    <div class="card">
      <h3>Seniority</h3>
      ${kv("Years band", esc(sen.tenure_min) + "\u2013" + esc(sen.tenure_max) + " years")}
      ${kv("Sweet spot", esc(sen.tenure_ideal_min) + "\u2013" + esc(sen.tenure_ideal_max) + " years")}
      ${kv("Too senior", tags(sen.too_senior_title, "no"))}
      ${kv("Too junior", tags(sen.too_junior_title, "no"))}
    </div>
    <div class="card">
      <h3>Location &amp; work mode</h3>
      ${kv("Country", esc(loc.country || "US"))}
      ${kv("Scope", loc.mode === "cities"
          ? tags(loc.cities) : esc((loc.country || "US")) + "-wide")}
      ${kv("Accepts", tags(wm.accept, "yes"))}
      ${kv("Remote penalty", wm.remote_penalty ? "\u2212" + esc(wm.remote_penalty) + " pts" : "none")}
      ${kv("Posted within", esc(c.recency_days || 7) + " days")}
    </div>`;

  document.getElementById("gates").innerHTML = `
    <div class="gate"><b>Tenure</b> \u2014 roles demanding fewer than ${esc(sen.tenure_min)} or more than ${esc(sen.tenure_max)} years never reach the table.</div>
    <div class="gate"><b>Sponsorship</b> \u2014 ${p.needs_sponsorship
      ? "postings that explicitly refuse visa sponsorship are dropped."
      : "not applied; you don't need sponsorship."}</div>
    <div class="gate"><b>Location</b> \u2014 outside ${esc(loc.country || "US")}${loc.mode === "cities" ? " or your chosen cities" : ""} is dropped.</div>
    <div class="gate"><b>Freshness</b> \u2014 anything posted more than ${esc(c.recency_days || 7)} days ago drops off automatically.</div>`;

  renderWeights();
}

function renderWeights() {
  const host = document.getElementById("wrows");
  const norm = normWeights(weights);
  host.innerHTML = DIMS.map(d => `
    <div class="wrow">
      <label for="w-${d}" title="${esc(DIM_HELP[d])}">${DIM_LABEL[d]}</label>
      <input type="range" id="w-${d}" data-dim="${d}" min="0" max="60" step="1" value="${weights[d]}" />
      <span class="num">${Math.round(norm[d])}</span>
    </div>`).join("");

  host.querySelectorAll("input[type=range]").forEach(r => r.addEventListener("input", e => {
    weights[e.target.dataset.dim] = Number(e.target.value);
    save(); renderWeights(); render();
  }));

  const dirty = DIMS.some(d => Math.round(normWeights(weights)[d]) !== Math.round(normWeights(SAVED_WEIGHTS)[d]));
  const el = document.getElementById("wtotal");
  el.className = "wtotal" + (dirty ? " dirty" : "");
  el.textContent = dirty
    ? "Edited \u2014 showing live scores. Saved config: " + DIMS.map(d => `${DIM_LABEL[d]} ${Math.round(normWeights(SAVED_WEIGHTS)[d])}`).join(" \u00b7 ")
    : "Matches your saved config.";
}

function renderCompanies() {
  const openCount = {};
  JOBS.forEach(j => {
    if (applied[j.id] || rejected[j.id]) return;
    openCount[j.company] = (openCount[j.company] || 0) + 1;
  });
  const rows = COMPANIES.filter(c => {
    if (state.cfilter !== "all" && c.priority !== state.cfilter) return false;
    if (state.csearch && !c.name.toLowerCase().includes(state.csearch.toLowerCase())) return false;
    return true;
  });
  const tbody = document.getElementById("company-rows");
  tbody.innerHTML = rows.map(c => `<tr class="${c.priority.toLowerCase()}">
    <td><span class="pill ${c.priority.toLowerCase()}">${esc(c.priority)}</span></td>
    <td class="company">${esc(c.name)}</td>
    <td><span class="pill industry">${esc(c.sector)}</span></td>
    <td>${openCount[c.name] ? `<b>${openCount[c.name]}</b>` : '<span style="color:var(--muted);">\u2014</span>'}</td>
    <td style="color:var(--muted);font-size:12.5px;">${esc(c.feed)}</td>
  </tr>`).join("");
  document.getElementById("company-empty").style.display = rows.length ? "none" : "block";
}

// ---------------------------------------------------------------- feedback
function renderFeedback() {
  const note = document.getElementById("fbnote");
  if (FEEDBACK_URL) {
    note.textContent = "Opens a short form in a new tab with your message ready to submit. "
      + "No name, email or job data is attached.";
  } else {
    document.getElementById("fbsend").style.display = "none";
    note.textContent = "No feedback address is configured for this copy yet. "
      + "Use Copy instead, and send it however you like.";
  }
}

// ------------------------------------------------------------------- wiring
document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.setAttribute("aria-selected", String(x === t)));
  const which = t.dataset.tab;
  ["open", "tracker", "profile", "feedback"].forEach(name => {
    document.getElementById("pane-" + name).style.display = which === name ? "" : "none";
  });
}));

document.getElementById("sortsel").addEventListener("change", e => {
  state.sortKey = e.target.value; state.sortDir = "desc";
  document.querySelectorAll("th[data-sort]").forEach(t => t.classList.toggle("sorted", t.dataset.sort === state.sortKey));
  render();
});
document.querySelectorAll("th[data-sort]").forEach(th => th.addEventListener("click", () => {
  const key = th.dataset.sort;
  if (state.sortKey === key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
  else { state.sortKey = key; state.sortDir = "desc"; }
  const sel = document.getElementById("sortsel");
  if ([...sel.options].some(o => o.value === key)) sel.value = key;
  document.querySelectorAll("th[data-sort]").forEach(t => t.classList.toggle("sorted", t === th));
  render();
}));
document.querySelectorAll(".chip[data-filter]").forEach(btn => btn.addEventListener("click", () => {
  state.filter = btn.dataset.filter;
  document.querySelectorAll(".chip[data-filter]").forEach(b => b.setAttribute("aria-pressed", String(b === btn)));
  render();
}));
document.getElementById("search").addEventListener("input", e => { state.search = e.target.value; render(); });

document.querySelectorAll(".chip[data-cfilter]").forEach(btn => btn.addEventListener("click", () => {
  state.cfilter = btn.dataset.cfilter;
  document.querySelectorAll(".chip[data-cfilter]").forEach(b => b.setAttribute("aria-pressed", String(b === btn)));
  renderCompanies();
}));
document.getElementById("csearch").addEventListener("input", e => { state.csearch = e.target.value; renderCompanies(); });

document.getElementById("selall").addEventListener("change", e => {
  visibleIds.forEach(id => e.target.checked ? selected.add(id) : selected.delete(id));
  render();
});
document.getElementById("clearsel").addEventListener("click", () => { selected.clear(); render(); });
document.getElementById("marksel").addEventListener("click", () => {
  const n = selected.size;
  selected.forEach(id => { applied[id] = { at: new Date().toISOString().slice(0, 10) }; delete rejected[id]; });
  selected.clear(); save(); render(); renderTracker(); renderCompanies();
  toast(n + " moved to Application tracker");
});

document.getElementById("wreset").addEventListener("click", () => {
  DIMS.forEach(d => weights[d] = SAVED_WEIGHTS[d]);
  save(); renderWeights(); render();
  toast("Weights reset to your saved config");
});
document.getElementById("wcopy").addEventListener("click", async () => {
  const norm = normWeights(weights);
  const text = "Update my job tracker scoring weights to: "
    + DIMS.map(d => `${DIM_LABEL[d]} ${Math.round(norm[d])}`).join(", ")
    + ". Save them to config/criteria.json and rebuild the dashboard.";
  try { await navigator.clipboard.writeText(text); toast("Copied \u2014 paste it into the Claude chat to save"); }
  catch (e) { toast("Copy blocked \u2014 tell Claude: " + text); }
});

// Browsers block programmatic multi-tab opens, so fire every window.open
// synchronously inside the click gesture (best odds of being allowed) and
// surface whatever got blocked as real anchors the user can click.
document.getElementById("openall").addEventListener("click", () => {
  const panel = document.getElementById("blockpanel");
  const jobs = [...selected].map(id => jobsById[id]).filter(Boolean);
  if (!jobs.length) return;
  const blocked = [];
  jobs.forEach(j => {
    const w = window.open(j.application_link, "_blank", "noopener");
    if (!w || w.closed || typeof w.closed === "undefined") blocked.push(j);
  });
  const opened = jobs.length - blocked.length;
  if (!blocked.length) {
    panel.classList.remove("show");
    panel.innerHTML = "";
    toast(`Opened ${opened} tab${opened === 1 ? "" : "s"}`);
    return;
  }
  panel.classList.add("show");
  panel.innerHTML =
    `<strong>${opened} opened, ${blocked.length} blocked by your browser's popup blocker.</strong>` +
    ` Allow popups for this site to open them all at once, or use these links:` +
    `<ol>` + blocked.map(j =>
      `<li><a href="${esc(j.application_link)}" target="_blank" rel="noopener">${esc(j.company)} \u2014 ${esc(j.title)}</a></li>`
    ).join("") + `</ol>`;
  toast(`${opened} opened \u00b7 ${blocked.length} blocked \u2014 see list below`);
});

document.getElementById("scanbtn").addEventListener("click", async () => {
  const cmd = "Run a full job scan: scrape all sources including the browser passes, merge, rebuild, and republish my job tracker dashboard. Report what changed since the last scan.";
  try { await navigator.clipboard.writeText(cmd); toast("Scan command copied \u2014 paste it into the Claude chat"); }
  catch (e) { toast("Copy blocked \u2014 type \u201cscan\u201d in the Claude chat instead"); }
});

document.getElementById("copybtn").addEventListener("click", async () => {
  const lines = [];
  for (const [id, v] of Object.entries(rejected)) {
    const j = jobsById[id];
    lines.push(`REJECT (${v.reason}) | ${j ? j.company : id} | ${j ? j.title : ""} | ${j ? j.location : ""} | ${j ? j.priority : ""}`);
  }
  for (const [id, v] of Object.entries(applied)) {
    const j = jobsById[id];
    lines.push(`APPLIED ${v.at} | ${j ? j.company : id} | ${j ? j.title : ""}`);
  }
  const text = lines.length ? "Job tracker feedback:\n" + lines.join("\n") : "(no feedback logged yet)";
  const box = document.getElementById("exportbox");
  box.style.display = "block"; box.value = text; box.select();
  try { await navigator.clipboard.writeText(text); toast("Feedback copied \u2014 paste it into the Claude chat"); }
  catch (e) { toast("Select and copy the text below"); }
});

const fbtext = document.getElementById("fbtext");
fbtext.addEventListener("input", () => {
  document.getElementById("fbcount").textContent = fbtext.value.length + " characters";
});
document.getElementById("fbsend").addEventListener("click", () => {
  const msg = fbtext.value.trim();
  if (!msg) { toast("Write something first"); fbtext.focus(); return; }
  // Opening the form as a top-level navigation rather than POSTing from here:
  // the page is served under a strict CSP that blocks cross-origin requests,
  // and a new tab also lets the sender see exactly what is being submitted.
  const sep = FEEDBACK_URL.includes("?") ? "&" : "?";
  const url = FEEDBACK_URL + sep + "usp=pp_url&" + "__FEEDBACK_FIELD__" + "=" + encodeURIComponent(msg);
  const w = window.open(url, "_blank", "noopener");
  if (!w) { toast("Popup blocked \u2014 use Copy instead"); return; }
  toast("Opened the feedback form \u2014 hit submit there to send");
});
document.getElementById("fbcopy").addEventListener("click", async () => {
  const msg = fbtext.value.trim() || "(empty)";
  try { await navigator.clipboard.writeText(msg); toast("Feedback copied to your clipboard"); }
  catch (e) { fbtext.select(); toast("Select and copy the text above"); }
});

render();
renderTracker();
renderProfile();
renderCompanies();
renderFeedback();
</script>
"""

manual_note = ""
notes = []
if static_page:
    notes.append(f"{', '.join(static_page)} posts roles on a static page with email "
                 f"applications (manual check)")
if unresolved:
    notes.append(f"{len(unresolved)} company(s) have no resolved job board yet")
if notes:
    manual_note = "; ".join(notes) + f"; the other {auto_count} are scanned automatically. "

def _role_bits():
    """Short list of role names for the subtitle. Onboarding writes
    profile.target_roles; falling back to the raw include list needs a dedupe,
    since that list deliberately carries near-duplicates ("strategy",
    "strategic", "strategy and operations") to widen title matching."""
    named = profile.get("target_roles")
    if named:
        return named[:6]
    out = []
    for term in criteria.get("role", {}).get("include") or []:
        stem = term.lower()[:6]
        if any(stem == s for s in (t.lower()[:6] for t in out)):
            continue
        out.append(term.title())
        if len(out) == 6:
            break
    return out


loc_cfg = criteria.get("location", {})
sen_cfg = criteria.get("seniority", {})

with open(os.path.join(BASE, "catalog", "location_reference.json")) as f:
    locref = json.load(f)
country = locref.get(loc_cfg.get("country", "US"), locref["US"])
metro = country["metro_buckets"]


def _scope():
    """Human-readable location scope.

    `location.cities` is a MATCHING vocabulary — it carries aliases like "nyc",
    "brooklyn" and "manhattan" so postings phrased any of those ways are caught.
    Title-casing that list verbatim reads as four separate places, so collapse
    it onto the canonical metro names instead. An explicit location.labels wins
    if onboarding wrote one.
    """
    if loc_cfg.get("mode") != "cities":
        return f"{loc_cfg.get('country', 'US')}-wide"
    labels = loc_cfg.get("labels")
    if not labels:
        import re as _re
        labels, seen = [], set()
        for city in loc_cfg.get("cities", []):
            name = next((n for n, pat in metro
                         if _re.search(pat, city, _re.I)), city.title())
            if name not in seen:
                seen.add(name)
                labels.append(name)
    return ", ".join(labels[:4]) + ("…" if len(labels) > 4 else "")


scope = _scope()
# Entity-escaped for the same byte-safety reason as the template glyphs.
subtitle = (" &middot; ".join(_role_bits()) +
            f" &mdash; {sen_cfg.get('tenure_min', 3)}&ndash;{sen_cfg.get('tenure_max', 8)}y, "
            f"{scope}, posted in the last {criteria.get('recency_days', 7)} days")

html = (TEMPLATE
        .replace("__DASH_TITLE__", profile.get("dashboard_title", "Job Tracker"))
        .replace("__DASH_SUBTITLE__", subtitle)
        .replace("__GEN_DISPLAY__", gen_display)
        .replace("__MANUAL_NOTE__", manual_note)
        .replace("__COMPANY_COUNT__", str(len(company_rows)))
        .replace("__FEEDBACK_FIELD__", profile.get("feedback_form_field", "entry.1"))
        .replace("__APPLIED_SEED__", json.dumps(applied_seed))
        .replace("__PROFILE_JSON__", json.dumps(profile))
        .replace("__CRITERIA_JSON__", json.dumps(criteria))
        .replace("__COMPANIES_JSON__", json.dumps(company_rows))
        .replace("__FEEDBACK_URL__", json.dumps(feedback_url))
        .replace("__METRO_BUCKETS__", json.dumps(metro))
        .replace("__JOBS_JSON__", json.dumps(jobs)))

out_dir = os.path.join(BASE, "dashboard")
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "index.html"), "w") as f:
    f.write(html)

print(f"Wrote dashboard/index.html with {len(jobs)} jobs, "
      f"{len(company_rows)} companies, 4 tabs")
