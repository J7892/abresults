# Alberta Referendum 2026 Results Tracker & Dashboard

Real-time scraper, data pipeline, and interactive web dashboard for the **2026 Alberta Referendum** results from Elections Alberta ([results.elections.ab.ca/8400](https://results.elections.ab.ca/8400)).

---

## Features

- **Automated Real-Time Scraper (`scraper.py`)**:
  - Pulls live unofficial returns directly from the Elections Alberta REST API.
  - Covers all **10 Referendum Questions** and all **87 Electoral Divisions (Wards)** across Alberta.
  - Computes voter turnout, poll reporting percentages, advance vs. election day counts, margins, and regional aggregations (Calgary vs. Edmonton vs. Regional/Rural).
  - Maintains deduplicated time-series history (`data/history.jsonl`) to track vote velocity and momentum shifts.
  - Exports clean CSVs for spreadsheet analysis (`referendum_summary.csv` and `riding_results.csv`).

- **Interactive Web Dashboard (`index.html`)**:
  - **Live Overview Bar**: Real-time ticker of polls reporting (`X / 5,595`), total valid votes, and voting channels (Advance, Election Day, Mail/VBM).
  - **Question 10 Spotlight**: Dedicated banner tracking the Alberta independence / constitutional separation question.
  - **Referendum Scoreboard**: All 10 questions with live Yes/No percentages, margins, and visual progress bars.
  - **Regional Analysis**: Calgary (26 ridings) vs Edmonton (20 ridings) vs Regional/Rural (41 ridings) comparison chart.
  - **Riding Explorer Table**: Filterable by region and outcome, searchable by name/code, sortable by Yes %, No %, Margin, Turnout, or Code.
  - **Auto-Refresh**: Live updates in browser with countdown timer and manual refresh button.

- **Optional GitHub Actions Automation (`workflows-sample/scrape.yml`)**:
  - Sample workflow to automatically run every 5 minutes on election night and push updated data snapshots to the repository (requires the `workflow` scope on your GitHub token if pushed to `.github/workflows/`).

---

## Directory Structure

```
├── .github/workflows/
│   └── scrape.yml               # Automated GitHub Actions scraper
├── data/
│   ├── latest.json              # Current snapshot for the dashboard
│   ├── history.jsonl            # Time-series log of vote updates
│   ├── referendum_summary.csv   # Question-by-question summary CSV
│   └── riding_results.csv       # 87 ridings breakdown CSV
├── index.html                   # Interactive web dashboard
├── metadata.json                # Questions text & riding definitions
├── requirements.txt             # Python dependencies
├── run.sh                       # Quick runner helper
└── scraper.py                   # Main Python scraper & ETL pipeline
```

---

## Quick Start

### 1. Run Scraper Once
```bash
python3 scraper.py
# or
./run.sh scrape
```

### 2. Run Scraper in Continuous Loop (Daemon Mode)
```bash
python3 scraper.py --loop --interval 30
# or
./run.sh loop
```

### 3. Launch Local Dashboard Web Server
```bash
./run.sh serve
# Open http://localhost:8000 in your browser
```

### 4. Run Both Scraper Daemon & Web Server Together
```bash
./run.sh all
```

---

## The 10 Referendum Questions Tracked

1. **Immigration Control & Alberta Priority**
2. **Citizenship/PR Requirement for Provincial Services**
3. **12-Month Residency Rule for Non-Permanent Support**
4. **Healthcare & Education Fees for Non-Permanent Residents**
5. **Proof of Citizenship to Vote in Provincial Elections**
6. **Provincial Selection of King's Bench & Appeal Judges**
7. **Abolition of the Federal Senate**
8. **Provincial Opt-Out of Federal Programs with Full Funding**
9. **Provincial Law Priority in Shared Constitutional Areas**
10. **Alberta Independence / Separation Referendum Process** (Option 1 Remain vs Option 2 Separate)
