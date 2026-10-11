# MacroTracker

A Discord bot that logs meals to Google Sheets. DM it `2 eggs and toast` or
`450 cals, 35p, 40c, 12f` and Gemini turns it into a row in your own tab of a
shared spreadsheet. Users don't need Google accounts; the bot writes with a
service account.

Because users talk to it through Discord, it works on every device. The bot
itself runs 24/7 on a Raspberry Pi (see [pi/](pi/README.md)).

## Project layout

```
MacroTracker/
├── bot/        Discord bot: message handling, AI parsing, access control
├── sheets/     Google Sheets reading and writing
├── core/       Shared settings (.env loading) and the SQLite user store
├── cli/        Original terminal tracker and its config.json profiles
├── oauth/      Per-user Google OAuth (not used yet; future feature)
├── deploy/     Dockerfile, docker-compose.yml, deploy.sh  → deploy/README.md
├── pi/         Raspberry Pi setup and maintenance          → pi/README.md
├── secrets/    .env, credentials.json (never committed)    → secrets/README.md
├── data/       user_data.db (never committed)
├── tests/      Unit tests
└── requirements.txt
```

| Folder | Files | Purpose |
| --- | --- | --- |
| `bot/` | `bot.py`, `ai_parser.py`, `access.py` | Entry point, Gemini prompt and validation, server-membership check and rate limit |
| `sheets/` | `sheet_manager.py`, `spreadsheet_manager.py` | Connecting to the sheet, per-user tabs, reading and editing meals |
| `core/` | `settings.py`, `user_store.py` | Loads `secrets/.env`; stores goals, timezones and tab IDs in `data/user_data.db` |
| `cli/` | `main.py`, `display.py`, `config_manager.py`, `config.json` | Interactive terminal tracker |
| `oauth/` | `oauth_manager.py` | Kept for a future version where each user owns a spreadsheet |

Run everything from the project root.

## What the bot understands

| Message | Action |
| --- | --- |
| `chicken burrito bowl` / `450 cals, 35p` | Logs a meal (AI-estimated or manual) |
| `change my goals to 2200 cals, 180p` | Updates only the goals you mention |
| `set my timezone to America/New_York` | Meals are dated in your local time |
| anything else | Replies with help |

Each user gets a worksheet named `Display Name (last 6 digits of Discord ID)`.
The bot remembers the worksheet's ID, so changing your Discord nickname keeps
the same tab.

## Configuration

Settings live in `secrets/.env`; see [secrets/README.md](secrets/README.md)
for setup.

| Variable | Required | Purpose |
| --- | --- | --- |
| `DISCORD_TOKEN` | yes | Bot token from the Discord Developer Portal |
| `GEMINI_API_KEY` | yes | Google AI Studio key |
| `GOOGLE_SHEET_ID` or `GOOGLE_SHEET_NAME` | yes | Spreadsheet to write to (ID is the long string in the URL) |
| `GOOGLE_CREDENTIALS_FILE` / `_JSON` / `_B64` | yes | Service-account key as a file (default `secrets/credentials.json`), inline JSON, or base64 |
| `ALLOWED_GUILD_ID` | recommended | Only members of this Discord server can use the bot |
| `DEFAULT_TIMEZONE` | no | Timezone until a user sets theirs (default `America/Los_Angeles`) |
| `GEMINI_MODEL` | no | Default `gemini-3.6-flash` |
| `GEMINI_FALLBACK_MODELS` | no | Comma-separated models to try when the main one is overloaded (default `gemini-3.5-flash,gemini-3.5-flash-lite`) |
| `RATE_LIMIT_COUNT` / `RATE_LIMIT_SECONDS` | no | Per-user limit (default 10 messages / 60s) |
| `DB_PATH` | no | SQLite file (default `data/user_data.db`; `/data/user_data.db` in Docker) |

One-time Google setup: share the spreadsheet with the `client_email` from
`secrets/credentials.json` and give it **Editor** access.

One-time Discord setup: in the Developer Portal → your app → **Bot**, enable
**Message Content Intent**. Invite the bot to the server whose ID you put in
`ALLOWED_GUILD_ID` (OAuth2 → URL Generator → scope `bot`).

## Run locally (for testing changes)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m bot.bot
```

Only run **one** copy of the bot per token. Pause the Pi first
(`ssh macrotracker 'cd ~/MacroTracker/deploy && docker compose stop'`), or
every message is processed twice. `./deploy/deploy.sh` starts it again.

## Deploying changes

Commit and push, then run `./deploy/deploy.sh`. Details, rollback, and
updating secrets are in [deploy/README.md](deploy/README.md).

## Tests

```bash
python -m unittest discover -s tests -t .
```

## Command-line tracker

```bash
python -m cli.main
```

The original interactive tracker. It uses the profiles and goals in
`cli/config.json` and the same spreadsheet. Bot users who haven't set goals
yet inherit goals from a `cli/config.json` profile with a matching display
name.

## Milestone 1 foundation

The data layer supports:

- Per-user goals, timezone, worksheet ID, reminder preferences, and pending
  confirmations in SQLite, with automatic migrations
- Reading recent meals and meals within a date range
- Daily totals and seven-day summaries
- Updating (timestamp preserved) or deleting a meal by worksheet row

These helpers are in `core/user_store.py` and `sheets/sheet_manager.py`. The
next milestone will expose them through Discord commands and
natural-language requests.

The Google OAuth modules (`oauth/oauth_manager.py`,
`sheets/spreadsheet_manager.py`) are kept for a future version where each
user owns a spreadsheet. They use a localhost redirect, so they will need a
hosted web callback before they can work on a server.
