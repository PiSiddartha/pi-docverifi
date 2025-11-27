#!/usr/bin/env python3
"""
get_recent_companies_v2.py

More robust approach to collect recently incorporated companies:
- Runs multiple simple queries (vowels) and pages through results
- Filters returned items by date_of_creation (client-side)
- Writes recent_company_numbers.txt and creates recent_companies/ folder

Usage:
  export COMPANIES_HOUSE_API_KEY="your_key_here"
  python3 get_recent_companies_v2.py
"""

from datetime import date, datetime, timedelta
import os, time, sys, json
import requests

# ------------- CONFIG -------------
API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY") or "YOUR_API_KEY_HERE"

# desired date window (inclusive)
INCORPORATED_FROM = (date.today() - timedelta(days=365)).isoformat()  # e.g., last 365 days
INCORPORATED_TO = date.today().isoformat()

TARGET_COUNT = 1000         # how many company numbers to collect
ITEMS_PER_PAGE = 100        # API page size (max 100)
OUTPUT_FILE = "recent_company_numbers.txt"
OUTPUT_DIR = "recent_companies"
SLEEP_BETWEEN_CALLS = 0.15
# queries to run; vowels cover a broad slice of companies
QUERIES = ["a", "e", "i", "o", "u"]
# ----------------------------------

if API_KEY in (None, "", "YOUR_API_KEY_HERE"):
    print("ERROR: set COMPANIES_HOUSE_API_KEY environment variable to a valid key")
    sys.exit(1)

session = requests.Session()
session.auth = (API_KEY, "")
session.headers.update({"User-Agent": "get-recent-companies-v2/1.0"})

def fetch_search(q, start_index=0):
    url = "https://api.companieshouse.gov.uk/search/companies"
    params = {
        "q": q,
        "start_index": start_index,
        "items_per_page": ITEMS_PER_PAGE
    }
    resp = session.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()

def iso_in_range(dt_str, start_iso, end_iso):
    # date_of_creation may be "YYYY-MM-DD" or "YYYY-MM" etc. handle gracefully
    try:
        # try full parse
        dt = datetime.fromisoformat(dt_str)
    except Exception:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
        except Exception:
            # try partial year-month
            try:
                dt = datetime.strptime(dt_str[:7], "%Y-%m")
            except Exception:
                return False
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return start <= dt <= end

def collect_recent_companies(target):
    collected = []
    seen = set()
    samples = []
    for q in QUERIES:
        start_index = 0
        while len(collected) < target:
            try:
                data = fetch_search(q, start_index=start_index)
            except Exception as e:
                print(f"Error fetching query='{q}' start_index={start_index}: {e}")
                break
            items = data.get("items", [])
            if not items:
                break
            for it in items:
                # item fields: company_number, title, date_of_creation (often)
                num = it.get("company_number")
                dt = it.get("date_of_creation") or it.get("date_of_creation") or it.get("date")
                if not num:
                    continue
                if num in seen:
                    continue
                if dt and iso_in_range(dt, INCORPORATED_FROM, INCORPORATED_TO):
                    collected.append(num)
                    seen.add(num)
                    if len(samples) < 20:
                        samples.append({"company_number": num, "title": it.get("title"), "date_of_creation": dt})
                    if len(collected) >= target:
                        break
            print(f"query='{q}': collected {len(collected)} / {target} (start_index={start_index})")
            # next page
            start_index += ITEMS_PER_PAGE
            time.sleep(SLEEP_BETWEEN_CALLS)
        if len(collected) >= target:
            break
    return collected, samples

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def main():
    print("Uploaded file path (for reference): /mnt/data/Screenshot 2025-11-25 at 6.46.50 AM.png")
    ensure_dir(OUTPUT_DIR)
    print(f"Collecting companies incorporated between {INCORPORATED_FROM} and {INCORPORATED_TO} ...")
    nums, samples = collect_recent_companies(TARGET_COUNT)
    if not nums:
        print("No companies collected. Try expanding date range or increasing queries (e.g., include digits or two-letter queries).")
        return
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for n in nums:
            f.write(n + "\n")
    print(f"Wrote {len(nums)} company numbers to {OUTPUT_FILE}")
    # save sample JSON for inspection
    with open("recent_samples.json", "w", encoding="utf-8") as sf:
        json.dump(samples, sf, indent=2)
    print(f"Wrote sample info to recent_samples.json")
    print(f"Created output dir: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
