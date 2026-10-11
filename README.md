# MacroTracker

A Discord bot that logs meals to Google Sheets. DM it `2 eggs and toast` or
`450 cals, 35p, 40c, 12f` and Gemini turns it into a row in your own tab of a
shared spreadsheet. Users don't need Google accounts; the bot writes with a
service account.

Because users talk to it through Discord, it already works on every device.
The bot process just has to run somewhere that is always on. See
[Deploy to a Raspberry Pi](#deploy-to-a-raspberry-pi).

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

Copy `.env.example` to `.env` and fill it in.

| Variable | Required | Purpose |
| --- | --- | --- |
| `DISCORD_TOKEN` | yes | Bot token from the Discord Developer Portal |
| `GEMINI_API_KEY` | yes | Google AI Studio key |
| `GOOGLE_SHEET_ID` or `GOOGLE_SHEET_NAME` | yes | Spreadsheet to write to (ID is the long string in the URL) |
| `GOOGLE_CREDENTIALS_FILE` / `_JSON` / `_B64` | yes | Service-account key as a file (default `credentials.json`), inline JSON, or base64 |
| `ALLOWED_GUILD_ID` | recommended | Only members of this Discord server can use the bot |
| `DEFAULT_TIMEZONE` | no | Timezone until a user sets theirs (default `America/Los_Angeles`) |
| `GEMINI_MODEL` | no | Default `gemini-3.6-flash` |
| `GEMINI_FALLBACK_MODELS` | no | Comma-separated models to try when the main one is overloaded (default `gemini-3.5-flash,gemini-3.5-flash-lite`) |
| `RATE_LIMIT_COUNT` / `RATE_LIMIT_SECONDS` | no | Per-user limit (default 10 messages / 60s) |
| `DB_PATH` | no | SQLite file (default `storage/user_data.db`; `/data/user_data.db` in Docker) |

One-time Google setup: share the spreadsheet with the `client_email` from
`credentials.json` and give it **Editor** access.

One-time Discord setup: in the Developer Portal → your app → **Bot**, enable
**Message Content Intent**. Invite the bot to the server whose ID you put in
`ALLOWED_GUILD_ID` (OAuth2 → URL Generator → scope `bot`).

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

Only run **one** copy of the bot per token. If your laptop and the server both
run it, every message is processed twice.

## Run with Docker

```bash
mkdir -p data                       # SQLite lives here, outside the container
docker compose up -d --build
docker compose logs -f              # watch it start
```

`docker-compose.yml` mounts `./credentials.json` read-only and `./data` for
the database, and restarts the bot automatically after crashes or reboots.

## Deploy to a Raspberry Pi

A Raspberry Pi 4 (any RAM size) runs the bot 24/7 on about 3–5 W. The bot
only makes outbound connections, so there's no port forwarding, router
setup, static IP, or domain to configure.

**You need:** a microSD card (32 GB, A1/A2 rated), the official 5V/3A USB-C
power supply (weak chargers cause random crashes), and ideally an ethernet
cable and a case with a heatsink or fan.

1. **Flash the card from your Mac** with
   [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   - Device: **Raspberry Pi 4**. OS: **Raspberry Pi OS Lite (64-bit)** (under
     "Raspberry Pi OS (other)"). Storage: your microSD card.
   - When asked to customize settings, choose **Edit settings**:
     - Hostname: `macrotracker`
     - Username and password: pick your own (e.g. `pi`)
     - Wi-Fi: your network name, password, and country (skip if using ethernet)
     - Locale: your timezone
     - Services: **Enable SSH → Allow public-key authentication only**, and
       paste your Mac's public key (`cat ~/.ssh/id_ed25519.pub`; create one
       with `ssh-keygen -t ed25519` if it doesn't exist)
2. **Boot the Pi:** insert the card, plug in ethernet (if used) and power,
   wait about 2 minutes, then from your Mac:
   ```bash
   ssh pi@macrotracker.local
   ```
   If `.local` doesn't resolve, find the Pi's IP in your router's device list.
3. **Update it and enable automatic security updates:**
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades   # choose Yes
   sudo reboot
   ```
4. **Install Docker** (after reconnecting):
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER && exit   # log back in afterwards
   ```
5. **Get the code** on the Pi:
   ```bash
   git clone https://github.com/justinencarnacion/MacroTracker.git
   cd MacroTracker && mkdir -p data
   ```
   If the repo is private, use a GitHub fine-grained token with read access
   as the password.
6. **Copy secrets and existing data from your Mac** (run in the project
   folder on the Mac):
   ```bash
   scp .env credentials.json pi@macrotracker.local:~/MacroTracker/
   scp storage/user_data.db pi@macrotracker.local:~/MacroTracker/data/
   ```
   Then on the Pi: `chmod 600 .env credentials.json`, and set
   `ALLOWED_GUILD_ID` and `DEFAULT_TIMEZONE` in `.env` (`nano .env`).
7. **Stop the bot on your Mac**, then start it on the Pi:
   ```bash
   docker compose up -d --build     # first build takes a few minutes
   docker compose logs -f
   ```
   Look for `Connected to spreadsheet` and `Logged in as ...`, then DM the
   bot from your phone.

Docker starts at boot and `restart: unless-stopped` brings the bot back after
power cuts, reboots, and crashes, with no action needed from you.

**Health checks:** `vcgencmd measure_temp` should stay under ~70°C, and
`vcgencmd get_throttled` should print `throttled=0x0`. Anything else usually
means a weak power supply or poor cooling.

**On Wi-Fi?** Disable power saving so the connection doesn't drop:
`sudo nmcli connection modify "$(nmcli -t -f NAME connection show --active | head -1)" 802-11-wireless.powersave 2`
then reboot.

**Updating:** commit and push from your Mac, then run `./deploy.sh` from the
project folder. It:

1. stops if you're not on `main` or have uncommitted or unpushed changes,
2. runs the unit tests and stops if any fail,
3. pulls the new code on the Pi, rebuilds, and restarts the bot,
4. waits for `Logged in as ...` and reports success, or prints the last log
   lines if the bot didn't come up.

If a deploy breaks the bot, `./deploy.sh --rollback` puts the Pi back on the
version it ran before the last deploy. Your Mac and GitHub aren't changed;
fix the problem, push, and run `./deploy.sh` again to move forward.

`deploy.sh` never copies secrets. When `.env` or `credentials.json` change:

```bash
scp .env credentials.json macrotracker:~/MacroTracker/
ssh macrotracker 'cd ~/MacroTracker && docker compose up -d --force-recreate'
```

**Backups:** meals live in Google Sheets; occasionally copy
`data/user_data.db` to your Mac with `scp`. SD cards eventually wear out, so
keep a copy of `.env` and `credentials.json` somewhere safe off the Pi.

## Tests

```bash
python -m unittest discover -s tests -t .
```

## Command-line tracker

`main.py` is the original interactive CLI. It uses the profiles and goals in
`config.json` and the same spreadsheet. Bot users who haven't set goals yet
inherit goals from a `config.json` profile with a matching display name.

## Milestone 1 foundation

The data layer supports:

- Per-user goals, timezone, worksheet ID, reminder preferences, and pending
  confirmations in SQLite, with automatic migrations
- Reading recent meals and meals within a date range
- Daily totals and seven-day summaries
- Updating (timestamp preserved) or deleting a meal by worksheet row

These helpers are in `user_store.py` and `sheet_manager.py`. The next
milestone will expose them through Discord commands and natural-language
requests.

The Google OAuth modules (`oauth_manager.py`, `spreadsheet_manager.py`) are
kept for a future version where each user owns a spreadsheet. They use a
localhost redirect, so they will need a hosted web callback before they can
work on a server.
