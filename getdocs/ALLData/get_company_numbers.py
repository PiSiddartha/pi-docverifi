import os
import requests
import time
import csv

API_KEY = "44406fbf-34e8-4ec6-88cf-3ae2bde25d7f"
OUTFILE = "company_numbers.txt"

if not API_KEY:
    raise SystemExit("ERROR: Set COMPANIES_HOUSE_API_KEY first!")

session = requests.Session()
session.auth = (API_KEY, "")

def search_chunk(query, start_index=0, items=100):
    url = "https://api.companieshouse.gov.uk/search/companies"
    params = {
        "q": query,
        "start_index": start_index,
        "items_per_page": items
    }
    resp = session.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def main():
    print("Fetching company numbers...")
    all_numbers = set()
    queries = ["a", "e", "i", "o", "u"]  # broad queries return many companies

    for q in queries:
        for page in range(0, 100):   # ~100 pages per query → ~10,000 companies
            try:
                data = search_chunk(q, start_index=page * 100)
            except Exception as e:
                print(f"Error on '{q}' page {page}: {e}")
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                num = item.get("company_number")
                if num:
                    all_numbers.add(num)

            time.sleep(0.2)

    print(f"Collected {len(all_numbers)} company numbers.")
    with open(OUTFILE, "w") as f:
        for num in sorted(all_numbers):
            f.write(num + "\n")

    print(f"Saved to {OUTFILE}")

if __name__ == "__main__":
    main()
