# Secrets

This folder holds the bot's private keys and tokens. Everything here is
ignored by git except this README and `.env.example`, and none of it is
copied into the Docker image. Keep the folder readable only by you:

```bash
chmod 700 secrets && chmod 600 secrets/.env secrets/credentials.json
```

| File | What it is | Where it comes from |
| --- | --- | --- |
| `.env` | Discord token, Gemini key, sheet ID, settings | `cp secrets/.env.example secrets/.env`, then fill it in |
| `credentials.json` | Google service-account key the bot writes to Sheets with | Google Cloud Console → IAM → Service Accounts → Keys |
| `oauth_client.json` | OAuth client for the future per-user Google login (unused today) | Google Cloud Console → APIs & Services → Credentials |
| `.env.example` | Template listing every setting (committed, no real values) | — |

Rules:

- Never commit, paste, or screenshot `.env` or `credentials.json`.
- The Pi has its own copy in `~/MacroTracker/secrets/`. `deploy.sh` never
  copies secrets; update them by hand (see
  [../deploy/README.md](../deploy/README.md#updating-secrets)).
- If a secret leaks, rotate it: reset the token in the Discord Developer
  Portal, create a new Gemini key in Google AI Studio, or add a new key to the
  service account and delete the old one. Then update both copies.
