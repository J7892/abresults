#!/usr/bin/env python3
"""
Alberta Referendum 2026 Results Scraper
Periodically fetches real-time voting data from Elections Alberta (https://results.elections.ab.ca/8400)
and produces structured JSON, historical time-series logs, and CSV exports for the web dashboard.
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests

# Base directory is the repository directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
METADATA_FILE = os.path.join(BASE_DIR, "metadata.json")

EAB_DATA_URL = "https://results.elections.ab.ca/data/8400"
API_VERSION = "3.0.0"
QUESTION_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11]

# Short question titles for compact display and CSVs
QUESTION_SHORT_TITLES = {
    1: "Immigration Control & Alberta Priority",
    2: "Citizenship/PR Requirement for Provincial Services",
    3: "12-Month Residency Rule for Non-Permanent Support",
    4: "Healthcare & Education Fees for Non-Permanent Residents",
    5: "Proof of Citizenship to Vote in Provincial Elections",
    6: "Provincial Selection of King's Bench & Appeal Judges",
    7: "Abolition of the Federal Senate",
    8: "Provincial Opt-Out of Federal Programs with Full Funding",
    9: "Provincial Law Priority in Shared Constitutional Areas",
    11: "Alberta Independence / Separation Referendum Process"
}

QUESTION_NUMBERS = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 11: 10
}

# Regional classification by ward code
def get_region(ward_code: str) -> str:
    try:
        num = int(ward_code)
        if 1 <= num <= 26:
            return "Calgary"
        elif 27 <= num <= 46:
            return "Edmonton"
        else:
            return "Regional / Other"
    except ValueError:
        return "Other"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("abresults")

def load_metadata():
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not read metadata.json: {e}")
    return {"questions": [], "wards": []}

METADATA = load_metadata()
WARD_LOOKUP = {w["ward"]: w["wardName"] for w in METADATA.get("wards", [])}

def fetch_api_data(questions=None, wards=None, timeout=15):
    """
    Fetches raw JSON from Elections Alberta API with robust headers and retry mechanism.
    """
    params = {
        "version": API_VERSION
    }
    if questions:
        params["questions"] = ",".join(str(q) for q in questions)
    else:
        params["questions"] = ",".join(str(q) for q in QUESTION_IDS)
        
    if wards:
        params["wards"] = ",".join(str(w) for w in wards)

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://results.elections.ab.ca/8400",
        "DNT": "1"
    }

    session = requests.Session()
    for attempt in range(1, 4):
        try:
            resp = session.get(EAB_DATA_URL, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return data
                else:
                    logger.warning(f"API returned success=false on attempt {attempt}")
            else:
                logger.warning(f"HTTP {resp.status_code} on attempt {attempt}")
        except Exception as e:
            logger.warning(f"Request failed (attempt {attempt}/3): {e}")
        time.sleep(2 * attempt)

    return None

def process_results(raw_data):
    """
    Parses and transforms raw API data into an enriched data structure.
    """
    ref_results = raw_data.get("referendumResults", {})
    widgets = ref_results.get("widgets", {})
    summary = widgets.get("summary", {})
    advance = widgets.get("advance", {})
    voting_day = widgets.get("votingDay", {})
    vbm = widgets.get("vbm", {})
    mobile = widgets.get("mobile", {})

    last_updated_iso = raw_data.get("lastUpdated")
    
    # Mountain Time conversion
    mt_formatted = "N/A"
    if last_updated_iso:
        try:
            dt = datetime.fromisoformat(last_updated_iso.replace("Z", "+00:00"))
            dt_mt = dt.astimezone(ZoneInfo("America/Edmonton"))
            mt_formatted = dt_mt.strftime("%b %d, %Y %I:%M:%S %p %Z")
        except Exception:
            mt_formatted = str(last_updated_iso)

    total_polls = summary.get("totalPolls", 5595) or 5595
    polls_reporting = summary.get("pollsReporting", 0) or 0
    polls_pct = round((polls_reporting / total_polls * 100), 2) if total_polls > 0 else 0.0

    # Build lookup for ward reporting status
    ward_poll_status = {}
    for w in ref_results.get("wards", []):
        w_code = w.get("ward")
        ward_poll_status[w_code] = {
            "pollsReporting": w.get("pollsReporting", 0) or 0,
            "totalPolls": w.get("totalPolls", 0) or 0
        }

    # Process each question
    question_stats_raw = ref_results.get("votes", {}).get("questionStats", [])
    processed_questions = []

    for q_item in question_stats_raw:
        q_id = q_item.get("questionID")
        q_num = QUESTION_NUMBERS.get(q_id, q_id)
        short_title = QUESTION_SHORT_TITLES.get(q_id, f"Question {q_num}")
        
        # Find matching full question text
        full_text = ""
        for mq in METADATA.get("questions", []):
            if mq.get("questionID") == q_id:
                full_text = mq.get("questionText", "")
                break

        yes_votes = q_item.get("yesVotes", 0) or 0
        no_votes = q_item.get("noVotes", 0) or 0
        total_votes = yes_votes + no_votes

        yes_pct = round((yes_votes / total_votes * 100), 2) if total_votes > 0 else 0.0
        no_pct = round((no_votes / total_votes * 100), 2) if total_votes > 0 else 0.0
        margin = yes_votes - no_votes
        margin_pct = round(yes_pct - no_pct, 2) if total_votes > 0 else 0.0

        if total_votes == 0:
            leader = "Awaiting Results"
        elif yes_votes > no_votes:
            leader = "YES"
        elif no_votes > yes_votes:
            leader = "NO"
        else:
            leader = "TIED"

        # Regional aggregation
        regional_stats = {
            "Calgary": {"yes": 0, "no": 0, "total": 0, "wards": 0},
            "Edmonton": {"yes": 0, "no": 0, "total": 0, "wards": 0},
            "Regional / Other": {"yes": 0, "no": 0, "total": 0, "wards": 0}
        }

        # Ward-by-ward breakdown
        ward_list = []
        for ws in q_item.get("wardStats", []):
            w_code = ws.get("ward")
            w_name = WARD_LOOKUP.get(w_code, f"Riding {w_code}")
            w_region = get_region(w_code)
            
            w_yes = ws.get("yesVotes")
            w_no = ws.get("noVotes")
            w_yes_val = w_yes or 0
            w_no_val = w_no or 0
            w_tot_val = w_yes_val + w_no_val

            w_yes_pct = round((w_yes_val / w_tot_val * 100), 2) if w_tot_val > 0 else 0.0
            w_no_pct = round((w_no_val / w_tot_val * 100), 2) if w_tot_val > 0 else 0.0

            p_info = ward_poll_status.get(w_code, {"pollsReporting": 0, "totalPolls": 0})
            w_polls_rep = p_info["pollsReporting"]
            w_polls_tot = p_info["totalPolls"]
            w_polls_pct = round((w_polls_rep / w_polls_tot * 100), 1) if w_polls_tot > 0 else 0.0

            if w_tot_val == 0:
                w_leader = "Awaiting"
            elif w_yes_val > w_no_val:
                w_leader = "YES"
            elif w_no_val > w_yes_val:
                w_leader = "NO"
            else:
                w_leader = "TIED"

            # Accumulate regional totals
            if w_region in regional_stats:
                regional_stats[w_region]["yes"] += w_yes_val
                regional_stats[w_region]["no"] += w_no_val
                regional_stats[w_region]["total"] += w_tot_val
                regional_stats[w_region]["wards"] += 1

            ward_list.append({
                "ward": w_code,
                "wardName": w_name,
                "region": w_region,
                "yesVotes": w_yes,
                "noVotes": w_no,
                "totalVotes": w_tot_val if (w_yes is not None or w_no is not None) else None,
                "yesPct": w_yes_pct,
                "noPct": w_no_pct,
                "marginVotes": (w_yes_val - w_no_val) if w_tot_val > 0 else 0,
                "marginPct": round(w_yes_pct - w_no_pct, 2) if w_tot_val > 0 else 0.0,
                "leader": w_leader,
                "pollsReporting": w_polls_rep,
                "totalPolls": w_polls_tot,
                "pollsPct": w_polls_pct
            })

        # Calculate regional percentages
        for reg_name, reg_data in regional_stats.items():
            tot = reg_data["total"]
            reg_data["yesPct"] = round(reg_data["yes"] / tot * 100, 2) if tot > 0 else 0.0
            reg_data["noPct"] = round(reg_data["no"] / tot * 100, 2) if tot > 0 else 0.0

        processed_questions.append({
            "questionID": q_id,
            "questionNumber": q_num,
            "title": short_title,
            "questionText": full_text,
            "yesVotes": yes_votes,
            "noVotes": no_votes,
            "totalVotes": total_votes,
            "yesPct": yes_pct,
            "noPct": no_pct,
            "marginVotes": margin,
            "marginPct": margin_pct,
            "leader": leader,
            "regionalStats": regional_stats,
            "wards": ward_list
        })

    # Sort questions by question number
    processed_questions.sort(key=lambda x: x["questionNumber"])

    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "lastUpdatedEAB": last_updated_iso,
        "lastUpdatedMountain": mt_formatted,
        "turnout": {
            "summary": {
                "votes": summary.get("votes", 0) or 0,
                "valid": summary.get("valid", 0) or 0,
                "pollsReporting": polls_reporting,
                "totalPolls": total_polls,
                "pollsReportingPct": polls_pct
            },
            "advance": advance,
            "votingDay": voting_day,
            "vbm": vbm,
            "mobile": mobile
        },
        "questions": processed_questions
    }

def save_data(enriched):
    """
    Saves latest.json, appends to history.jsonl, and updates CSV exports.
    Returns True if data changed, False otherwise.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    latest_path = os.path.join(DATA_DIR, "latest.json")
    history_path = os.path.join(DATA_DIR, "history.jsonl")
    summary_csv_path = os.path.join(DATA_DIR, "referendum_summary.csv")
    ridings_csv_path = os.path.join(DATA_DIR, "riding_results.csv")

    # Check if data actually changed compared to existing latest.json
    if os.path.exists(latest_path):
        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                prev = json.load(f)
            prev_sum = prev.get("turnout", {}).get("summary", {})
            curr_sum = enriched.get("turnout", {}).get("summary", {})
            if (prev.get("lastUpdatedEAB") == enriched.get("lastUpdatedEAB") and
                prev_sum.get("votes") == curr_sum.get("votes") and
                prev_sum.get("pollsReporting") == curr_sum.get("pollsReporting")):
                logger.info("No vote changes from Elections Alberta; data unchanged.")
                return False
        except Exception as e:
            logger.debug(f"Error checking previous latest.json: {e}")

    # 1. Save latest.json
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2)

    # 2. Append concise history line
    hist_record = {
        "timestamp": enriched["fetchedAt"],
        "eabTimestamp": enriched["lastUpdatedEAB"],
        "pollsReporting": enriched["turnout"]["summary"]["pollsReporting"],
        "totalPolls": enriched["turnout"]["summary"]["totalPolls"],
        "totalVotes": enriched["turnout"]["summary"]["votes"],
        "questions": {
            f"Q{q['questionNumber']}": {
                "id": q["questionID"],
                "yes": q["yesVotes"],
                "no": q["noVotes"],
                "yesPct": q["yesPct"],
                "noPct": q["noPct"],
                "leader": q["leader"]
            }
            for q in enriched["questions"]
        }
    }

    # Only append if different from last recorded line
    should_append = True
    if os.path.exists(history_path):
        try:
            with open(history_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size > 0:
                    # Read last line
                    f.seek(max(0, size - 2048))
                    lines = f.read().decode("utf-8", errors="ignore").strip().splitlines()
                    if lines:
                        last_line_obj = json.loads(lines[-1])
                        if (last_line_obj.get("eabTimestamp") == hist_record["eabTimestamp"] and
                            last_line_obj.get("totalVotes") == hist_record["totalVotes"] and
                            last_line_obj.get("pollsReporting") == hist_record["pollsReporting"]):
                            should_append = False
        except Exception as e:
            logger.debug(f"History deduplication check error: {e}")

    if should_append:
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(hist_record) + "\n")
        logger.info(f"Appended snapshot to {history_path}")
    else:
        logger.debug("Data unchanged; skipped duplicate history record.")

    # 3. Export referendum_summary.csv
    try:
        with open(summary_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Question Number", "Question ID", "Short Title", "Leader",
                "Yes Votes", "No Votes", "Total Votes", "Yes %", "No %", "Margin (Votes)", "Margin %",
                "Calgary Yes %", "Calgary Total", "Edmonton Yes %", "Edmonton Total", "Other Yes %", "Other Total"
            ])
            for q in enriched["questions"]:
                reg = q.get("regionalStats", {})
                calg = reg.get("Calgary", {})
                edm = reg.get("Edmonton", {})
                oth = reg.get("Regional / Other", {})
                writer.writerow([
                    q["questionNumber"],
                    q["questionID"],
                    q["title"],
                    q["leader"],
                    q["yesVotes"],
                    q["noVotes"],
                    q["totalVotes"],
                    q["yesPct"],
                    q["noPct"],
                    q["marginVotes"],
                    q["marginPct"],
                    calg.get("yesPct", 0.0),
                    calg.get("total", 0),
                    edm.get("yesPct", 0.0),
                    edm.get("total", 0),
                    oth.get("yesPct", 0.0),
                    oth.get("total", 0)
                ])
    except Exception as e:
        logger.error(f"Error writing summary CSV: {e}")

    # 4. Export riding_results.csv
    try:
        with open(ridings_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Ward Code", "Ward Name", "Region", "Question Number", "Question Title",
                "Yes Votes", "No Votes", "Total Votes", "Yes %", "No %", "Leader",
                "Polls Reporting", "Total Polls", "Polls Reporting %"
            ])
            for q in enriched["questions"]:
                for w in q.get("wards", []):
                    writer.writerow([
                        w["ward"],
                        w["wardName"],
                        w["region"],
                        q["questionNumber"],
                        q["title"],
                        w["yesVotes"] if w["yesVotes"] is not None else "",
                        w["noVotes"] if w["noVotes"] is not None else "",
                        w["totalVotes"] if w["totalVotes"] is not None else "",
                        w["yesPct"],
                        w["noPct"],
                        w["leader"],
                        w["pollsReporting"],
                        w["totalPolls"],
                        w["pollsPct"]
                    ])
    except Exception as e:
        logger.error(f"Error writing ridings CSV: {e}")

    logger.info(f"Saved latest data. Polls: {enriched['turnout']['summary']['pollsReporting']}/{enriched['turnout']['summary']['totalPolls']}, Votes: {enriched['turnout']['summary']['votes']}")
    return True

def run_once():
    logger.info("Fetching referendum data from Elections Alberta...")
    raw = fetch_api_data()
    if not raw:
        logger.error("Failed to fetch data from Elections Alberta.")
        return False
    enriched = process_results(raw)
    return save_data(enriched)

def main():
    parser = argparse.ArgumentParser(description="Alberta Referendum 2026 Results Scraper")
    parser.add_argument("--loop", action="store_true", help="Run continuously in a loop")
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds (default: 30)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (default behaviour)")
    args = parser.parse_args()

    if args.loop:
        logger.info(f"Starting continuous polling loop every {args.interval}s (Press Ctrl+C to stop)...")
        while True:
            try:
                run_once()
            except Exception as e:
                logger.exception(f"Unhandled error during scrape cycle: {e}")
            time.sleep(args.interval)
    else:
        success = run_once()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
