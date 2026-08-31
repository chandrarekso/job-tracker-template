#!/bin/zsh
# Full scan pipeline. The browser pass for bot-blocked companies is driven by
# Claude separately and must run BEFORE this, since ingest_browser.py reads the
# file it writes.
set -e
cd "$(dirname "$0")"
python3 scripts/scrape_ats.py
python3 scripts/scrape_custom.py
python3 scripts/ingest_browser.py
python3 scripts/merge_jobs.py
python3 scripts/build_dashboard.py
