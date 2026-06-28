#!/usr/bin/env python3
"""
NetFile SFO Lobbyist Filings Monitor
Checks for new filings and sends Discord notifications.

API docs: https://netfile.com/Connect2/api/json/metadata?op=FilingList
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# --- Config ---
NETFILE_API = "https://netfile.com/Connect2/api/public/list/filing"
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
SEEN_FILE = "seen_filings.json"
LOBBYIST_PUB_URL = "https://netfile.com/lobbyistpub/#/sfo/directory/filings"

PAGE_SIZE = 50


def load_seen() -> set:
    p = Path(SEEN_FILE)
    if p.exists():
        return set(json.loads(p.read_text()))
    return set()


def save_seen(seen: set):
    Path(SEEN_FILE).write_text(json.dumps(sorted(seen), indent=2))


def fetch_filings() -> list[dict]:
    """Fetch the most recent SFO lobbyist filings from the NetFile public API."""
    payload = {
        "aid": "SFO",
        "application": "Lobbyist",
        "currentPageIndex": 0,
        "pageSize": PAGE_SIZE,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "netfile-discord-bot/1.0",
    }
    resp = requests.post(NETFILE_API, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("filings", [])


def format_discord_embed(f: dict) -> dict:
    filer = f.get("filerName") or "Unknown Filer"
    title = f.get("title") or "Untitled Filing"
    filing_date = (f.get("filingDate") or "")[:10]
    fid = f.get("id", "")
    is_amendment = f.get("amendmentSequenceNumber", 0) > 0

    lines = [f"**Filing:** {title}"]
    if filing_date:
        lines.append(f"**Filed:** {filing_date}")
    if is_amendment:
        lines.append(f"**Amendment #{f['amendmentSequenceNumber']}**")
    lines.append(f"**ID:** `{fid}`")

    filing_url = f"https://netfile.com/app/lobbyist/filing/{fid}/report" if fid else LOBBYIST_PUB_URL

    return {
        "title": f"📄 New Lobbyist Filing: {filer}",
        "description": "\n".join(lines),
        "url": filing_url,
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
        filings = fetch_filings()
    except Exception as e:
        print(f"ERROR fetching filings: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetched {len(filings)} filing(s) from API.")

    seen = load_seen()
    new_filings = [(f["id"], f) for f in filings if f.get("id") and f["id"] not in seen]
    print(f"New filing(s) since last run: {len(new_filings)}")

    errors = 0
    for fid, f in new_filings:
        try:
            embed = format_discord_embed(f)
            post_to_discord(embed)
            seen.add(fid)
            print(f"  ✓ Notified: {f.get('filerName')} — {f.get('title')}")
        except Exception as e:
            print(f"  ✗ ERROR for {fid}: {e}", file=sys.stderr)
            errors += 1

    save_seen(seen)
    print("Done.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
