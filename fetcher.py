"""
Script 1 — Fetcher
Leader Decision Tracker · Philippines / Marcos Jr.

What this does:
  - Visits the official PCO (Presidential Communications Office) website
  - Finds all speech/remarks/address pages
  - Downloads the full text of each one
  - Saves everything as structured JSON in data/raw_speeches/

Run: python fetcher.py
Output: data/raw_speeches/*.json  +  data/speech_index.json

Requirements: pip install requests beautifulsoup4 python-dotenv
"""

import os
import json
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

SOURCES = [
    {
        "name": "PCO News Releases",
        "index_url": "https://pco.gov.ph/news_releases/",
        "base_url": "https://pco.gov.ph",
        # Keywords that indicate a speech (vs a press release about policy)
        "speech_keywords": [
            "speech", "address", "remarks", "message", "statement",
            "state of the nation", "sona", "inaugural"
        ],
        # CSS selectors — adjust if the site changes layout
        "link_selector": "article a, .entry-title a, h2 a, h3 a",
        "body_selector": ".entry-content, .post-content, article .content, .single-content",
        "date_selector": ".entry-date, time, .post-date, .date",
        "title_selector": "h1.entry-title, h1.post-title, h1",
        # How many index pages to crawl (each page = ~10 articles)
        "max_pages": 20,
        # Pagination pattern — PCO uses ?paged=2, ?paged=3...
        "pagination": "?paged={page}",
    }
]

# Only fetch speeches from Marcos Jr.'s presidency onward
CUTOFF_DATE = "2022-07-01"

# Where to save everything
OUTPUT_DIR = Path("data/raw_speeches")
INDEX_FILE = Path("data/speech_index.json")

# Be polite — don't hammer the server
DELAY_BETWEEN_REQUESTS = 1.5  # seconds

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return s


def url_to_id(url: str) -> str:
    """Stable 12-char ID for a URL — used as filename."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def is_speech(title: str, keywords: list) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords)


def load_existing_index() -> dict:
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            return json.load(f)
    return {}


def save_index(index: dict):
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def save_speech(speech: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{speech['id']}.json"
    with open(path, "w") as f:
        json.dump(speech, f, indent=2, ensure_ascii=False)
    return path

# ── Core: discover links ───────────────────────────────────────────────────────

def get_speech_links(session, source: dict) -> list[dict]:
    """
    Crawl index pages for one source and return a list of candidate speech URLs.
    Returns: [{"url": ..., "title": ..., "source_name": ...}, ...]
    """
    found = []
    base = source["base_url"]
    index_url = source["index_url"]

    for page_num in range(1, source["max_pages"] + 1):
        if page_num == 1:
            url = index_url
        else:
            url = index_url.rstrip("/") + "/" + source["pagination"].format(page=page_num)

        log.info(f"  Scanning index page {page_num}: {url}")

        try:
            r = session.get(url, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"  Failed to fetch index page {page_num}: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.select(source["link_selector"])

        if not links:
            log.info(f"  No links found on page {page_num} — stopping pagination.")
            break

        page_found = 0
        for a in links:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not href:
                continue
            full_url = urljoin(base, href)

            # Only keep links that look like speeches
            if is_speech(title, source["speech_keywords"]):
                found.append({
                    "url": full_url,
                    "title": title,
                    "source_name": source["name"],
                })
                page_found += 1

        log.info(f"  Found {page_found} speech links on page {page_num}")
        time.sleep(DELAY_BETWEEN_REQUESTS)

    log.info(f"Total candidate links from '{source['name']}': {len(found)}")
    return found

# ── Core: fetch one speech ─────────────────────────────────────────────────────

def fetch_speech(session, link: dict, source: dict) -> dict | None:
    """
    Download one speech page and extract structured data.
    Returns a speech dict or None if it fails / is pre-Marcos.
    """
    url = link["url"]

    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        log.warning(f"  Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # ── Title ──
    title_el = soup.select_one(source["title_selector"])
    title = title_el.get_text(strip=True) if title_el else link["title"]

    # ── Date ──
    date_str = None
    date_el = soup.select_one(source["date_selector"])
    if date_el:
        # Try datetime attribute first (most reliable)
        date_str = date_el.get("datetime") or date_el.get_text(strip=True)

    # Normalise date to YYYY-MM-DD where possible
    date_parsed = parse_date(date_str)

    # Skip if before Marcos Jr. presidency
    if date_parsed and date_parsed < CUTOFF_DATE:
        log.info(f"  Skipping (pre-Marcos): {title[:60]}")
        return None

    # ── Body text ──
    body_el = soup.select_one(source["body_selector"])
    if not body_el:
        log.warning(f"  No body content found at {url}")
        return None

    # Clean up the text
    for tag in body_el.find_all(["script", "style", "nav", "aside"]):
        tag.decompose()
    body_text = body_el.get_text(separator="\n", strip=True)

    if len(body_text) < 200:
        log.info(f"  Skipping (too short, probably not a speech): {title[:60]}")
        return None

    speech = {
        "id": url_to_id(url),
        "title": title,
        "url": url,
        "source": source["name"],
        "date_raw": date_str,
        "date": date_parsed,
        "leader": "Ferdinand Marcos Jr.",
        "country": "Philippines",
        "language": "en",
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "word_count": len(body_text.split()),
        "body": body_text,
    }

    return speech


def parse_date(raw: str | None) -> str | None:
    """Try to normalise a messy date string to YYYY-MM-DD."""
    if not raw:
        return None
    raw = raw.strip()
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw[:len(fmt)], fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return raw  # Return raw if we can't parse — don't silently drop it

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Leader Decision Tracker — Script 1: Fetcher")
    log.info("Target: Ferdinand Marcos Jr. · Philippines")
    log.info("=" * 60)

    session = make_session()
    existing_index = load_existing_index()
    log.info(f"Already have {len(existing_index)} speeches in index.")

    new_count = 0
    skipped_count = 0

    for source in SOURCES:
        log.info(f"\nSource: {source['name']}")
        log.info("-" * 40)

        links = get_speech_links(session, source)

        for link in links:
            speech_id = url_to_id(link["url"])

            # Skip if we already have this one
            if speech_id in existing_index:
                skipped_count += 1
                continue

            log.info(f"  Fetching: {link['title'][:70]}")
            time.sleep(DELAY_BETWEEN_REQUESTS)

            speech = fetch_speech(session, link, source)

            if speech:
                path = save_speech(speech)
                existing_index[speech_id] = {
                    "id": speech_id,
                    "title": speech["title"],
                    "date": speech["date"],
                    "url": speech["url"],
                    "word_count": speech["word_count"],
                    "file": str(path),
                    "status": "raw",  # raw → extracted → verified
                }
                save_index(existing_index)  # Save after each speech (safe on crash)
                new_count += 1
                log.info(f"    ✓ Saved ({speech['word_count']} words) → {path.name}")

    log.info("\n" + "=" * 60)
    log.info(f"Done. New speeches fetched: {new_count}")
    log.info(f"Already existed (skipped): {skipped_count}")
    log.info(f"Total in index: {len(existing_index)}")
    log.info(f"Index saved to: {INDEX_FILE}")
    log.info(f"Speeches saved to: {OUTPUT_DIR}/")
    log.info("=" * 60)
    log.info("Next step: run extractor.py to extract promises from these speeches.")


if __name__ == "__main__":
    main()