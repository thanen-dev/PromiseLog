"""
Script 2 — Extractor
Leader Decision Tracker · Philippines / Marcos Jr.

What this does:
  - Reads raw speeches from data/raw_speeches/ (output of fetcher.py)
  - Sends each speech to Claude with a carefully engineered prompt
  - Claude identifies only specific, testable, time-bound promises
  - Saves each promise as structured JSON in data/promises/
  - Updates speech_index.json to mark speeches as "extracted"

Run: python extractor.py
Output: data/promises/*.json  +  updated data/speech_index.json

Requirements: pip install anthropic python-dotenv
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

# Haiku 4.5 — fast, cheap, good enough for extraction. ~$0.001 per speech.
MODEL = "claude-haiku-4-5-20251001"

# Paths (must match fetcher.py)
RAW_SPEECHES_DIR = Path("data/raw_speeches")
PROMISES_DIR     = Path("data/promises")
INDEX_FILE       = Path("data/speech_index.json")

# How many speeches to process in one run (set to None for all)
MAX_SPEECHES = None

# Delay between API calls — be gentle
DELAY_BETWEEN_CALLS = 1.0

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────
#
# This is the most important thing in the whole project.
# Every word here affects promise quality. Iterate carefully.
#
SYSTEM_PROMPT = """You are a political accountability analyst. Your job is to read speeches by political leaders and extract only SPECIFIC, TESTABLE, TIME-BOUND promises or commitments they make.

STRICT EXTRACTION RULES:

INCLUDE a promise if it:
- Commits to a specific, observable outcome ("we will build 100,000 homes")
- Names a policy, law, or program that will be enacted or implemented
- States a measurable target with a timeframe ("reduce poverty to 10% by 2028")
- Commits to a specific action ("I will sign the law within 30 days")
- Promises funding or budget allocation for something specific

EXCLUDE anything that is:
- Vague aspiration ("we will make the Philippines great")
- Statement of values ("we believe in transparency")
- Description of past achievements ("we have already built X")
- General intention without specifics ("we plan to improve healthcare")
- Rhetorical flourish or metaphor
- Restatement of existing law or policy (not a new promise)

For each valid promise, extract:
1. exact_quote: The verbatim sentence(s) from the speech containing the promise (max 3 sentences)
2. summary: A one-sentence plain-English description of the promise (your words, not theirs)
3. category: One of [economy, infrastructure, healthcare, education, agriculture, security, anti-corruption, social_welfare, environment, foreign_policy, other]
4. timeframe: When they said it would happen (e.g. "by end of 2024", "within 100 days", "unspecified")
5. measurable_target: The specific thing that would count as fulfillment (what would "kept" look like?)
6. confidence: Your confidence this is a real, testable promise — "high", "medium", or "low"

Respond ONLY with a JSON object in this exact format:
{
  "promises": [
    {
      "exact_quote": "...",
      "summary": "...",
      "category": "...",
      "timeframe": "...",
      "measurable_target": "...",
      "confidence": "high|medium|low"
    }
  ],
  "extraction_notes": "Any notes on the speech quality, ambiguity, or why few/many promises were found"
}

If no valid promises are found, return: {"promises": [], "extraction_notes": "reason"}
"""

def build_user_message(speech: dict) -> str:
    return f"""Leader: {speech.get('leader', 'Unknown')}
Date: {speech.get('date', 'Unknown')}
Title: {speech.get('title', 'Unknown')}
Source URL: {speech.get('url', 'Unknown')}

SPEECH TEXT:
{speech.get('body', '')}"""

# ── Core: extract promises from one speech ─────────────────────────────────────

def extract_promises(client: anthropic.Anthropic, speech: dict) -> dict | None:
    """
    Send a speech to Claude, get back structured promises.
    Returns the parsed JSON response or None on failure.
    """
    user_message = build_user_message(speech)

    # Truncate very long speeches to ~80k chars (~20k tokens) to stay within limits
    if len(user_message) > 80_000:
        log.info(f"  Speech is long ({len(user_message)} chars) — truncating to 80k")
        user_message = user_message[:80_000] + "\n\n[SPEECH TRUNCATED]"

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
    except anthropic.APIError as e:
        log.error(f"  API error: {e}")
        return None

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if Claude added them
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        log.error(f"  JSON parse error: {e}")
        log.error(f"  Raw response: {raw_text[:500]}")
        return None

    return result


def save_promises(speech: dict, extraction: dict) -> list[dict]:
    """
    Save all extracted promises from one speech to data/promises/.
    Returns the list of saved promise dicts.
    """
    PROMISES_DIR.mkdir(parents=True, exist_ok=True)
    saved = []

    for i, p in enumerate(extraction.get("promises", [])):
        promise_id = f"{speech['id']}_{i:03d}"
        promise = {
            "id": promise_id,
            "speech_id": speech["id"],
            "speech_title": speech.get("title"),
            "speech_date": speech.get("date"),
            "speech_url": speech.get("url"),
            "leader": speech.get("leader"),
            "country": speech.get("country"),
            # Extracted fields
            "exact_quote": p.get("exact_quote", ""),
            "summary": p.get("summary", ""),
            "category": p.get("category", "other"),
            "timeframe": p.get("timeframe", "unspecified"),
            "measurable_target": p.get("measurable_target", ""),
            "confidence": p.get("confidence", "low"),
            # Tracking fields (updated by verdict_writer.py later)
            "verdict": None,           # kept / broken / partial / too_early / unverifiable
            "verdict_date": None,
            "evidence_urls": [],
            "evidence_summary": None,
            # Metadata
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "model_used": MODEL,
        }

        path = PROMISES_DIR / f"{promise_id}.json"
        with open(path, "w") as f:
            json.dump(promise, f, indent=2, ensure_ascii=False)

        saved.append(promise)
        log.info(f"    → [{p.get('confidence','?').upper()}] {p.get('summary','')[:70]}")

    return saved


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Leader Decision Tracker — Script 2: Extractor")
    log.info(f"Model: {MODEL}")
    log.info("=" * 60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not found. Check your .env file.")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # Load speech index
    if not INDEX_FILE.exists():
        log.error(f"No speech index found at {INDEX_FILE}. Run fetcher.py first.")
        return

    with open(INDEX_FILE) as f:
        index = json.load(f)

    # Find speeches that haven't been extracted yet
    to_process = [
        entry for entry in index.values()
        if entry.get("status") == "raw"
    ]

    if MAX_SPEECHES:
        to_process = to_process[:MAX_SPEECHES]

    log.info(f"Speeches ready to extract: {len(to_process)}")
    log.info(f"Already extracted: {sum(1 for e in index.values() if e.get('status') == 'extracted')}")

    if not to_process:
        log.info("Nothing new to extract. All speeches already processed.")
        return

    total_promises = 0

    for i, entry in enumerate(to_process, 1):
        speech_path = Path(entry["file"])

        if not speech_path.exists():
            log.warning(f"  Speech file not found: {speech_path}")
            continue

        with open(speech_path) as f:
            speech = json.load(f)

        log.info(f"\n[{i}/{len(to_process)}] {speech.get('title', 'Unknown')[:70]}")
        log.info(f"  Date: {speech.get('date', 'Unknown')} | Words: {speech.get('word_count', '?')}")

        time.sleep(DELAY_BETWEEN_CALLS)

        extraction = extract_promises(client, speech)

        if extraction is None:
            log.warning("  Extraction failed — skipping.")
            continue

        promise_count = len(extraction.get("promises", []))
        notes = extraction.get("extraction_notes", "")

        log.info(f"  Promises found: {promise_count}")
        if notes:
            log.info(f"  Notes: {notes[:120]}")

        saved = save_promises(speech, extraction)
        total_promises += len(saved)

        # Update index to mark this speech as extracted
        index[speech["id"]]["status"] = "extracted"
        index[speech["id"]]["promise_count"] = promise_count
        index[speech["id"]]["extracted_at"] = datetime.utcnow().isoformat() + "Z"

        with open(INDEX_FILE, "w") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

    log.info("\n" + "=" * 60)
    log.info(f"Done. Speeches processed: {len(to_process)}")
    log.info(f"Total promises extracted: {total_promises}")
    log.info(f"Promises saved to: {PROMISES_DIR}/")
    log.info("=" * 60)
    log.info("Next step: run evidence_finder.py to search for outcomes.")


if __name__ == "__main__":
    main()