# PromiseLog

This project fetches political speeches, extracts promises, finds supporting evidence, and publishes a report as a static site.

## Requirements

- Python 3.10+ (or whatever version you use)
- Packages from `requirements.txt`:
  - requests
  - beautifulsoup4
  - anthropic
  - python-dotenv
- An Anthropic API key in a `.env` file

## Environment variables

Create a `.env` file in the project root with:

ANTHROPIC_API_KEY=your_real_key_here

You can use `.env.example` as a template.

## How to run

From the project root, run these scripts in order:

1. `python fetcher.py`  
   Fetches raw speeches into `data/raw_speeches/`.

2. `python extractor.py`  
   Extracts promises from the raw speeches into `data/promises/`.

3. `python evidence_finder.py`  
   Finds evidence related to the promises.

4. `python verdict_writer.py`  
   Uses Anthropic to write verdicts and a report, saving to `data/verdicts_report.json` and/or the `site` folder.

5. `python publisher.py`  
   Generates/updates the static site content in the `site/` directory for GitHub Pages.
