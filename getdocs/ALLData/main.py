#!/usr/bin/env python3
"""
main.py - Companies House downloader with per-type caps and XHTML->PDF conversion

Usage:
  export COMPANIES_HOUSE_API_KEY="your_key_here"
  python3 main.py

Requirements (recommended):
  pip install requests python-dotenv weasyprint pdfkit

If using pdfkit fallback, install wkhtmltopdf on your system:
  macOS: brew install wkhtmltopdf
  Ubuntu: sudo apt install wkhtmltopdf

Place company numbers (one per line) in company_numbers.txt
"""

from dotenv import load_dotenv
load_dotenv()

import os
import re
import csv
import sys
import time
import logging
import requests
from typing import List, Dict, Optional
from requests.exceptions import HTTPError, ConnectionError, Timeout

# ---------- Configuration ----------
API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY") or "YOUR_API_KEY_HERE"
OUTPUT_DIR = "companies_house_pdfs"
MANIFEST_FILE = "manifest.csv"
COMPANY_NUMBERS_FILE = "company_numbers.txt"

# Filter: only download filings with these types (case-sensitive)
FILING_TYPE_FILTER = ["IN01", "CS01", "NEWINC"]  # Edit as required

# Per-type caps mapping (0 = unlimited). Example: 100 each.
PER_TYPE_CAPS: Dict[str, int] = {
    "IN01": 100,
    "CS01": 100,
    "NEWINC": 100
}

# Global cap across all types (0 = unlimited)
GLOBAL_CAP = 0

# Other config
REQUESTS_TIMEOUT = 15
MAX_RETRIES = 3
SLEEP_BETWEEN_DOWNLOADS = 0.5
USER_AGENT = "getdocs-script/1.0 (+https://example.com)"

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------- Session ----------
SESSION = requests.Session()
SESSION.auth = (API_KEY, "")
SESSION.headers.update({"User-Agent": USER_AGENT})

# ---------- Conversion helpers: try weasyprint, then pdfkit ----------
try:
    from weasyprint import HTML as WeasyHTML
    HAVE_WEASY = True
except Exception:
    HAVE_WEASY = False

try:
    import pdfkit
    HAVE_PDFKIT = True
except Exception:
    HAVE_PDFKIT = False

def xhtml_to_pdf(xhtml: str, output_pdf_path: str, base_url: Optional[str] = None) -> str:
    """
    Convert XHTML string to PDF. Returns conversion method used.
    Tries weasyprint first, then pdfkit (wkhtmltopdf).
    Raises RuntimeError if conversion not possible.
    """
    if HAVE_WEASY:
        try:
            # base_url helps resolve relative assets/CSS/images
            WeasyHTML(string=xhtml, base_url=base_url).write_pdf(output_pdf_path)
            return "weasyprint"
        except Exception as e:
            logger.warning(f"WeasyPrint conversion failed: {e}")

    if HAVE_PDFKIT:
        try:
            # pdfkit requires wkhtmltopdf available on system path
            options = {"enable-local-file-access": None}
            pdfkit.from_string(xhtml, output_pdf_path, options=options)
            return "pdfkit"
        except Exception as e:
            logger.warning(f"pdfkit conversion failed: {e}")

    raise RuntimeError("No available XHTML->PDF converter (install weasyprint or pdfkit + wkhtmltopdf)")

# ---------- State & counters ----------
global_pdf_count = 0
per_type_count: Dict[str, int] = {ft: 0 for ft in FILING_TYPE_FILTER}

# ---------- Helpers ----------
def read_company_numbers() -> List[str]:
    if os.path.exists(COMPANY_NUMBERS_FILE):
        with open(COMPANY_NUMBERS_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            logger.info(f"Loaded {len(lines)} companies from {COMPANY_NUMBERS_FILE}")
            return lines
    logger.info(f"No {COMPANY_NUMBERS_FILE} found; using inline COMPANY_NUMBERS (0 entries)")
    return []

def valid_company_number_format(num: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9]{5,8}$", num))

def safe_request(url: str, params: dict = None, headers: dict = None, accept: Optional[str] = None) -> requests.Response:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            hdrs = headers.copy() if headers else {}
            if accept:
                hdrs["Accept"] = accept
            resp = SESSION.get(url, params=params, headers=hdrs, timeout=REQUESTS_TIMEOUT)
            if resp.status_code >= 500 or resp.status_code == 429:
                logger.warning(f"Transient HTTP {resp.status_code} for {url} (attempt {attempt}); backing off")
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp
        except (ConnectionError, Timeout) as e:
            logger.warning(f"Connection/Timeout on attempt {attempt} for {url}: {e}")
            time.sleep(2 ** attempt)
        except HTTPError:
            # propagate 4xx for caller
            raise
    raise RuntimeError(f"Failed to get {url} after {MAX_RETRIES} attempts")

def get_filing_history(company_number: str, items_per_page: int = 100) -> List[dict]:
    url = f"https://api.companieshouse.gov.uk/company/{company_number}/filing-history"
    params = {"items_per_page": items_per_page}
    resp = safe_request(url, params=params)
    return resp.json().get("items", [])

def get_document_metadata(document_metadata_link: str) -> dict:
    resp = safe_request(document_metadata_link)
    return resp.json()

def download_document_stream(doc_link: str, save_path: str, accept_type: str = "application/pdf"):
    resp = safe_request(doc_link, accept=accept_type)
    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def append_manifest_row(row: dict):
    file_exists = os.path.exists(MANIFEST_FILE)
    standard_keys = ["company_number", "status", "file", "folder", "f_type", "f_date", "download_index", "http_status", "notes", "conversion", "conversion_method"]
    fieldnames = standard_keys + [k for k in row.keys() if k not in standard_keys]
    seen = set()
    ordered = []
    for k in fieldnames:
        if k not in seen:
            ordered.append(k)
            seen.add(k)
    with open(MANIFEST_FILE, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=ordered)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def matches_filter(filing_type: str) -> bool:
    if not FILING_TYPE_FILTER:
        return True
    return filing_type in FILING_TYPE_FILTER

def cap_reached_for_type(ftype: str) -> bool:
    cap = PER_TYPE_CAPS.get(ftype, 0)
    if cap and per_type_count.get(ftype, 0) >= cap:
        return True
    return False

def global_cap_reached() -> bool:
    if GLOBAL_CAP and global_pdf_count >= GLOBAL_CAP:
        return True
    return False

# ---------- Main processing ----------
def process_company(company_number: str):
    global global_pdf_count
    logger.info(f"Processing company: {company_number}")

    if global_cap_reached():
        logger.info("Global cap reached; exiting.")
        sys.exit(0)

    if not valid_company_number_format(company_number):
        logger.error(f"Invalid format for company number: {company_number} — skipping")
        append_manifest_row({
            "company_number": company_number,
            "status": "invalid_format",
            "notes": "format_check_failed"
        })
        return

    try:
        items = get_filing_history(company_number)
    except HTTPError as e:
        resp = e.response
        code = resp.status_code if resp is not None else "HTTPError"
        msg = (resp.text[:200] if resp is not None else str(e)).replace("\n", " ")
        logger.error(f"HTTP error fetching filing history for {company_number}: {code} - {msg}")
        append_manifest_row({
            "company_number": company_number,
            "status": "error_filing_history",
            "http_status": code,
            "notes": msg[:500]
        })
        return
    except Exception as e:
        logger.exception(f"Unexpected error fetching filing history for {company_number}: {e}")
        append_manifest_row({
            "company_number": company_number,
            "status": "error_filing_history",
            "http_status": "exception",
            "notes": str(e)[:500]
        })
        return

    if not items:
        logger.info(f"No filing history items found for {company_number}")
        append_manifest_row({
            "company_number": company_number,
            "status": "no_items",
            "notes": "no_filing_history_items"
        })
        return

    for item in items:
        ftype = item.get("type", "unknown_type")
        if not matches_filter(ftype):
            continue
        if cap_reached_for_type(ftype):
            logger.info(f"Per-type cap reached for {ftype}; skipping further {ftype} downloads.")
            continue
        if global_cap_reached():
            logger.info("Global cap reached; exiting.")
            sys.exit(0)

        links = item.get("links", {})
        doc_metadata_link = links.get("document_metadata")
        if not doc_metadata_link:
            continue

        try:
            metadata = get_document_metadata(doc_metadata_link)
        except HTTPError as e:
            code = e.response.status_code if e.response is not None else "HTTPError"
            logger.warning(f"HTTP error getting metadata for {doc_metadata_link}: {code}")
            append_manifest_row({
                "company_number": company_number,
                "status": "error_doc_metadata",
                "document_metadata_link": doc_metadata_link,
                "http_status": code,
                "f_type": ftype,
                "f_date": item.get("date")
            })
            continue
        except Exception as e:
            logger.exception(f"Error getting metadata for {doc_metadata_link}: {e}")
            append_manifest_row({
                "company_number": company_number,
                "status": "error_doc_metadata",
                "document_metadata_link": doc_metadata_link,
                "http_status": "exception",
                "notes": str(e)[:300]
            })
            continue

        resources = metadata.get("resources", {})
        date = item.get("date", "unknown_date")
        safe_company = re.sub(r"[^A-Za-z0-9_-]", "_", company_number)
        safe_type = re.sub(r"[^A-Za-z0-9_-]", "_", ftype)
        folder = os.path.join(OUTPUT_DIR, safe_type)
        ensure_dir(folder)

        # Prefer PDF resource; if not present, attempt XHTML -> PDF conversion
        if "application/pdf" in resources:
            ext = ".pdf"
            accept = "application/pdf"
            filename = f"{safe_company}_{date}_{safe_type}{ext}"
            save_path = os.path.join(folder, filename)
            doc_link = metadata.get("links", {}).get("document")
            if not doc_link:
                logger.warning(f"No document link found for {doc_metadata_link}")
                append_manifest_row({
                    "company_number": company_number,
                    "status": "no_doc_link",
                    "document_metadata_link": doc_metadata_link,
                    "f_type": ftype,
                    "f_date": date
                })
                continue
            try:
                download_document_stream(doc_link, save_path, accept_type=accept)
                global_pdf_count += 1
                per_type_count[ftype] = per_type_count.get(ftype, 0) + 1
                logger.info(f"[{global_pdf_count}] Downloaded PDF ({ftype}): {save_path}")
                append_manifest_row({
                    "company_number": company_number,
                    "status": "downloaded",
                    "file": save_path,
                    "folder": folder,
                    "f_type": ftype,
                    "f_date": date,
                    "download_index": global_pdf_count,
                    "conversion": "none",
                    "conversion_method": ""
                })
            except HTTPError as e:
                code = e.response.status_code if e.response is not None else "HTTPError"
                logger.error(f"HTTP error downloading PDF for {company_number}: {code}")
                append_manifest_row({
                    "company_number": company_number,
                    "status": "error_download",
                    "http_status": code,
                    "document_metadata_link": doc_metadata_link,
                    "f_type": ftype,
                    "f_date": date
                })
            except Exception as e:
                logger.exception(f"Error downloading PDF for {company_number}: {e}")
                append_manifest_row({
                    "company_number": company_number,
                    "status": "error_download",
                    "http_status": "exception",
                    "notes": str(e)[:300],
                    "f_type": ftype,
                    "f_date": date
                })
        elif "application/xhtml+xml" in resources:
            # Fetch the XHTML and convert to PDF
            try:
                xhtml_link = metadata.get("links", {}).get("document")
                if not xhtml_link:
                    logger.warning(f"No document link for XHTML resource: {doc_metadata_link}")
                    append_manifest_row({
                        "company_number": company_number,
                        "status": "no_doc_link",
                        "document_metadata_link": doc_metadata_link,
                        "f_type": ftype,
                        "f_date": date
                    })
                    continue

                # fetch xhtml content
                resp = safe_request(xhtml_link, accept="application/xhtml+xml")
                xhtml_content = resp.text

                # choose pdf filename
                pdf_filename = f"{safe_company}_{date}_{safe_type}.pdf"
                pdf_save_path = os.path.join(folder, pdf_filename)

                # try conversion
                try:
                    method = xhtml_to_pdf(xhtml_content, pdf_save_path, base_url=None)
                    conversion_status = "converted"
                    conversion_method = method
                    logger.info(f"Converted XHTML -> PDF using {method}: {pdf_save_path}")
                    global_pdf_count += 1
                    per_type_count[ftype] = per_type_count.get(ftype, 0) + 1
                    append_manifest_row({
                        "company_number": company_number,
                        "status": "downloaded_converted",
                        "file": pdf_save_path,
                        "folder": folder,
                        "f_type": ftype,
                        "f_date": date,
                        "download_index": global_pdf_count,
                        "conversion": conversion_status,
                        "conversion_method": conversion_method
                    })
                except Exception as conv_e:
                    logger.error(f"Conversion failed for {company_number} {ftype}: {conv_e}")
                    append_manifest_row({
                        "company_number": company_number,
                        "status": "conversion_failed",
                        "file": "",
                        "folder": folder,
                        "f_type": ftype,
                        "f_date": date,
                        "download_index": global_pdf_count,
                        "conversion": "failed",
                        "conversion_method": str(conv_e)[:200]
                    })
            except HTTPError as e:
                code = e.response.status_code if e.response is not None else "HTTPError"
                logger.error(f"HTTP error fetching XHTML for {company_number}: {code}")
                append_manifest_row({
                    "company_number": company_number,
                    "status": "error_fetch_xhtml",
                    "http_status": code,
                    "document_metadata_link": doc_metadata_link,
                    "f_type": ftype,
                    "f_date": date
                })
            except Exception as e:
                logger.exception(f"Unexpected error handling XHTML for {company_number}: {e}")
                append_manifest_row({
                    "company_number": company_number,
                    "status": "error_fetch_xhtml",
                    "http_status": "exception",
                    "notes": str(e)[:300],
                    "f_type": ftype,
                    "f_date": date
                })
        else:
            logger.info(f"Skipping item (no pdf/xhtml) for {company_number} - {ftype}")
            append_manifest_row({
                "company_number": company_number,
                "status": "skipped_no_pdf",
                "f_type": ftype,
                "f_date": date
            })

        # polite rate limit
        time.sleep(SLEEP_BETWEEN_DOWNLOADS)

        # exit early if caps reached
        if global_cap_reached():
            logger.info("Global cap reached after processing; exiting.")
            sys.exit(0)

def main():
    # prepare dirs
    ensure_dir(OUTPUT_DIR)
    for ft in FILING_TYPE_FILTER:
        ensure_dir(os.path.join(OUTPUT_DIR, ft))

    company_numbers = read_company_numbers()
    logger.info(f"Starting run. Filter: {FILING_TYPE_FILTER}. Per-type caps: {PER_TYPE_CAPS}. Global cap: {GLOBAL_CAP or 'unlimited'}")
    if not company_numbers:
        logger.warning("No company numbers found in company_numbers.txt - exiting.")
        return
    for comp in company_numbers:
        try:
            process_company(comp)
        except SystemExit:
            logger.info("Exiting after reaching cap or explicit sys.exit.")
            break
        except Exception as e:
            logger.exception(f"Fatal error processing {comp}: {e}")
            # continue to next company

    logger.info(f"Finished run. Total PDFs downloaded: {global_pdf_count}")
    logger.info(f"Per-type counts: {per_type_count}")

if __name__ == "__main__":
    if API_KEY in (None, "", "YOUR_API_KEY_HERE"):
        logger.warning("No API key set in COMPANIES_HOUSE_API_KEY; requests will likely fail.")
        logger.warning("Set your key: export COMPANIES_HOUSE_API_KEY='your_real_key'")
    main()
