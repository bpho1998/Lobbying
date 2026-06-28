#!/usr/bin/env python3
"""
NetFile SFO Lobbyist Filings Monitor
Checks for new filings and sends Discord notifications.

The NetFile public API docs (Swagger) are at:
  https://netfile.com/Connect2/api/swagger-ui/#!/public
"""

import json
import os
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import requests

# --- Config ---
# NetFile's public filing search endpoint (documented in their Swagger UI)
NETFILE_API = "https://netfile.com/Connect2/api/public/filing/search"
AGENCY = "SFO"
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
SEEN_FILE = "seen_filings.json"
LOBBYIST_PUB_URL = "https://netfile.com/lobbyistpub/#/sfo/directory/filings"

# How many recent filings to fetch per run
PAGE_SIZE = 50


def load_seen() -> set:
    p = Path(SEEN_FILE)
    if p.exists():
        return set(json.loads(p.read_text()))
    return set()


def save_seen(seen: set):
    Path(SEEN_FILE).write_text(json.dumps(sorted(seen), indent=2))


def fetch_filings() -> list[dict]:
    """Fetch the most recent filings from the NetFile public API."""
    params = {
        "Aid": AGENCY,
        "CurrentPageIndex": 0,
        "PageSize": PAGE_SIZE,
        "SortOrder": "FilingDate",
        "SortAscending": "false",
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": "netfile-discord-bot/1.0",
    }
    resp = requests.get(NETFILE_API, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # API returns {"results": [...], "totalCount": N} or just a list
    if isinstance(data, dict):
        return data.get("results", data.get("filings", []))
    return data


def filing_id(f: dict) -> str:
    """Return a stable unique ID for a filing."""
    for key in ("id", "Id", "filingId", "FilingId", "filing_id", "FilingNid"):
        if f.get(key):
            return str(f[key])
    # Fallback: hash the whole record
    return hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest()[:16]


def format_discord_embed(f: dict) -> dict:
    """Format a filing as a Discord embed."""
    filer = (
        f.get("filerName") or f.get("FilerName") or
        f.get("lobbyistName") or f.get("LobbyistName") or
        f.get("name") or f.get("Name") or "Unknown Filer"
    )
    form = (
        f.get("formName") or f.get("FormName") or
        f.get("formType") or f.get("FormType") or
        f.get("statementType") or f.get("StatementType") or "Unknown Form"
    )
    filed_date = (
        f.get("filingDate") or f.get("FilingDate") or
        f.get("filed_date") or f.get("receivedDate") or ""
    )
    if filed_date:
        filed_date = filed_date[:10]

    period = f.get("periodName") or f.get("PeriodName") or f.get("period") or ""
    fid = filing_id(f)

    lines = [f"**Form:** {form}"]
    if period:
        lines.append(f"**Period:** {period}")
    if filed_date:
        lines.append(f"**Filed:** {filed_date}")
    lines.append(f"**Filing ID:** `{fid}`")

    return {
        "title": f"📄 New Lobbyist Filing: {filer}",
        "description": "\n".join(lines),
        "url": LOBBYIST_PUB_URL,
        "color": 0x1E88E5,
        "footer": {"text": "SF Ethics Commission · NetFile Lobbyist Public Portal"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def post_to_discord(embed: dict):
    resp = requests.post(
        DISCORD_WEBHOOK,
        json={"embeds": [embed]},
        timeout=10,
    )
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
    new_filings = [(filing_id(f), f) for f in filings if filing_id(f) not in seen]

    print(f"New filing(s) since last run: {len(new_filings)}")

    errors = 0
    for fid, f in new_filings:
        try:
            embed = format_discord_embed(f)
            post_to_discord(embed)
            seen.add(fid)
            print(f"  ✓ Notified: {embed['title']}")
        except Exception as e:
            print(f"  ✗ ERROR for {fid}: {e}", file=sys.stderr)
            errors += 1

    save_seen(seen)
    print("Done.")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
