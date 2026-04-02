"""
Script 3 — Evidence Finder
Leader Decision Tracker · Philippines / Marcos Jr.

What this does:
  - Reads all promises from data/promises/ that have no evidence yet
  - For each promise, searches GDELT for related news coverage
  - Also queries World Bank API for economic/social indicator data
  - Saves all found evidence back into the promise JSON file
  - Updates promise status to "evidence_found" or "no_evidence"

Run: python evidence_finder.py
Output: updates data/promises/*.json with evidence_urls + evidence_summary

Requirements: pip install requests python-dotenv
(No extra API key needed — GDELT and World Bank are free/open)
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

PROMISES_DIR = Path("data/promises")

# How many GDELT articles to fetch per promise
GDELT_MAX_RESULTS = 5

# How many promises to process per run (None = all)
MAX_PROMISES = None

# Seconds between requests — GDELT asks you not to hammer them
DELAY_BETWEEN_REQUESTS = 2.0

# World Bank indicator codes mapped to our promise categories
# These are real WB API codes for Philippines data
WORLD_BANK_INDICATORS = {
    "economy":       ["NY.GDP.MKTP.KD.ZG", "SL.UEM.TOTL.ZS"],   # GDP growth, unemployment
    "healthcare":    ["SH.XPD.CHEX.GD.ZS", "SP.DYN.IMRT.IN"],   # Health spend, infant mortality
    "education":     ["SE.XPD.TOTL.GD.ZS", "SE.PRM.ENRR"],      # Education spend, enrollment
    "agriculture":   ["NV.AGR.TOTL.ZS"],                          # Agriculture % of GDP
    "environment":   ["EN.ATM.CO2E.PC"],                          # CO2 emissions
    "social_welfare":["SI.POV.NAHC", "SI.POV.GINI"],             # Poverty rate, Gini
    "infrastructure":["EG.ELC.ACCS.ZS"],                          # Electricity access
}

WORLD_BANK_COUNTRY = "PH"  # Philippines ISO code

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── GDELT Search ─────────────────────────────────────────────────────────────

def build_gdelt_query(promise: dict) -> str:
    """
    Build a focused search query from a promise's summary + category.
    GDELT full-text search works best with 3-6 key terms.
    """
    summary = promise.get("summary", "")
    category = promise.get("category", "")
    leader = promise.get("leader", "Marcos")

    # Strip filler words, keep the substance
    stop_words = {
        "a", "an", "the", "to", "of", "in", "for", "and", "or",
        "will", "shall", "by", "on", "at", "with", "is", "are",
        "was", "were", "be", "been", "have", "has", "had",
        "that", "this", "we", "our", "his", "her", "their",
        "commit", "commits", "pledge", "pledges", "promise", "promises",
        "increase", "improve", "ensure", "provide", "build", "create",
    }

    words = [
        w.strip(".,;:'\"") for w in summary.lower().split()
        if w.strip(".,;:'\"") not in stop_words and len(w) > 3
    ]

    # Take the 4 most meaningful words + always include Philippines
    key_terms = words[:4]
    query_parts = key_terms + ["Philippines", "Marcos"]

    return " ".join(query_parts)


def search_gdelt(promise: dict) -> list[dict]:
    """
    Search GDELT Full-Text Search API for news articles related to a promise.
    Returns a list of article dicts: {title, url, date, source, snippet}
    """
    query = build_gdelt_query(promise)

    # GDELT date range: from promise date to today
    promise_date = promise.get("speech_date", "2022-07-01")
    try:
        start_dt = datetime.strptime(promise_date[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        start_dt = datetime(2022, 7, 1)

    end_dt = datetime.utcnow()

    # GDELT uses YYYYMMDDHHMMSS format
    start_str = start_dt.strftime("%Y%m%d%H%M%S")
    end_str   = end_dt.strftime("%Y%m%d%H%M%S")

    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={quote_plus(query)}"
        f"&mode=artlist"
        f"&maxrecords={GDELT_MAX_RESULTS}"
        f"&startdatetime={start_str}"
        f"&enddatetime={end_str}"
        f"&sort=hybridrel"
        f"&format=json"
    )

    log.info(f"  GDELT query: '{query}'")

    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.warning(f"  GDELT request failed: {e}")
        return []

    articles = data.get("articles", [])
    results = []

    for a in articles:
        results.append({
            "source": "gdelt",
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "date": a.get("seendate", "")[:8],  # YYYYMMDD → YYYY-MM-DD later
            "outlet": a.get("domain", ""),
            "snippet": a.get("socialimage", ""),  # GDELT doesn't give full text
        })

    log.info(f"  GDELT results: {len(results)} articles")
    return results


# ── World Bank Search ─────────────────────────────────────────────────────────

def fetch_world_bank_indicator(indicator_code: str, country: str = "PH") -> list[dict]:
    """
    Fetch an indicator's recent values from the World Bank API.
    Returns list of {year, value, indicator_code, indicator_name}
    """
    url = (
        f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator_code}"
        f"?format=json&mrv=5&per_page=5"  # Most recent 5 years
    )

    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        log.warning(f"  World Bank request failed for {indicator_code}: {e}")
        return []

    if not data or len(data) < 2 or not data[1]:
        return []

    results = []
    indicator_name = data[1][0].get("indicator", {}).get("value", indicator_code) if data[1] else indicator_code

    for entry in data[1]:
        if entry.get("value") is not None:
            results.append({
                "source": "world_bank",
                "indicator_code": indicator_code,
                "indicator_name": indicator_name,
                "year": entry.get("date"),
                "value": entry.get("value"),
                "country": entry.get("country", {}).get("value", country),
                "url": f"https://data.worldbank.org/indicator/{indicator_code}?locations={country}",
            })

    return results


def get_world_bank_evidence(promise: dict) -> list[dict]:
    """
    Fetch relevant World Bank indicators based on promise category.
    Only runs for categories that have matching indicators.
    """
    category = promise.get("category", "other")
    indicator_codes = WORLD_BANK_INDICATORS.get(category, [])

    if not indicator_codes:
        return []

    log.info(f"  Fetching World Bank indicators for category '{category}': {indicator_codes}")

    all_data = []
    for code in indicator_codes:
        data = fetch_world_bank_indicator(code)
        all_data.extend(data)
        time.sleep(0.5)

    log.info(f"  World Bank data points: {len(all_data)}")
    return all_data


# ── Evidence packaging ────────────────────────────────────────────────────────

def package_evidence(gdelt_results: list, wb_results: list, promise: dict) -> dict:
    """
    Combine all evidence sources into a clean package to be stored on the promise.
    """
    # Clean up GDELT dates
    for a in gdelt_results:
        raw_date = a.get("date", "")
        if len(raw_date) == 8:  # YYYYMMDD
            a["date"] = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"

    # Build a flat list of all evidence URLs (for quick reference)
    evidence_urls = list({a["url"] for a in gdelt_results if a.get("url")})
    evidence_urls += list({d["url"] for d in wb_results if d.get("url")})

    # Remove duplicates preserving order
    seen = set()
    unique_urls = []
    for u in evidence_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    # Build a short plain-text summary of what was found
    summary_parts = []

    if gdelt_results:
        headlines = [a["title"] for a in gdelt_results if a.get("title")][:3]
        summary_parts.append(
            f"News coverage ({len(gdelt_results)} articles): " + " | ".join(headlines)
        )

    if wb_results:
        # Summarise the most recent value for each indicator
        by_indicator = {}
        for d in wb_results:
            code = d["indicator_code"]
            if code not in by_indicator:
                by_indicator[code] = d
        for code, d in by_indicator.items():
            summary_parts.append(
                f"{d['indicator_name']} ({d['year']}): {d['value']}"
            )

    evidence_summary = "\n".join(summary_parts) if summary_parts else None

    status = "evidence_found" if (gdelt_results or wb_results) else "no_evidence"

    return {
        "evidence_status": status,
        "evidence_found_at": datetime.utcnow().isoformat() + "Z",
        "evidence_urls": unique_urls,
        "evidence_summary": evidence_summary,
        "gdelt_articles": gdelt_results,
        "world_bank_data": wb_results,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Leader Decision Tracker — Script 3: Evidence Finder")
    log.info("Sources: GDELT (news) + World Bank (indicators)")
    log.info("=" * 60)

    if not PROMISES_DIR.exists():
        log.error(f"No promises directory found at {PROMISES_DIR}. Run extractor.py first.")
        return

    # Load all promise files
    promise_files = list(PROMISES_DIR.glob("*.json"))
    log.info(f"Total promise files: {len(promise_files)}")

    # Filter to only promises that don't have evidence yet
    to_process = []
    for path in promise_files:
        with open(path) as f:
            p = json.load(f)
        if not p.get("evidence_status"):  # Not yet searched
            to_process.append((path, p))

    if MAX_PROMISES:
        to_process = to_process[:MAX_PROMISES]

    log.info(f"Promises needing evidence search: {len(to_process)}")

    if not to_process:
        log.info("All promises already have evidence searches. Nothing to do.")
        return

    found_count = 0
    no_evidence_count = 0

    for i, (path, promise) in enumerate(to_process, 1):
        log.info(f"\n[{i}/{len(to_process)}] {promise.get('summary', '')[:70]}")
        log.info(f"  Category: {promise.get('category')} | Date: {promise.get('speech_date')}")

        # 1. Search GDELT for news coverage
        time.sleep(DELAY_BETWEEN_REQUESTS)
        gdelt_results = search_gdelt(promise)

        # 2. Fetch World Bank indicators for relevant categories
        time.sleep(DELAY_BETWEEN_REQUESTS)
        wb_results = get_world_bank_evidence(promise)

        # 3. Package everything
        evidence = package_evidence(gdelt_results, wb_results, promise)

        # 4. Write evidence back into the promise file
        promise.update(evidence)
        with open(path, "w") as f:
            json.dump(promise, f, indent=2, ensure_ascii=False)

        if evidence["evidence_status"] == "evidence_found":
            found_count += 1
            log.info(f"  ✓ Evidence found — {len(evidence['evidence_urls'])} URLs")
        else:
            no_evidence_count += 1
            log.info(f"  ✗ No evidence found")

    log.info("\n" + "=" * 60)
    log.info(f"Done. Promises processed: {len(to_process)}")
    log.info(f"Evidence found:    {found_count}")
    log.info(f"No evidence found: {no_evidence_count}")
    log.info("=" * 60)
    log.info("Next step: run verdict_writer.py to evaluate evidence and assign verdicts.")


if __name__ == "__main__":
    main()