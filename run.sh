#!/usr/bin/env bash
# Alberta Referendum 2026 - Local Runner
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=============================================="
echo " Alberta Referendum 2026 Live Scraper & Server"
echo "=============================================="

usage() {
  echo "Usage: $0 [scrape|loop|serve|all]"
  echo "  scrape : Run scraper once"
  echo "  loop   : Run scraper daemon (every 30s)"
  echo "  serve  : Start local dashboard web server on port 8000"
  echo "  all    : Start scraper daemon and web server simultaneously"
  exit 1
}

MODE="${1:-serve}"

case "$MODE" in
  scrape)
    python3 scraper.py --once
    ;;
  loop)
    python3 scraper.py --loop --interval 30
    ;;
  serve)
    echo "Starting local web server at http://localhost:8000"
    python3 -m http.server 8000
    ;;
  all)
    echo "Starting scraper daemon in background..."
    python3 scraper.py --loop --interval 30 &
    SCRAPER_PID=$!
    trap "kill $SCRAPER_PID 2>/dev/null || true" EXIT
    echo "Starting local web server at http://localhost:8000"
    python3 -m http.server 8000
    ;;
  *)
    usage
    ;;
esac
