#!/usr/bin/env python3
"""
Downloads 2021 Census of Canada PED profiles from Open Alberta CKAN API,
extracts key demographic indicators for each of Alberta's 87 Provincial Electoral Divisions,
and merges them with Election Alberta riding codes.
"""

import json
import logging
import os
import re
import urllib.request
import io
import concurrent.futures
import csv
import pypdf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
METADATA_FILE = os.path.join(BASE_DIR, "metadata.json")

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("census_extractor")

CKAN_API_URL = 'https://open.alberta.ca/api/3/action/package_search?q=tags:"provincial+electoral+divisions"+AND+tags:"2021+Census+of+Canada"&rows=100'

def load_metadata_wards():
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        meta = json.load(f)
    lookup = {}
    for w in meta.get("wards", []):
        ward_code = w["ward"]
        # e.g., "01 - Calgary-Acadia" -> "Calgary-Acadia"
        ward_name = w["wardName"].split(" - ", 1)[1].strip()
        lookup[ward_name.lower()] = {
            "ward": ward_code,
            "wardName": w["wardName"],
            "cleanName": ward_name
        }
    return lookup

NAME_ALIASES = {
    "calgary-mccall": "calgary-bhullar-mccall",
    "livingstone - macleod": "livingstone-macleod"
}

def clean_title(title):
    # e.g. "Alberta provincial electoral divisions : Leduc-Beaumont. Compiled from the 2021 Census of Canada"
    if ":" in title:
        part = title.split(":", 1)[1]
    else:
        part = title
    if "compiled from" in part.lower():
        part = re.split(r'compiled from', part, flags=re.IGNORECASE)[0]
    cleaned = part.strip().strip(".").strip()
    return cleaned

def fetch_packages():
    logger.info("Querying Open Alberta CKAN API...")
    req = urllib.request.Request(CKAN_API_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    
    results = data.get("result", {}).get("results", [])
    logger.info(f"Retrieved {len(results)} packages from Open Alberta.")
    return results

def extract_pdf_data(item):
    name = item["name"]
    url = item["url"]
    ward_info = item.get("ward_info")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            pdf_bytes = resp.read()
        
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        full_text = "\n".join([page.extract_text() for page in reader.pages])

        # 1. Population
        pop_m = re.search(r'Total population\(1\)\s*([0-9,]+)', full_text)
        pop = int(pop_m.group(1).replace(",", "")) if pop_m else None

        # 2. Average Age
        age_m = re.search(r'Average age \(years\)\s*([0-9\.]+)', full_text)
        avg_age = float(age_m.group(1)) if age_m else None

        # 3. Immigrant %
        imm_m = re.search(r'Immigrant population[^\n]*?([0-9\.]+)%', full_text)
        imm_pct = float(imm_m.group(1)) if imm_m else None

        # 4. Visible Minority %
        vis_m = re.search(r'Visible minority population\s*[0-9,]+\s*([0-9\.]+)%', full_text)
        vis_pct = float(vis_m.group(1)) if vis_m else None

        # 5. Bachelor's Degree or Higher %
        bach_m = re.search(r'Bachelor[’\']s degree or higher\s*[0-9,]+\s*([0-9\.]+)%', full_text)
        bach_pct = float(bach_m.group(1)) if bach_m else None

        # 6. Homeownership %
        owner_m = re.search(r'Owner\s*[0-9,]+\s*([0-9\.]+)%', full_text)
        owner_pct = float(owner_m.group(1)) if owner_m else None

        # 7. Median Household Income ($)
        med_inc = None
        for line in full_text.splitlines():
            if "median household income" in line.lower():
                parts = line.split("$")
                if len(parts) >= 2:
                    raw_val = parts[-1].strip().replace(",", "")
                    m_val = re.search(r'([0-9]+)', raw_val)
                    if m_val:
                        med_inc = int(m_val.group(1))
                        break

        # 8. Oil & Gas / Resources Extraction %
        oil_m = re.search(r'Mining, quarrying, and oil and gas extraction\s*[0-9,]+\s*([0-9\.]+)%', full_text)
        oil_pct = float(oil_m.group(1)) if oil_m else None

        return {
            "ward": ward_info["ward"] if ward_info else None,
            "wardName": ward_info["wardName"] if ward_info else name,
            "name": name,
            "population": pop,
            "avgAge": avg_age,
            "immigrantPct": imm_pct,
            "visibleMinorityPct": vis_pct,
            "bachelorDegreePct": bach_pct,
            "homeownershipPct": owner_pct,
            "medianHouseholdIncome": med_inc,
            "oilAndGasPct": oil_pct
        }
    except Exception as e:
        logger.error(f"Error parsing PDF for {name}: {e}")
        return None

def main():
    wards_lookup = load_metadata_wards()
    packages = fetch_packages()

    items_to_download = []
    for p in packages:
        title = p.get("title", "")
        clean = clean_title(title)
        
        # Skip province-wide summary
        if clean.lower() == "alberta":
            continue

        resources = p.get("resources", [])
        pdf_res = next((r for r in resources if r.get("format", "").upper() == "PDF"), None)
        if not pdf_res:
            continue

        key = clean.lower()
        if key in NAME_ALIASES:
            key = NAME_ALIASES[key]

        ward_info = wards_lookup.get(key)
        if not ward_info:
            logger.warning(f"Could not map '{clean}' (key: '{key}') to metadata ward.")
        
        items_to_download.append({
            "name": clean,
            "url": pdf_res["url"],
            "ward_info": ward_info
        })

    logger.info(f"Downloading and extracting demographic data for {len(items_to_download)} ridings in parallel...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(extract_pdf_data, item): item for item in items_to_download}
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            if res:
                results.append(res)

    # Sort by ward code
    results.sort(key=lambda x: x["ward"] or "99")

    logger.info(f"Successfully extracted demographics for {len(results)} ridings.")

    # Save to JSON
    os.makedirs(DATA_DIR, exist_ok=True)
    json_path = os.path.join(DATA_DIR, "riding_demographics.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved {json_path}")

    # Save to CSV
    csv_path = os.path.join(DATA_DIR, "riding_demographics.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Ward Code", "Ward Name", "2021 Population", "Average Age",
            "Immigrant %", "Visible Minority %", "Bachelor Degree or Higher %",
            "Homeownership %", "Median Household Income ($)", "Oil & Gas Employment %"
        ])
        for r in results:
            writer.writerow([
                r["ward"],
                r["wardName"],
                r["population"],
                r["avgAge"],
                r["immigrantPct"],
                r["visibleMinorityPct"],
                r["bachelorDegreePct"],
                r["homeownershipPct"],
                r["medianHouseholdIncome"],
                r["oilAndGasPct"]
            ])
    logger.info(f"Saved {csv_path}")

if __name__ == "__main__":
    main()
