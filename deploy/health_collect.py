"""Collects MacroTracker health data on the Pi and prints it as JSON.

Run by deploy/health.sh over SSH (`ssh macrotracker python3 - < health_collect.py`),
so nothing needs installing on the Pi. Uses only the Python standard library.
"""

import json
import os
import re
import shutil
import subprocess

CONTAINER = "macrotracker"
REPO = os.path.expanduser("~/MacroTracker")

USAGE_SNIPPET = """
import json, os
from core.metrics import summarize
print(json.dumps(summarize("/data/user_data.db",
                           tz_name=os.getenv("DEFAULT_TIMEZONE", "America/Los_Angeles"))))
"""

USERS_ONLY_SNIPPET = """
import json, sqlite3
row = sqlite3.connect("/data/user_data.db").execute(
    "SELECT COUNT(*), SUM(goals_json IS NOT NULL AND goals_json != ''), "
    "SUM(timezone IS NOT NULL AND timezone != '') FROM users").fetchone()
print(json.dumps({"total": row[0] or 0, "with_goals": row[1] or 0, "with_timezone": row[2] or 0}))
"""


def run(*command, stdin=None):
    try:
        result = subprocess.run(command, input=stdin, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def meminfo():
    values = {}
    for line in read("/proc/meminfo").splitlines():
        key, _, rest = line.partition(":")
        values[key] = int(rest.split()[0]) // 1024  # MB
    return values


def temperature():
    output = run("vcgencmd", "measure_temp") or ""
    match = re.search(r"([\d.]+)", output)
    if match:
        return float(match.group(1))
    raw = read("/sys/class/thermal/thermal_zone0/temp").strip()
    return int(raw) / 1000 if raw.isdigit() else None


def throttled():
    output = run("vcgencmd", "get_throttled") or ""
    match = re.search(r"0x[0-9a-fA-F]+", output)
    return int(match.group(0), 16) if match else None


def system():
    memory = meminfo()
    disk = shutil.disk_usage("/")
    load = read("/proc/loadavg").split()
    return {
        "model": read("/proc/device-tree/model").strip("\x00\n "),
        "uptime_hours": round(float(read("/proc/uptime").split()[0]) / 3600, 1),
        "temperature_c": temperature(),
        "throttled": throttled(),
        "cpu_count": os.cpu_count(),
        "load": [float(value) for value in load[:3]] if load else None,
        "mem_total_mb": memory.get("MemTotal"),
        "mem_available_mb": memory.get("MemAvailable"),
        "swap_total_mb": memory.get("SwapTotal"),
        "swap_free_mb": memory.get("SwapFree"),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "disk_free_gb": round(disk.free / 1e9, 1),
    }


def bot():
    inspect = run("docker", "inspect", CONTAINER, "--format",
                  "{{json .State}}|{{.RestartCount}}|{{.Image}}")
    if not inspect:
        return {"found": False}
    state_json, restarts, image_id = inspect.split("|")
    state = json.loads(state_json)
    status = read_container_file("/proc/1/status")
    rss = re.search(r"VmRSS:\s+(\d+)", status or "")
    image_size = run("docker", "image", "inspect", image_id, "--format", "{{.Size}}")
    logs = run_logs()
    return {
        "found": True,
        "status": state.get("Status"),
        "started_at": state.get("StartedAt"),
        "restarts": int(restarts),
        "cpu_percent": (run("docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}", CONTAINER) or "").rstrip("%") or None,
        "memory_mb": int(rss.group(1)) // 1024 if rss else None,
        "image_mb": int(image_size) // 1_000_000 if image_size else None,
        "log_errors_24h": logs.count("ERROR") + logs.count("Traceback"),
        "commit": run("git", "-C", REPO, "rev-parse", "HEAD"),
        "commit_subject": run("git", "-C", REPO, "log", "-1", "--format=%s"),
    }


def read_container_file(path):
    return run("docker", "exec", CONTAINER, "cat", path)


def run_logs():
    try:
        result = subprocess.run(["docker", "logs", "--since", "24h", CONTAINER],
                                capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout + result.stderr  # the bot logs to stderr


def usage():
    output = run("docker", "exec", "-i", CONTAINER, "python", "-", stdin=USAGE_SNIPPET)
    if output:
        return json.loads(output)
    # The running bot predates usage tracking; user counts are still available.
    users = run("docker", "exec", "-i", CONTAINER, "python", "-", stdin=USERS_ONLY_SNIPPET)
    return {"users": json.loads(users) if users else None, "tracking": False}


print(json.dumps({"system": system(), "bot": bot(), "usage": usage()}))
