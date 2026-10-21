# MacroTracker

A Discord bot that logs meals to Google Sheets and tracks progress against
daily goals. DM it `2 eggs and toast` or `450 cals, 35p, 40c, 12f` and Gemini
turns it into a row in your own tab of a shared spreadsheet; ask
`what did I eat today?` or use `/today` and `/week` to see totals, progress
bars, and what's left. Users don't need Google accounts; the bot writes with a
service account.

Because users talk to it through Discord, it works on every device. The bot
itself runs 24/7 on a Raspberry Pi (see [pi/](pi/README.md)).

## Project layout

```
MacroTracker/
├── bot/        Discord bot: message handling, AI parsing, access control
│   ├── commands/   Slash commands (/today, /week, /goals, /edit, /delete)
│   └── views/      Buttons, meal picker, edit form, confirmations
├── charts/     Chart images for /today and /week (logic only, no Discord)
├── tracking/   Goals, daily and weekly summaries (logic only, no Discord)
├── sheets/     Google Sheets reading and writing
├── core/       Shared settings (.env loading), macro definitions, SQLite user store
├── cli/        Original terminal tracker and its config.json profiles
├── oauth/      Per-user Google OAuth (not used yet; future feature)
├── deploy/     Dockerfile, docker-compose.yml, deploy.sh  → deploy/README.md
├── pi/         Raspberry Pi setup, maintenance, remote SSH → pi/README.md, pi/remote-access.md
├── secrets/    .env, credentials.json (never committed)    → secrets/README.md
├── data/       user_data.db (never committed)
├── web/        Website: React + TypeScript (Vite), on GitHub Pages → web/README.md
├── tests/      Unit tests
└── requirements.txt
```

| Folder | Files | Purpose |
| --- | --- | --- |
| `bot/` | `bot.py`, `ai_parser.py`, `access.py` | Entry point and DM routing, Gemini prompt and validation, server-membership check and rate limit |
| `bot/` | `replies.py`, `embeds.py`, `formatting.py` | Builds replies (shared by DMs, slash commands, and buttons); embed cards; text formatting and the text-only fallback |
| `bot/commands/` | `summaries.py`, `meals.py`, `common.py` | `/today`, `/week`, `/goals show`, `/goals set`, `/edit`, `/delete`; shared access checks |
| `bot/views/` | `summary.py`, `meals.py` | Persistent `[Today]` `[Week]` buttons; meal picker, edit form, and Yes/No confirmation |
| `charts/` | `theme.py`, `today.py`, `week.py` | Draws PNG charts with matplotlib in Discord's dark-theme colors |
| `tracking/` | `goals.py`, `summaries.py`, `service.py`, `meal_service.py` | Goal rules, Monday–Sunday and daily calculations, reading a user's meals in their timezone, safely editing and deleting meals |
| `sheets/` | `sheet_manager.py`, `spreadsheet_manager.py` | Connecting to the sheet, per-user tabs, reading and editing meals |
| `core/` | `settings.py`, `macros.py`, `user_store.py` | Loads `secrets/.env`; macro names and limits; stores goals, timezones and tab IDs in `data/user_data.db` |
| `cli/` | `main.py`, `display.py`, `config_manager.py`, `config.json` | Interactive terminal tracker |
| `oauth/` | `oauth_manager.py` | Kept for a future version where each user owns a spreadsheet |
| `web/` | `src/` (React components), `scripts/generate_demo.py` | The project website; its Discord demo is generated from the bot's own chart and embed code |

Run everything from the project root.

## What the bot understands

| DM message | Slash command | Action |
| --- | --- | --- |
| `chicken burrito bowl` / `450 cals, 35p` | — | Logs a meal (AI-estimated or manual), then shows what's left today |
| `what did I eat today?` / `how many macros do I have left?` | `/today` | A card with today's numbered meals, totals vs goals, and a macro progress-bar chart |
| `how's my week going?` | `/week` | A card with a Monday–Sunday calorie chart against your goal, a per-day table, and the week so far vs goals × days elapsed |
| `what are my goals?` | `/goals show` | Current daily goals |
| `set my goals to 2200 cals, 180p, 220c, 70f` | `/goals set` | Sets goals; the first time needs all four, later any subset |
| — | `/edit` | Pick a meal from the last 7 days, change it in a form, confirm |
| — | `/delete` | Pick a meal from the last 7 days and confirm before it's removed |
| `set my timezone to America/New_York` | — | Meals and "today" use your local time |
| anything else | — | Replies with help |

Summary cards have `[Today]` and `[Week]` buttons that redraw the card in
place; they keep working after the bot restarts. Users never need to open the
Google Sheet, which remains the bot's storage behind the scenes.

Progress features require personally set goals; until then the bot asks the
user to set them. Slash commands work in the bot's DMs and in server channels;
in channels, replies are visible only to the person who ran the command.

Each user gets a worksheet named `Display Name (last 6 digits of Discord ID)`.
The bot remembers the worksheet's ID, so changing your Discord nickname keeps
the same tab. Summaries are read live from the sheet, so manual edits there are
always reflected.

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
`ALLOWED_GUILD_ID` (OAuth2 → URL Generator → scopes `bot` and
`applications.commands`; the second is needed for slash commands). Slash
commands are registered automatically each time the bot starts.

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
`cli/config.json` and the same spreadsheet. Since Milestone 6, the Discord bot
no longer reads goals from `cli/config.json`; bot users set their own.

## Milestones

A running history of the project. New milestones are added at the bottom;
earlier ones are kept as written.

**Before Milestone 1**

- **2026-09-07: Command-line tracker.** `cli/main.py` logs meals per profile
  to their own tab in a Google Sheet, with daily totals vs goals.
- **2026-09-08: Per-user Google OAuth spreadsheets.** Each Discord user would
  own a spreadsheet; only workable on the local machine (localhost redirect).
- **2026-10-01: Shared-sheet Discord bot.** OAuth set aside; the bot writes to
  one shared spreadsheet with a service account and creates a tab per user
  when they first DM it.

### Milestone 1: Data-layer foundation

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

### Milestone 2: Always-on deployment (2026-10-09)

- Configuration from environment variables; Docker image and Compose setup
  with auto-restart and a persistent data volume
- Gemini output validated before anything is written; new intents for goals,
  timezone, and help; automatic fallback to backup models when overloaded
- Non-blocking Sheets/SQLite/Gemini calls; meals dated in each user's timezone
- Access limited to one Discord server, plus per-user rate limiting
- Unit test suite; the bot moved from a laptop to a Raspberry Pi running 24/7

### Milestone 3: One-command deploys (2026-10-11)

- `deploy/deploy.sh`: refuses uncommitted or unpushed work, runs the tests,
  updates and rebuilds the bot on the Pi, waits for it to log in, and supports
  `--rollback`

### Milestone 4: Project reorganization (2026-10-11)

- Code split into `bot/`, `sheets/`, `core/`, `cli/`, `oauth/`, `deploy/`,
  `pi/`, and `secrets/`; secrets and data kept out of git and the image
- Documentation split into per-folder READMEs

### Milestone 5: Remote SSH access (2026-10-11)

- SSH to the Pi from any network without a third-party VPN: DHCP reservation,
  SSH hardening, fail2ban, Dynamic DNS, and router port forwarding
- Written up as a computer networks case study in
  [pi/remote-access.md](pi/remote-access.md)

### Milestone 6: Summaries and goal progress (2026-10-12)

- `/today`: today's numbered meals, totals, progress bars, and what's left
- `/week`: Monday–Sunday table plus the week so far vs daily goals × days
  elapsed, and the daily average
- `/goals show` and `/goals set`; the first goal-setting requires all four
  macros, later updates can change any subset
- The same features in plain English (`what did I eat today?`,
  `how's my week going?`, `what are my goals?`)
- Every logged meal now replies with a one-line "Left today"
- New `tracking/` package for the calculations and `bot/commands/` for slash
  commands; summaries are read live from the sheet
- The bot no longer falls back to `cli/config.json` or built-in default goals

### Milestone 7: Separate test and production API keys (2026-10-16)

- No code changes
- Created separate **test** and **production** Gemini API keys in separate
  Google Cloud projects, so new versions of MacroTracker can be tested without
  using the limited daily requests real users depend on (the bot runs on
  Gemini's free tier, which caps requests per model per day)
- The Mac's `secrets/.env` uses the test key; the Pi uses the production key,
  mirrored on the Mac as `secrets/.env.prod`
- Updated `secrets/README.md` and `deploy/README.md` with the split and the
  command for updating the Pi's settings

### Milestone 8: Charts inside Discord (2026-10-16)

- `/today` and `/week` (and their plain-English versions) now reply with
  embed cards containing chart images, so users never need the Google Sheet
- Today: a progress bar per macro toward the goal (blurple in progress, green
  on target, red when over; protein counts as a minimum)
- Week: Monday–Sunday calorie bars against a dashed goal line; today
  highlighted, unlogged days shown as faint placeholders, future days blank
- `[Today]` `[Week]` buttons redraw the card in place and survive restarts
- Charts are drawn with code (matplotlib) on the Pi, not AI, so they cost no
  AI requests; if a chart fails, the text summary is sent instead
- Meal-log replies now say "✅ Logged!" instead of mentioning the Google Sheet
- New `charts/` package, `bot/embeds.py`, and `bot/views/`; Docker image grows
  to about 512 MB (matplotlib)

### Milestone 9: Edit and delete meals (2026-10-17)

- `/edit` and `/delete` show a dropdown of the user's meals from the last
  7 days, newest first
- Edit opens a form pre-filled with the meal's name, calories, protein,
  carbs, and fat; the meal keeps its original time. No AI requests are used
- Nothing changes until the user presses the confirm button; afterwards the
  bot shows what changed and the refreshed `/today` card
- Before writing, the bot re-reads the sheet: if rows shifted it finds the
  meal at its new position; if the meal was changed or is ambiguous, it
  refuses instead of touching the wrong row
- Only the person who ran the command can use its menu and buttons
- Fixed `update_meal` to pass values to gspread 6 by name
- Plain-English edit/delete ("delete my last meal") is deferred until the
  project has a larger AI request budget

### Milestone 10: Project website (2026-10-20)

- New `web/` folder: a React + TypeScript site built with Vite, explaining
  what MacroTracker is and how it works
- Pages and home-page sections are typed registries, so adding a section or a
  page is one component plus one entry
- An interactive mock Discord conversation shows the bot's real output: the
  demo's charts and card text are generated from the bot's own code by
  `web/scripts/generate_demo.py`, and its `[Today]` `[Week]` buttons work
- Responsive down to phone widths, light and dark themes, keyboard focus
  styles, and reduced-motion support
- Published to GitHub Pages by a GitHub Actions workflow whenever `web/`
  changes on `main`; the bot's Docker image excludes `web/`

### Milestone 11: Website picture banner (2026-10-21)

- A picture banner at the top of the website, set in one place
  (`banner` in `web/src/content/site.ts`): image, description, optional
  caption, and which part to keep if cropped; set it to `null` to hide it
- Keeps the picture's shape so nothing is cut off on phones; the caption moves
  below the picture on small screens; a missing image hides the banner
  instead of showing a broken one
- Ships with a placeholder banner until a real picture is added

**Next:** zero-AI logging to stretch the free AI quota (number-only meals,
a `/log` command, saved meals).
