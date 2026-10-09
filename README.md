# MacroTracker

## Run the Discord bot locally

The Phase 1 bot uses the service account in `credentials.json` to write to
the shared spreadsheet configured in `config.json`. Discord users do not need
Google access or an OAuth authorization step. Each user gets a separate
worksheet named after their Discord display name with a short Discord ID
suffix.

1. Share the Google Sheet named `Macro Tracker` with the service-account email
   from `credentials.json` and give it Editor access.
2. Copy the required values into `.env`:

   ```text
   DISCORD_TOKEN=your-bot-token
   GEMINI_API_KEY=your-gemini-key
   GOOGLE_SHEET_NAME=Macro Tracker
   ```

3. Install dependencies and start the bot:

   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   python bot.py
   ```

Keep the terminal and computer running while testing from Discord mobile.

The Google OAuth modules remain in the project for a future version where
each user owns a separate spreadsheet. They are not used by the Phase 1 bot.

## Run the tests

```bash
python -m unittest discover -s tests
```
