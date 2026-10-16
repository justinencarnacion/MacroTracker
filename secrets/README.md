# Secrets

This folder holds the bot's private keys and tokens. Everything here is
ignored by git except this README and `.env.example`, and none of it is
copied into the Docker image. Keep the folder readable only by you:

```bash
chmod 700 secrets && chmod 600 secrets/.env secrets/.env.prod secrets/credentials.json
```

| File | What it is | Where it comes from |
| --- | --- | --- |
| `.env` | Settings for **local development and testing** on your Mac, with the **test** Gemini key | `cp secrets/.env.example secrets/.env`, then fill it in |
| `.env.prod` | Your Mac's copy of the **Pi's production settings**, with the **prod** Gemini key. Used only to update the Pi | Kept identical to the Pi's `secrets/.env` |
| `credentials.json` | Google service-account key the bot writes to Sheets with | Google Cloud Console → IAM → Service Accounts → Keys |
| `oauth_client.json` | OAuth client for the future per-user Google login (unused today) | Google Cloud Console → APIs & Services → Credentials |
| `.env.example` | Template listing every setting (committed, no real values) | — |

## Test and production keys

The bot uses Gemini's free tier, which allows a limited number of requests
per model per day. Quotas belong to the **Google Cloud project**, not the key,
so the two keys live in **separate projects**:

| Key | Google Cloud project | Used by | File |
| --- | --- | --- | --- |
| Production | Prod project | The bot on the Pi (real users) | Pi `secrets/.env`, Mac `secrets/.env.prod` |
| Test | Test project | Local runs, unit tests, and model experiments on the Mac | Mac `secrets/.env` |

Testing, experiments, and local runs therefore never use up the requests real
users depend on. Two keys in the *same* project would share one quota.

To confirm the Pi and `.env.prod` still match without revealing values:

```bash
shasum -a 256 secrets/.env.prod | cut -c1-12
ssh macrotracker 'sha256sum ~/MacroTracker/secrets/.env' | cut -c1-12
```

Rules:

- Never commit, paste, or screenshot `.env` or `credentials.json`.
- The Pi has its own copy in `~/MacroTracker/secrets/`. `deploy.sh` never
  copies secrets; update them by hand from `.env.prod` (see
  [../deploy/README.md](../deploy/README.md#updating-secrets)). Never copy the
  Mac's `.env` to the Pi: it holds the test key.
- If a secret leaks, rotate it: reset the token in the Discord Developer
  Portal, create a new Gemini key in Google AI Studio, or add a new key to the
  service account and delete the old one. Then update both copies.
