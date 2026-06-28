#!/usr/bin/env python3
"""
NetFile SFO Lobbyist Filings Monitor
Uses Playwright to render the SPA and scrape the filings table,
then sends Discord notifications for new filings.
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
SEEN_FILE = "seen_filings.json"
TARGET_URL = "https://netfile.com/lobbyistpub/#/sfo/directory/filings"
LOBBYIST_PUB_URL = TARGET_URL


def load_seen() -> set:
    p = Path(SEEN_FILE)
    if p.exists():
        return set(json.loads(p.read_text()))
    return set()


def save_seen(seen: set):
    Path(SEEN_FILE).write_text(json.dumps(sorted(seen), indent=2))


def filing_hash(f: dict) -> str:
    raw = json.dumps(f, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def scrape_filings() -> list[dict]:
    """Launch a headless browser, load the filings page, and extract rows."""
    filings = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"  Loading {TARGET_URL} ...")
        page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)

        # Wait for the filings table to appear
        try:
            page.wait_for_selector("table tbody tr, .filing-row, [class*='filing']", timeout=30000)
        except PlaywrightTimeout:
            # Try waiting a bit longer for the SPA to hydrate
            page.wait_for_timeout(5000)

        # Dump page content for debugging
        content = page.content()
        print(f"  Page content length: {len(content)} chars")

        # Try to extract table rows
        rows = page.query_selector_all("table tbody tr")
        print(f"  Found {len(rows)} table rows")

        for row in rows:
            cells = row.query_selector_all("td")
            cell_texts = [c.inner_text().strip() for c in cells]
            if cell_texts and any(cell_texts):
                f = {"cells": cell_texts, "raw": " | ".join(cell_texts)}
                f["id"] = filing_hash(f)
                filings.append(f)

        # If no table rows found, try other selectors
        if not filings:
            # Try list items or cards
            items = page.query_selector_all("[class*='row'], [class*='item'], [class*='card'], li")
            print(f"  Fallback: found {len(items)} items")
            for item in items[:50]:
                text = item.inner_text().strip()
                if len(text) > 10:
                    f = {"raw": text, "id": filing_hash({"raw": text})}
                    filings.append(f)

        browser.close()
    return filings


def format_discord_embed(f: dict) -> dict:
    cells = f.get("cells", [])
    raw = f.get("raw", "")

    # Try to parse common column patterns: [filer, form, date, ...]
    if len(cells) >= 3:
        filer = cells[0]
        form = cells[1] if len(cells) > 1 else ""
        date = cells[2] if len(cells) > 2 else ""
        description = f"**Form:** {form}\n**Filed:** {date}"
    else:
        filer = raw[:80] if raw else "New Filing"
        description = raw[:300] if raw else ""

    return {
        "title": f"📄 New Lobbyist Filing: {filer[:100]}",
        "description": description,
        "url": LOBBYIST_PUB_URL,
        "color": 0x1E88E5,
        "footer": {"text": "SF Ethics Commission · NetFile Lobbyist Portal"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def post_to_discord(embed: dict):
    resp = requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=10)
    resp.raise_for_status()


def main():
    print(f"[{datetime.now().isoformat()}] Checking NetFile SFO filings…")

    try:
        filings = scrape_filings()
    except Exception as e:
        print(f"ERROR scraping filings: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        sys.exit(1)

    print(f"Scraped {len(filings)} filing(s).")

    seen = load_seen()
    new_filings = [(f["id"], f) for f in filings if f["id"] not in seen]
    print(f"New filing(s): {len(new_filings)}")

    errors = 0
    for fid, f in new_filings:
        try:
            embed = format_discord_embed(f)
            post_to_discord(embed)
            seen.add(fid)
            print(f"  ✓ Notified: {f.get('raw', '')[:60]}")
        except Exception as e:
            print(f"  ✗ ERROR for {fid}: {e}", file=sys.stderr)
            errors += 1

    save_seen(seen)
    print("Done.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
