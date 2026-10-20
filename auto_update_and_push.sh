#!/usr/bin/env bash
# Auto-scraper and GitHub updater daemon
# Periodically fetches new results from Elections Alberta and pushes updates to GitHub Pages.

INTERVAL=${1:-60}
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "Starting Alberta Referendum Auto-Updater daemon (interval: ${INTERVAL}s)..."
echo "Live dashboard: https://j7892.github.io/abresults/"

while true; do
  python3 scraper.py --once
  
  # Check if data files changed
  if [ -n "$(git status --porcelain data/)" ]; then
    echo "New results detected. Committing and pushing to GitHub..."
    git add data/
    TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    git commit -m "Auto-update referendum returns: $TIMESTAMP"
    git push origin main
    echo "Pushed to GitHub. GitHub Pages will refresh automatically."
  else
    echo "No changes in returns since last check."
  fi

  sleep "$INTERVAL"
done
