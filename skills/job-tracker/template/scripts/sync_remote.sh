#!/bin/zsh
# Push the tracker's data and config to a private git remote so other tools
# (a scoring task, an applications tracker) can read the latest scan without
# touching this machine. Optional: nothing else in the pipeline depends on it.
#
# One-time setup, from ~/job-tracker:
#   git init && git remote add origin <your PRIVATE repo url>
# Then run this after every scan:  zsh scripts/sync_remote.sh
set -e
cd "$(dirname "$0")/.."
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repo. From $(pwd): git init && git remote add origin <private repo url>"; exit 1
fi
git add data/jobs.json data/applied.json data/rejected.json data/companies.json config/profile.json config/criteria.json 2>/dev/null || true
if git diff --cached --quiet; then echo "Nothing new to sync."; exit 0; fi
git commit -qm "scan $(date -u +%Y-%m-%dT%H:%MZ)"
branch=$(git rev-parse --abbrev-ref HEAD)
git pull -q --rebase origin "$branch" 2>/dev/null || true
git push -q -u origin "$branch"
echo "Synced data to origin/$branch"
