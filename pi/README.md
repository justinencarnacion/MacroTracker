# Raspberry Pi

The bot runs 24/7 on a Raspberry Pi 4 using about 3–5 W. It only makes
outbound connections, so there's no port forwarding, router setup, static IP,
or domain to configure.

## Connecting

Your Mac's `~/.ssh/config` has a `macrotracker` shortcut (host
`macrotracker.local`, your Pi username, key `~/.ssh/macrotracker-pi`):

```bash
ssh macrotracker          # log in (exit or Ctrl+D to leave)
```

If `.local` doesn't resolve, find the Pi's IP in your router's device list.
If a session freezes, press Enter, then type `~.` to force-close it.

**Away from home:** `ssh macrotracker-remote` reaches the Pi from any network
through Dynamic DNS and a router port-forward. How it was built, and the
networking concepts behind it, are in [remote-access.md](remote-access.md).
To deploy while away: `DEPLOY_HOST=macrotracker-remote ./deploy/deploy.sh`.

## Health checks

From your Mac:

```bash
ssh macrotracker 'vcgencmd measure_temp; vcgencmd get_throttled; uptime; free -h | head -2; df -h / | tail -1'
```

| Line | Healthy |
| --- | --- |
| `temp=` | Under ~70°C (the Pi slows itself down at 80°C) |
| `throttled=` | `0x0`; anything else usually means a weak power supply or overheating |
| `load average:` | Under 4.0; an idle bot sits near 0.0–0.2 |
| `Mem:` available | More than 300 MB |
| Disk `Avail` | More than 1–2 GB |

Bot status and resource use:

```bash
ssh macrotracker 'cd ~/MacroTracker/deploy && docker compose ps && docker compose logs --tail 10'
ssh macrotracker 'docker stats --no-stream macrotracker'
```

`docker stats` shows memory as `0B` unless memory accounting is enabled (run
once, then the bot restarts by itself after the reboot):

```bash
ssh macrotracker "sudo sed -i '\$ s/\$/ cgroup_enable=memory cgroup_memory=1/' /boot/firmware/cmdline.txt && sudo reboot"
```

Live dashboard (install once with `sudo apt install -y htop`):

```bash
ssh -t macrotracker htop      # q to quit
```

## Maintenance

- **Security updates** install automatically (`unattended-upgrades`).
- **Reboots and power cuts:** Docker starts at boot and the bot restarts on
  its own.
- **Backups:** meals live in Google Sheets. Occasionally copy the settings
  database to your Mac:
  `scp macrotracker:~/MacroTracker/data/user_data.db data/user_data.db.pi-backup`.
  SD cards eventually wear out, so keep your `secrets/` folder somewhere safe
  off the Pi.
- **On Wi-Fi?** Disable power saving so the connection doesn't drop:
  `sudo nmcli connection modify "$(nmcli -t -f NAME connection show --active | head -1)" 802-11-wireless.powersave 2`,
  then reboot.

## Setting up a new Pi from scratch

**You need:** a microSD card (32 GB, A1/A2 rated), the official 5V/3A USB-C
power supply (weak chargers cause random crashes), and ideally a case with a
heatsink or fan.

1. **Create an SSH key on your Mac** (skip if `~/.ssh/macrotracker-pi`
   exists):
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/macrotracker-pi -C "macrotracker-pi"
   pbcopy < ~/.ssh/macrotracker-pi.pub
   ```
2. **Flash the card** with [Raspberry Pi Imager](https://www.raspberrypi.com/software/):
   - Device **Raspberry Pi 4**; OS **Raspberry Pi OS Lite (64-bit)** (under
     "Raspberry Pi OS (other)"); Storage: your card.
   - **Edit settings:** hostname `macrotracker`; a username and password;
     your home Wi-Fi name, password, and country (or skip for ethernet);
     your timezone; **Enable SSH → public-key authentication only**, clear
     the key box, and paste with ⌘V. Leave Raspberry Pi Connect off.
3. **Point the SSH shortcut at the Pi** (use the username you chose):
   ```bash
   cat >> ~/.ssh/config <<'EOF'

   Host macrotracker
       HostName macrotracker.local
       User YOUR_PI_USERNAME
       IdentityFile ~/.ssh/macrotracker-pi
   EOF
   ```
4. **Boot the Pi**, wait 2–3 minutes, then `ssh macrotracker`.
5. **Install updates, git, and Docker** (on the Pi):
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   sudo apt install -y git unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER
   sudo reboot
   ```
   Choose **Yes** for automatic updates. After reconnecting,
   `docker run --rm hello-world` should print "Hello from Docker!".
6. **Clone the bot** (on the Pi):
   ```bash
   git clone https://github.com/justinencarnacion/MacroTracker.git
   mkdir -p ~/MacroTracker/data ~/MacroTracker/secrets && chmod 700 ~/MacroTracker/secrets
   ```
7. **Copy secrets and the database** (on your Mac, from the project root):
   ```bash
   scp secrets/.env secrets/credentials.json macrotracker:~/MacroTracker/secrets/
   scp data/user_data.db macrotracker:~/MacroTracker/data/
   ssh macrotracker 'chmod 600 ~/MacroTracker/secrets/*'
   ```
8. **Stop any other copy of the bot**, then start it (on the Pi):
   ```bash
   cd ~/MacroTracker/deploy
   docker compose up -d --build
   docker compose logs -f
   ```
   The first build takes 3–5 minutes. Look for `Connected to spreadsheet`
   and `Logged in as ...`, then DM the bot.

After that, ship changes with `./deploy/deploy.sh` from your Mac
(see [../deploy/README.md](../deploy/README.md)).
