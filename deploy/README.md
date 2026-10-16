# Deploy

Everything needed to run the bot in Docker and ship changes to the server.
These files work on any Linux machine with Docker; the Raspberry Pi specifics
are in [../pi/README.md](../pi/README.md).

| File | Purpose |
| --- | --- |
| `Dockerfile` | Builds the bot image (Python 3.13, runs `python -m bot.bot` as a non-root user) |
| `Dockerfile.dockerignore` | Keeps `secrets/`, `data/`, `.git`, and caches out of the image |
| `docker-compose.yml` | Runs the container: auto-restart, log rotation, mounts `secrets/` and `data/` |
| `deploy.sh` | One-command deploy from your Mac to the Pi, with tests and rollback |

## Deploying a change

From the project root on your Mac:

```bash
git add -A
git commit -m "Describe your change"
git push origin main
./deploy/deploy.sh
```

`deploy.sh`:

1. stops if you're not on `main` or have uncommitted or unpushed changes,
2. runs the unit tests and stops if any fail,
3. pulls the new code on the Pi, rebuilds, and restarts the bot,
4. waits for `Logged in as ...` and reports success, or prints the last log
   lines if the bot didn't come up.

## Rolling back

```bash
./deploy/deploy.sh --rollback
```

Puts the Pi back on the version it ran before the last deploy. Your Mac and
GitHub aren't changed; fix the problem, push, and deploy again to move
forward.

## Updating secrets

`deploy.sh` never copies secrets. The Pi's settings come from the Mac's
`secrets/.env.prod` (production key), **not** `secrets/.env` (test key); see
[../secrets/README.md](../secrets/README.md#test-and-production-keys).

After editing `secrets/.env.prod`:

```bash
scp secrets/.env.prod macrotracker:~/MacroTracker/secrets/.env
ssh macrotracker 'cd ~/MacroTracker/deploy && docker compose up -d --force-recreate'
```

After replacing `secrets/credentials.json`:

```bash
scp secrets/credentials.json macrotracker:~/MacroTracker/secrets/
ssh macrotracker 'cd ~/MacroTracker/deploy && docker compose up -d --force-recreate'
```

The `--force-recreate` restart (about 5-10 seconds of downtime) is needed
because the bot reads its settings only when the container starts.

## Running Docker commands

`docker-compose.yml` lives in `deploy/`, so either run commands from inside
that folder or point at the file:

```bash
cd ~/MacroTracker/deploy && docker compose logs -f
# or, from the project root:
docker compose -f deploy/docker-compose.yml logs -f
```

| Command (inside `deploy/`) | Does |
| --- | --- |
| `docker compose ps` | Is the bot running? |
| `docker compose logs -f` | Live logs (Ctrl+C to exit; the bot keeps running) |
| `docker compose logs --since 1h` | Logs from the last hour |
| `docker compose restart` | Restart the bot |
| `docker compose stop` / `start` | Pause or resume, e.g. while testing on your Mac |
| `docker compose up -d --build` | Rebuild and start (what `deploy.sh` runs) |
