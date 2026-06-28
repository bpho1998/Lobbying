# NetFile SFO Lobbyist Filings Discord Bot

A GitHub Actions bot that monitors the [SF Ethics Commission lobbyist filings page](https://netfile.com/lobbyistpub/#/sfo/directory/filings) and sends a Discord notification whenever a new filing appears.

## How it works

1. A GitHub Actions workflow runs **every hour** (configurable).
2. It calls the NetFile public API to fetch the 50 most recent SFO lobbyist filings.
3. It compares them against a `seen_filings.json` file committed to the repo.
4. Any new filings get posted to your Discord channel via a webhook.
5. The updated `seen_filings.json` is committed back to the repo so duplicates are never re-sent.

## Setup

### 1. Fork or create this repo

Push these files to a GitHub repository you own.

### 2. Create a Discord Webhook

1. Open your Discord server → **Channel Settings** → **Integrations** → **Webhooks**
2. Click **New Webhook**, name it (e.g. "NetFile Monitor"), and copy the URL.

### 3. Add the webhook as a GitHub Secret

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `DISCORD_WEBHOOK_URL`
4. Value: paste your Discord webhook URL

### 4. Enable Actions

GitHub Actions should be enabled by default. Check under **Actions** → make sure workflows are allowed.

### 5. Test it

Go to **Actions** → **NetFile SFO Filings Monitor** → **Run workflow** to trigger it manually.

## Customization

| What | Where |
|---|---|
| Check frequency | `cron` line in `.github/workflows/monitor.yml` |
| Number of filings fetched per run | `PAGE_SIZE` in `check_filings.py` |
| Discord message format | `format_discord_message()` in `check_filings.py` |

### Cron examples

```
"0 * * * *"      # Every hour (default)
"*/30 * * * *"   # Every 30 minutes
"0 9,17 * * 1-5" # 9am and 5pm, weekdays only
```

## Files

```
.
├── .github/
│   └── workflows/
│       └── monitor.yml     # GitHub Actions workflow
├── check_filings.py        # Main script
├── seen_filings.json       # Auto-generated; tracks already-notified filings
└── README.md
```

## Notes

- The NetFile API is public and doesn't require authentication.
- `seen_filings.json` grows over time but stays small (just filing IDs).
- The `[skip ci]` tag on the commit prevents the workflow from re-triggering itself.
