"""
Script 4 — Verdict Writer
Leader Decision Tracker · Philippines / Marcos Jr.

What this does:
  - Reads all promises from data/promises/ that have evidence but no verdict yet
  - Sends promise + evidence to Claude for evaluation
  - Claude assigns one of five verdicts: kept / broken / partial / too_early / unverifiable
  - Saves verdict back into the promise JSON file
  - Writes a summary report to data/verdicts_report.json

Run: python verdict_writer.py
Output: updates data/promises/*.json with verdict fields
        writes  data/verdicts_report.json

Requirements: pip install anthropic python-dotenv
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from collections import Counter

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

# Sonnet 4.6 for verdicts — this is the judgment call that matters most.
# More expensive than Haiku but significantly better reasoning on nuanced evidence.
MODEL = "claude-sonnet-4-6"

PROMISES_DIR    = Path("data/promises")
REPORT_FILE     = Path("data/verdicts_report.json")

MAX_PROMISES    = None   # None = process all pending
DELAY_BETWEEN_CALLS = 1.5

VALID_VERDICTS = {"kept", "broken", "partial", "too_early", "unverifiable"}

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────
#
# The verdict prompt is even more critical than the extraction prompt.
# It must be conservative, evidence-only, and never speculate.
#
SYSTEM_PROMPT = """You are a non-partisan political accountability analyst. Your job is to evaluate whether a political promise was kept, broken, or something in between — based ONLY on the evidence provided.

VERDICT DEFINITIONS (use exactly one):

- kept: The promise was clearly fulfilled. There is direct evidence the specific commitment was carried out.
- broken: The promise was clearly not fulfilled. The deadline passed with no action, or the leader took the opposite action.
- partial: Something was done, but it falls short of the full commitment (e.g. promised 100 units, delivered 40).
- too_early: The deadline hasn't passed yet, OR it's been less than 12 months since the promise and no deadline was given. Do not speculate about future outcomes.
- unverifiable: There is no reliable evidence either way. The evidence is too thin, contradictory, or impossible to verify without access to classified/non-public information.

STRICT RULES:
1. If you are not certain, lean toward "unverifiable" over "kept" or "broken". A wrong verdict destroys credibility.
2. You MUST cite at least one specific piece of evidence for any verdict other than "unverifiable" or "too_early".
3. Never infer. Never assume. Only use what is directly stated in the evidence provided.
4. If the evidence is only news articles with no outcome data, and the promise is outcome-based, use "unverifiable".
5. A promise about passing a law is only "kept" if the law was actually signed/passed — not just introduced or proposed.
6. Economic promises need actual data (World Bank, official statistics), not just news coverage of the topic.

Respond ONLY with a JSON object in this exact format:
{
  "verdict": "kept|broken|partial|too_early|unverifiable",
  "verdict_summary": "One sentence explaining the verdict in plain English.",
  "key_evidence": "The single most important piece of evidence that determined this verdict. Include the source name or URL if available. If none exists, write 'No direct evidence found.'",
  "confidence": "high|medium|low",
  "analyst_notes": "Any important nuance, caveats, or flags for human review. Keep under 2 sentences."
}
"""

def build_user_message(promise: dict) -> str:
    # Format World Bank data readably
    wb_section = ""
    wb_data = promise.get("world_bank_data", [])
    if wb_data:
        wb_lines = []
        seen = set()
        for d in wb_data:
            key = (d.get("indicator_name"), d.get("year"))
            if key not in seen:
                seen.add(key)
                wb_lines.append(
                    f"  - {d.get('indicator_name')} ({d.get('year')}): {d.get('value')}"
                )
        if wb_lines:
            wb_section = "\n\nWORLD BANK DATA:\n" + "\n".join(wb_lines)

    # Format GDELT articles readably
    news_section = ""
    articles = promise.get("gdelt_articles", [])
    if articles:
        news_lines = []
        for a in articles[:5]:
            title = a.get("title", "No title")
            outlet = a.get("outlet", "unknown source")
            date = a.get("date", "unknown date")
            url = a.get("url", "")
            news_lines.append(f"  - [{date}] {title} ({outlet})\n    URL: {url}")
        news_section = "\n\nNEWS COVERAGE:\n" + "\n".join(news_lines)

    no_evidence_note = ""
    if not wb_data and not articles:
        no_evidence_note = "\n\nNOTE: No evidence was found for this promise."

    today = datetime.utcnow().strftime("%Y-%m-%d")

    return f"""PROMISE TO EVALUATE:

Leader: {promise.get('leader', 'Unknown')}
Country: {promise.get('country', 'Philippines')}
Speech date: {promise.get('speech_date', 'Unknown')}
Today's date: {today}

Original quote: "{promise.get('exact_quote', '')}"

Promise summary: {promise.get('summary', '')}
Category: {promise.get('category', '')}
Stated timeframe: {promise.get('timeframe', 'unspecified')}
What "kept" looks like: {promise.get('measurable_target', 'Not specified')}
{wb_section}{news_section}{no_evidence_note}

Based on the evidence above, evaluate this promise."""


# ── Core: write verdict for one promise ───────────────────────────────────────

def write_verdict(client: anthropic.Anthropic, promise: dict) -> dict | None:
    """
    Send promise + evidence to Claude, get back a structured verdict.
    Returns parsed verdict dict or None on failure.
    """
    user_message = build_user_message(promise)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
    except anthropic.APIError as e:
        log.error(f"  API error: {e}")
        return None

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        log.error(f"  JSON parse error: {e}")
        log.error(f"  Raw response: {raw_text[:400]}")
        return None

    # Validate verdict value
    verdict = result.get("verdict", "").lower()
    if verdict not in VALID_VERDICTS:
        log.warning(f"  Invalid verdict '{verdict}' — defaulting to 'unverifiable'")
        result["verdict"] = "unverifiable"

    return result


# ── Verdict display ───────────────────────────────────────────────────────────

VERDICT_ICONS = {
    "kept":          "✓  KEPT",
    "broken":        "✗  BROKEN",
    "partial":       "~  PARTIAL",
    "too_early":     "…  TOO EARLY",
    "unverifiable":  "?  UNVERIFIABLE",
}

def log_verdict(promise: dict, verdict_result: dict):
    v = verdict_result.get("verdict", "?")
    icon = VERDICT_ICONS.get(v, v.upper())
    conf = verdict_result.get("confidence", "?")
    summary = verdict_result.get("verdict_summary", "")
    log.info(f"  {icon} [{conf}] {summary[:90]}")


# ── Report generator ──────────────────────────────────────────────────────────

def generate_report(promises: list[dict]) -> dict:
    """
    Build a summary report across all verdicted promises.
    """
    verdicted = [p for p in promises if p.get("verdict") in VALID_VERDICTS]

    verdict_counts = Counter(p["verdict"] for p in verdicted)
    category_counts = Counter(p["category"] for p in verdicted)

    total = len(verdicted)
    kept = verdict_counts.get("kept", 0)
    broken = verdict_counts.get("broken", 0)
    partial = verdict_counts.get("partial", 0)
    too_early = verdict_counts.get("too_early", 0)
    unverifiable = verdict_counts.get("unverifiable", 0)

    # Keep rate = kept / (kept + broken + partial) — excludes too_early and unverifiable
    scoreable = kept + broken + partial
    keep_rate = round((kept / scoreable * 100), 1) if scoreable > 0 else None

    # High-confidence broken promises — the most newsworthy
    broken_high_conf = [
        {
            "summary": p["summary"],
            "category": p["category"],
            "speech_date": p.get("speech_date"),
            "verdict_summary": p.get("verdict_summary"),
            "key_evidence": p.get("key_evidence"),
        }
        for p in verdicted
        if p.get("verdict") == "broken" and p.get("confidence") == "high"
    ]

    # High-confidence kept promises
    kept_high_conf = [
        {
            "summary": p["summary"],
            "category": p["category"],
            "speech_date": p.get("speech_date"),
            "verdict_summary": p.get("verdict_summary"),
        }
        for p in verdicted
        if p.get("verdict") == "kept" and p.get("confidence") == "high"
    ]

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "leader": "Ferdinand Marcos Jr.",
        "country": "Philippines",
        "total_promises_verdicted": total,
        "keep_rate_percent": keep_rate,
        "scoreable_promises": scoreable,
        "verdict_breakdown": {
            "kept": kept,
            "broken": broken,
            "partial": partial,
            "too_early": too_early,
            "unverifiable": unverifiable,
        },
        "by_category": dict(category_counts),
        "notable_broken_high_confidence": broken_high_conf,
        "notable_kept_high_confidence": kept_high_conf,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("Leader Decision Tracker — Script 4: Verdict Writer")
    log.info(f"Model: {MODEL}")
    log.info("=" * 60)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not found. Check your .env file.")
        return

    client = anthropic.Anthropic(api_key=api_key)

    if not PROMISES_DIR.exists():
        log.error(f"No promises directory at {PROMISES_DIR}. Run extractor.py first.")
        return

    promise_files = list(PROMISES_DIR.glob("*.json"))
    log.info(f"Total promise files: {len(promise_files)}")

    # Load all promises
    all_promises = []
    for path in promise_files:
        with open(path) as f:
            all_promises.append((path, json.load(f)))

    # Find promises with evidence but no verdict yet
    to_process = [
        (path, p) for path, p in all_promises
        if p.get("evidence_status") is not None   # evidence_finder has run
        and p.get("verdict") is None               # no verdict yet
    ]

    # Also process promises with no evidence — they get "unverifiable" directly
    no_evidence = [
        (path, p) for path, p in all_promises
        if p.get("evidence_status") == "no_evidence"
        and p.get("verdict") is None
    ]

    log.info(f"Promises with evidence, needing verdict: {len(to_process) - len(no_evidence)}")
    log.info(f"Promises with no evidence (auto-unverifiable): {len(no_evidence)}")

    if MAX_PROMISES:
        to_process = to_process[:MAX_PROMISES]

    if not to_process:
        log.info("No promises need verdicts right now.")
    else:
        processed = 0

        for i, (path, promise) in enumerate(to_process, 1):
            log.info(f"\n[{i}/{len(to_process)}] {promise.get('summary', '')[:70]}")

            # Auto-unverifiable if no evidence found
            if promise.get("evidence_status") == "no_evidence":
                verdict_result = {
                    "verdict": "unverifiable",
                    "verdict_summary": "No evidence found to evaluate this promise.",
                    "key_evidence": "No direct evidence found.",
                    "confidence": "high",
                    "analyst_notes": "Auto-assigned. Evidence search returned no results.",
                }
                log.info("  ?  UNVERIFIABLE [auto — no evidence]")
            else:
                time.sleep(DELAY_BETWEEN_CALLS)
                verdict_result = write_verdict(client, promise)

                if verdict_result is None:
                    log.warning("  Verdict failed — skipping.")
                    continue

                log_verdict(promise, verdict_result)

            # Write verdict fields back into the promise
            promise["verdict"]          = verdict_result["verdict"]
            promise["verdict_summary"]  = verdict_result.get("verdict_summary")
            promise["key_evidence"]     = verdict_result.get("key_evidence")
            promise["confidence"]       = verdict_result.get("confidence")
            promise["analyst_notes"]    = verdict_result.get("analyst_notes")
            promise["verdict_date"]     = datetime.utcnow().isoformat() + "Z"
            promise["verdict_model"]    = MODEL

            with open(path, "w") as f:
                json.dump(promise, f, indent=2, ensure_ascii=False)

            processed += 1

        log.info(f"\nVerdicts written: {processed}")

    # Reload all promises (including newly verdicted ones) for the report
    all_loaded = []
    for path in PROMISES_DIR.glob("*.json"):
        with open(path) as f:
            all_loaded.append(json.load(f))

    # Generate and save summary report
    report = generate_report(all_loaded)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    log.info("\n" + "=" * 60)
    log.info("SUMMARY REPORT")
    log.info(f"  Total verdicted:   {report['total_promises_verdicted']}")
    log.info(f"  Keep rate:         {report['keep_rate_percent']}%")
    log.info(f"  Kept:              {report['verdict_breakdown']['kept']}")
    log.info(f"  Broken:            {report['verdict_breakdown']['broken']}")
    log.info(f"  Partial:           {report['verdict_breakdown']['partial']}")
    log.info(f"  Too early:         {report['verdict_breakdown']['too_early']}")
    log.info(f"  Unverifiable:      {report['verdict_breakdown']['unverifiable']}")
    log.info(f"\nReport saved to: {REPORT_FILE}")
    log.info("=" * 60)
    log.info("Next step: run publisher.py to build and deploy the live website.")


if __name__ == "__main__":
    main()