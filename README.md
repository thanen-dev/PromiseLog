# PromiseLog

PromiseLog is an AI-powered pipeline that tracks public promises by political leaders and publishes a simple public report site. The initial focus is on speeches from the Philippines, but the system can be adapted to other countries.

## What this project does

The project:

1. Fetches raw speeches from the web  
2. Extracts promises from those speeches  
3. Finds evidence relevant to each promise  
4. Uses an AI model to write verdicts and a summary report  
5. Publishes a static site (for GitHub Pages) with the results

## Requirements

- Python 3 (3.10+ recommended)
- The Python packages in `requirements.txt`:
  - requests
  - beautifulsoup4
  - anthropic
  - python-dotenv
- An Anthropic API key

## Environment setup

Create a file named `.env` in the project root with:

ANTHROPIC_API_KEY=your_real_key_here

You can use `.env.example` as a reference. The `.env` file is ignored by git and should never be committed.

## How to run (scripts in order)

From the project root, run these scripts in this exact order:

1. `python fetcher.py`  
   Fetches raw speeches and saves them under `data/raw_speeches/`.

2. `python extractor.py`  
   Processes the raw speeches and extracts promises into structured data under `data/promises/`.

3. `python evidence_finder.py`  
   Searches for and attaches evidence related to each promise.

4. `python verdict_writer.py`  
   Uses the Anthropic model (configured via `MODEL` in this file) to generate verdicts and a consolidated report, saving outputs to `data/verdicts_report.json` and/or the `site` directory.

5. `python publisher.py`  
   Builds or updates the static site in the `site/` folder for publication via GitHub Pages.

## GitHub Pages

After pushing to GitHub, enable GitHub Pages in the repository settings:

Settings → Pages → Source: main branch → Folder: `/site` → Save.

GitHub will then serve the static site from the `site` directory.
